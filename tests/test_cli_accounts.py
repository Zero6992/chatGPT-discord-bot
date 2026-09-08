import asyncio
import json
import os
import shutil
import signal
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.cli import CLIProvider, DockerRunner, ProcessResult, arguments, run_process
from src.cli_accounts import AccountProfile, interactive_process, login_arguments
from src.config import Backend, load_settings
from src.domain import BotError, Completion
from src.storage import Scope

KINDS = ["codex-cli", "claude-cli", "grok-cli"]
SESSION = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"
RUNTIME = Path("runtime/account-runtime.mjs").resolve()


@pytest.fixture
def account_model(model, tmp_path):
    return replace(
        model,
        backend=Backend(
            "personal",
            "codex-cli",
            auth="account",
            owner_id=4,
            auth_profile=str(tmp_path / "account"),
            image="sha256:" + "a" * 64,
            docker_socket="/run/user/1000/docker.sock",
            network="account-internal",
            proxy_url="http://egress:3128",
            cli_version="0.153.4",
        ),
        parameters={},
    )


def account_config(kind="codex-cli"):
    return f'''
[bot]
default_model = "personal"
allowed_user_ids = [4]
[backends.personal]
kind = "{kind}"
auth = "account"
owner_id = 4
auth_profile = "data/personal-login"
image = "sha256:{"a" * 64}"
docker_socket = "/run/user/1000/docker.sock"
network = "account-internal"
proxy_url = "http://egress:3128"
cli_version = "test-version"
[models.personal]
backend = "personal"
model = "configured-model"
capabilities = ["chat"]
'''


@pytest.mark.parametrize("kind", KINDS)
def test_account_config_needs_no_api_key(tmp_path, kind):
    path = tmp_path / "config.toml"
    path.write_text(account_config(kind))
    settings = load_settings(path)
    backend = settings.models["personal"].backend
    assert backend.key() == "" and backend.auth == "account"
    assert Path(backend.auth_profile) == tmp_path / "data/personal-login"
    assert settings.allowed_user_ids == (backend.owner_id,)


@pytest.mark.parametrize(
    "before,after",
    [
        ("allowed_user_ids = [4]", "allowed_user_ids = []"),
        ("allowed_user_ids = [4]", "allowed_user_ids = [4, 5]"),
        ("owner_id = 4", "owner_id = 5"),
        ('auth = "account"', 'auth = "account"\napi_key_env = "OPENAI_API_KEY"'),
        ('auth = "account"', 'auth = "account"\nbase_url = "https://other.example"'),
        ('auth_profile = "data/personal-login"', 'auth_profile = ""'),
    ],
)
def test_account_config_rejects_shared_or_mixed_auth(tmp_path, before, after):
    path = tmp_path / "config.toml"
    path.write_text(account_config().replace(before, after))
    with pytest.raises(BotError):
        load_settings(path)


def test_account_example_and_duplicate_profile_rejection(tmp_path):
    example = (
        Path("config.account.example.toml")
        .read_text()
        .replace("REPLACE_WITH_64_HEX_DIGITS", "a" * 64)
    )
    path = tmp_path / "config.toml"
    path.write_text(example)
    settings = load_settings(path)
    assert {m.backend.kind for m in settings.models.values()} == set(KINDS)
    assert all(m.backend.auth == "account" for m in settings.models.values())
    path.write_text(example.replace("data/cli-auth/claude", "data/cli-auth/codex"))
    with pytest.raises(BotError, match="profile"):
        load_settings(path)


@pytest.mark.parametrize("unsafe", ["permissions", "symlink", "foreign_files"])
async def test_profile_rejects_unsafe_directory(account_model, tmp_path, unsafe):
    profile = AccountProfile(account_model.backend)
    if unsafe == "symlink":
        target = tmp_path / "existing-personal-profile"
        target.mkdir(mode=0o700)
        profile.path.symlink_to(target, target_is_directory=True)
    else:
        profile.path.mkdir(mode=0o755 if unsafe == "permissions" else 0o700)
        if unsafe == "foreign_files":
            (profile.path / "auth.json").write_text("existing-user-data")
    with pytest.raises(BotError):
        async with profile.lease():
            pytest.fail("Unsafe credential directory was accepted")
    if unsafe == "foreign_files":
        assert (profile.path / "auth.json").read_text() == "existing-user-data"


async def test_account_preflight_rejects_old_runtime_image(account_model):
    runner = DockerRunner(account_model, 10)
    runner.docker = AsyncMock(
        side_effect=[
            ProcessResult(
                0,
                json.dumps(
                    {
                        "SecurityOptions": ["name=rootless", "name=seccomp,profile=builtin"],
                        "CgroupDriver": "systemd",
                        "CgroupVersion": "2",
                        "MemoryLimit": True,
                        "CpuCfsQuota": True,
                        "PidsLimit": True,
                    }
                ).encode(),
                b"",
            ),
            ProcessResult(0, b'[{"Internal":true}]', b""),
            ProcessResult(
                0,
                json.dumps([{"Config": {"Labels": {"io.chatgptbot.cli": "codex-cli"}}}]).encode(),
                b"",
            ),
        ]
    )
    with pytest.raises(BotError, match="runtime label"):
        await runner.verify()
    assert not runner.verified
    assert all(call.args[0][1] != "run" for call in runner.docker.call_args_list)


@pytest.mark.parametrize("kind", KINDS)
def test_account_arguments_keep_official_login_and_disable_tools(account_model, kind):
    model = replace(account_model, backend=replace(account_model.backend, kind=kind))
    argv = arguments(model, SESSION)
    if kind == "codex-cli":
        assert argv[:4] == ["codex", "exec", "resume", SESSION]
        assert 'forced_login_method="chatgpt"' in argv
        assert 'forced_login_method="api"' not in argv
    elif kind == "claude-cli":
        assert "--safe-mode" in argv and "--bare" not in argv
        assert argv[argv.index("--tools") + 1] == ""
        assert "--claudeai" in login_arguments(kind)
    else:
        assert argv[argv.index("--deny") + 1] == "*"
        assert "--device-auth" in login_arguments(kind)
    assert SESSION in argv and "--continue" not in argv


async def test_profile_revision_persistence_and_owner_binding(account_model):
    first = AccountProfile(account_model.backend)
    before = account_model.fingerprint()
    async with first.lease():
        first.record(True)
    assert account_model.fingerprint() != before
    reopened = AccountProfile(account_model.backend)
    assert reopened.configured() and first.revision() == reopened.revision()
    current = account_model.fingerprint()
    async with reopened.lease():
        reopened.record(True, rotate=False)
    assert account_model.fingerprint() == current
    async with reopened.lease():
        reopened.record(False)
    assert account_model.fingerprint() != current
    with pytest.raises(BotError, match="another account"):
        AccountProfile(replace(account_model.backend, owner_id=5)).revision()
    assert (first.path.stat().st_mode & 0o777) == 0o700
    assert ((first.path / "profile.json").stat().st_mode & 0o777) == 0o600


async def test_profile_path_alias_uses_same_native_account_volume(account_model, tmp_path):
    original = AccountProfile(account_model.backend)
    (tmp_path / "subdir").mkdir()
    alternate = AccountProfile(
        replace(account_model.backend, auth_profile=str(tmp_path / "subdir/../account"))
    )
    assert original.volume == alternate.volume
    async with alternate.lease():
        alternate.record(True)
    assert original.configured() and original.revision() == alternate.revision()


async def test_account_lease_serializes_instances_and_cancel_releases(account_model):
    first = AccountProfile(account_model.backend)
    second = AccountProfile(account_model.backend)
    entered = asyncio.Event()

    async def acquire():
        async with second.lease():
            entered.set()

    async with first.lease():
        waiter = asyncio.create_task(acquire())
        await asyncio.sleep(0.08)
        assert not entered.is_set()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        async with first.lease():
            first.record(True)
    await acquire()
    assert entered.is_set() and first.holder is None and second.holder is None


async def test_missing_login_does_not_fall_back_to_api(account_model, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-use-this-key")
    runner = DockerRunner(account_model, 10)
    runner.docker = AsyncMock()
    with pytest.raises(BotError, match="not signed in"):
        async with runner.account_guard():
            pass
    runner.docker.assert_not_called()


@pytest.mark.parametrize("kind", KINDS)
async def test_login_status_logout_use_native_terminal_and_rotate(account_model, monkeypatch, kind):
    model = replace(account_model, backend=replace(account_model.backend, kind=kind))
    runner = DockerRunner(model, 10)
    runner.verify = AsyncMock()
    runner.docker = AsyncMock(return_value=ProcessResult(0, b"", b""))
    runner.account_status = AsyncMock(side_effect=[True, True, False])
    calls = []

    async def terminal(argv, env):
        assert runner.profile.configured() is False
        assert not any(key.endswith(("_KEY", "_TOKEN")) for key in env)
        assert "-it" in argv and "--read-only" in argv
        assert argv[-len(login_arguments(kind)) + 1 :] == login_arguments(kind)[1:]
        calls.append(argv)
        return 0

    monkeypatch.setattr("src.cli.interactive_process", terminal)
    assert await runner.account_action("login") == {"configured": True, "provider_verified": False}
    revision = runner.profile.revision()
    assert (await runner.account_action("status"))["configured"] is True
    assert (await runner.account_action("logout"))["configured"] is False
    assert revision != runner.profile.revision() and len(calls) == 1
    assert runner.docker.call_args_list[-1].args[0][1:3] == ["rm", "-f"]


async def test_aborted_login_disables_old_session_and_cleans_container(account_model, monkeypatch):
    runner = DockerRunner(account_model, 10)
    async with runner.profile.lease():
        runner.profile.record(True)
    before = runner.profile.revision()
    runner.verify = AsyncMock()
    runner.docker = AsyncMock(return_value=ProcessResult(0, b"", b""))

    async def abort(*args):
        raise asyncio.CancelledError

    monkeypatch.setattr("src.cli.interactive_process", abort)
    with pytest.raises(asyncio.CancelledError):
        await runner.account_action("login")
    assert not runner.profile.configured() and runner.profile.revision() != before
    assert runner.docker.call_args.args[0][1:3] == ["rm", "-f"]


async def test_account_run_has_separate_mounts_and_no_keys(account_model, monkeypatch):
    runner = DockerRunner(account_model, 10)
    runner.verified = True
    runner.docker = AsyncMock(return_value=ProcessResult(0, b"result", b""))
    async with runner.profile.lease():
        runner.profile.record(True)
        await runner.run(arguments(account_model, None), b"private prompt", "a" * 64)
    call = next(c for c in runner.docker.call_args_list if c.args[0][1] == "run")
    argv = call.args[0]
    assert any("target=/account" in value for value in argv)
    assert any("target=/state" in value for value in argv)
    assert not any("type=bind" in value for value in argv)
    assert "/opt/chatgptbot/account-runtime.mjs" in argv
    assert not any(key.endswith(("_KEY", "_TOKEN")) for key in call.kwargs["env"])
    assert any(c.args[0][1] == "stop" for c in runner.docker.call_args_list)


async def test_failed_graceful_stop_still_forces_cleanup(account_model):
    runner = DockerRunner(account_model, 10)
    runner.docker = AsyncMock(side_effect=[BotError("timeout"), ProcessResult(0, b"", b"")])
    await runner.cleanup("own-container", graceful=True)
    assert runner.docker.call_args.args[0] == ["docker", "rm", "-f", "own-container"]


async def test_native_status_never_forwards_raw_data(account_model):
    runner = DockerRunner(account_model, 10)
    runner.docker = AsyncMock(
        side_effect=[
            ProcessResult(0, b"[]", b""),
            ProcessResult(0, b'{"token":"sensitive"}', b""),
            ProcessResult(0, b"", b""),
        ]
    )
    with pytest.raises(BotError) as error:
        await runner.account_status()
    assert "sensitive" not in str(error.value)


async def test_service_holds_account_lease_until_history_commit(service, account_model):
    scope = Scope(1, 2, 3, 4)
    model = replace(account_model, name="local")
    service.settings.models["local"] = model
    runner = DockerRunner(model, 10)
    async with runner.profile.lease():
        runner.profile.record(True)
    provider = CLIProvider(model, runner)
    provider._complete = AsyncMock(return_value=Completion("answer", SESSION))
    service.providers["local"] = provider
    entered, release, relogged = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = service.store.save

    async def save(conversation):
        entered.set()
        await release.wait()
        await original(conversation)

    async def relogin():
        async with AccountProfile(model.backend).lease() as _:
            assert release.is_set()
        async with runner.profile.lease():
            runner.profile.record(True)
        relogged.set()

    service.store.save = save
    first = asyncio.create_task(service.chat(scope, "first"))
    await entered.wait()
    login = asyncio.create_task(relogin())
    await asyncio.sleep(0.08)
    assert not relogged.is_set()
    release.set()
    await asyncio.gather(first, login)
    result = await service.chat(scope, "second")
    assert provider._complete.call_args.args[1] is None
    assert "reconstructed" in result.notice
    assert any(m.content == "first" for m in provider._complete.call_args.args[0])


async def test_reset_deletes_conversation_but_preserves_account_login(service, account_model):
    scope = Scope(1, 2, 3, 4)
    model = replace(account_model, name="local")
    service.settings.models["local"] = model
    runner = DockerRunner(model, 10)
    async with runner.profile.lease():
        runner.profile.record(True)
    revision = runner.profile.revision()
    native_volume = f"bot-cli-{runner.namespace}-{scope.key}-" + "b" * 16
    runner.docker = AsyncMock(
        side_effect=[
            ProcessResult(0, native_volume.encode(), b""),
            ProcessResult(0, b"", b""),
        ]
    )
    provider = CLIProvider(model, runner)
    provider._complete = AsyncMock(return_value=Completion("answer", SESSION))
    service.providers["local"] = provider
    await service.chat(scope, "remember")
    await service.reset(scope)
    conversation = await service.conversation(scope)
    assert conversation.turns == [] and conversation.session is None
    assert runner.profile.configured() and runner.profile.revision() == revision
    assert runner.docker.call_args.args[0] == ["docker", "volume", "rm", native_volume]
    assert all(runner.profile.volume not in c.args[0] for c in runner.docker.call_args_list)


async def test_login_requires_a_private_terminal(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(BotError, match="private interactive terminal"):
        await interactive_process(["must-not-run"], {})


@pytest.fixture
def native_runtime(tmp_path):
    node = shutil.which("node")
    assert node, "Offline account-runtime contracts require Node.js 22+ (also installed in CI)."
    account, state, binaries = (
        tmp_path / name for name in ("native-account", "conversation", "bin")
    )
    for root in (account, state, binaries):
        root.mkdir()
    script = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
kind = Path(sys.argv[0]).name
root = Path(os.environ[{{"codex":"CODEX_HOME","claude":"CLAUDE_CONFIG_DIR","grok":"GROK_HOME"}}[kind]])
auth = root / (".credentials.json" if kind == "claude" else "auth.json")
data = json.loads(auth.read_text())
data["rotation"] += 1
temporary = auth.with_suffix(".updated")
temporary.write_text(json.dumps(data))
temporary.replace(auth)
(root / "transcript.txt").write_text(sys.stdin.read())
print(json.dumps({{"rotation":data["rotation"], "keys": [k for k in os.environ if k.endswith(("_KEY", "_TOKEN"))]}}), flush=True)
if "hang" in sys.argv:
    (root / "ready").write_text(str(os.getpid()))
    time.sleep(60)
sys.exit(1 if "fail" in sys.argv else 0)
"""
    for name in ("codex", "claude", "grok"):
        executable = binaries / name
        executable.write_text(script)
        executable.chmod(0o700)
    return node, account, state, binaries


def native_command(runtime, kind, mode="normal"):
    node, account, state, binaries = runtime
    native = kind.removesuffix("-cli")
    program = (
        "import {execute} from "
        + json.dumps(RUNTIME.as_uri())
        + "; process.exitCode = await execute(...JSON.parse(process.argv[1]));"
    )
    argv = [
        node,
        "--input-type=module",
        "-e",
        program,
        json.dumps([kind, [native, mode], str(account), str(state)]),
    ]
    env = {"PATH": str(binaries) + os.pathsep + os.defpath, "OPENAI_API_KEY": "must-be-removed"}
    return argv, env


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mode", ["normal", "fail"])
async def test_native_refresh_is_preserved_and_transcripts_stay_separate(
    native_runtime, kind, mode
):
    _, account, state, _ = native_runtime
    relative = kind.removesuffix("-cli") + (
        "/.credentials.json" if kind == "claude-cli" else "/auth.json"
    )
    auth = account / relative
    auth.parent.mkdir()
    auth.write_text(json.dumps({"rotation": 0, "access_token": "synthetic-private-token"}))
    argv, env = native_command(native_runtime, kind, mode)
    first = await run_process(argv, env=env, stdin=b"channel one")
    assert first.code == (1 if mode == "fail" else 0)
    assert json.loads(first.stdout) == {"rotation": 1, "keys": []}
    assert "synthetic-private-token" not in first.stdout.decode() + first.stderr.decode()
    assert json.loads(auth.read_text())["rotation"] == 1
    assert not (state / relative).exists()
    assert not list(account.rglob("transcript.txt"))
    other = state.parent / "other-conversation"
    other.mkdir()
    node, _, _, binaries = native_runtime
    argv, env = native_command((node, account, other, binaries), kind, mode)
    second = await run_process(argv, env=env, stdin=b"next request")
    assert json.loads(second.stdout)["rotation"] == 2
    assert json.loads(auth.read_text())["rotation"] == 2
    assert (state / kind.removesuffix("-cli") / "transcript.txt").read_text() == "channel one"
    assert (other / kind.removesuffix("-cli") / "transcript.txt").read_text() == "next request"


async def test_native_cancellation_flushes_refresh_and_cleans_copy(native_runtime):
    _, account, state, _ = native_runtime
    auth = account / "codex/auth.json"
    auth.parent.mkdir()
    auth.write_text('{"rotation":0}')
    argv, env = native_command(native_runtime, "codex-cli", "hang")
    process = await asyncio.create_subprocess_exec(
        *argv,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            while not (state / "codex/ready").exists():
                await asyncio.sleep(0.01)
            process.send_signal(signal.SIGTERM)
            await process.communicate()
        assert process.returncode == 143
        assert json.loads(auth.read_text())["rotation"] == 1
        assert not (state / "codex/auth.json").exists()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def test_native_login_file_symlink_rejected(native_runtime, tmp_path):
    _, account, _, _ = native_runtime
    (account / "codex").mkdir()
    secret = tmp_path / "unrelated-file"
    secret.write_text("must-not-read")
    (account / "codex/auth.json").symlink_to(secret)
    argv, env = native_command(native_runtime, "codex-cli")
    result = await run_process(argv, env=env)
    assert result.code != 0 and b"must-not-read" not in result.stdout + result.stderr
    assert secret.read_text() == "must-not-read"
