"""Conversation routing, context budgets and bounded scheduling."""

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext

from src import personas
from src.config import CLI_KINDS, Model, Settings
from src.domain import BotError, Capability, ChatProvider, Completion, Message, Session
from src.storage import Conversation, Scope, Store


class Gate:
    def __init__(self, concurrency: int, maximum: int):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.maximum = maximum
        self.pending = 0
        self.locks: dict[str, tuple[asyncio.Lock, int]] = {}
        self.tasks: dict[str, set[asyncio.Task[object]]] = {}

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[None]:
        if self.pending >= self.maximum:
            raise BotError("The bot is busy; try again shortly.")
        self.pending += 1
        lock, count = self.locks.get(key, (asyncio.Lock(), 0))
        self.locks[key] = lock, count + 1
        task = asyncio.current_task()
        assert task is not None
        self.tasks.setdefault(key, set()).add(task)
        try:
            async with lock, self.semaphore:
                yield
        finally:
            self.pending -= 1
            self.tasks[key].discard(task)
            if not self.tasks[key]:
                del self.tasks[key]
            _, count = self.locks[key]
            if count == 1:
                del self.locks[key]
            else:
                self.locks[key] = lock, count - 1

    async def cancel(self, key: str | None = None) -> None:
        tasks = set().union(*(self.tasks.values() if key is None else [self.tasks.get(key, set())]))
        tasks.discard(asyncio.current_task())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def budget_context(system: str, turns: list[Message], prompt: str, budget: int) -> list[Message]:
    def cost(message: Message) -> int:
        return len(message.content.encode()) + len(message.role) + 16

    first, last = Message("system", system), Message("user", prompt)
    used = cost(first) + cost(last)
    if used > budget:
        raise BotError("The prompt and system instructions exceed the configured context budget.")
    recent: list[Message] = []
    # Preserve complete pairs. Never send an orphan assistant response.
    for index in range(len(turns) - 2, -1, -2):
        pair = turns[index : index + 2]
        size = sum(cost(message) for message in pair)
        if used + size > budget:
            break
        recent[0:0] = pair
        used += size
    return [first, *recent, last]


def context_fingerprint(model: Model, messages: list[Message]) -> str:
    content = json.dumps([m.__dict__ for m in messages], ensure_ascii=False)
    return hashlib.sha256((model.fingerprint() + content).encode()).hexdigest()


class ConversationService:
    def __init__(self, settings: Settings, store: Store, providers: dict[str, ChatProvider]):
        self.settings = settings
        self.store = store
        self.providers = providers
        self.gate = Gate(settings.concurrency, settings.max_pending)

    def model(self, name: str, scope: Scope, capability: Capability = Capability.CHAT) -> Model:
        if self.settings.allowed_user_ids and scope.user_id not in self.settings.allowed_user_ids:
            raise BotError("This bot is restricted to configured users.")
        if name not in self.settings.models:
            raise BotError("Model alias is unavailable; use /models to select a configured model.")
        model = self.settings.models[name]
        model.require(capability)
        if model.backend.kind in CLI_KINDS and scope.user_id != model.backend.owner_id:
            raise BotError("This CLI backend is restricted to its configured account owner.")
        return model

    async def conversation(self, scope: Scope) -> Conversation:
        return await self.store.get(
            scope,
            self.settings.default_model,
            self.settings.max_conversations,
            self.settings.retention_days,
        )

    def prompt(self, persona: str, scope: Scope) -> str:
        if persona not in personas.PERSONAS:
            raise BotError("Unknown persona.")
        if (
            personas.is_jailbreak_persona(persona)
            and scope.user_id not in self.settings.admin_user_ids
        ):
            raise BotError("This persona requires administrator access.")
        return self.settings.system_prompt + "\n\n" + personas.PERSONAS[persona]

    async def chat(self, scope: Scope, prompt: str) -> Completion:
        prompt = prompt.replace("\x00", "").strip()
        if not prompt or len(prompt) > self.settings.input_chars:
            raise BotError(
                f"Provide a prompt between 1 and {self.settings.input_chars} characters."
            )
        try:
            async with asyncio.timeout(self.settings.request_timeout), self.gate.hold(scope.key):
                conversation = await self.conversation(scope)
                model = self.model(conversation.model, scope)
                provider = self.providers[model.name]
                guard = getattr(provider, "auth_guard", None)
                async with guard() if guard else nullcontext():
                    messages = budget_context(
                        self.prompt(conversation.persona, scope),
                        conversation.turns,
                        prompt,
                        self.settings.context_bytes,
                    )
                    expected = context_fingerprint(model, messages[:-1])
                    session = conversation.session
                    notice = None
                    if session and session.fingerprint != expected:
                        session = None
                        notice = "Context was reconstructed from retained bot history."
                    # Persist uncertainty before external work, so restart never reuses a partially advanced session.
                    await self.store.invalidate_session(scope.key)
                    result = await self.providers[model.name].complete(
                        messages, session, conversation_id=scope.key
                    )
                    conversation.turns.extend(
                        [Message("user", prompt), Message("assistant", result.text)]
                    )
                    conversation.turns = conversation.turns[-self.settings.max_turns * 2 :]
                    conversation.session = (
                        Session(
                            result.session_id,
                            context_fingerprint(
                                model, [*messages, Message("assistant", result.text)]
                            ),
                        )
                        if result.session_id
                        else None
                    )
                    await self.store.save(conversation)
                    return Completion(result.text, notice=result.notice or notice)
        except TimeoutError:
            raise BotError(
                "Request timed out; history was preserved. No automatic retry was made."
            ) from None

    async def switch(self, scope: Scope, name: str) -> None:
        self.model(name, scope)
        async with self.gate.hold(scope.key):
            conversation = await self.conversation(scope)
            conversation.model = name
            conversation.session = None
            await self.store.save(conversation)

    async def persona(self, scope: Scope, name: str) -> None:
        self.prompt(name, scope)  # Validate before changing anything.
        async with self.gate.hold(scope.key):
            conversation = await self.conversation(scope)
            conversation.persona = name
            conversation.session = None
            await self.store.save(conversation)

    async def reset(self, scope: Scope) -> None:
        await self.gate.cancel(scope.key)
        async with self.gate.hold(scope.key):
            await self.store.delete(scope)
            await self.delete_cli_state(scope.key)

    async def delete_cli_state(self, key: str) -> None:
        # Optional method belongs only to isolated native-session providers.
        for provider in self.providers.values():
            delete = getattr(provider, "delete_state", None)
            if delete is not None:
                await delete(key)

    async def close(self) -> None:
        await self.gate.cancel()
        for provider in self.providers.values():
            await provider.close()
