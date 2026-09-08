import asyncio
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot import create_bot
from src.cli import DockerRunner, ProcessResult, run_process
from src.cli_accounts import AccountProfile, ChallengeReader, DeviceChallenge
from src.cli_auth import CLIAuth
from src.config import Backend
from src.domain import BotError

CODE = "ABCD-EFGH"
CODEX = (
    "Welcome to Codex\n1. Open this link in your browser and sign in to your account\n"
    "   \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m\n\n"
    "2. Enter this one-time code (expires in 15 minutes)\n   ABCD-EFGH\n"
)
GROK = (
    "To sign in, open this URL in your browser:\n\n"
    "  https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH\n\n"
    "  (Could not open browser automatically — open the URL above manually.)\n\n"
    "Confirm this code in your browser:\n\n  ABCD-EFGH\nWaiting for authorization...\n"
)


@pytest.fixture
def auth_settings(settings, tmp_path):
    backend = Backend(
        "personal",
        "codex-cli",
        auth="account",
        owner_id=4,
        auth_profile=str(tmp_path / "auth"),
        image="sha256:" + "a" * 64,
        docker_socket="/run/user/1000/docker.sock",
        network="internal",
        proxy_url="http://egress:3128",
        cli_version="0.153.4",
    )
    first = replace(settings.models["local"], backend=backend, parameters={})
    return replace(
        settings,
        allowed_user_ids=(4,),
        models={"local": first, "alias": replace(first, name="alias")},
    )


@pytest.mark.parametrize(
    "kind,pipe,prompt", [("codex-cli", "stdout", CODEX), ("grok-cli", "stderr", GROK)]
)
async def test_native_challenge_chunking_and_only_safe_fields(kind, pipe, prompt):
    callback = AsyncMock()
    reader = ChallengeReader(kind, callback)
    for byte in prompt.encode():
        await reader(pipe, bytes([byte]))
    await reader(pipe, b"private-diagnostic-token: must-not-forward\n")
    callback.assert_awaited_once()
    challenge = callback.call_args.args[0]
    assert challenge.code == CODE
    assert challenge.url == (
        "https://auth.openai.com/codex/device"
        if kind == "codex-cli"
        else "https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH"
    )
    assert CODE not in repr(challenge)
    assert reader.buffer == b""


@pytest.mark.parametrize(
    "url",
    [
        "https://auth.openai.com.evil.example/codex/device",
        "https://attacker@auth.openai.com/codex/device",
        "https://auth.openai.com:8443/codex/device",
        "https://auth.openai.com/codex/device?access_token=private",
        "https://auth.openai.com/codex/device#private",
        "https://auth.openai.com/../codex/device",
    ],
)
async def test_untrusted_authorization_url_rejected(url):
    callback = AsyncMock()
    reader = ChallengeReader("codex-cli", callback)
    prompt = CODEX.replace("https://auth.openai.com/codex/device", url)
    with pytest.raises(BotError, match="authorization URL"):
        await reader("stdout", prompt.encode())
    callback.assert_not_awaited()


async def test_grok_code_must_match_prefilled_url():
    reader = ChallengeReader("grok-cli", AsyncMock())
    with pytest.raises(BotError, match="authorization URL"):
        await reader("stderr", GROK.replace("user_code=ABCD-EFGH", "user_code=IJKL-MNOP").encode())


@pytest.mark.parametrize(
    "destination",
    ["auth.x.ai/device", "auth.x.ai/oauth2/device", "accounts.x.ai/oauth2/device"],
)
@pytest.mark.parametrize("query", ["", "?user_code=ABCD-EFGH"])
async def test_grok_native_device_destinations(destination, query):
    callback = AsyncMock()
    reader = ChallengeReader("grok-cli", callback)
    url = f"https://{destination}{query}"
    prompt = GROK.replace("https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH", url)
    await reader("stderr", prompt.encode())
    callback.assert_awaited_once_with(DeviceChallenge(url, CODE))


@pytest.mark.parametrize(
    "url",
    [
        "http://accounts.x.ai/oauth2/device",
        "https://accounts.x.ai.evil.example/oauth2/device",
        "https://attacker@accounts.x.ai/oauth2/device",
        "https://accounts.x.ai:8443/oauth2/device",
        "https://accounts.x.ai/oauth2/token",
        "https://auth.x.ai/unreviewed",
        "https://accounts.x.ai/oauth2/device?access_token=private",
        "https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH&user_code=ABCD-EFGH",
        "https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH&next=https://evil.example",
        "https://accounts.x.ai/oauth2/device#private",
        "https://accounts.x.ai/../oauth2/device",
    ],
)
async def test_grok_device_url_rejects_unreviewed_destinations_and_fields(url):
    callback = AsyncMock()
    reader = ChallengeReader("grok-cli", callback)
    prompt = GROK.replace("https://accounts.x.ai/oauth2/device?user_code=ABCD-EFGH", url)
    with pytest.raises(BotError, match="authorization URL"):
        await reader("stderr", prompt.encode())
    callback.assert_not_awaited()


async def test_real_subprocess_observation_and_callback_failure_cleanup(tmp_path):
    script = tmp_path / "native_login.py"
    pid_file = tmp_path / "child.pid"
    script.write_text(
        "import pathlib,subprocess,sys,time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
        f"print({CODEX!r},flush=True)\n"
        "time.sleep(60)\n"
    )
    callback = AsyncMock(side_effect=RuntimeError("secret error must not escape"))
    reader = ChallengeReader("codex-cli", callback)
    with pytest.raises(BotError, match="deliver login instructions") as error:
        await run_process([sys.executable, str(script), str(pid_file)], observe=reader, timeout=5)
    assert "secret" not in str(error.value)
    from pathlib import Path

    status = Path(f"/proc/{pid_file.read_text()}/stat")
    assert not status.exists() or status.read_text().split()[2] == "Z"


async def test_device_login_uses_native_process_and_persists_metadata(auth_settings):
    runner = DockerRunner(auth_settings.models["local"], 10)
    runner.verify = AsyncMock()
    runner.account_status = AsyncMock(return_value=True)
    calls = []

    async def docker(argv, **kwargs):
        calls.append((argv, kwargs))
        if "observe" in kwargs:
            assert "-it" not in argv and "--device-auth" in argv
            assert kwargs["maximum"] == 65536 and kwargs["timeout"] == 600
            await kwargs["observe"]("stdout", CODEX.encode())
        return ProcessResult(0, b"", b"")

    runner.docker = docker
    callback = AsyncMock()
    assert (await runner.account_action("login", callback))["configured"]
    callback.assert_awaited_once()
    assert AccountProfile(auth_settings.models["local"].backend).configured()
    assert calls[-1][0][1:3] == ["rm", "-f"]


async def test_native_success_without_prompt_keeps_login_disabled(auth_settings):
    runner = DockerRunner(auth_settings.models["local"], 10)
    runner.verify = AsyncMock()
    runner.docker = AsyncMock(return_value=ProcessResult(0, b"", b""))
    with pytest.raises(BotError, match="device login prompt"):
        await runner.account_action("login", AsyncMock())
    assert not runner.profile.configured()


async def test_device_prompt_wrong_pipe_and_bounded_output():
    callback = AsyncMock()
    reader = ChallengeReader("codex-cli", callback)
    await reader("stderr", CODEX.encode())
    callback.assert_not_awaited()
    assert reader.buffer == b""
    with pytest.raises(BotError, match="output exceeded"):
        await reader("stdout", b"x" * 65537)
    callback.assert_not_awaited()


@pytest.mark.parametrize("termination", ["timeout", "cancel"])
async def test_device_login_wait_cleans_actual_process_tree(tmp_path, termination):
    script = tmp_path / "native_login.py"
    pid_file = tmp_path / "child.pid"
    script.write_text(
        "import pathlib,subprocess,sys,time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
        f"print({CODEX!r},flush=True)\n"
        "time.sleep(60)\n"
    )
    presented = asyncio.Event()

    async def show(challenge):
        presented.set()

    task = asyncio.create_task(
        run_process(
            [sys.executable, str(script), str(pid_file)],
            observe=ChallengeReader("codex-cli", show),
            timeout=1 if termination == "timeout" else 10,
        )
    )
    await asyncio.wait_for(presented.wait(), 3)
    if termination == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(BotError, match="timed out"):
            await task
    from pathlib import Path

    status = Path(f"/proc/{pid_file.read_text()}/stat")
    assert not status.exists() or status.read_text().split()[2] == "Z"


async def test_failed_relogin_rotates_and_disables_previous_profile(auth_settings):
    runner = DockerRunner(auth_settings.models["local"], 10)
    runner.verify = AsyncMock()
    async with runner.profile.lease():
        runner.profile.record(True)
    revision = runner.profile.revision()
    calls = []

    async def docker(argv, **kwargs):
        calls.append(argv)
        if "observe" in kwargs:
            await kwargs["observe"]("stdout", CODEX.encode())
            return ProcessResult(1, b"", b"private native credentials or diagnostics")
        return ProcessResult(0, b"", b"")

    runner.docker = docker
    with pytest.raises(BotError, match="account operation failed") as error:
        await runner.account_action("login", AsyncMock())
    assert "credentials" not in str(error.value)
    assert not runner.profile.configured() and runner.profile.revision() != revision
    assert calls[-1][1:3] == ["rm", "-f"]


async def test_owner_checks_and_claude_local_only(auth_settings):
    manager = CLIAuth(auth_settings)
    native = AsyncMock()
    manager.runners["personal"] = SimpleNamespace(account_action=native)
    with pytest.raises(BotError, match="owned by you"):
        await manager.execute("login", "local", 5, AsyncMock())
    with pytest.raises(BotError):
        await manager.execute("login", "not-configured", 4, AsyncMock())
    model = auth_settings.models["local"]
    auth_settings.models["local"] = replace(
        model, backend=replace(model.backend, kind="claude-cli")
    )
    result = await manager.execute("login", "local", 4, AsyncMock())
    assert "not implemented" in result
    assert "src.cli_accounts login local" in result
    native.assert_not_awaited()
    await manager.close()


async def test_alias_duplicate_cancel_and_shutdown_wait_for_cleanup(auth_settings):
    manager = CLIAuth(auth_settings)
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def native(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cleaning.set()
            await release.wait()

    manager.runners["personal"] = SimpleNamespace(account_action=native)
    login = asyncio.create_task(manager.execute("login", "local", 4, AsyncMock()))
    await entered.wait()
    assert "login is in progress" in await manager.execute("status", "alias", 4, AsyncMock())
    with pytest.raises(BotError, match="already pending"):
        await manager.execute("login", "alias", 4, AsyncMock())
    cancel = asyncio.create_task(manager.execute("cancel", "alias", 4, AsyncMock()))
    await cleaning.wait()
    shutdown = asyncio.create_task(manager.close())
    await asyncio.sleep(0)
    assert not cancel.done() and not shutdown.done()
    release.set()
    await asyncio.gather(cancel, shutdown)
    assert login.cancelled() and manager.active == {}


async def test_account_administration_admission_and_slot_recovery(auth_settings):
    model = auth_settings.models["local"]
    backend = replace(model.backend, name="second", auth_profile=model.backend.auth_profile + "2")
    auth_settings.models["second"] = replace(model, name="second", backend=backend)
    manager = CLIAuth(replace(auth_settings, concurrency=1))
    entered = asyncio.Event()

    async def native(*args, **kwargs):
        entered.set()
        await asyncio.Future()

    manager.runners["personal"] = SimpleNamespace(account_action=native)
    second = AsyncMock(return_value={"configured": False})
    manager.runners["second"] = SimpleNamespace(account_action=second)
    login = asyncio.create_task(manager.execute("login", "local", 4, AsyncMock()))
    await entered.wait()
    with pytest.raises(BotError, match="administration is busy"):
        await manager.execute("status", "second", 4, AsyncMock())
    second.assert_not_awaited()
    await manager.execute("cancel", "local", 4, AsyncMock())
    assert login.cancelled()
    assert "not signed in" in await manager.execute("status", "second", 4, AsyncMock())
    assert manager.active == {}
    await manager.close()


async def test_discord_auth_is_always_private_and_clears_challenge(auth_settings, service):
    client = create_bot(auth_settings)
    client._connection.user = SimpleNamespace(id=100)
    client.store = service.store
    target = SimpleNamespace(
        user=SimpleNamespace(id=4),
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3),
        response=SimpleNamespace(defer=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    await service.store.set_private(await client.scope(target), False)

    async def native(action, **kwargs):
        await kwargs["on_challenge"](DeviceChallenge("https://auth.openai.com/codex/device", CODE))
        return {"configured": True, "provider_verified": False}

    client.cli_auth.runners["personal"] = SimpleNamespace(account_action=native)
    try:
        await client.tree.get_command("cli_auth").callback(target, "login", "local")
        target.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        calls = target.edit_original_response.call_args_list
        assert CODE in calls[0].kwargs["content"]
        assert CODE not in calls[-1].kwargs["content"]
        assert "login saved" in calls[-1].kwargs["content"]
        assert all(call.kwargs["allowed_mentions"].everyone is False for call in calls)
    finally:
        await client.close()
