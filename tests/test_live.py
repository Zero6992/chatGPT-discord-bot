"""Optional, explicitly authorized smoke tests. Never part of the offline run."""

import os
import uuid
from pathlib import Path

import pytest

from src.art import MediaProvider, MediaService
from src.cli import CLIProvider, DockerRunner
from src.cli_accounts import AccountProfile
from src.config import CLI_KINDS, load_settings
from src.providers import APIProvider
from src.service import ConversationService
from src.storage import Scope, Store

pytestmark = pytest.mark.live


@pytest.mark.parametrize("operation", ["chat", "image", "video", "cli"])
async def test_live_provider(operation, tmp_path):
    if os.getenv("BOT_LIVE_TESTS") != "1" or os.getenv("BOT_ALLOW_PAID_TESTS") != "1":
        pytest.skip("Unverified: explicit live/paid smoke-test authorization is absent")
    alias = os.getenv(f"LIVE_{operation.upper()}_MODEL")
    if not alias:
        pytest.skip(f"Unverified: LIVE_{operation.upper()}_MODEL is unset")
    settings = load_settings(Path(os.environ.get("BOT_CONFIG", "config.toml")))
    model = settings.models[alias]
    if not os.getenv(model.backend.api_key_env) and model.backend.auth == "api":
        pytest.skip("Unverified: configured provider credential is absent")
    if model.backend.auth == "account" and not AccountProfile(model.backend).configured():
        pytest.skip("Unverified: native CLI account login has not been completed")
    store = Store(tmp_path / "smoke.sqlite3")
    await store.open()
    owner = model.backend.owner_id or next(iter(settings.allowed_user_ids), 1)
    scope = Scope(1, 0, 1, owner)
    if operation in {"chat", "cli"}:
        if operation == "cli" and model.backend.kind not in CLI_KINDS:
            pytest.fail("LIVE_CLI_MODEL must name a CLI backend")
        provider = (
            CLIProvider(model, DockerRunner(model, settings.request_timeout, str(store.path)))
            if operation == "cli"
            else APIProvider(model)
        )
        service = ConversationService(settings, store, {alias: provider})
        try:
            conversation = await service.conversation(scope)
            conversation.model = alias
            await store.save(conversation)
            answer = await service.chat(
                scope, "Remember the word apricot. Reply with the word only."
            )
            assert "apricot" in answer.text.lower()
            answer = await service.chat(
                scope, "What word did I ask you to remember? Reply with the word only."
            )
            assert "apricot" in answer.text.lower()
        finally:
            await service.reset(scope)
            await service.close()
            await store.close()
    else:
        provider = MediaProvider(model, settings.attachment_bytes)
        service = ConversationService(settings, store, {})
        media = MediaService(settings, store, service, {alias: provider})

        async def progress(text):
            pass

        try:
            artifact = await media.generate(
                scope,
                alias,
                "A blue circle on a white background",
                uuid.uuid4().hex,
                video=operation == "video",
                progress=progress,
            )
            assert len(artifact.data) > 100
            assert artifact.content_type == ("video/mp4" if operation == "video" else "image/png")
        finally:
            await media.close()
            await store.close()
