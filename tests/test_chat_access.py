from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot import create_bot
from src.config import Backend
from src.domain import BotError
from src.storage import Scope

MODES = [
    ("compatible", "none"),
    ("compatible", "api"),
    *[(kind, "api") for kind in ("openai", "anthropic", "gemini", "xai", "deepseek")],
    *[
        (kind, auth)
        for kind in ("codex-cli", "claude-cli", "grok-cli")
        for auth in ("api", "account")
    ],
]
OWNER_SESSION = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
OTHER_SESSION = "f726541c-8519-42a2-8691-4da25b2053ae"


@pytest.mark.parametrize("kind,auth", MODES)
@pytest.mark.parametrize("private", [True, False])
async def test_every_mode_allows_chat_with_separate_user_history_and_sessions(
    service, tmp_path, monkeypatch, kind, auth, private
):
    monkeypatch.setenv("FIXTURE_KEY", "fixture-credential")
    model = service.settings.models["local"]
    service.settings.models["local"] = replace(
        model,
        backend=Backend(
            "configured",
            kind,
            auth=auth,
            owner_id=4,
            api_key_env="FIXTURE_KEY" if auth == "api" else "",
            auth_profile=str(tmp_path / "account") if auth == "account" else "",
        ),
        parameters={},
    )
    assert service.settings.allowed_user_ids == ()
    provider = service.providers["local"]
    owner = Scope(1, 2, 3, 4, private)
    other = replace(owner, user_id=99)

    provider.session = OWNER_SESSION
    await service.chat(owner, "owner's first prompt")
    provider.session = OTHER_SESSION
    await service.switch(other, "local")
    await service.chat(other, "other user's first prompt")
    messages, session, key = provider.calls[-1]
    assert session is None and key == other.key and key != owner.key
    assert [message.content for message in messages[1:]] == ["other user's first prompt"]

    for scope, session_id, prompt in (
        (owner, OWNER_SESSION, "owner's first prompt"),
        (other, OTHER_SESSION, "other user's first prompt"),
    ):
        provider.session = session_id
        await service.chat(scope, "follow-up")
        messages, session, key = provider.calls[-1]
        assert session.id == session_id and key == scope.key
        assert [message.content for message in messages[1:]] == [
            prompt,
            "reply to " + prompt,
            "follow-up",
        ]
    await service.reset(other)
    assert (await service.conversation(other)).turns == []
    assert len((await service.conversation(owner)).turns) == 4

    service.settings = replace(service.settings, allowed_user_ids=(4, 5))
    assert (await service.switch(replace(owner, user_id=5), "local")).name == "local"
    calls = len(provider.calls)
    with pytest.raises(BotError, match="restricted"):
        await service.chat(other, "blocked by explicit allowlist")
    with pytest.raises(BotError, match="restricted"):
        await service.switch(other, "local")
    assert len(provider.calls) == calls


@pytest.mark.parametrize("kind", ["codex-cli", "claude-cli", "grok-cli"])
@pytest.mark.parametrize("auth", ["api", "account"])
async def test_nonowner_can_select_cli_and_chat_through_discord(
    service, tmp_path, monkeypatch, kind, auth
):
    monkeypatch.setenv("FIXTURE_KEY", "fixture-credential")
    model = service.settings.models["local"]
    service.settings.models["cli"] = replace(
        model,
        name="cli",
        backend=Backend(
            "cli",
            kind,
            auth=auth,
            owner_id=4,
            api_key_env="FIXTURE_KEY" if auth == "api" else "",
            auth_profile=str(tmp_path / "account") if auth == "account" else "",
        ),
        parameters={},
    )
    service.providers["cli"] = service.providers["local"]
    client = create_bot(service.settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store, client.service = service.store, service
    target = SimpleNamespace(
        user=SimpleNamespace(id=99),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    try:
        await client.tree.get_command("provider").callback(target, "cli")
        await client.tree.get_command("chat").callback(target, "hello from another user")
        assert (
            "reply to hello from another user" in target.followup.send.call_args.kwargs["content"]
        )
        conversation = await service.conversation(await client.scope(target))
        assert conversation.model == "cli" and len(conversation.turns) == 2
    finally:
        await client.close()
