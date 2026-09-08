from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.art import Artifact
from src.bot import create_bot
from src.domain import BotError
from utils.message_utils import send_artifact, send_text


@pytest.mark.parametrize("private", [True, False])
@pytest.mark.parametrize("content", ["short", "```python\n" + "@everyone secret\n" * 500 + "```"])
async def test_delivery_retains_visibility_for_all_content(private, content):
    calls = []

    async def send(**kwargs):
        if "file" in kwargs:
            assert kwargs["file"].fp.read().decode() == content
        calls.append(kwargs)

    target = SimpleNamespace(
        followup=SimpleNamespace(send=send), channel=SimpleNamespace(send=AsyncMock())
    )
    await send_text(target, content, private=private)
    assert len(calls) == 1
    assert calls[0]["ephemeral"] is private
    assert calls[0]["allowed_mentions"].everyone is False
    target.channel.send.assert_not_called()


async def test_ordinary_messages_use_channel_transport():
    target = SimpleNamespace(channel=SimpleNamespace(send=AsyncMock()))
    await send_text(target, "answer", private=False)
    target.channel.send.assert_awaited_once()
    with pytest.raises(BotError):
        await send_text(target, "private", private=True)


async def test_media_attachment_limit_and_cleanup():
    delivered = []

    async def send(**kwargs):
        assert kwargs["file"].fp.read() == b"artifact"
        delivered.append(kwargs["file"])

    target = SimpleNamespace(
        followup=SimpleNamespace(send=send), guild=SimpleNamespace(filesize_limit=10)
    )
    await send_artifact(
        target, Artifact(b"artifact", "result.png", "image/png"), private=True, maximum=20
    )
    with pytest.raises(BotError, match="attachment limit"):
        await send_artifact(
            target, Artifact(b"x" * 11, "result.png", "image/png"), private=True, maximum=20
        )
    assert len(delivered) == 1


async def test_actual_command_registration_and_scope(settings, service):
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=100)
    client.store = service.store
    client.service = service
    target = SimpleNamespace(
        user=SimpleNamespace(id=4),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    try:
        commands = {command.name for command in client.tree.get_commands()}
        assert {
            "chat",
            "provider",
            "models",
            "draw",
            "video",
            "job",
            "cancel",
            "delete",
            "reset",
            "public",
            "private",
            "replyall",
        } <= commands
        await client.tree.get_command("chat").callback(target, "hello")
        target.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        assert target.followup.send.call_args.kwargs["ephemeral"] is True
        assert (await client.scope(target)).bot_id == 100
    finally:
        await client.close()


async def test_auto_replies_ignore_bots_and_unlisted_channels(settings, service):
    client = create_bot(settings)
    client.service = service
    client.initialized = True
    target = SimpleNamespace(
        author=SimpleNamespace(id=22, bot=True), webhook_id=None, channel=SimpleNamespace(id=3)
    )
    await client.on_message(target)
    assert service.providers["local"].calls == []
    client.initialized = False
    await client.close()


async def test_actual_draw_command_downloads_and_delivers_privately(settings, service, monkeypatch):
    import base64

    import httpx

    from src.art import MediaService
    from tests.test_media import PNG, make_provider

    calls = []

    def handler(request):
        assert request.url.path.endswith("/images/edits")
        assert PNG in request.content
        calls.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})

    provider = make_provider("openai", handler, monkeypatch)
    settings.models["media"] = provider.model
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store = service.store
    client.service = service
    client.media = MediaService(settings, service.store, service, {"media": provider})
    delivered = []

    async def send(**kwargs):
        assert kwargs["ephemeral"] is True
        assert kwargs["file"].fp.read() == PNG
        delivered.append(kwargs["file"])

    target = SimpleNamespace(
        id=123,
        user=SimpleNamespace(id=4),
        guild=SimpleNamespace(id=2, filesize_limit=100000),
        channel=SimpleNamespace(id=3),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=send),
        edit_original_response=AsyncMock(),
    )
    attachment = SimpleNamespace(size=len(PNG), read=AsyncMock(return_value=PNG))
    try:
        await client.tree.get_command("draw").callback(target, "paint", "media", attachment)
        attachment.read.assert_awaited_once()
        assert len(calls) == 1 and len(delivered) == 1
        assert delivered[0].fp.closed
        assert (await service.store.job("123", await client.scope(target)))["state"] == "delivered"
    finally:
        await client.media.close()
        await client.close()
