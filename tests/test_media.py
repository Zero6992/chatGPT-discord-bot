import asyncio
import base64
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from src.art import MediaProvider, MediaService
from src.config import OFFICIAL_URLS, Backend, Model
from src.domain import BotError, Capability
from src.providers import HTTPTransport
from src.storage import Scope

SCOPE = Scope(1, 2, 3, 4)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)
MP4 = (Path(__file__).parent / "fixtures/tiny.mp4").read_bytes()
OPERATION = "models/veo-3.1-generate-preview/operations/job-123"
URI = "https://generativelanguage.googleapis.com/v1beta/files/video:download?alt=media"
DONE = {
    "name": OPERATION,
    "done": True,
    "response": {"generateVideoResponse": {"generatedSamples": [{"video": {"uri": URI}}]}},
}


def make_provider(kind, handler, monkeypatch, maximum=100000):
    monkeypatch.setenv("MEDIA_KEY", "media-test-secret")
    caps = (
        {Capability.TEXT_TO_IMAGE, Capability.IMAGE_TO_IMAGE}
        if kind == "openai"
        else (
            {Capability.TEXT_TO_VIDEO}
            if kind == "xai"
            else {Capability.TEXT_TO_VIDEO, Capability.IMAGE_TO_VIDEO}
        )
    )
    backend = Backend(
        kind,
        kind,
        OFFICIAL_URLS[kind],
        "MEDIA_KEY",
    )
    model = Model(
        "media",
        backend,
        {
            "openai": "gpt-image-2",
            "gemini": "veo-3.1-generate-preview",
            "xai": "grok-imagine-video",
        }[kind],
        frozenset(caps),
    )
    return MediaProvider(
        model,
        maximum,
        HTTPTransport(model, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )


@pytest.mark.parametrize("source", [None, PNG])
async def test_image_generation_and_edit_bytes(source, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if source:
            assert request.url.path == "/v1/images/edits"
            assert b"image/png" in request.content and PNG in request.content
            assert b"gpt-image-2" in request.content
        else:
            assert request.url.path == "/v1/images/generations"
            assert json.loads(request.content)["prompt"] == "a landscape"
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})

    provider = make_provider("openai", handler, monkeypatch)
    artifact = await provider.image("a landscape", source)
    assert artifact.data == PNG and artifact.filename == "generated.png"
    assert len(calls) == 1
    await provider.close()


@pytest.mark.parametrize("source", [None, PNG])
async def test_video_submission_polling_and_authenticated_artifact(source, monkeypatch):
    methods = []

    def handler(request):
        methods.append((request.method, request.url.path))
        assert request.headers["x-goog-api-key"] == "media-test-secret"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["instances"][0]["prompt"] == "a landscape"
            if source:
                assert base64.b64decode(body["instances"][0]["image"]["bytesBase64Encoded"]) == PNG
            return httpx.Response(200, json={"name": OPERATION})
        if request.url.path.endswith(":download"):
            return httpx.Response(200, content=MP4, headers={"Content-Type": "video/mp4"})
        return httpx.Response(200, json=DONE)

    provider = make_provider("gemini", handler, monkeypatch)
    operation = await provider.submit_video("a landscape", source)
    artifact = await provider.poll_video(operation)
    assert artifact.data == MP4 and artifact.filename == "generated.mp4"
    assert [method for method, _ in methods] == ["POST", "GET", "GET"]
    await provider.close()


async def test_media_job_duplicate_and_restart_recovery(service, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"name": OPERATION})
        if request.url.path.endswith(":download"):
            return httpx.Response(200, content=MP4)
        return httpx.Response(200, json=DONE)

    provider = make_provider("gemini", handler, monkeypatch)
    service.settings.models["media"] = provider.model
    media = MediaService(service.settings, service.store, service, {"media": provider})
    progress = []

    async def record(text):
        progress.append(text)

    artifact = await media.generate(SCOPE, "media", "prompt", "job1", video=True, progress=record)
    assert artifact.data == MP4 and len(progress) == 2
    assert (await service.store.job("job1", SCOPE))["operation"] == OPERATION
    with pytest.raises(BotError, match="already"):
        await media.generate(SCOPE, "media", "prompt", "job1", video=True, progress=record)
    # Reopen the actual SQLite connection, as a restarted process would do.
    await service.store.close()
    await service.store.open()
    artifact = await media.retrieve(SCOPE, "job1", progress=record)
    assert artifact.data == MP4
    assert requests.count("POST") == 1
    with pytest.raises(BotError, match="belongs"):
        await media.retrieve(replace(SCOPE, user_id=99), "job1", progress=record)
    await media.close()


async def test_pending_job_timeout_and_cancellation_preserve_id(service, monkeypatch):
    count = 0

    async def handler(request):
        nonlocal count
        if request.method == "POST":
            count += 1
            return httpx.Response(200, json={"name": OPERATION})
        return httpx.Response(200, json={"name": OPERATION, "done": False})

    provider = make_provider("gemini", handler, monkeypatch)
    service.settings.models["media"] = provider.model
    media = MediaService(
        replace(service.settings, media_timeout=0.04), service.store, service, {"media": provider}
    )

    async def progress(text):
        pass

    with pytest.raises(BotError, match="timed out"):
        await media.generate(SCOPE, "media", "prompt", "slow", video=True, progress=progress)
    assert (await service.store.job("slow", SCOPE))["state"] == "pending"
    assert count == 1
    task = asyncio.create_task(media.retrieve(SCOPE, "slow", progress=progress))
    await asyncio.sleep(0.01)
    await service.gate.cancel(SCOPE.key)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await service.store.job("slow", SCOPE))["operation"] == OPERATION
    await media.close()


async def test_failed_submission_is_unknown_not_retried(service, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private secret")

    provider = make_provider("gemini", handler, monkeypatch)
    service.settings.models["media"] = provider.model
    media = MediaService(service.settings, service.store, service, {"media": provider})

    async def progress(text):
        pass

    with pytest.raises(BotError):
        await media.generate(SCOPE, "media", "prompt", "unknown", video=True, progress=progress)
    assert (await service.store.job("unknown", SCOPE))["state"] == "unknown"
    assert len(calls) == 1
    await media.close()


async def test_artifact_redirect_redacts_key_and_limits_bytes(monkeypatch):
    def handler(request):
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(
                302, headers={"Location": "https://storage.googleapis.com/test/video.mp4"}
            )
        assert "x-goog-api-key" not in request.headers
        return httpx.Response(200, content=MP4)

    provider = make_provider("gemini", handler, monkeypatch, maximum=10)
    with pytest.raises(BotError, match="attachment limit"):
        await provider.download(URI)
    with pytest.raises(BotError, match="allowed download"):
        await provider.download("http://127.0.0.1/secrets")
    with pytest.raises(BotError, match="operation"):
        await provider.poll_video("../../secrets")
    await provider.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"done": True, "error": {"message": "private secret"}},
        {"done": True, "response": {}},
        {"done": "yes"},
    ],
)
async def test_failed_filtered_malformed_video(payload, monkeypatch):
    provider = make_provider(
        "gemini", lambda request: httpx.Response(200, json=payload), monkeypatch
    )
    with pytest.raises(BotError) as error:
        await provider.poll_video(OPERATION)
    assert "private secret" not in str(error.value)
    await provider.close()


async def test_terminal_failure_is_persisted_and_not_polled_again(service, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"name": OPERATION})
        return httpx.Response(
            200, json={"done": True, "error": {"message": "private provider error"}}
        )

    provider = make_provider("gemini", handler, monkeypatch)
    service.settings.models["media"] = provider.model
    media = MediaService(service.settings, service.store, service, {"media": provider})

    async def progress(text):
        pass

    with pytest.raises(BotError, match="failed"):
        await media.generate(SCOPE, "media", "prompt", "failed", video=True, progress=progress)
    assert (await service.store.job("failed", SCOPE))["state"] == "failed"
    with pytest.raises(BotError, match="failed"):
        await media.retrieve(SCOPE, "failed", progress=progress)
    assert calls == ["POST", "GET"]
    await media.close()


async def test_upload_is_not_downloaded_when_admission_is_full(service, monkeypatch):
    provider = make_provider(
        "openai", lambda request: pytest.fail("No inference should be submitted"), monkeypatch
    )
    service.settings.models["media"] = provider.model
    service.gate.maximum = 1
    media = MediaService(service.settings, service.store, service, {"media": provider})

    async def load():
        pytest.fail("Attachment download must wait for admission")

    async def progress(text):
        pass

    async with service.gate.hold("occupied"):
        with pytest.raises(BotError, match="busy"):
            await media.generate(
                SCOPE, "media", "prompt", "upload", load_source=load, progress=progress
            )
    await media.close()


@pytest.mark.parametrize("url", [None, "https://generativelanguage.googleapis.com:invalid/file"])
async def test_malformed_artifact_urls_are_safe_errors(url, monkeypatch):
    provider = make_provider(
        "gemini", lambda request: pytest.fail("Invalid URLs must not be requested"), monkeypatch
    )
    with pytest.raises(BotError, match="invalid artifact URL"):
        await provider.download(url)
    await provider.close()


XAI_ID = "38e6e8d7-1842-43b2-b740-b1b8d0172da2"
XAI_URI = f"https://vidgen.x.ai/{XAI_ID}/video.mp4"
XAI_DONE = {"status": "done", "video": {"url": XAI_URI, "respect_moderation": True}}


async def test_xai_video_submission_restart_retrieval_and_credential_boundary(service, monkeypatch):
    calls = []
    polls = 0

    def handler(request):
        nonlocal polls
        calls.append(request.method)
        if request.url.host == "vidgen.x.ai":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=MP4)
        assert request.headers["authorization"] == "Bearer media-test-secret"
        if request.method == "POST":
            assert request.url.path == "/v1/videos/generations"
            assert json.loads(request.content) == {
                "model": "grok-imagine-video",
                "prompt": "a landscape",
                "duration": 1,
                "resolution": "480p",
                "aspect_ratio": "16:9",
            }
            return httpx.Response(200, json={"request_id": XAI_ID})
        assert request.url.path == f"/v1/videos/{XAI_ID}"
        polls += 1
        return httpx.Response(200, json={"status": "pending"} if polls == 1 else XAI_DONE)

    provider = make_provider("xai", handler, monkeypatch)
    service.settings.models["media"] = provider.model
    media = MediaService(service.settings, service.store, service, {"media": provider})

    async def progress(text):
        pass

    result = await media.generate(
        SCOPE, "media", "a landscape", "xai-job", video=True, progress=progress
    )
    assert result.data == MP4
    await service.store.close()
    await service.store.open()
    assert (await service.store.job("xai-job", SCOPE))["operation"] == XAI_ID
    assert (await media.retrieve(SCOPE, "xai-job", progress=progress)).data == MP4
    with pytest.raises(BotError, match="already"):
        await media.generate(
            SCOPE, "media", "a landscape", "xai-job", video=True, progress=progress
        )
    assert calls.count("POST") == 1
    await media.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "failed", "error": {"message": "private secret"}},
        {"status": "expired"},
        {"status": "done", "video": {"respect_moderation": False}},
        {"status": "done", "video": {"respect_moderation": True}},
        {"status": "invented"},
        {"status": []},
        {"status": "done", "video": {"url": XAI_URI}},
    ],
)
async def test_xai_failed_filtered_and_malformed_video(payload, monkeypatch):
    provider = make_provider("xai", lambda request: httpx.Response(200, json=payload), monkeypatch)
    with pytest.raises(BotError) as error:
        await provider.poll_video(XAI_ID)
    assert "private secret" not in str(error.value)
    await provider.close()


async def test_xai_video_rejects_unsupported_edit_invalid_session_and_download_redirect(
    monkeypatch,
):
    calls = []

    def handler(request):
        calls.append(request)
        assert "authorization" not in request.headers
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    provider = make_provider("xai", handler, monkeypatch)
    with pytest.raises(BotError, match="image-to-video"):
        await provider.submit_video("prompt", PNG)
    with pytest.raises(BotError, match="request ID"):
        await provider.poll_video("../../secret")
    assert not calls
    with pytest.raises(BotError, match="allowed download"):
        await provider.download(XAI_URI)
    assert len(calls) == 1
    await provider.close()
