"""Small shared contracts; no Discord or SDK dependencies."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class BotError(Exception):
    """Only deliberately safe messages may cross the Discord boundary."""


class Capability(StrEnum):
    CHAT = "chat"
    IMAGE_SEARCH = "image-search"
    TEXT_TO_IMAGE = "text-to-image"
    IMAGE_TO_IMAGE = "image-to-image"
    TEXT_TO_VIDEO = "text-to-video"
    IMAGE_TO_VIDEO = "image-to-video"


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class Session:
    id: str
    fingerprint: str


@dataclass(frozen=True)
class Completion:
    text: str
    session_id: str | None = None
    notice: str | None = None


class ChatProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        session: Session | None = None,
        *,
        conversation_id: str = "",
    ) -> Completion: ...

    async def close(self) -> None: ...
