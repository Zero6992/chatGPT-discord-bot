from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from src.bot import create_bot
from src.config import Backend
from src.domain import Capability
from utils.command_ui import ModelPages, model_choices, model_pages, visible_models


def catalog(settings, cli_auth="api"):
    models = dict(settings.models)
    for name, kind, caps in (
        ("claude_account", "claude-cli", {Capability.CHAT}),
        ("codex_account", "codex-cli", {Capability.CHAT}),
        ("grok_account", "grok-cli", {Capability.CHAT}),
        ("image", "openai", {Capability.TEXT_TO_IMAGE}),
        ("edit", "openai", {Capability.TEXT_TO_IMAGE, Capability.IMAGE_TO_IMAGE}),
        ("video", "xai", {Capability.TEXT_TO_VIDEO}),
        ("animate", "gemini", {Capability.TEXT_TO_VIDEO, Capability.IMAGE_TO_VIDEO}),
        ("search", "xai", {Capability.IMAGE_SEARCH}),
    ):
        models[name] = replace(
            settings.models["local"],
            name=name,
            model="model-" + name,
            backend=Backend(
                name, kind, auth=cli_auth if kind.endswith("-cli") else "api", owner_id=4
            ),
            capabilities=frozenset(caps),
        )
    return replace(settings, models=models)


@pytest.mark.parametrize("private", [True, False])
@pytest.mark.parametrize("user_id", [4, 99])
async def test_models_and_help_use_embeds_and_preserve_visibility(
    settings, service, private, user_id
):
    settings = catalog(settings)
    client = create_bot(settings)
    client._connection.user = SimpleNamespace(id=1)
    client.store, client.service = service.store, service
    target = SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3),
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    try:
        scope = await client.scope(target)
        await service.store.set_private(scope, private)
        await client.tree.get_command("models").callback(target)
        sent = target.followup.send.call_args.kwargs
        assert sent["ephemeral"] is private
        assert "content" not in sent and sent["view"] is discord.utils.MISSING
        assert sent["embed"].title == "Available models"
        names = [field.name for field in sent["embed"].fields]
        assert names[0].startswith("★ local")
        assert any("Claude Code" in name for name in names)
        assert any("Codex CLI" in name for name in names)
        assert any("Grok CLI" in name for name in names)
        assert sent["allowed_mentions"].everyone is False

        await client.tree.get_command("help").callback(target)
        help_reply = target.response.send_message.call_args.kwargs
        assert help_reply["ephemeral"] is True
        assert help_reply["embed"].title == "ChatGPT Discord Bot"
        contents = "\n".join(field.value for field in help_reply["embed"].fields)
        for command in ("/provider", "/cli_auth", "/image_search", "/video", "/draw", "/reset"):
            assert command in contents
        assert service.providers["local"].calls == []
    finally:
        await client.close()


@pytest.mark.parametrize(
    "command,image,expected",
    [
        ("provider", None, {"local", "claude_account", "codex_account", "grok_account"}),
        ("image_search", None, {"search"}),
        ("draw", None, {"image", "edit"}),
        ("draw", object(), {"edit"}),
        ("video", None, {"video", "animate"}),
        ("video", object(), {"animate"}),
    ],
)
async def test_registered_model_menus_filter_capabilities_and_attachment(
    settings, command, image, expected
):
    client = create_bot(catalog(settings))
    target = SimpleNamespace(user=SimpleNamespace(id=4), namespace=SimpleNamespace(image=image))
    try:
        registered = client.tree.get_command(command)
        option = next(
            item for item in registered.to_dict(client.tree)["options"] if item["name"] == "model"
        )
        assert option["autocomplete"] is True
        callback = registered._params["model"].autocomplete
        choices = await callback(target, "")
        assert {choice.value for choice in choices} == expected
        assert all(choice.value in client.settings.models for choice in choices)
        assert await callback(target, "unconfigured endpoint") == []
    finally:
        await client.close()


@pytest.mark.parametrize("auth", ["api", "account"])
@pytest.mark.parametrize("user_id", [4, 99])
def test_cli_options_allow_everyone_and_are_searchable_by_cli_name(settings, auth, user_id):
    settings = catalog(settings, auth)
    choices = model_choices(settings, user_id, Capability.CHAT, "Claude Code")
    assert [choice.value for choice in choices] == ["claude_account"]
    assert {choice.value for choice in model_choices(settings, user_id, Capability.CHAT, "")} == {
        "local",
        "claude_account",
        "codex_account",
        "grok_account",
    }
    assert visible_models(replace(settings, allowed_user_ids=(4,)), 99) == []


async def test_large_catalog_paginates_one_message_and_enforces_page_owner(settings):
    models = [
        replace(settings.models["local"], name=f"model_{n}", model="id-" + "x" * 1800)
        for n in range(60)
    ]
    pages = model_pages(models, "model_0")
    assert len(pages) > 1
    assert sum(len(page.fields) for page in pages) == len(models)
    for page in pages:
        assert len(page) <= 6000 and len(page.fields) <= 25
        assert all(len(field.name) <= 256 and len(field.value) <= 1024 for field in page.fields)
    many = replace(settings, models={model.name: model for model in models})
    choices = model_choices(many, 4, Capability.CHAT, "")
    assert len(choices) == 25 and all(len(choice.name) <= 100 for choice in choices)
    view = ModelPages(pages, 4)
    owner = SimpleNamespace(
        user=SimpleNamespace(id=4), response=SimpleNamespace(edit_message=AsyncMock())
    )
    stranger = SimpleNamespace(
        user=SimpleNamespace(id=9), response=SimpleNamespace(send_message=AsyncMock())
    )
    try:
        assert view.previous.disabled and not view.next.disabled
        assert await view.interaction_check(stranger) is False
        assert stranger.response.send_message.call_args.kwargs["ephemeral"] is True
        assert await view.interaction_check(owner) is True
        await view.next.callback(owner)
        assert view.index == 1
        assert owner.response.edit_message.call_args.kwargs["embed"] is pages[1]
        await view.previous.callback(owner)
        assert view.index == 0 and view.previous.disabled
    finally:
        view.stop()
