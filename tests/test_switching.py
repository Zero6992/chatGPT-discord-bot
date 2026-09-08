import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from src.bot import create_bot
from src.config import OFFICIAL_URLS, Backend
from src.domain import BotError
from src.providers import HTTPTransport
from tests.test_providers import FIXTURES


def interaction(*, user_id=4, channel_id=3):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=channel_id),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


async def test_switch_routes_with_current_identity_and_retained_history(settings, monkeypatch):
    models = {}
    for kind in ("openai", "anthropic", "xai"):
        key = f"{kind.upper()}_FIXTURE_KEY"
        monkeypatch.setenv(key, f"fixture-{kind}-credential")
        models[kind] = replace(
            settings.models["local"],
            name=kind,
            model=f"fixture-{kind}-model",
            backend=Backend(kind, kind, OFFICIAL_URLS[kind], key),
        )
    settings = replace(settings, models=models, default_model="openai")
    requests = []
    old_identity = "我是 OpenAI 開發的 ChatGPT。測試暗號是藍色鳳梨。"

    def handler(request):
        kind = {"api.openai.com": "openai", "api.anthropic.com": "anthropic", "api.x.ai": "xai"}[
            request.url.host
        ]
        requests.append((kind, request, json.loads(request.content)))
        result = json.loads(json.dumps(FIXTURES[kind]))
        if kind == "openai":
            result["output"][0]["content"][0]["text"] = old_identity
        return httpx.Response(200, json=result)

    def transport(model, timeout):
        return HTTPTransport(
            model,
            timeout,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr("src.aclient.HTTPTransport", transport)
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.tree.sync = AsyncMock()
    target = interaction()
    await client.setup_hook()
    try:
        previous = []
        for index, kind in enumerate(("openai", "anthropic", "xai", "openai")):
            await client.tree.get_command("provider").callback(target, kind)
            prompt = "你現在使用哪個模型？之前的暗號是什麼？"
            await client.tree.get_command("chat").callback(target, prompt)
            assert len(requests) == index + 1
            routed_kind, request, body = requests[-1]
            assert routed_kind == kind
            assert request.method == "POST"
            assert body["model"] == models[kind].model
            if kind == "anthropic":
                assert request.url.path == "/v1/messages"
                assert request.headers["x-api-key"] == "fixture-anthropic-credential"
                system, turns = body["system"], body["messages"]
            else:
                assert request.url.path == "/v1/responses"
                assert request.headers["authorization"] == f"Bearer fixture-{kind}-credential"
                assert body["input"][0]["role"] == "system"
                system, turns = body["input"][0]["content"], body["input"][1:]
            assert f'"backend": "{kind}"' in system
            assert f'"model_id": "{models[kind].model}"' in system
            assert all(other.model not in system for other in models.values() if other.name != kind)
            assert turns == [*previous, {"role": "user", "content": prompt}]
            reply = old_identity if kind == "openai" else "Hello from the model."
            previous = [*turns, {"role": "assistant", "content": reply}]

            await client.tree.get_command("provider").callback(target)
            status = target.followup.send.call_args.kwargs
            assert status["ephemeral"] is True
            assert f"Backend: {kind}" in status["content"]
            assert f"Model ID: {models[kind].model}" in status["content"]
            assert len(requests) == index + 1

        conversation = await client.service.conversation(await client.scope(target))
        assert [message.__dict__ for message in conversation.turns] == previous
        assert conversation.turns[1].content == old_identity
    finally:
        await client.close()


async def test_provider_status_uses_requesters_conversation_without_model_calls(settings, service):
    settings.models["other"] = replace(settings.models["local"], name="other", model="another")
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store = service.store
    client.service = service
    target = interaction()
    other_channel = interaction(channel_id=9)
    try:
        await client.tree.get_command("provider").callback(target, "other")
        await client.tree.get_command("provider").callback(other_channel)
        assert "Model ID: fixture-model" in other_channel.followup.send.call_args.kwargs["content"]
        await client.tree.get_command("provider").callback(target)
        assert "Model ID: another" in target.followup.send.call_args.kwargs["content"]
        assert service.providers["local"].calls == []
        assert (await service.conversation(await client.scope(target))).turns == []
        model_option = client.tree.get_command("provider").to_dict(client.tree)["options"][0]
        assert not model_option["required"]
    finally:
        await client.close()


async def test_provider_status_enforces_user_allowlist(settings):
    client = create_bot(replace(settings, allowed_user_ids=(4,)))
    client._connection.user = SimpleNamespace(id=1)
    target = interaction(user_id=5)
    try:
        with pytest.raises(BotError, match="restricted"):
            await client.tree.get_command("provider").callback(target)
        target.response.defer.assert_not_called()
        target.followup.send.assert_not_called()
    finally:
        await client.close()
