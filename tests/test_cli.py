import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from src.cli import CLIProvider, DockerRunner, ProcessResult, arguments, parse_output, run_process
from src.config import Backend
from src.domain import BotError, Message, Session

FAKE = Path(__file__).parent / "fixtures/fake_cli.py"
SESSION = "a430c365-ec1b-479f-9a8d-647fd4cdb8a9"


def codex_disabled_mode_events():
    fixture = Path(__file__).parent / "fixtures/codex_disabled_code_mode.jsonl"
    return [json.loads(line) for line in fixture.read_text().splitlines()]


def test_codex_expected_disabled_code_mode_diagnostic_keeps_successful_text():
    events = codex_disabled_mode_events()
    payload = "\n".join(json.dumps(event) for event in events).encode()
    result = parse_output("codex-cli", payload, SESSION)
    assert result.text == "CLI answer"
    assert result.session_id == SESSION
    assert result.notice is None


@pytest.mark.parametrize("mutation", ["different_message", "extra_field", "unfinished", "bad_id"])
def test_codex_other_runtime_diagnostics_are_rejected_and_redacted(mutation):
    events = codex_disabled_mode_events()
    item = events[1]["item"]
    if mutation == "different_message":
        item["message"] = "private runtime credentials must not be disclosed"
    elif mutation == "extra_field":
        item["command"] = "private command"
    elif mutation == "unfinished":
        events[1]["type"] = "item.started"
    else:
        item["id"] = {"private": "data"}
    payload = "\n".join(json.dumps(event) for event in events).encode()
    with pytest.raises(BotError, match="runtime error") as error:
        parse_output("codex-cli", payload)
    assert "credentials" not in str(error.value)
    assert "private command" not in str(error.value)


@pytest.mark.parametrize(
    "kind", ["command_execution", "file_change", "mcp_tool_call", "web_search", "image_generation"]
)
def test_codex_expected_diagnostic_does_not_allow_disabled_tools(kind):
    events = codex_disabled_mode_events()
    events.insert(3, {"type": "item.completed", "item": {"id": "item_2", "type": kind}})
    payload = "\n".join(json.dumps(event) for event in events).encode()
    with pytest.raises(BotError, match="unsupported tool"):
        parse_output("codex-cli", payload)


def test_codex_expected_diagnostic_does_not_hide_a_failed_turn():
    events = codex_disabled_mode_events()
    events[-1] = {"type": "turn.failed", "error": {"message": "private provider diagnostic"}}
    payload = "\n".join(json.dumps(event) for event in events).encode()
    with pytest.raises(BotError, match="valid turn"):
        parse_output("codex-cli", payload)


@pytest.mark.parametrize("auth", ["api", "account"])
@pytest.mark.parametrize("native_id", [None, SESSION])
def test_codex_chat_explicitly_disables_media_and_external_agent_tools(model, auth, native_id):
    model = replace(model, backend=Backend("cli", "codex-cli", auth=auth), parameters={})
    argv = arguments(model, native_id)
    settings = {argv[i + 1] for i, value in enumerate(argv) if value == "-c"}
    assert {
        "features.image_generation=false",
        "features.view_image=false",
        "features.shell_tool=false",
        "features.browser_use=false",
        "features.computer_use=false",
        "features.code_mode_host=false",
        "features.plugins=false",
        "features.remote_plugin=false",
        "features.hooks=false",
        "features.skill_search=false",
        "features.unbounded_connection_retries=false",
        'web_search="disabled"',
    } <= settings


@pytest.mark.parametrize("kind", ["claude-cli", "codex-cli", "grok-cli"])
async def test_real_subprocess_and_cli_integration(kind, model):
    model = replace(model, backend=Backend("cli", kind), parameters={})

    class Runner:
        def __init__(self):
            self.calls = []

        async def has_session(self, *args):
            return True

        async def run(self, argv, prompt, conversation_id, **kwargs):
            self.calls.append((argv, prompt, conversation_id))
            return await run_process(
                [sys.executable, str(FAKE), *argv[1:]],
                stdin=prompt,
                env={"FIXTURE_MODE": "codex" if kind == "codex-cli" else "claude"},
            )

    runner = Runner()
    provider = CLIProvider(model, runner)
    messages = [
        Message("system", "rules"),
        Message("user", "first"),
        Message("assistant", "answer"),
        Message("user", "$(touch /tmp/never-created) --dangerous; `id`"),
    ]
    result = await provider.complete(messages, conversation_id="a" * 64)
    assert result.text == "CLI answer" and result.session_id == SESSION
    first_args, first_stdin, key = runner.calls[0]
    assert messages[-1].content.encode() in first_stdin
    assert all(messages[-1].content not in arg for arg in first_args)
    assert b'"role": "assistant"' in first_stdin
    result = await provider.complete(
        messages, Session(SESSION, "fingerprint"), conversation_id="a" * 64
    )
    args, stdin, _ = runner.calls[-1]
    assert stdin.decode() == messages[-1].content
    assert SESSION in args
    assert "--last" not in args and "--continue" not in args
    if kind == "grok-cli":
        assert "--resume" in args and "--session-id" not in args
    assert result.session_id == SESSION


async def test_minimal_environment_and_shell_metacharacters(tmp_path):
    malicious = "$(touch " + str(tmp_path / "bad") + "); echo secret"
    result = await run_process(
        [sys.executable, str(FAKE), malicious],
        stdin=malicious.encode(),
        env={"FIXTURE_MODE": "echo"},
    )
    payload = json.loads(result.stdout)
    assert payload["argv"] == [malicious] and payload["prompt"] == malicious
    assert "HOME" not in payload["env"] and "DISCORD_BOT_TOKEN" not in payload["env"]
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("mode,expected", [("overflow", "output exceeded"), ("hang", "timed out")])
async def test_output_bounds_timeouts_and_descendant_cleanup(tmp_path, mode, expected):
    pid_file = tmp_path / "child.pid"
    with pytest.raises(BotError, match=expected):
        await run_process(
            [sys.executable, str(FAKE)],
            env={"FIXTURE_MODE": mode, "PID_FILE": str(pid_file)},
            maximum=1024,
            timeout=0.3,
        )
    if pid_file.exists():
        stat = Path(f"/proc/{pid_file.read_text()}/stat")
        assert not stat.exists() or stat.read_text().split()[2] == "Z"


async def test_cancel_reaps_children(tmp_path):
    pid_file = tmp_path / "child.pid"
    task = asyncio.create_task(
        run_process(
            [sys.executable, str(FAKE)], env={"FIXTURE_MODE": "hang", "PID_FILE": str(pid_file)}
        )
    )
    for _ in range(100):
        if pid_file.exists():
            break
        await asyncio.sleep(0.01)
    assert pid_file.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    stat = Path(f"/proc/{pid_file.read_text()}/stat")
    assert not stat.exists() or stat.read_text().split()[2] == "Z"


@pytest.mark.parametrize(
    "payload", [b"malformed", b"[]", b"{}", b'{"type":"result","is_error":true,"result":"secret"}']
)
def test_structured_output_fails_closed(payload):
    with pytest.raises(BotError) as error:
        parse_output("claude-cli", payload)
    assert "secret" not in str(error.value)


def test_codex_tool_use_and_mismatched_session_rejected():
    payload = b"\n".join(
        json.dumps(x).encode()
        for x in [
            {"type": "thread.started", "thread_id": SESSION},
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "cat secrets"},
            },
            {"type": "turn.completed"},
        ]
    )
    with pytest.raises(BotError, match="unsupported tool"):
        parse_output("codex-cli", payload)
    payload = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "text",
            "session_id": SESSION,
        }
    ).encode()
    with pytest.raises(BotError, match="different session"):
        parse_output("claude-cli", payload, "f430c365-ec1b-479f-9a8d-647fd4cdb8a9")


async def test_nonzero_diagnostics_not_forwarded(model):
    model = replace(model, backend=Backend("cli", "claude-cli"), parameters={})

    class Runner:
        async def run(self, *args, **kwargs):
            return await run_process([sys.executable, str(FAKE)], env={"FIXTURE_MODE": "bad"})

    with pytest.raises(BotError) as error:
        await CLIProvider(model, Runner()).complete([Message("user", "prompt")])
    assert "secret" not in str(error.value) and "preserved" in str(error.value)


async def test_docker_preflight_fails_on_rootful_runtime(model, monkeypatch):
    async def fake_run(*args, **kwargs):
        return ProcessResult(0, b'["name=seccomp"]', b"")

    monkeypatch.setattr("src.cli.run_process", fake_run)
    with pytest.raises(BotError, match="rootless"):
        await DockerRunner(model, 10).verify()


@pytest.mark.parametrize(
    "override",
    [
        {"CgroupDriver": "none"},
        {"CgroupVersion": "1"},
        {"MemoryLimit": False},
        {"CpuCfsQuota": False},
        {"PidsLimit": False},
        {"PidsLimit": None},
        {"MemoryLimit": 1},
    ],
)
async def test_rootless_runtime_must_enforce_resource_limits(model, monkeypatch, override):
    runtime = {
        "SecurityOptions": ["name=rootless", "name=seccomp,profile=builtin"],
        "CgroupDriver": "systemd",
        "CgroupVersion": "2",
        "MemoryLimit": True,
        "CpuCfsQuota": True,
        "PidsLimit": True,
        **override,
    }
    calls = []

    async def fake_run(argv, **kwargs):
        calls.append(argv)
        return ProcessResult(0, json.dumps(runtime).encode(), b"")

    monkeypatch.setattr("src.cli.run_process", fake_run)
    runner = DockerRunner(model, 10)
    with pytest.raises(BotError, match="enforced CPU, memory and PID"):
        await runner.verify()
    assert not runner.verified
    assert len(calls) == 1 and calls[0][1] == "info"


async def test_container_boundary_and_cleanup(model, monkeypatch):
    model = replace(
        model,
        backend=Backend(
            "cli",
            "claude-cli",
            api_key_env="CLI_TEST_KEY",
            owner_id=4,
            image="approved@sha256:" + "a" * 64,
            network="isolated",
            cli_version="2.1.263",
            proxy_url="http://egress:3128",
        ),
        parameters={},
    )
    monkeypatch.setenv("CLI_TEST_KEY", "a-test-credential")
    calls = []

    async def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[1] == "run":
            raise asyncio.CancelledError
        return ProcessResult(0, b"", b"")

    monkeypatch.setattr("src.cli.run_process", fake_run)
    runner = DockerRunner(model, 10)
    runner.verified = True
    with pytest.raises(asyncio.CancelledError):
        await runner.run(arguments(model, None), b"untrusted prompt", "a" * 64)
    argv, kwargs = next(call for call in calls if call[0][1] == "run")
    assert "--read-only" in argv and "--cap-drop=ALL" in argv
    assert "65532:65532" in argv and "--security-opt=no-new-privileges" in argv
    assert not any("type=bind" in arg or "/mnt/c" in arg or "docker.sock" in arg for arg in argv)
    assert "a-test-credential" not in str(argv)
    assert kwargs["env"]["ANTHROPIC_API_KEY"] == "a-test-credential"
    assert "DISCORD_BOT_TOKEN" not in kwargs["env"]
    assert calls[-1][0][1:3] == ["rm", "-f"]


async def test_missing_native_session_reconstructs_without_retry(model):
    model = replace(model, backend=Backend("cli", "claude-cli"), parameters={})

    class Runner:
        def __init__(self):
            self.calls = []

        async def has_session(self, conversation_id, native_id):
            assert native_id == SESSION
            return False

        async def run(self, argv, prompt, conversation_id, **kwargs):
            self.calls.append((argv, prompt, kwargs))
            return await run_process([sys.executable, str(FAKE)], stdin=prompt)

    runner = Runner()
    response = await CLIProvider(model, runner).complete(
        [Message("user", "remember"), Message("assistant", "remembered"), Message("user", "next")],
        Session(SESSION, "f"),
        conversation_id="a" * 64,
    )
    assert "reconstructed" in response.notice
    assert len(runner.calls) == 1
    args, prompt, kwargs = runner.calls[0]
    assert "--resume" not in args and b"remembered" in prompt
    assert kwargs["new_session"] is True


async def test_native_volume_cleanup_is_scoped(model, monkeypatch):
    runner = DockerRunner(model, 10, "unique-instance")
    key = "a" * 64
    owned = f"bot-cli-{runner.namespace}-{key}-" + "b" * 16
    calls = []

    async def fake_run(argv, **kwargs):
        calls.append(argv)
        return ProcessResult(0, owned.encode() if "ls" in argv else b"", b"")

    monkeypatch.setattr("src.cli.run_process", fake_run)
    await runner.delete_state(key)
    assert f"label=io.chatgptbot.instance={runner.namespace}" in calls[0]
    assert f"label=io.chatgptbot.scope={key}" in calls[0]
    assert calls[-1] == ["docker", "volume", "rm", owned]


def test_claude_accepts_whitespace_in_single_json_document():
    result = parse_output(
        "claude-cli",
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "answer",
                "session_id": SESSION,
            },
            indent=2,
        ).encode(),
    )
    assert result.text == "answer" and result.session_id == SESSION
