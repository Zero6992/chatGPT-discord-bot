import asyncio
from dataclasses import replace

import pytest

from src.domain import BotError, Message
from src.service import ConversationService, budget_context, model_instructions
from src.storage import Scope, Store

SCOPE = Scope(1, 2, 3, 4)


@pytest.mark.parametrize(
    "changed",
    [
        dict(bot_id=9),
        dict(guild_id=9),
        dict(guild_id=0),
        dict(channel_id=9),
        dict(user_id=9),
        dict(private=False),
    ],
)
async def test_conversation_isolation(service, changed):
    await service.chat(SCOPE, "private first prompt")
    other = replace(SCOPE, **changed)
    await service.chat(other, "independent prompt")
    messages, _, key = service.providers["local"].calls[-1]
    assert key != SCOPE.key
    assert all("private first" not in message.content for message in messages)
    await service.reset(other)
    assert len((await service.conversation(SCOPE)).turns) == 2


async def test_restart_history_visibility_and_session(settings):
    from tests.conftest import RecordingProvider

    store = Store(settings.database)
    await store.open()
    provider = RecordingProvider()
    provider.session = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
    service = ConversationService(settings, store, {"local": provider})
    await service.chat(SCOPE, "first")
    await store.set_private(SCOPE, False)
    await service.close()
    await store.close()
    store = Store(settings.database)
    await store.open()
    service = ConversationService(settings, store, {"local": provider})
    try:
        assert await store.private(SCOPE) is False
        await service.chat(SCOPE, "second")
        messages, session, _ = provider.calls[-1]
        assert session.id == provider.session
        assert [m.content for m in messages[1:]] == ["first", "reply to first", "second"]
    finally:
        await service.close()
        await store.close()


async def test_failed_turn_not_saved_and_uncertain_session_invalidated(service):
    provider = service.providers["local"]
    provider.session = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
    await service.chat(SCOPE, "good")
    provider.fail = True
    with pytest.raises(RuntimeError):
        await service.chat(SCOPE, "failed")
    conversation = await service.conversation(SCOPE)
    assert [m.content for m in conversation.turns] == ["good", "reply to good"]
    assert conversation.session is None


async def test_switch_preserves_history_but_reconstructs_session(service):
    first = service.providers["local"]
    first.session = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
    await service.chat(SCOPE, "one")
    second_model = replace(service.settings.models["local"], name="other", model="different")
    service.settings.models["other"] = second_model
    service.providers["other"] = first
    await service.switch(SCOPE, "other")
    await service.chat(SCOPE, "two")
    messages, session, _ = first.calls[-1]
    assert session is None
    assert messages[1].content == "one"
    with pytest.raises(BotError):
        await service.switch(SCOPE, "https://attacker.example")
    assert (await service.conversation(SCOPE)).model == "other"


async def test_budget_reconstructs_and_retains_successful_pairs(service):
    # Keep the same space for turns while accounting for the fixed identity instructions.
    identity_bytes = len(("\n\n" + model_instructions(service.settings.models["local"])).encode())
    service.settings = replace(service.settings, context_bytes=200 + identity_bytes, max_turns=2)
    for n in range(6):
        await service.chat(SCOPE, "question " + str(n))
    conversation = await service.conversation(SCOPE)
    assert len(conversation.turns) == 4
    messages = service.providers["local"].calls[-1][0]
    assert [m.role for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1].content == "question 4"
    assert messages[-1].content == "question 5"


async def test_identity_instructions_count_towards_context_budget(service):
    service.settings = replace(service.settings, context_bytes=200)
    with pytest.raises(BotError, match="context budget"):
        await service.chat(SCOPE, "hello")
    assert service.providers["local"].calls == []


async def test_local_identity_uses_configured_id_without_private_backend_configuration(service):
    model = service.settings.models["local"]
    service.settings.models["local"] = replace(
        model,
        backend=replace(model.backend, account="private-account", owner_id=123456789),
    )
    await service.chat(SCOPE, "What model are you?")
    system = service.providers["local"].calls[-1][0][0].content
    assert '"backend": "compatible"' in system
    assert '"model_id": "fixture-model"' in system
    assert "does not verify its developer" in system
    for private_value in (model.backend.base_url, "private-account", "123456789"):
        assert private_value not in system


def test_context_rejects_oversized_system_and_utf8():
    with pytest.raises(BotError):
        budget_context("system", [], "界" * 10, 50)
    messages = budget_context(
        "system", [Message("user", "old"), Message("assistant", "old reply")], "new", 65
    )
    assert [message.role for message in messages] == ["system", "user"]


async def test_reset_restores_defaults_and_deletes_job_mappings(service):
    await service.chat(SCOPE, "hello")
    await service.persona(SCOPE, "creative")
    await service.store.create_job("123", SCOPE, "local", "identity")
    await service.reset(SCOPE)
    conversation = await service.conversation(SCOPE)
    assert conversation.turns == [] and conversation.persona == "standard"
    with pytest.raises(BotError, match="No media job"):
        await service.store.job("123", SCOPE)


async def test_retention_and_capacity(service):
    await service.chat(SCOPE, "old")
    await service.store.db.execute("UPDATE conversations SET updated=0")
    await service.store.prune(1)
    assert (await service.conversation(SCOPE)).turns == []
    service.settings = replace(service.settings, max_conversations=1)
    with pytest.raises(BotError, match="storage is full"):
        await service.chat(replace(SCOPE, user_id=99), "new")


async def test_single_process_database_lock(service):
    second = Store(service.settings.database)
    with pytest.raises(BotError, match="Another bot process"):
        await second.open()


async def test_persona_permissions_validate_before_mutation(service):
    await service.chat(SCOPE, "hello")
    with pytest.raises(BotError, match="administrator"):
        await service.persona(SCOPE, "jailbreak-v1")
    assert (await service.conversation(SCOPE)).persona == "standard"


async def test_same_conversation_serialized_other_conversations_run(service):
    entered = asyncio.Event()
    release = asyncio.Event()
    original = service.providers["local"].complete
    active = 0
    peak = 0

    async def blocking(messages, session=None, *, conversation_id=""):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        entered.set()
        await release.wait()
        try:
            return await original(messages, session, conversation_id=conversation_id)
        finally:
            active -= 1

    service.providers["local"].complete = blocking
    first = asyncio.create_task(service.chat(SCOPE, "first"))
    await entered.wait()
    same = asyncio.create_task(service.chat(SCOPE, "second"))
    other = asyncio.create_task(service.chat(replace(SCOPE, user_id=99), "other"))
    for _ in range(20):
        await asyncio.sleep(0.005)
        if active == 2:
            break
    assert active == 2
    release.set()
    await asyncio.gather(first, same, other)
    assert peak == 2
    assert service.gate.pending == 0 and not service.gate.locks
    last = [c for c in service.providers["local"].calls if c[2] == SCOPE.key][-1]
    assert [m.content for m in last[0][1:]] == ["first", "reply to first", "second"]


async def test_admission_cancellation_and_deadline(service):
    service.settings = replace(service.settings, request_timeout=0.05)
    service.gate.maximum = 1
    entered = asyncio.Event()

    async def blocking(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    service.providers["local"].complete = blocking
    first = asyncio.create_task(service.chat(SCOPE, "first"))
    await entered.wait()
    with pytest.raises(BotError, match="busy"):
        await service.chat(replace(SCOPE, user_id=99), "next")
    with pytest.raises(BotError, match="timed out"):
        await first
    assert service.gate.pending == 0
    assert (await service.conversation(SCOPE)).turns == []
    second = asyncio.create_task(service.chat(SCOPE, "second"))
    await asyncio.sleep(0.01)
    await service.gate.cancel(SCOPE.key)
    with pytest.raises(asyncio.CancelledError):
        await second
    assert not service.gate.tasks and not service.gate.locks
