"""Thin Discord commands. Model aliases and visibility belong to the requester."""

import asyncio
from dataclasses import replace

import discord
from discord import app_commands

from src.aclient import DiscordClient
from src.cli_accounts import DeviceChallenge
from src.config import Settings
from src.domain import BotError, Capability
from src.storage import Scope
from utils.command_ui import ModelPages, help_embed, model_choices, model_pages, visible_models
from utils.message_utils import send_artifact, send_search_images, send_text


def create_bot(settings: Settings) -> DiscordClient:
    client = DiscordClient(settings)

    async def begin(interaction: discord.Interaction) -> Scope:
        scope = await client.scope(interaction)
        await interaction.response.defer(ephemeral=scope.private, thinking=True)
        return scope

    async def progress(interaction: discord.Interaction, text: str) -> None:
        await interaction.edit_original_response(
            content=text, allowed_mentions=discord.AllowedMentions.none()
        )

    @client.tree.error
    async def error_handler(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        text = (
            str(original)
            if isinstance(original, BotError)
            else "The request failed. Contact the administrator."
        )
        if interaction.response.is_done():
            await interaction.edit_original_response(
                content=text, allowed_mentions=discord.AllowedMentions.none()
            )
        else:
            await interaction.response.send_message(
                text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
            )

    @client.tree.command(name="chat", description="Chat in your conversation in this channel")
    async def chat(interaction: discord.Interaction, message: str) -> None:
        scope = await begin(interaction)
        try:
            result = await client.service.chat(scope, message)
            text = result.text + (f"\n\n{result.notice}" if result.notice else "")
            await send_text(interaction, text, private=scope.private)
        except asyncio.CancelledError:
            await progress(interaction, "Request cancelled. Provider work may still be billed.")

    @client.tree.command(
        name="models", description="List administrator-configured model aliases and capabilities"
    )
    async def models(interaction: discord.Interaction) -> None:
        scope = await begin(interaction)
        conversation = await client.service.conversation(scope)
        pages = model_pages(visible_models(settings, scope.user_id), conversation.model)
        await interaction.followup.send(
            embed=pages[0],
            view=ModelPages(pages, scope.user_id) if len(pages) > 1 else discord.utils.MISSING,
            ephemeral=scope.private,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @client.tree.command(
        name="provider", description="Show or change this conversation's configured chat model"
    )
    async def provider(interaction: discord.Interaction, model: str | None = None) -> None:
        scope = await begin(interaction)
        selected = (
            await client.service.current_model(scope)
            if model is None
            else await client.service.switch(scope, model)
        )
        auth = (
            "CLI account / plan usage"
            if selected.backend.auth == "account"
            else ("API key" if selected.backend.auth == "api" else "Local/custom, no API key")
        )
        notice = (
            "\nRetained text history will be reconstructed for the next turn."
            if model is not None
            else ""
        )
        await send_text(
            interaction,
            f"Current model alias: {selected.name}\nBackend: {selected.backend.kind}\n"
            f"Model ID: {selected.model}\nAccess: {auth}{notice}",
            private=scope.private,
        )

    @provider.autocomplete("model")
    async def autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return model_choices(settings, interaction.user.id, Capability.CHAT, current)

    @client.tree.command(
        name="cli_auth", description="Owner: native CLI account login, status, logout or cancel"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name=name, value=name)
            for name in ("login", "status", "logout", "cancel")
        ]
    )
    async def cli_auth(interaction: discord.Interaction, action: str, model: str) -> None:
        scope = await client.scope(interaction, private=True)
        await interaction.response.defer(ephemeral=True, thinking=True)

        async def challenge(value: DeviceChallenge) -> None:
            await progress(
                interaction,
                f"Sign in to your personal {model} CLI runtime at <{value.url}>\n"
                f"Device code: `{value.code}`\n"
                "Complete approval on the official website for the login you just started. "
                "Do not paste codes or tokens into Discord. This request expires within 10 minutes.",
            )

        try:
            result = await client.cli_auth.execute(action, model, scope.user_id, challenge)
        except asyncio.CancelledError:
            result = "Account operation cancelled. Login may need to be restarted."
        except BotError as error:
            result = str(error)
        # Replace the authorization challenge after success, failure or cancellation.
        await progress(interaction, result)

    @cli_auth.autocomplete("model")
    async def auth_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name, model in settings.models.items()
            if model.backend.auth == "account"
            and model.backend.owner_id == interaction.user.id
            and settings.allowed_user_ids == (interaction.user.id,)
            and current.lower() in name.lower()
        ][:25]

    @client.tree.command(
        name="image_search", description="Find images using an explicit search model alias"
    )
    async def image_search(interaction: discord.Interaction, query: str, model: str) -> None:
        scope = await begin(interaction)
        try:
            images = await client.search.search(scope, model, query)
            await send_search_images(interaction, images, private=scope.private)
            await progress(interaction, "Image search finished.")
        except asyncio.CancelledError:
            await progress(
                interaction, "Image search cancelled. Provider work may still be billed."
            )

    @image_search.autocomplete("model")
    async def search_models(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return model_choices(settings, interaction.user.id, Capability.IMAGE_SEARCH, current)

    async def generate(
        interaction: discord.Interaction,
        prompt: str,
        model: str,
        image: discord.Attachment | None,
        video: bool,
    ) -> None:
        scope = await begin(interaction)
        if image is not None and image.size > settings.attachment_bytes:
            raise BotError("Input attachment exceeds the configured size limit.")

        async def load_source() -> bytes:
            assert image is not None
            async with asyncio.timeout(30):
                return await image.read()

        try:
            artifact = await client.media.generate(
                scope,
                model,
                prompt,
                str(interaction.id),
                video=video,
                load_source=load_source if image is not None else None,
                progress=lambda text: progress(interaction, text),
            )
            await send_artifact(
                interaction, artifact, private=scope.private, maximum=settings.attachment_bytes
            )
            await client.store.update_job(str(interaction.id), "delivered")
            await progress(interaction, f"Media job {interaction.id} delivered.")
        except BotError as error:
            await progress(interaction, f"Media request {interaction.id}: {error}")
        except asyncio.CancelledError:
            await progress(
                interaction,
                f"Stopped waiting for job {interaction.id}. Provider generation may continue and be billed; /job can retrieve a submitted video.",
            )

    @client.tree.command(
        name="draw", description="Generate or edit an image with an explicit image model alias"
    )
    async def draw(
        interaction: discord.Interaction,
        prompt: str,
        model: str,
        image: discord.Attachment | None = None,
    ) -> None:
        await generate(interaction, prompt, model, image, False)

    @client.tree.command(
        name="video", description="Generate a video with an explicit video model alias"
    )
    async def video(
        interaction: discord.Interaction,
        prompt: str,
        model: str,
        image: discord.Attachment | None = None,
    ) -> None:
        await generate(interaction, prompt, model, image, True)

    @draw.autocomplete("model")
    async def image_models(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        capability = (
            Capability.IMAGE_TO_IMAGE
            if getattr(interaction.namespace, "image", None) is not None
            else Capability.TEXT_TO_IMAGE
        )
        return model_choices(settings, interaction.user.id, capability, current)

    @video.autocomplete("model")
    async def video_models(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        capability = (
            Capability.IMAGE_TO_VIDEO
            if getattr(interaction.namespace, "image", None) is not None
            else Capability.TEXT_TO_VIDEO
        )
        return model_choices(settings, interaction.user.id, capability, current)

    @client.tree.command(
        name="job", description="Retrieve an existing video job without resubmitting generation"
    )
    async def job(interaction: discord.Interaction, job_id: str) -> None:
        scope = await begin(interaction)
        try:
            artifact = await client.media.retrieve(
                scope, job_id, progress=lambda text: progress(interaction, text)
            )
            await send_artifact(
                interaction, artifact, private=scope.private, maximum=settings.attachment_bytes
            )
            await client.store.update_job(job_id, "delivered")
            await progress(interaction, f"Video job {job_id} delivered.")
        except asyncio.CancelledError:
            await progress(
                interaction, "Stopped waiting. Use /job to retrieve the existing video later."
            )

    @client.tree.command(
        name="cancel", description="Cancel outstanding requests in your current conversation"
    )
    async def cancel(interaction: discord.Interaction) -> None:
        scope = await begin(interaction)
        await client.service.gate.cancel(scope.key)
        await send_text(
            interaction,
            "Outstanding requests cancelled. Submitted provider jobs may continue and be billed.",
            private=scope.private,
        )

    @client.tree.command(
        name="reset", description="Delete your current conversation history and job mappings"
    )
    async def reset(interaction: discord.Interaction) -> None:
        scope = await begin(interaction)
        await client.service.reset(scope)
        await send_text(
            interaction,
            "Current conversation and job mappings deleted. Provider-side retention is separate.",
            private=scope.private,
        )

    @client.tree.command(
        name="delete", description="Delete both your private and public histories in this channel"
    )
    async def delete(interaction: discord.Interaction) -> None:
        scope = await begin(interaction)
        await client.service.reset(scope)
        await client.service.reset(replace(scope, private=not scope.private))
        await send_text(
            interaction,
            "Your private and public histories and job mappings in this channel were deleted.",
            private=scope.private,
        )

    @client.tree.command(name="switchpersona", description="Change this conversation's personality")
    async def switchpersona(interaction: discord.Interaction, persona: str) -> None:
        scope = await begin(interaction)
        await client.service.persona(scope, persona)
        await send_text(
            interaction,
            f"Selected persona {persona}. Retained text history is preserved.",
            private=scope.private,
        )

    async def visibility(interaction: discord.Interaction, private: bool) -> None:
        scope = await client.scope(interaction)
        await client.store.set_private(scope, private)
        await interaction.response.send_message(
            f"Future slash commands use your {'private' if private else 'public'} conversation. Each has separate history.",
            ephemeral=True,
        )

    @client.tree.command(
        name="private", description="Use your private conversation for future slash commands"
    )
    async def private(interaction: discord.Interaction) -> None:
        await visibility(interaction, True)

    @client.tree.command(
        name="public", description="Use your public conversation for future slash commands"
    )
    async def public(interaction: discord.Interaction) -> None:
        await visibility(interaction, False)

    @client.tree.command(
        name="replyall",
        description="Administrator: enable or disable automatic replies in this allowed channel",
    )
    async def replyall(interaction: discord.Interaction, enabled: bool) -> None:
        scope = await client.scope(interaction)
        if (
            scope.user_id not in settings.admin_user_ids
            or scope.channel_id not in settings.reply_channels
        ):
            raise BotError(
                "Only configured administrators can change auto-replies in allowed channels."
            )
        await client.store.set_reply(scope, enabled)
        await interaction.response.send_message(
            f"Automatic replies {'enabled' if enabled else 'disabled'} in this channel.",
            ephemeral=True,
        )

    @client.tree.command(name="help", description="Show bot commands and conversation behavior")
    async def help_command(interaction: discord.Interaction) -> None:
        await client.scope(interaction)
        await interaction.response.send_message(
            embed=help_embed(),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    return client


def run_discord_bot(settings: Settings, token: str) -> None:
    create_bot(settings).run(token, log_handler=None)
