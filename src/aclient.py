"""Discord lifecycle and dependency wiring. No import-time clients or network calls."""

import asyncio
from dataclasses import replace
from typing import Any

import discord
from discord import app_commands

from src.art import MediaProvider, MediaService
from src.cli import CLIProvider, DockerRunner
from src.cli_auth import CLIAuth
from src.config import CLI_KINDS, Settings
from src.domain import BotError, Capability, ChatProvider
from src.log import logger
from src.providers import APIProvider, HTTPTransport
from src.search import ImageSearchProvider, ImageSearchService
from src.service import ConversationService
from src.storage import Scope, Store
from utils.message_utils import send_text


class DiscordClient(discord.Client):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.message_content = bool(settings.reply_channels)
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.settings = settings
        self.cli_auth = CLIAuth(settings)
        self.tree = app_commands.CommandTree(self)
        self.store = Store(settings.database)
        self.service: ConversationService
        self.media: MediaService
        self.search: ImageSearchService
        self.maintenance: asyncio.Task[None] | None = None
        self.initialized = False

    async def setup_hook(self) -> None:
        await self.store.open()
        providers: dict[str, ChatProvider] = {}
        media = {}
        searches = {}
        for name, model in self.settings.models.items():
            if Capability.IMAGE_SEARCH in model.capabilities:
                searches[name] = ImageSearchProvider(
                    model, HTTPTransport(model, self.settings.request_timeout)
                )
            elif Capability.CHAT in model.capabilities:
                if model.backend.kind in CLI_KINDS:
                    providers[name] = CLIProvider(
                        model,
                        DockerRunner(
                            model,
                            self.settings.request_timeout,
                            str(self.settings.database.resolve()),
                        ),
                    )
                else:
                    providers[name] = APIProvider(
                        model, HTTPTransport(model, self.settings.request_timeout)
                    )
            else:
                media[name] = MediaProvider(
                    model,
                    self.settings.attachment_bytes,
                    HTTPTransport(model, self.settings.media_timeout),
                )
        self.service = ConversationService(self.settings, self.store, providers)
        self.media = MediaService(self.settings, self.store, self.service, media)
        self.search = ImageSearchService(self.settings, self.service, searches)
        self.initialized = True
        await self.prune_state()
        self.maintenance = asyncio.create_task(self._maintenance())
        await self.tree.sync()

    async def prune_state(self) -> None:
        await self.store.prune(self.settings.retention_days)
        retained = await self.store.conversation_keys() | set(self.service.gate.tasks)
        for provider in self.service.providers.values():
            prune = getattr(provider, "prune_state", None)
            if prune:
                try:
                    await prune(retained)
                except BotError:
                    logger.error(
                        "CLI retention cleanup is pending; check the isolated runtime. It will be retried next maintenance cycle."
                    )

    async def _maintenance(self) -> None:
        while True:
            await asyncio.sleep(3600)
            await self.prune_state()

    async def scope(self, target: Any, *, private: bool | None = None) -> Scope:
        if self.user is None:
            raise BotError("Bot is not ready yet.")
        owner = target.user if hasattr(target, "user") else target.author
        if self.settings.allowed_user_ids and owner.id not in self.settings.allowed_user_ids:
            raise BotError("This bot is restricted to configured users.")
        channel = target.channel
        if channel is None:
            raise BotError("This Discord channel is unavailable.")
        scope = Scope(self.user.id, target.guild.id if target.guild else 0, channel.id, owner.id)
        return replace(
            scope, private=await self.store.private(scope) if private is None else private
        )

    async def on_message(self, message: discord.Message) -> None:
        if (
            not self.initialized
            or message.author.bot
            or message.webhook_id
            or message.channel.id not in self.settings.reply_channels
        ):
            return
        if (
            self.settings.allowed_user_ids
            and message.author.id not in self.settings.allowed_user_ids
        ):
            return
        scope = await self.scope(message, private=False)
        if not await self.store.reply_enabled(scope):
            return
        try:
            async with message.channel.typing():
                result = await self.service.chat(scope, message.content)
            text = result.text + (f"\n\n{result.notice}" if result.notice else "")
            await send_text(message, text, private=False)
        except BotError as error:
            await send_text(message, str(error), private=False)
        except asyncio.CancelledError:
            await send_text(
                message, "Request cancelled. Provider work may still be billed.", private=False
            )
        except Exception:
            await send_text(
                message, "The request failed. Contact the administrator.", private=False
            )

    async def close(self) -> None:
        await self.cli_auth.close()
        if self.maintenance:
            self.maintenance.cancel()
            await asyncio.gather(self.maintenance, return_exceptions=True)
        if self.initialized:
            await self.service.close()
            await self.media.close()
            await self.search.close()
            await self.store.close()
            self.initialized = False
        await super().close()
