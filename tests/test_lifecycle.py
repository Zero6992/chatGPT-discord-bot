from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.aclient import DiscordClient
from src.config import Backend
from src.domain import BotError
from src.storage import Scope


async def test_lifecycle_initializes_once_and_closes(settings):
    settings = replace(settings, models={"local": settings.models["local"]})
    client = DiscordClient(settings)
    client.tree.sync = AsyncMock()
    await client.setup_hook()
    maintenance = client.maintenance
    assert maintenance is not None and not maintenance.done()
    client.tree.sync.assert_awaited_once()
    await client.close()
    assert maintenance.done() and not client.initialized


async def test_bot_and_webhook_filters_then_real_auto_reply(settings, service):
    settings = replace(settings, reply_channels=(3,), allowed_user_ids=(4,))
    client = DiscordClient(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store = service.store
    client.service = service
    client.initialized = True
    service.providers["local"].session = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"

    class Typing:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    channel = SimpleNamespace(id=3, typing=Typing, send=AsyncMock())
    target = SimpleNamespace(
        author=SimpleNamespace(id=4, bot=False),
        webhook_id=None,
        guild=SimpleNamespace(id=2),
        channel=channel,
        content="hello",
    )
    await client.on_message(target)
    channel.send.assert_awaited_once()
    assert service.providers["local"].calls[0][2] == Scope(1, 2, 3, 4, False).key
    service.settings.models["local"] = replace(
        service.settings.models["local"], model="changed-model"
    )
    await client.on_message(target)
    assert "Context was reconstructed" in channel.send.call_args.kwargs["content"]
    await service.store.set_reply(Scope(1, 2, 3, 4), False)
    await client.on_message(target)
    assert len(service.providers["local"].calls) == 2
    client.initialized = False
    await client.close()


async def test_cli_owner_is_enforced_before_execution(service):
    model = service.settings.models["local"]
    service.settings.models["cli"] = replace(
        model, name="cli", backend=Backend("cli", "claude-cli", owner_id=5)
    )
    with pytest.raises(BotError, match="owner"):
        await service.switch(Scope(1, 2, 3, 4), "cli")
    assert service.providers["local"].calls == []


async def test_retention_is_enforced_on_access_between_sweeps(service):
    scope = Scope(1, 2, 3, 4)
    await service.chat(scope, "expired secret")
    await service.store.db.execute("UPDATE conversations SET updated=0")
    await service.chat(scope, "new prompt")
    messages = service.providers["local"].calls[-1][0]
    assert all("expired secret" not in m.content for m in messages)


async def test_media_job_capacity(service):
    scope = Scope(1, 2, 3, 4)
    await service.store.create_job("one", scope, "local", "f", maximum=1)
    with pytest.raises(BotError, match="storage is full"):
        await service.store.create_job("two", scope, "local", "f", maximum=1)


async def test_unknown_schema_rejected_without_modification_or_lock_leak(tmp_path):
    import sqlite3

    from src.storage import Store

    path = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE schema_version(version INTEGER)")
        db.execute("INSERT INTO schema_version VALUES(999)")
    before = path.read_bytes()
    for _ in range(2):
        with pytest.raises(BotError, match="Unsupported conversation schema"):
            await Store(path).open()
    assert path.read_bytes() == before


async def test_media_capacity_is_atomic_across_conversations(service):
    import asyncio

    first = Scope(1, 2, 3, 4)
    second = Scope(1, 2, 3, 5)
    results = await asyncio.gather(
        service.store.create_job("first", first, "local", "f", maximum=1),
        service.store.create_job("second", second, "local", "f", maximum=1),
        return_exceptions=True,
    )
    assert sum(result is True for result in results) == 1
    assert sum(isinstance(result, BotError) for result in results) == 1
