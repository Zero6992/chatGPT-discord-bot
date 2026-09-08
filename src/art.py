"""Official image/video APIs; no retries of generation submissions."""

import asyncio
import base64
import binascii
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx

from src.config import Model, Settings
from src.domain import BotError, Capability
from src.providers import HTTPTransport
from src.service import ConversationService
from src.storage import Scope, Store


class MediaJobFailed(BotError):
    """A provider reported a terminal failure; do not keep polling it."""


@dataclass(frozen=True)
class Artifact:
    data: bytes
    filename: str
    content_type: str


def input_image(data: bytes, maximum: int) -> str:
    if len(data) > maximum:
        raise BotError("Input image exceeds the configured attachment limit.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise BotError("Provide a PNG or JPEG image attachment.")


class MediaProvider:
    def __init__(self, model: Model, maximum: int, http: HTTPTransport | None = None):
        self.model = model
        self.maximum = maximum
        self.http = http or HTTPTransport(model)

    async def image(self, prompt: str, source: bytes | None) -> Artifact:
        self.model.require(
            Capability.IMAGE_TO_IMAGE if source is not None else Capability.TEXT_TO_IMAGE
        )
        fields = {"model": self.model.model, "prompt": prompt, "n": 1, **self.model.parameters}
        if source is None:
            result = await self.http.request("POST", "images/generations", json=fields)
        else:
            mime = input_image(source, self.maximum)
            result = await self.http.request(
                "POST",
                "images/edits",
                data={k: str(v) for k, v in fields.items()},
                files={
                    "image": ("input.png" if mime == "image/png" else "input.jpg", source, mime)
                },
            )
        try:
            encoded = result["data"][0]["b64_json"]
            if not isinstance(encoded, str) or len(encoded) > (self.maximum + 2) // 3 * 4:
                raise BotError("Generated image exceeds the attachment limit.")
            data = base64.b64decode(encoded, validate=True)
            mime = input_image(data, self.maximum)
            return Artifact(data, "generated.png" if mime == "image/png" else "generated.jpg", mime)
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
            raise BotError("Provider did not return a valid image artifact.") from None

    async def submit_video(self, prompt: str, source: bytes | None) -> str:
        self.model.require(
            Capability.IMAGE_TO_VIDEO if source is not None else Capability.TEXT_TO_VIDEO
        )
        if self.model.backend.kind == "xai":
            if source is not None:
                raise BotError("This xAI adapter implements text-to-video only.")
            params = self.model.parameters
            result = await self.http.request(
                "POST",
                "videos/generations",
                json={
                    "model": self.model.model,
                    "prompt": prompt,
                    "duration": params.get("duration_seconds", 1),
                    "aspect_ratio": params.get("aspect_ratio", "16:9"),
                    "resolution": params.get("resolution", "480p"),
                },
            )
            return self.operation(result.get("request_id"))
        instance: dict[str, Any] = {"prompt": prompt}
        if source is not None:
            mime = input_image(source, self.maximum)
            instance["image"] = {
                "bytesBase64Encoded": base64.b64encode(source).decode(),
                "mimeType": mime,
            }
        params = self.model.parameters
        payload = {
            "instances": [instance],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": params.get("aspect_ratio", "16:9"),
                "durationSeconds": params.get("duration_seconds", 8),
            },
        }
        result = await self.http.request(
            "POST", f"models/{quote(self.model.model, safe='')}:predictLongRunning", json=payload
        )
        return self.operation(result.get("name"))

    def operation(self, value: Any) -> str:
        if self.model.backend.kind == "xai":
            try:
                if not isinstance(value, str) or str(uuid.UUID(value)) != value:
                    raise ValueError("request id")
            except (ValueError, TypeError, AttributeError):
                raise BotError("Provider returned an invalid video request ID.") from None
            return value
        if not isinstance(value, str) or not re.fullmatch(
            r"(?:models/[A-Za-z0-9._-]+/)?operations/[A-Za-z0-9._-]+", value
        ):
            raise BotError("Provider returned an invalid video operation ID.")
        return value

    async def poll_video(self, operation: str) -> Artifact | None:
        if self.model.backend.kind == "xai":
            result = await self.http.request("GET", "videos/" + self.operation(operation))
            status = result.get("status")
            if not isinstance(status, str):
                raise BotError("Invalid xAI video job status.")
            if status in {"failed", "expired"} or result.get("error"):
                raise MediaJobFailed("Video generation failed or expired at xAI.")
            if status == "pending":
                return None
            if status != "done":
                raise BotError("Invalid xAI video job status.")
            video = result.get("video")
            if not isinstance(video, dict) or video.get("respect_moderation") is not True:
                raise MediaJobFailed("xAI video was filtered or did not return an artifact.")
            return await self.download(video.get("url", ""))
        result = await self.http.request("GET", self.operation(operation))
        if result.get("error"):
            raise MediaJobFailed("Video generation failed at the provider.")
        if result.get("done") is not True:
            if result.get("done") not in (None, False):
                raise BotError("Invalid video job status.")
            return None
        try:
            uri = result["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
        except (KeyError, IndexError, TypeError):
            raise MediaJobFailed(
                "Video generation returned no artifact; it may have been filtered."
            ) from None
        return await self.download(uri)

    async def download(self, uri: str) -> Artifact:
        # Credentials go only to the documented API origin, never to signed redirect targets.
        if not isinstance(uri, str):
            raise BotError("Provider returned an invalid artifact URL.")
        for _ in range(4):
            try:
                parsed = urlsplit(uri)
                port = parsed.port
            except ValueError:
                raise BotError("Provider returned an invalid artifact URL.") from None
            host = parsed.hostname or ""
            allowed = (
                host == "vidgen.x.ai"
                if self.model.backend.kind == "xai"
                else (
                    host in {"generativelanguage.googleapis.com", "storage.googleapis.com"}
                    or host.endswith(".googleusercontent.com")
                )
            )
            if (
                parsed.scheme != "https"
                or parsed.username
                or parsed.password
                or port not in {None, 443}
                or not allowed
            ):
                raise BotError("Provider artifact URL is outside the allowed download origins.")
            headers = self.http.headers() if host == "generativelanguage.googleapis.com" else {}
            try:
                async with self.http.client.stream("GET", uri, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if "location" not in response.headers:
                            raise BotError("Invalid artifact redirect.")
                        uri = urljoin(uri, response.headers["location"])
                        continue
                    HTTPTransport.check_status(response.status_code)
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > self.maximum:
                            raise BotError(
                                "Generated video exceeds the attachment limit; ask the administrator about a shorter output."
                            )
                    if len(content) < 12 or content[4:8] != b"ftyp":
                        raise BotError("Provider returned an invalid MP4 artifact.")
                    return Artifact(bytes(content), "generated.mp4", "video/mp4")
            except httpx.HTTPError:
                raise BotError(
                    "Artifact download failed; use /job to retrieve the existing video again."
                ) from None
        raise BotError("Too many artifact redirects.")

    async def close(self) -> None:
        await self.http.close()


Progress = Callable[[str], Awaitable[None]]


class MediaService:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        conversations: ConversationService,
        providers: dict[str, MediaProvider],
    ):
        self.settings, self.store = settings, store
        self.conversations, self.providers = conversations, providers

    async def generate(
        self,
        scope: Scope,
        name: str,
        prompt: str,
        job_id: str,
        *,
        video: bool = False,
        source: bytes | None = None,
        load_source: Callable[[], Awaitable[bytes]] | None = None,
        progress: Progress,
    ) -> Artifact:
        prompt = prompt.strip()
        if not prompt or len(prompt) > self.settings.input_chars:
            raise BotError("Provide a nonempty prompt within the configured length limit.")
        editing = source is not None or load_source is not None
        capability = (
            (Capability.IMAGE_TO_VIDEO if editing else Capability.TEXT_TO_VIDEO)
            if video
            else (Capability.IMAGE_TO_IMAGE if editing else Capability.TEXT_TO_IMAGE)
        )
        model = self.conversations.model(name, scope, capability)
        if source is not None:
            input_image(source, self.settings.attachment_bytes)
        try:
            async with (
                asyncio.timeout(self.settings.media_timeout),
                self.conversations.gate.hold(scope.key),
            ):
                fingerprint = model.fingerprint()
                if load_source is not None:
                    source = await load_source()
                    input_image(source, self.settings.attachment_bytes)
                if not await self.store.create_job(
                    job_id, scope, name, fingerprint, self.settings.max_jobs
                ):
                    raise BotError(
                        "This request already has a media job. Use /job; it will not be submitted twice."
                    )
                await progress(f"Media job {job_id} is submitting. Use /cancel to stop waiting.")
                try:
                    provider = self.providers[name]
                    if video:
                        operation = await provider.submit_video(prompt, source)
                        await self.store.update_job(job_id, "pending", operation)
                        artifact = await self._poll(job_id, provider, operation, progress)
                    else:
                        artifact = await provider.image(prompt, source)
                    await self.store.update_job(job_id, "ready")
                    return artifact
                except MediaJobFailed:
                    await self.store.update_job(job_id, "failed")
                    raise
                except BaseException:
                    job = await self.store.job(job_id, scope)
                    await self.store.update_job(
                        job_id, "pending" if job["operation"] else "unknown"
                    )
                    raise
        except TimeoutError:
            raise BotError(
                "Media wait timed out. Use /job for a submitted video; no generation was retried."
            ) from None

    async def _poll(
        self, job_id: str, provider: MediaProvider, operation: str, progress: Progress
    ) -> Artifact:
        await progress(
            f"Video job {job_id} is processing. Use /job after a restart, or /cancel to stop waiting."
        )
        while True:
            artifact = await provider.poll_video(operation)
            if artifact is not None:
                return artifact
            await asyncio.sleep(self.settings.poll_interval)

    async def retrieve(self, scope: Scope, job_id: str, *, progress: Progress) -> Artifact:
        try:
            async with (
                asyncio.timeout(self.settings.media_timeout),
                self.conversations.gate.hold(scope.key),
            ):
                job = await self.store.job(job_id, scope)
                configured = self.settings.models.get(job["model"])
                capability = (
                    Capability.TEXT_TO_VIDEO
                    if configured and Capability.TEXT_TO_VIDEO in configured.capabilities
                    else Capability.IMAGE_TO_VIDEO
                )
                model = self.conversations.model(job["model"], scope, capability)
                if job["state"] == "failed":
                    raise BotError(
                        "The provider marked this video job as failed. It will not be resubmitted."
                    )
                if model.fingerprint() != job["fingerprint"]:
                    raise BotError(
                        "The job's provider configuration or account changed; restore it to retrieve this job."
                    )
                if not job["operation"]:
                    raise BotError(
                        "This job has no recoverable video operation. Check the provider account before submitting another paid request."
                    )
                try:
                    artifact = await self._poll(
                        job_id, self.providers[model.name], job["operation"], progress
                    )
                except MediaJobFailed:
                    await self.store.update_job(job_id, "failed")
                    raise
                await self.store.update_job(job_id, "ready")
                return artifact
        except TimeoutError:
            raise BotError(
                "Video is still unavailable; use /job again later. No generation was retried."
            ) from None

    async def close(self) -> None:
        for provider in self.providers.values():
            await provider.close()
