"""Async CLI adapters. Host executables never receive Discord prompts."""

import asyncio
import hashlib
import json
import os
import re
import signal
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from src.cli_accounts import (
    DEVICE_KINDS,
    AccountProfile,
    ChallengeCallback,
    ChallengeReader,
    interactive_process,
    login_arguments,
    logout_arguments,
)
from src.config import Model
from src.domain import BotError, Capability, Completion, Message, Session
from src.providers import text_result

CODEX_DISABLED_CODE_MODE_NOTICE = (
    "Code Mode is unavailable because code-mode host is disabled. "
    "Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`."
)


@dataclass(frozen=True)
class ProcessResult:
    code: int
    stdout: bytes
    stderr: bytes


async def run_process(
    argv: list[str],
    *,
    stdin: bytes = b"",
    env: dict[str, str] | None = None,
    timeout: float = 120,
    maximum: int = 2 * 1024 * 1024,
    observe: Callable[[str, bytes], Awaitable[None]] | None = None,
) -> ProcessResult:
    """Bound both pipes, terminate the process group and reap its leader."""
    if os.name != "posix":
        raise BotError("CLI execution requires the supported Linux runtime.")
    process = None
    tasks: list[asyncio.Task[Any]] = []
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env or {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},
            cwd="/tmp",
            start_new_session=True,
        )

        async def read(stream: asyncio.StreamReader | None, pipe: str) -> bytes:
            assert stream is not None
            output = bytearray()
            while chunk := await stream.read(65536):
                output.extend(chunk)
                if len(output) > maximum:
                    raise BotError("CLI output exceeded the configured limit.")
                if observe:
                    await observe(pipe, chunk)
            return bytes(output)

        async def write() -> None:
            assert process is not None and process.stdin is not None
            try:
                process.stdin.write(stdin)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()

        async with asyncio.timeout(timeout):
            tasks = [
                asyncio.create_task(read(process.stdout, "stdout")),
                asyncio.create_task(read(process.stderr, "stderr")),
                asyncio.create_task(write()),
            ]
            output = await asyncio.gather(*tasks)
            code = await process.wait()
            return ProcessResult(code, output[0], output[1])
    except TimeoutError:
        raise BotError("CLI request timed out; no automatic retry was made.") from None
    except OSError:
        raise BotError("CLI isolation runtime could not be started.") from None
    finally:
        if process is not None:
            # Kill descendants even when their parent has already exited.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def session_id(value: Any) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise BotError("CLI returned an invalid session identifier.") from None


def arguments(model: Model, native_id: str | None) -> list[str]:
    kind = model.backend.kind
    if native_id:
        native_id = session_id(native_id)
    if kind == "claude-cli":
        args = [
            "claude",
            "--safe-mode" if model.backend.auth == "account" else "--bare",
            "--print",
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--permission-mode",
            "dontAsk",
            "--model",
            model.model,
        ]
        if native_id:
            args += ["--resume", native_id]
        return args
    if kind == "grok-cli":
        args = [
            "grok",
            "--prompt-file",
            "/dev/stdin",
            "--output-format",
            "streaming-messages-json",
            "--tools",
            "",
            "--deny",
            "*",
            "--no-subagents",
            "--disable-web-search",
            "--permission-mode",
            "dontAsk",
            "--max-turns",
            "1",
            "--model",
            model.model,
        ]
        if native_id:
            args += ["--resume", native_id]
        return args
    if kind == "codex-cli":
        args = ["codex", "exec"]
        if native_id:
            args += ["resume", native_id]
        args += [
            "--json",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "-c",
            'sandbox_mode="read-only"',
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
        ]
        for feature in (
            "shell_tool",
            "unified_exec",
            "shell_snapshot",
            "apps",
            "multi_agent",
            "skill_mcp_dependency_install",
            "image_generation",
            "view_image",
            "browser_use",
            "browser_use_external",
            "browser_use_full_cdp_access",
            "computer_use",
            "in_app_browser",
            "code_mode_host",
            "plugins",
            "remote_plugin",
            "skill_search",
            "hooks",
            "goals",
            "sleep_tool",
            "workspace_dependencies",
            "unbounded_connection_retries",
        ):
            args += ["-c", f"features.{feature}=false"]
        mode = "chatgpt" if model.backend.auth == "account" else "api"
        args += [
            "-c",
            'shell_environment_policy.inherit="none"',
            "-c",
            f'forced_login_method="{mode}"',
        ]
        if model.backend.auth == "account":
            args += ["-c", 'cli_auth_credentials_store="file"']
        return [*args, "--model", model.model, "-"]
    raise BotError("Unsupported CLI backend.")


def parse_output(kind: str, output: bytes, expected: str | None = None) -> Completion:
    try:
        events = (
            [json.loads(output)]
            if kind == "claude-cli"
            else [json.loads(line) for line in output.splitlines() if line.strip()]
        )
        if not events or any(not isinstance(event, dict) for event in events):
            raise ValueError("invalid events")
        if kind == "claude-cli":
            event = json.loads(output)
            if (
                event.get("type") != "result"
                or event.get("is_error") is not False
                or event.get("subtype") != "success"
            ):
                raise BotError(
                    "CLI failed; check authentication, quota and runtime configuration privately."
                )
            result = Completion(text_result(event["result"]), session_id(event["session_id"]))
        elif kind == "grok-cli":
            # Documented streaming Messages wire format; reject any tool use.
            for event in events:
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") in {"tool_use", "server_tool_use", "tool_result"}:
                        raise BotError("CLI attempted a disabled tool; the result was rejected.")
            finals = [e for e in events if e.get("type") == "result"]
            if (
                len(finals) != 1
                or finals[0].get("is_error") is not False
                or finals[0].get("subtype") != "success"
                or finals[0].get("stop_reason") != "end_turn"
            ):
                raise BotError("Grok CLI result did not match the supported output contract.")
            result = Completion(
                text_result(finals[0]["result"]), session_id(finals[0]["session_id"])
            )
        elif kind == "codex-cli":
            ids = [session_id(e["thread_id"]) for e in events if e.get("type") == "thread.started"]
            if (
                len(ids) != 1
                or sum(e.get("type") == "turn.completed" for e in events) != 1
                or any(e.get("type") in {"error", "turn.failed"} for e in events)
            ):
                raise BotError("Codex did not complete a valid turn.")
            text = []
            for event in events:
                if str(event.get("type", "")).startswith("item."):
                    item = event["item"]
                    if item.get("type") == "error":
                        # Pinned native exec emits this expected startup diagnostic
                        # when our text-only configuration disables Code Mode.
                        if (
                            event["type"] == "item.completed"
                            and set(item) == {"id", "type", "message"}
                            and isinstance(item["id"], str)
                            and re.fullmatch(r"item_\d+", item["id"])
                            and item["message"] == CODEX_DISABLED_CODE_MODE_NOTICE
                        ):
                            continue
                        raise BotError(
                            "Codex reported a runtime error; check the CLI configuration privately."
                        )
                    if item.get("type") not in {"agent_message", "reasoning"}:
                        raise BotError(
                            "Codex attempted an unsupported tool; the result was rejected."
                        )
                    if event["type"] == "item.completed" and item["type"] == "agent_message":
                        text.append(item["text"])
            result = Completion(text_result("\n".join(text)), ids[0])
        else:
            raise BotError("Unsupported CLI output format.")
        if expected and result.session_id != expected:
            raise BotError("CLI resumed a different session; the result was rejected.")
        return result
    except BotError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise BotError("CLI returned malformed structured output.") from None


class DockerRunner:
    def __init__(self, model: Model, timeout: float, namespace: str = "default"):
        self.model, self.timeout = model, timeout
        self.namespace = hashlib.sha256(namespace.encode()).hexdigest()[:16]
        self.verified = False
        self.verify_lock = asyncio.Lock()
        self.profile = AccountProfile(model.backend) if model.backend.auth == "account" else None

    def base(self, name: str, *, network: str = "none") -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--read-only",
            "--user",
            "65532:65532",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=128",
            "--memory=1g",
            "--cpus=1",
            "--network",
            network,
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--workdir",
            "/work",
            "--env",
            "HOME=/state/home",
            "--env",
            "CLAUDE_CONFIG_DIR=/state/claude",
            "--env",
            "CODEX_HOME=/state/codex",
            "--env",
            "XDG_CONFIG_HOME=/state/config",
            "--env",
            "XDG_DATA_HOME=/state/data",
            "--env",
            "GROK_HOME=/state/grok",
            "--env",
            "ENABLE_CLAUDEAI_MCP_SERVERS=false",
            "--env",
            "CLAUDE_CODE_DISABLE_ARTIFACT=1",
        ]

    def proxy_environment(self) -> list[str]:
        return [
            "--env",
            f"HTTPS_PROXY={self.model.backend.proxy_url}",
            "--env",
            f"HTTP_PROXY={self.model.backend.proxy_url}",
        ]

    @asynccontextmanager
    async def account_guard(self, *, require_login: bool = True) -> AsyncIterator[None]:
        if self.profile is None:
            yield
        else:
            async with self.profile.lease(require_login=require_login):
                yield

    async def docker(self, argv: list[str], **kwargs: Any) -> ProcessResult:
        env = dict(kwargs.pop("env", {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}))
        env["DOCKER_HOST"] = "unix://" + self.model.backend.docker_socket
        return await run_process(argv, env=env, **kwargs)

    async def delete_state(self, conversation_id: str) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", conversation_id):
            raise BotError("Invalid isolated conversation identity.")
        result = await self.docker(
            [
                "docker",
                "volume",
                "ls",
                "--filter",
                f"label=io.chatgptbot.instance={self.namespace}",
                "--filter",
                f"label=io.chatgptbot.scope={conversation_id}",
                "--format",
                "{{.Name}}",
            ],
            timeout=15,
        )
        if result.code:
            raise BotError("Isolated CLI transcript cleanup needs administrator attention.")
        for volume in result.stdout.decode().splitlines():
            if not re.fullmatch(
                rf"bot-cli-{self.namespace}-{conversation_id}-[a-f0-9]{{16}}", volume
            ):
                raise BotError("Unexpected CLI volume identity; cleanup stopped.")
            removed = await self.docker(["docker", "volume", "rm", volume], timeout=15)
            if removed.code:
                raise BotError("An isolated CLI transcript volume could not be deleted.")

    async def prune_state(self, retained: set[str]) -> None:
        result = await self.docker(
            [
                "docker",
                "volume",
                "ls",
                "--filter",
                f"label=io.chatgptbot.instance={self.namespace}",
                "--format",
                "{{.Name}}",
            ],
            timeout=15,
        )
        if result.code:
            raise BotError("CLI retention cleanup could not contact its isolated runtime.")
        stale = set()
        for name in result.stdout.decode().splitlines():
            match = re.fullmatch(rf"bot-cli-{self.namespace}-([a-f0-9]{{64}})-[a-f0-9]{{16}}", name)
            if not match:
                raise BotError("Unexpected CLI volume name; cleanup stopped.")
            if match[1] not in retained:
                stale.add(match[1])
        for key in stale:
            await self.delete_state(key)

    async def cleanup(self, name: str, *, graceful: bool = False) -> None:
        if graceful:
            # Give the native CLI and credential persistence helper time to flush a refresh.
            try:
                await self.docker(["docker", "stop", "--time", "5", name], timeout=10)
            except BotError:
                pass  # Still attempt forced removal when graceful shutdown is unavailable.
        result = await self.docker(["docker", "rm", "-f", name], timeout=10)
        if result.code and b"No such container" not in result.stderr:
            self.verified = False
            raise BotError(
                "CLI container cleanup could not be confirmed; administrator attention is required."
            )

    async def verify(self) -> None:
        async with self.verify_lock:
            if self.verified:
                return
            backend = self.model.backend
            info = await self.docker(["docker", "info", "--format", "{{json .}}"], timeout=15)
            try:
                runtime = json.loads(info.stdout)
                options = runtime["SecurityOptions"]
                if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
                    raise ValueError("options")
            except (ValueError, KeyError, TypeError):
                raise BotError("CLI backends require a verified rootless Docker daemon.") from None
            if info.code or "name=rootless" not in options:
                raise BotError("CLI backends require a rootless Docker daemon.")
            if not any(o.startswith("name=seccomp,profile=") for o in options) or any(
                "unconfined" in o for o in options
            ):
                raise BotError("CLI runtime requires an active seccomp profile.")
            if (
                runtime.get("CgroupDriver") != "systemd"
                or runtime.get("CgroupVersion") != "2"
                or any(
                    runtime.get(field) is not True
                    for field in ("MemoryLimit", "CpuCfsQuota", "PidsLimit")
                )
            ):
                raise BotError(
                    "CLI runtime requires cgroup v2 with systemd and enforced CPU, memory and PID limits."
                )
            network = await self.docker(
                ["docker", "network", "inspect", backend.network], timeout=15
            )
            try:
                if network.code or json.loads(network.stdout)[0]["Internal"] is not True:
                    raise ValueError("network")
            except (ValueError, KeyError, IndexError, TypeError):
                raise BotError(
                    "CLI egress network must be an internal Docker network with an administrator-controlled API proxy."
                ) from None
            image = await self.docker(["docker", "image", "inspect", backend.image], timeout=15)
            try:
                config = json.loads(image.stdout)[0]["Config"]
                if (
                    image.code
                    or config["Labels"]["io.chatgptbot.cli"] != backend.kind
                    or config.get("Volumes")
                    or (
                        backend.auth == "account"
                        and config["Labels"].get("io.chatgptbot.account-auth") != "1"
                    )
                ):
                    raise ValueError("image")
            except (ValueError, KeyError, IndexError, TypeError):
                raise BotError(
                    "CLI image is missing, has implicit volumes, or lacks the required runtime label."
                ) from None
            binary = arguments(self.model, None)[0]
            probes = [
                (["--version"], [backend.cli_version]),
                (
                    ["--help"],
                    {
                        "claude": [
                            "--safe-mode" if backend.auth == "account" else "--bare",
                            "--tools",
                            "--resume",
                            "--output-format",
                            "--strict-mcp-config",
                        ],
                        "grok": [
                            "--prompt-file",
                            "--tools",
                            "--deny",
                            "--resume",
                            "streaming-messages-json",
                        ],
                        "codex": ["exec"],
                    }[binary],
                ),
            ]
            if binary == "codex":
                probes.extend(
                    [
                        (
                            ["exec", "--help"],
                            [
                                "--json",
                                "--ignore-user-config",
                                "--ignore-rules",
                                "--skip-git-repo-check",
                            ],
                        ),
                        (["exec", "resume", "--help"], ["SESSION_ID", "--json", "--model"]),
                    ]
                )
            if backend.auth == "account":
                probes.append(
                    (
                        ["auth", "login", "--help"] if binary == "claude" else ["login", "--help"],
                        ["--claudeai"] if binary == "claude" else ["--device-auth"],
                    )
                )
            for flags, required in probes:
                name = "bot-probe-" + uuid.uuid4().hex
                try:
                    result = await self.docker(
                        [
                            *self.base(name),
                            "--tmpfs",
                            "/state:rw,nosuid,size=32m,uid=65532,gid=65532",
                            "--entrypoint",
                            binary,
                            backend.image,
                            *flags,
                        ],
                        timeout=20,
                    )
                    if result.code or any(
                        token.encode() not in result.stdout for token in required
                    ):
                        raise BotError(
                            "CLI version/help does not match the configured contract; backend remains disabled."
                        )
                finally:
                    await self.cleanup(name)
            self.verified = True

    async def account_status(self) -> bool:
        assert self.profile is not None
        inspected = await self.docker(
            ["docker", "volume", "inspect", self.profile.volume], timeout=15
        )
        if inspected.code:
            return False
        name = "bot-account-status-" + uuid.uuid4().hex
        try:
            result = await self.docker(
                [
                    *self.base(name),
                    "--mount",
                    f"type=volume,source={self.profile.volume},target=/account,readonly",
                    "--entrypoint",
                    "node",
                    self.model.backend.image,
                    "/opt/chatgptbot/account-runtime.mjs",
                    "status",
                    self.model.backend.kind,
                ],
                timeout=20,
            )
            if result.code or result.stdout not in {b"present", b"missing"}:
                raise BotError("Could not inspect native CLI login state safely.")
            return result.stdout == b"present"
        finally:
            await self.cleanup(name)

    async def account_action(
        self, action: str, on_challenge: ChallengeCallback | None = None
    ) -> dict[str, Any]:
        if self.profile is None or action not in {"login", "status", "logout"}:
            raise BotError("Unsupported CLI account operation.")
        if on_challenge and (action != "login" or self.model.backend.kind not in DEVICE_KINDS):
            raise BotError("This CLI requires local native terminal login.")
        async with self.account_guard(require_login=False):
            await self.verify()
            if action == "status":
                return {
                    "configured": self.profile.configured() and await self.account_status(),
                    "provider_verified": False,
                }
            # Rotate before any native account change; a failed/aborted login stays disabled.
            self.profile.record(False)
            created = await self.docker(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    "io.chatgptbot.account-auth=1",
                    "--label",
                    f"io.chatgptbot.account={self.profile.binding}",
                    self.profile.volume,
                ],
                timeout=15,
            )
            if created.code:
                raise BotError("Could not create isolated CLI login storage.")
            command = (
                login_arguments(self.model.backend.kind)
                if action == "login"
                else logout_arguments(self.model.backend.kind)
            )
            name = "bot-account-login-" + uuid.uuid4().hex
            argv = [
                *self.base(name, network=self.model.backend.network),
                *self.proxy_environment(),
                "--mount",
                f"type=volume,source={self.profile.volume},target=/state",
                *(["-it"] if action == "login" and on_challenge is None else []),
                "--entrypoint",
                command[0],
                self.model.backend.image,
                *command[1:],
            ]
            try:
                if action == "login" and on_challenge:
                    reader = ChallengeReader(self.model.backend.kind, on_challenge)
                    result = await self.docker(argv, timeout=600, maximum=65536, observe=reader)
                    code = result.code
                    if code == 0 and not reader.delivered:
                        raise BotError(
                            "Native CLI did not produce a supported device login prompt."
                        )
                elif action == "login":
                    code = await interactive_process(
                        argv,
                        {
                            "PATH": "/usr/local/bin:/usr/bin:/bin",
                            "LANG": "C.UTF-8",
                            "DOCKER_HOST": "unix://" + self.model.backend.docker_socket,
                        },
                    )
                else:
                    code = (await self.docker(argv, timeout=60)).code
            finally:
                await self.cleanup(name, graceful=True)
            if code:
                raise BotError(
                    "Native CLI account operation failed; account mode stays disabled. Use the local login command to recover."
                )
            if action == "login":
                if not await self.account_status():
                    raise BotError("Native CLI login did not create usable local credentials.")
                self.profile.record(True, rotate=False)
            elif await self.account_status():
                raise BotError(
                    "Native CLI logout did not clear credentials; administrator attention is required."
                )
            return {"configured": action == "login", "provider_verified": False}

    async def has_session(self, conversation_id: str, native_id: str) -> bool:
        await self.verify()
        native_id = session_id(native_id)
        if not re.fullmatch(r"[a-f0-9]{64}", conversation_id):
            raise BotError("Invalid isolated conversation identity.")
        volume = f"bot-cli-{self.namespace}-{conversation_id}-{self.model.fingerprint()[:16]}"
        inspected = await self.docker(["docker", "volume", "inspect", volume], timeout=15)
        if inspected.code:
            return False
        # A fixed helper examines only names inside this conversation's volume.
        # No credentials, networking, symlink traversal, or transcript output.
        script = """const fs=require('fs'); let count=0, found=false;
const walk=(p)=>{ for(const e of fs.readdirSync(p,{withFileTypes:true})) {
if(++count>10000) process.exit(2); if(e.name.includes(process.argv[1])) found=true;
if(e.isDirectory()) walk(p+'/'+e.name); }};
walk('/state'); process.stdout.write(found ? 'present' : 'missing');"""
        name = "bot-session-" + uuid.uuid4().hex
        try:
            result = await self.docker(
                [
                    *self.base(name),
                    "--mount",
                    f"type=volume,source={volume},target=/state,readonly",
                    "--entrypoint",
                    "node",
                    self.model.backend.image,
                    "-e",
                    script,
                    native_id,
                ],
                timeout=20,
            )
            if result.code or result.stdout not in {b"present", b"missing"}:
                raise BotError("Could not verify the isolated native session.")
            return result.stdout == b"present"
        finally:
            await self.cleanup(name)

    async def run(
        self, argv: list[str], prompt: bytes, conversation_id: str, *, new_session: bool = False
    ) -> ProcessResult:
        if self.profile and (
            self.profile.holder is not asyncio.current_task() or not self.profile.configured()
        ):
            raise BotError(
                "CLI account execution requires an active account lease and local login."
            )
        await self.verify()
        if not re.fullmatch(r"[a-f0-9]{64}", conversation_id):
            raise BotError("Invalid isolated conversation identity.")
        if new_session:
            await self.delete_state(conversation_id)
        backend = self.model.backend
        name = "bot-cli-" + uuid.uuid4().hex
        volume = f"bot-cli-{self.namespace}-{conversation_id}-{self.model.fingerprint()[:16]}"
        created = await self.docker(
            [
                "docker",
                "volume",
                "create",
                "--label",
                f"io.chatgptbot.instance={self.namespace}",
                "--label",
                f"io.chatgptbot.scope={conversation_id}",
                volume,
            ],
            timeout=15,
        )
        if created.code:
            raise BotError("Could not create isolated CLI session storage.")
        # Only the provider credential enters the container; no inherited host HOME or config.
        credential = {
            "claude-cli": "ANTHROPIC_API_KEY",
            "codex-cli": "CODEX_API_KEY",
            "grok-cli": "XAI_API_KEY",
        }[backend.kind]
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
        auth_options = []
        command = argv
        if self.profile:
            if self.profile.holder is not asyncio.current_task() or not self.profile.configured():
                raise BotError(
                    "CLI account execution requires an active account lease and local login."
                )
            auth_options = ["--mount", f"type=volume,source={self.profile.volume},target=/account"]
            command = ["node", "/opt/chatgptbot/account-runtime.mjs", "run", backend.kind, *argv]
        else:
            env[credential] = backend.key()
            auth_options = ["--env", credential]
        args = [
            *self.base(name, network=backend.network),
            "-i",
            "--mount",
            f"type=volume,source={volume},target=/state",
            *auth_options,
            *self.proxy_environment(),
            "--entrypoint",
            command[0],
            backend.image,
            *command[1:],
        ]
        try:
            return await self.docker(args, stdin=prompt, env=env, timeout=self.timeout)
        finally:
            # Killing the docker client alone does not stop the container.
            await self.cleanup(name, graceful=self.profile is not None)


class CLIProvider:
    def __init__(self, model: Model, runner: DockerRunner):
        self.model, self.runner = model, runner

    @asynccontextmanager
    async def auth_guard(self) -> AsyncIterator[None]:
        if self.model.backend.auth == "account":
            async with self.runner.account_guard():
                yield
        else:
            yield

    async def complete(
        self, messages: list[Message], session: Session | None = None, *, conversation_id: str = ""
    ) -> Completion:
        async with self.auth_guard():
            return await self._complete(messages, session, conversation_id=conversation_id)

    async def _complete(
        self, messages: list[Message], session: Session | None = None, *, conversation_id: str = ""
    ) -> Completion:
        self.model.require(Capability.CHAT)
        native = session.id if session else None
        notice = None
        if native and not await self.runner.has_session(conversation_id, native):
            native = None
            notice = (
                "Native session was missing; context was reconstructed from retained bot history."
            )
        # A fresh native session receives the bot's retained text transcript exactly once.
        prompt = (
            messages[-1].content
            if native
            else "Continue this conversation. The following JSON contains prior roles and the newest user turn:\n"
            + json.dumps([m.__dict__ for m in messages], ensure_ascii=False)
        )
        result = await self.runner.run(
            arguments(self.model, native),
            prompt.encode(),
            conversation_id,
            new_session=native is None,
        )
        if result.code:
            raise BotError(
                "CLI failed; history is preserved. Check authentication, session availability and quota privately; account users can run local cli-auth login again. No billing mode was changed. The next request will reconstruct context."
            )
        parsed = parse_output(self.model.backend.kind, result.stdout, native)
        return Completion(parsed.text, parsed.session_id, notice)

    async def delete_state(self, conversation_id: str) -> None:
        await self.runner.delete_state(conversation_id)

    async def prune_state(self, retained: set[str]) -> None:
        await self.runner.prune_state(retained)

    async def close(self) -> None:
        return None
