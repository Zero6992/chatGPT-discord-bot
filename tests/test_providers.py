import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from src.config import OFFICIAL_URLS, Backend
from src.domain import BotError, Capability, Message
from src.providers import APIProvider, HTTPTransport

FIXTURES = json.loads((Path(__file__).parent / "fixtures/http.json").read_text())


@pytest.mark.parametrize("kind", ["openai", "anthropic", "gemini", "xai", "deepseek", "compatible"])
async def test_actual_translation_one_request(kind, model, monkeypatch):
    monkeypatch.setenv("FIXTURE_KEY", "fixture-secret")
    model = replace(
        model,
        backend=Backend(kind, kind, OFFICIAL_URLS.get(kind, model.backend.base_url), "FIXTURE_KEY"),
    )
    history = [
        Message("system", "system one"),
        Message("system", "system two"),
        Message("user", "first"),
        Message("assistant", "prior reply"),
        Message("user", "second"),
    ]
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=FIXTURES[kind])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = APIProvider(model, HTTPTransport(model, client=client))
    try:
        response = await provider.complete(history)
        assert response.text == "Hello from the model."
        assert len(seen) == 1  # Regression: Gemini used to call once per historical user turn.
        body = json.loads(seen[0].content)
        if kind == "gemini":
            assert seen[0].url.path.endswith(":generateContent")
            assert body["systemInstruction"]["parts"][0]["text"] == "system one\n\nsystem two"
            assert body["contents"] == [
                {"role": "user", "parts": [{"text": "first"}]},
                {"role": "model", "parts": [{"text": "prior reply"}]},
                {"role": "user", "parts": [{"text": "second"}]},
            ]
            assert body["generationConfig"] == {"maxOutputTokens": 512}
            assert seen[0].headers["x-goog-api-key"] == "fixture-secret"
        elif kind == "anthropic":
            assert seen[0].url.path == "/v1/messages"
            assert body["system"] == "system one\n\nsystem two"
            assert body["messages"] == [m.__dict__ for m in history[2:]]
            assert body["max_tokens"] == 512
            assert seen[0].headers["anthropic-version"] == "2023-06-01"
        elif kind in {"openai", "xai"}:
            assert seen[0].url.path == "/v1/responses"
            assert body["input"] == [m.__dict__ for m in history]
            assert body["store"] is False
            assert body["max_output_tokens"] == 512
        else:
            assert seen[0].url.path.endswith("/chat/completions")
            assert body["messages"] == [m.__dict__ for m in history]
            assert body["stream"] is False
            assert body["max_tokens"] == 512
    finally:
        await provider.close()
    assert client.is_closed


async def test_local_no_key_does_not_send_fake_auth(model):
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json=FIXTURES["compatible"])

    provider = APIProvider(
        model,
        HTTPTransport(model, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )
    await provider.complete([Message("user", "hi")])
    await provider.close()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
async def test_errors_redacted_and_never_retried(status, model):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status, json={"error": "secret provider key and private prompt"})

    provider = APIProvider(
        model,
        HTTPTransport(model, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )
    with pytest.raises(BotError) as error:
        await provider.complete([Message("user", "hi")])
    assert "secret" not in str(error.value)
    assert count == 1
    await provider.close()


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"error": {"code": "billing_not_active"}}, "billing is not active"),
        ({"error": {"code": "credit_balance_exhausted"}}, "credits are exhausted"),
        ({"error": {"code": "organization_spend_limit_exceeded"}}, "organization spend limit"),
        ({"error": {"code": "project_spend_limit_exceeded"}}, "project spend limit"),
        ({"error": {"code": "organization_usage_limit_exceeded"}}, "organization usage limit"),
        ({"error": {"code": "insufficient_quota"}}, "quota is unavailable"),
        ({"error": {"code": "unknown-code"}}, "quota or rate limit"),
        ({"error": {"code": ["billing_not_active"]}}, "quota or rate limit"),
        ({"error": "secret diagnostic"}, "quota or rate limit"),
        ([], "quota or rate limit"),
    ],
)
async def test_openai_billing_errors_are_actionable_redacted_and_not_retried(
    model, payload, expected
):
    model = replace(
        model, backend=Backend("openai", "openai", OFFICIAL_URLS["openai"], auth="none")
    )
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            payload["error"]["message"] = "secret provider credential and diagnostic"
        return httpx.Response(429, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = APIProvider(model, HTTPTransport(model, client=client))
    try:
        with pytest.raises(BotError, match=expected) as error:
            await provider.complete([Message("user", "test")])
        assert "secret" not in str(error.value) and count == 1
    finally:
        await provider.close()
    assert client.is_closed


async def test_openai_oversized_error_body_is_bounded(model):
    model = replace(
        model, backend=Backend("openai", "openai", OFFICIAL_URLS["openai"], auth="none")
    )
    chunks = 0
    closed = False

    class ErrorStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            nonlocal chunks
            for _ in range(1000):
                chunks += 1
                yield b"secret" * 1000

        async def aclose(self):
            nonlocal closed
            closed = True

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, stream=ErrorStream()))
    )
    provider = APIProvider(model, HTTPTransport(model, client=client))
    try:
        with pytest.raises(BotError, match="quota or rate limit"):
            await provider.complete([Message("user", "test")])
        assert chunks == 3 and closed
    finally:
        await provider.close()


@pytest.mark.parametrize("payload", [b"not json", b"[]", b"{}", b'{"choices":[]}'])
async def test_malformed_contract(payload, model):
    provider = APIProvider(
        model,
        HTTPTransport(
            model,
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
            ),
        ),
    )
    with pytest.raises(BotError):
        await provider.complete([Message("user", "hi")])
    await provider.close()


async def test_timeout_and_capability_rejection(model):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private diagnostics")

    provider = APIProvider(
        model,
        HTTPTransport(model, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )
    with pytest.raises(BotError, match="timed out"):
        await provider.complete([Message("user", "hi")])
    assert len(calls) == 1
    provider.model = replace(model, capabilities=frozenset({Capability.TEXT_TO_IMAGE}))
    with pytest.raises(BotError, match="does not support"):
        await provider.complete([])
    assert len(calls) == 1
    await provider.close()
