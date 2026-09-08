"""Explicit xAI image search; public image URLs are rendered by Discord's proxy."""

import asyncio
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from src.config import Model, Settings
from src.domain import BotError, Capability
from src.providers import HTTPTransport, text_result
from src.service import ConversationService
from src.storage import Scope


@dataclass(frozen=True)
class SearchImage:
    title: str
    url: str


def public_image_url(value: str) -> bool:
    """Never fetch these URLs on the bot host, even after this lexical validation."""
    if len(value) > 2048 or re.search(r"[\s<>\\\x00-\x1f\x7f]", value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
            or "." not in host
            or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
        ):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False
    except ValueError:
        return False


class ImageSearchProvider:
    def __init__(self, model: Model, http: HTTPTransport | None = None):
        self.model = model
        self.http = http or HTTPTransport(model)

    async def search(self, query: str) -> list[SearchImage]:
        self.model.require(Capability.IMAGE_SEARCH)
        if self.model.backend.kind != "xai":
            raise BotError("This backend does not implement image search.")
        result = await self.http.request(
            "POST",
            "responses",
            json={
                "model": self.model.model,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Search for images matching the user's query using image search. "
                            "Return at most three relevant images from search results, each as "
                            "![short descriptive title](https://direct-image-url). Do not invent image URLs. "
                            "Use one image search if sufficient. Do not generate images."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "store": False,
                "tools": [{"type": "web_search", "enable_image_search": True}],
                "parallel_tool_calls": False,
                "max_turns": self.model.parameters.get("max_turns", 2),
                "max_output_tokens": self.model.parameters.get("max_output_tokens", 2048),
            },
        )
        try:
            if result.get("status") != "completed":
                raise BotError("Image search did not finish. No automatic retry was made.")
            output = result["output"]
            if any(
                item.get("type") == "web_search_call" and item.get("status") == "failed"
                for item in output
            ):
                raise BotError(
                    "The provider's image-search tool failed. No automatic retry was made."
                )
            if not any(
                item.get("type") == "web_search_call" and item.get("status") == "completed"
                for item in output
            ):
                raise BotError(
                    "The provider did not confirm a completed search; no images were delivered."
                )
            text = text_result(
                "\n".join(
                    part["text"]
                    for item in output
                    if item.get("type") == "message"
                    for part in item["content"]
                    if part.get("type") == "output_text"
                )
            )
        except (KeyError, TypeError, AttributeError):
            raise BotError("Provider returned malformed image-search results.") from None
        images: list[SearchImage] = []
        seen = set()
        for title, url in re.findall(r"!\[([^\]\n]{0,256})\]\((https://[^\s<>]+?)\)", text):
            if public_image_url(url) and url not in seen:
                images.append(SearchImage(title or "Search result", url))
                seen.add(url)
                if len(images) == 3:
                    break
        if not images:
            raise BotError("Search returned no usable public image URLs. No images were generated.")
        return images

    async def close(self) -> None:
        await self.http.close()


class ImageSearchService:
    def __init__(
        self,
        settings: Settings,
        conversations: ConversationService,
        providers: dict[str, ImageSearchProvider],
    ):
        self.settings, self.conversations, self.providers = settings, conversations, providers

    async def search(self, scope: Scope, name: str, query: str) -> list[SearchImage]:
        query = query.strip()
        if not query or len(query) > self.settings.input_chars:
            raise BotError("Provide a nonempty image query within the configured length limit.")
        self.conversations.model(name, scope, Capability.IMAGE_SEARCH)
        try:
            async with (
                asyncio.timeout(self.settings.request_timeout),
                self.conversations.gate.hold(scope.key),
            ):
                return await self.providers[name].search(query)
        except TimeoutError:
            raise BotError("Image search timed out; no automatic retry was made.") from None

    async def close(self) -> None:
        for provider in self.providers.values():
            await provider.close()
