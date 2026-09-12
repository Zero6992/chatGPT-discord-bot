"""Owner-only account operations shared by Discord commands; no OAuth client."""

import asyncio
from typing import Any

from src.cli import DockerRunner
from src.cli_accounts import DEVICE_KINDS, ChallengeCallback
from src.config import Model, Settings
from src.domain import BotError


class CLIAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.runners = {
            model.backend.name: DockerRunner(
                model, settings.request_timeout, str(settings.database.resolve())
            )
            for model in settings.models.values()
            if model.backend.auth == "account"
        }
        self.active: dict[str, tuple[str, asyncio.Task[Any]]] = {}
        self.closed = False

    def model(self, alias: str, owner: int) -> Model:
        model = self.settings.models.get(alias)
        if (
            model is None
            or model.backend.auth != "account"
            or model.backend.owner_id != owner
            or (self.settings.allowed_user_ids and owner not in self.settings.allowed_user_ids)
        ):
            raise BotError("Choose an account CLI alias owned by you and permitted by the bot.")
        return model

    async def execute(
        self, action: str, alias: str, owner: int, on_challenge: ChallengeCallback
    ) -> str:
        model = self.model(alias, owner)
        key = model.backend.name
        if self.closed or action not in {"login", "status", "logout", "cancel"}:
            raise BotError("CLI account operation is unavailable.")
        pending = self.active.get(key)
        if action == "cancel":
            if not pending:
                return "No account operation is pending."
            if pending[1] is asyncio.current_task():
                raise BotError("An account operation cannot cancel itself.")
            if not pending[1].cancelling():
                pending[1].cancel()
            await asyncio.gather(pending[1], return_exceptions=True)
            return "Pending account operation cancelled. Run login again if needed."
        if pending:
            if action == "status":
                return f"Account {pending[0]} is in progress. Use /cli_auth cancel to cancel it."
            raise BotError(
                "An account operation is already pending; use /cli_auth status or cancel."
            )
        if action == "login" and model.backend.kind not in DEVICE_KINDS:
            return (
                "Discord login is not implemented for this provider. On the bot host run "
                f"`python -m src.cli_accounts login {alias}` with the bot's configuration. "
                "Complete authorization in that terminal; do not paste codes or tokens into Discord. "
                "Use /cli_auth status here afterwards."
            )
        if len(self.active) >= min(self.settings.concurrency, 4):
            raise BotError("Account administration is busy; try again after an operation finishes.")
        task = asyncio.current_task()
        assert task is not None
        self.active[key] = (action, task)
        try:
            async with asyncio.timeout(600 if action == "login" else 90):
                result = await self.runners[key].account_action(
                    action, on_challenge=on_challenge if action == "login" else None
                )
            if action == "status":
                return (
                    "Local CLI login is configured. Subscription/model access is not verified."
                    if result["configured"]
                    else "CLI account is not signed in. Use /cli_auth login."
                )
            if action == "logout":
                return "Native CLI signed out. Bot conversation history is preserved."
            return (
                "Native CLI login saved. Bot history is preserved; native context will be rebuilt. "
                "Subscription/model access still needs a chat test."
            )
        except TimeoutError:
            raise BotError(
                "CLI account operation timed out; no automatic retry was made."
            ) from None
        finally:
            self.active.pop(key, None)

    async def close(self) -> None:
        self.closed = True
        tasks = [task for _, task in self.active.values()]
        for task in tasks:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
