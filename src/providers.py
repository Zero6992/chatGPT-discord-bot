"""Official REST translations and explicitly configured compatible chat servers."""

import json
from typing import Any
from urllib.parse import quote

import httpx

from src.config import Model
from src.domain import BotError, Capability, Completion, Message, Session


class HTTPTransport:
    def __init__(
        self, model: Model, timeout: float = 120, *, client: httpx.AsyncClient | None = None
    ):
        self.model = model
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10),
            trust_env=False,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    def headers(self) -> dict[str, str]:
        backend = self.model.backend
        key = backend.key()
        if backend.kind == "anthropic":
            return {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if backend.kind == "gemini":
            return {"x-goog-api-key": key}
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = self.model.backend.base_url + "/" + path.lstrip("/")
        try:
            async with self.client.stream(
                method, url, headers=self.headers(), **kwargs
            ) as response:
                if response.status_code == 429 and self.model.backend.kind == "openai":
                    await self.openai_limit_error(response)
                self.check_status(response.status_code)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 40 * 1024 * 1024:
                        raise BotError("Provider response exceeded the size limit.")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("expected object")
            return result
        except BotError:
            raise
        except httpx.TimeoutException:
            raise BotError(
                "Provider timed out; the request may have been billed. No automatic retry was made."
            ) from None
        except httpx.HTTPError:
            raise BotError("Provider connection failed; no automatic retry was made.") from None
        except (ValueError, UnicodeError):
            raise BotError("Provider returned malformed data.") from None

    @staticmethod
    async def openai_limit_error(response: httpx.Response) -> None:
        """Classify bounded error codes without exposing the provider's diagnostic text."""
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > 16384:
                return  # The caller still raises the generic 429 error.
        try:
            code = json.loads(content)["error"]["code"]
        except (ValueError, KeyError, TypeError, UnicodeError):
            return
        messages = {
            "billing_not_active": "OpenAI API billing is not active. The administrator must activate API billing before retrying.",
            "credit_balance_exhausted": "OpenAI API prepaid credits are exhausted. Check API billing before retrying.",
            "organization_spend_limit_exceeded": "OpenAI API organization spend limit reached. Check organization limits before retrying.",
            "project_spend_limit_exceeded": "OpenAI API project spend limit reached. Check project limits before retrying.",
            "organization_usage_limit_exceeded": "OpenAI API organization usage limit reached. Check approved usage limits before retrying.",
            "insufficient_quota": "OpenAI API quota is unavailable. Check API billing and account limits before retrying.",
        }
        if isinstance(code, str) and code in messages:
            raise BotError(messages[code])

    @staticmethod
    def check_status(status: int) -> None:
        if status in {401, 403}:
            raise BotError("Provider authentication or access failed; contact the administrator.")
        if status == 429:
            raise BotError(
                "Provider quota or rate limit reached; check account billing and limits."
            )
        if not 200 <= status < 300:
            raise BotError("Provider rejected or failed the request; no automatic retry was made.")

    async def close(self) -> None:
        await self.client.aclose()


def text_result(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BotError("Provider returned no text; it may have refused the request.")
    if len(value.encode()) > 128000:
        raise BotError("Provider text exceeded the response limit.")
    return value


class APIProvider:
    def __init__(self, model: Model, http: HTTPTransport | None = None):
        self.model = model
        self.http = http or HTTPTransport(model)

    async def complete(
        self,
        messages: list[Message],
        session: Session | None = None,
        *,
        conversation_id: str = "",
    ) -> Completion:
        self.model.require(Capability.CHAT)
        kind = self.model.backend.kind
        params = self.model.parameters
        history = [{"role": m.role, "content": m.content} for m in messages]
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [m for m in history if m["role"] != "system"]
        payload: dict[str, Any] = {"model": self.model.model}
        try:
            if kind in {"openai", "xai"}:
                payload.update(input=history, store=False)
                if "max_output_tokens" in params:
                    payload["max_output_tokens"] = params["max_output_tokens"]
                if "reasoning_effort" in params:
                    payload["reasoning"] = {"effort": params["reasoning_effort"]}
                result = await self.http.request("POST", "responses", json=payload)
                if result.get("status") != "completed":
                    raise BotError(
                        "Provider did not complete the response; history was not changed."
                    )
                text = "\n".join(
                    part["text"]
                    for item in result["output"]
                    if item.get("type") == "message"
                    for part in item["content"]
                    if part.get("type") == "output_text"
                )
            elif kind == "anthropic":
                payload.update(messages=turns, max_tokens=params.get("max_output_tokens", 1024))
                if system:
                    payload["system"] = system
                result = await self.http.request("POST", "messages", json=payload)
                if result.get("stop_reason") not in {"end_turn", "stop_sequence"}:
                    raise BotError(
                        "Provider response was incomplete; increase the output budget if needed."
                    )
                text = "\n".join(p["text"] for p in result["content"] if p.get("type") == "text")
            elif kind == "gemini":
                payload = {
                    "contents": [
                        {
                            "role": "model" if m["role"] == "assistant" else "user",
                            "parts": [{"text": m["content"]}],
                        }
                        for m in turns
                    ]
                }
                if system:
                    payload["systemInstruction"] = {"parts": [{"text": system}]}
                fields = {
                    "max_output_tokens": "maxOutputTokens",
                    "temperature": "temperature",
                    "top_p": "topP",
                }
                if params:
                    payload["generationConfig"] = {fields[k]: v for k, v in params.items()}
                result = await self.http.request(
                    "POST",
                    f"models/{quote(self.model.model, safe='')}:generateContent",
                    json=payload,
                )
                candidate = result["candidates"][0]
                if candidate.get("finishReason") != "STOP":
                    raise BotError(
                        "Provider did not finish a text response; history was not changed."
                    )
                text = "\n".join(
                    p["text"]
                    for p in candidate["content"]["parts"]
                    if "text" in p and not p.get("thought")
                )
            elif kind in {"deepseek", "compatible"}:
                payload.update(messages=history, stream=False)
                for key, value in params.items():
                    if key == "thinking":
                        payload["thinking"] = {"type": value}
                    else:
                        payload["max_tokens" if key == "max_output_tokens" else key] = value
                result = await self.http.request("POST", "chat/completions", json=payload)
                choice = result["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise BotError(
                        "Provider response was incomplete or requested unsupported tools."
                    )
                text = choice["message"]["content"]
            else:
                raise BotError("This backend cannot use the HTTP chat adapter.")
            return Completion(text_result(text))
        except (KeyError, IndexError, TypeError, AttributeError):
            raise BotError("Provider returned an unexpected response structure.") from None

    async def close(self) -> None:
        await self.http.close()
