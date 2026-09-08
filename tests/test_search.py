import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from src.bot import create_bot
from src.config import OFFICIAL_URLS, Backend, Model, load_settings
from src.domain import BotError, Capability
from src.providers import HTTPTransport
from src.search import ImageSearchProvider, ImageSearchService, public_image_url
from src.storage import Scope
from tests.test_config import EXAMPLE, write

URL = "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"
RESULT = {
    "status": "completed",
    "output": [
        {
            "type": "web_search_call",
            "status": "completed",
            "action": {"type": "search", "query": "orange ball"},
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": f"![Orange ball]({URL})"}],
        },
    ],
}


def provider(monkeypatch, handler):
    monkeypatch.setenv("SEARCH_KEY", "private-fixture-key")
    model = Model(
        "search",
        Backend("xai", "xai", OFFICIAL_URLS["xai"], "SEARCH_KEY"),
        "grok-4.6",
        frozenset({Capability.IMAGE_SEARCH}),
    )
    return ImageSearchProvider(
        model,
        HTTPTransport(model, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )


async def test_actual_search_command_request_translation_and_private_embeds(
    settings, service, monkeypatch
):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url == "https://api.x.ai/v1/responses"
        assert request.headers["authorization"] == "Bearer private-fixture-key"
        body = json.loads(request.content)
        assert body["tools"] == [{"type": "web_search", "enable_image_search": True}]
        assert body["input"][-1] == {"role": "user", "content": "orange ball"}
        assert len(body["input"]) == 2 and "private conversation" not in request.content.decode()
        assert body["store"] is False and body["parallel_tool_calls"] is False
        assert body["max_turns"] == 2 and body["max_output_tokens"] == 2048
        return httpx.Response(200, json=RESULT)

    search = provider(monkeypatch, handler)
    settings.models["search"] = search.model
    await service.chat(Scope(1, 2, 3, 4), "private conversation")
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store, client.service = service.store, service
    client.search = ImageSearchService(settings, service, {"search": search})
    target = SimpleNamespace(
        user=SimpleNamespace(id=4),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3, send=AsyncMock()),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    try:
        await client.tree.get_command("image_search").callback(target, "orange ball", "search")
        target.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        sent = target.followup.send.call_args.kwargs
        assert sent["ephemeral"] is True and sent["allowed_mentions"].everyone is False
        assert sent["embeds"][0].image.url == URL and sent["embeds"][0].url == URL
        assert len(calls) == 1  # No host-side request to the untrusted image origin.
        target.channel.send.assert_not_called()
        assert len(service.providers["local"].calls) == 1
    finally:
        await client.search.close()
        await client.close()


@pytest.mark.parametrize(
    "value",
    [
        "http://example.org/a.png",
        "https://127.0.0.1/a",
        "https://169.254.169.254/meta",
        "https://[::1]/a",
        "https://localhost/a",
        "https://x.internal/a",
        "https://user:secret@example.org/a",
        "https://example.org:invalid/a",
        "https://example.org:8000/a",
        "https://example.org\\@127.0.0.1/a",
        "https://example.org/a\n.png",
    ],
)
def test_image_urls_reject_private_or_malformed_sources(value):
    assert not public_image_url(value)


@pytest.mark.parametrize(
    "value",
    [
        {
            "status": "completed",
            "output": [
                {
                    "type": "web_search_call",
                    "status": "failed",
                    "action": {"type": "search", "query": "Taipei 101 in daylight", "sources": []},
                },
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Unable to retrieve a downloadable image."}
                    ],
                },
            ],
        },
        {"status": "incomplete", "output": RESULT["output"]},
        {"status": "completed", "output": RESULT["output"][1:]},
        {"status": "completed", "output": [None]},
        {
            "status": "completed",
            "output": [
                RESULT["output"][0],
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "![secret](https://127.0.0.1/a)"}],
                },
            ],
        },
    ],
)
async def test_search_requires_completed_tool_and_safe_image_results(value, monkeypatch):
    search = provider(monkeypatch, lambda request: httpx.Response(200, json=value))
    with pytest.raises(BotError):
        await search.search("a ball")
    await search.close()


async def test_search_limits_duplicates_and_result_count(monkeypatch):
    result = {
        "status": "completed",
        "output": [
            RESULT["output"][0],
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": f"![first]({URL})\n![duplicate]({URL})\n"
                        + "\n".join(
                            f"![item {n}](https://images.example.org/{n}.jpg)" for n in range(5)
                        ),
                    }
                ],
            },
        ],
    }
    search = provider(monkeypatch, lambda request: httpx.Response(200, json=result))
    images = await search.search("a ball")
    assert len(images) == 3 and len({image.url for image in images}) == 3
    await search.close()


async def test_search_timeout_cancellation_and_capability_check(service, monkeypatch):
    started = asyncio.Event()
    finished = asyncio.Event()
    calls = []

    async def handler(request):
        calls.append(request)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    search = provider(monkeypatch, handler)
    service.settings.models["search"] = search.model
    api = ImageSearchService(
        replace(service.settings, request_timeout=0.03), service, {"search": search}
    )
    scope = Scope(1, 2, 3, 4)
    with pytest.raises(BotError, match="image-search"):
        await api.search(scope, "local", "a ball")
    assert not calls
    with pytest.raises(BotError, match="timed out"):
        await api.search(scope, "search", "a ball")
    assert finished.is_set() and len(calls) == 1
    started.clear()
    task = asyncio.create_task(api.search(scope, "search", "a ball"))
    await started.wait()
    await service.gate.cancel(scope.key)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) == 2
    await api.close()


@pytest.mark.parametrize(
    "before,after",
    [
        ('capabilities = ["image-search"]', 'capabilities = ["image-search", "chat"]'),
        ("max_turns = 2,", "max_turns = true,"),
        ("max_turns = 2,", "max_turns = 4,"),
        ("max_turns = 2,", 'endpoint = "https://untrusted.example",'),
    ],
)
def test_search_config_rejects_unsupported_settings(tmp_path, before, after):
    with pytest.raises(BotError):
        load_settings(write(tmp_path, EXAMPLE.replace(before, after)))


async def test_search_rate_limit_is_not_retried_or_disclosed(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "private-fixture-key"}})

    search = provider(monkeypatch, handler)
    with pytest.raises(BotError, match="quota") as error:
        await search.search("a ball")
    assert "private-fixture-key" not in str(error.value) and len(calls) == 1
    await search.close()
