"""Local administration of native CLI login. The Python bot never reads OAuth tokens."""

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlsplit

from src.domain import BotError

if TYPE_CHECKING:
    from src.config import Backend


@dataclass(frozen=True, repr=False)
class DeviceChallenge:
    url: str
    code: str


ChallengeCallback = Callable[[DeviceChallenge], Awaitable[None]]
DEVICE_KINDS = {"codex-cli", "grok-cli"}


class ChallengeReader:
    """Extract only the native device prompt; never forward raw CLI output."""

    def __init__(self, kind: str, callback: ChallengeCallback):
        if kind not in DEVICE_KINDS:
            raise BotError("This CLI needs its native local terminal login.")
        self.kind, self.callback = kind, callback
        self.buffer = bytearray()
        self.delivered = False

    async def __call__(self, pipe: str, chunk: bytes) -> None:
        expected = "stdout" if self.kind == "codex-cli" else "stderr"
        if pipe != expected or self.delivered:
            return
        self.buffer.extend(chunk)
        if len(self.buffer) > 65536:
            raise BotError("Native login output exceeded the supported limit.")
        content = self.buffer.decode("utf-8", errors="replace")
        content = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", content)
        if self.kind == "codex-cli":
            pattern = (
                r"Open this link in your browser[^\n]*\n\s*(https?://[^\s]+)\s*\n"
                r"\s*2\. Enter this one-time code[^\n]*\n[ \t]*([A-Za-z0-9-]{6,32})[ \t]*\r?\n"
            )
        else:
            pattern = (
                r"To sign in, open this URL in your browser:\s*\n\s*(https?://[^\s]+)\s*\n"
                r"(?:[^\n]*\n)*?(?:Confirm this code in your browser:|Then enter this code:)"
                r"\s*\n[ \t]*([A-Za-z0-9-]{6,32})[ \t]*\r?\n"
            )
        match = re.search(pattern, content)
        if not match:
            return
        url, code = match.groups()
        try:
            parsed = urlsplit(url)
            destinations = (
                {("auth.openai.com", "/codex/device")}
                if self.kind == "codex-cli"
                else {
                    ("auth.x.ai", "/device"),
                    ("auth.x.ai", "/oauth2/device"),
                    ("accounts.x.ai", "/oauth2/device"),
                }
            )
            query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
            if (
                parsed.scheme != "https"
                or (parsed.netloc, parsed.path) not in destinations
                or parsed.fragment
                or (self.kind == "codex-cli" and (parsed.path != "/codex/device" or query))
                or (self.kind == "grok-cli" and query not in ([], [("user_code", code)]))
            ):
                raise ValueError("origin")
        except ValueError:
            raise BotError("Native CLI returned an unsupported authorization URL.") from None
        self.delivered = True
        self.buffer.clear()
        try:
            await self.callback(DeviceChallenge(url, code))
        except asyncio.CancelledError:
            raise
        except Exception:
            raise BotError(
                "Could not deliver login instructions privately; login was cancelled."
            ) from None


class AccountProfile:
    def __init__(self, backend: "Backend"):
        self.path = Path(backend.auth_profile)
        binding = [
            backend.name,
            backend.kind,
            backend.owner_id,
            backend.account,
            backend.docker_socket,
        ]
        self.binding = hashlib.sha256(json.dumps(binding).encode()).hexdigest()
        self.volume = (
            "bot-account-"
            + hashlib.sha256((str(self.path.resolve()) + self.binding).encode()).hexdigest()[:32]
        )
        self.holder: asyncio.Task[Any] | None = None

    def _read(self) -> dict[str, Any] | None:
        path = self.path / "profile.json"
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError:
            raise BotError(
                "CLI login metadata is unavailable; use the local cli-auth command."
            ) from None
        try:
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
                    raise ValueError("metadata")
                data = json.load(stream)
            if (
                data["binding"] != self.binding
                or type(data["configured"]) is not bool
                or uuid.UUID(hex=data["revision"]).hex != data["revision"]
            ):
                raise ValueError("identity")
            return data
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise BotError(
                "CLI login profile is invalid or belongs to another account configuration."
            ) from None

    def revision(self) -> str:
        data = self._read()
        return data["revision"] if data else "unconfigured"

    def configured(self) -> bool:
        data = self._read()
        return bool(data and data["configured"])

    def record(self, configured: bool, *, rotate: bool = True) -> None:
        if self.holder is not asyncio.current_task():
            raise RuntimeError("Account profile mutation requires its lease")
        data = {
            "binding": self.binding,
            "revision": uuid.uuid4().hex if rotate else self.revision(),
            "configured": configured,
        }
        temporary = self.path / (".profile-" + uuid.uuid4().hex)
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path / "profile.json")
            directory = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    @asynccontextmanager
    async def lease(self, *, require_login: bool = False) -> AsyncIterator[None]:
        task = asyncio.current_task()
        if task is not None and self.holder is task:
            if require_login and not self.configured():
                raise BotError(
                    "CLI account is not signed in; run the local cli-auth login command."
                )
            yield
            return
        try:
            self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
            info = self.path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise BotError(
                    "CLI auth_profile must be a private directory owned by the bot user (0700)."
                )
            descriptor = os.open(
                self.path / "lease.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
        except OSError:
            raise BotError(
                "CLI account lease is unavailable; check local directory permissions."
            ) from None
        try:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.05)
            self.holder = task
            if any(p.name not in {"lease.lock", "profile.json"} for p in self.path.iterdir()):
                raise BotError(
                    "CLI auth_profile is reserved for bot metadata; use a separate empty directory."
                )
            self._read()  # Reject owner/configuration changes before touching credentials.
            if require_login and not self.configured():
                raise BotError(
                    "CLI account is not signed in; run the local cli-auth login command."
                )
            yield
        finally:
            if self.holder is task:
                self.holder = None
            os.close(descriptor)


def login_arguments(kind: str) -> list[str]:
    return {
        "codex-cli": [
            "codex",
            "login",
            "--device-auth",
            "-c",
            'cli_auth_credentials_store="file"',
            "-c",
            'forced_login_method="chatgpt"',
        ],
        "claude-cli": ["claude", "auth", "login", "--claudeai"],
        "grok-cli": ["grok", "login", "--device-auth"],
    }[kind]


def logout_arguments(kind: str) -> list[str]:
    return {
        "codex-cli": ["codex", "logout", "-c", 'cli_auth_credentials_store="file"'],
        "claude-cli": ["claude", "auth", "logout"],
        "grok-cli": ["grok", "logout"],
    }[kind]


async def interactive_process(argv: list[str], env: dict[str, str], timeout: float = 600) -> int:
    """Only the private local terminal sees the official CLI authorization UI."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise BotError(
            "CLI login needs a private interactive terminal; it cannot run from Discord or CI."
        )
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, env=env, cwd="/tmp", start_new_session=True
        )
        async with asyncio.timeout(timeout):
            return await process.wait()
    except TimeoutError:
        raise BotError("CLI login timed out; run the local login command again.") from None
    except OSError:
        raise BotError("Could not start the isolated CLI login runtime.") from None
    finally:
        if process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


async def administer(config: Path, model_name: str, action: str) -> dict[str, Any]:
    from src.cli import DockerRunner
    from src.config import load_settings

    settings = load_settings(config)
    model = settings.models.get(model_name)
    if model is None or model.backend.auth != "account":
        raise BotError("Choose a configured CLI model with auth = 'account'.")
    runner = DockerRunner(model, settings.request_timeout, str(settings.database.resolve()))
    return await runner.account_action(action)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["login", "status", "logout"])
    parser.add_argument("model", help="Administrator-configured CLI model alias")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    os.umask(0o077)
    try:

        async def run() -> dict[str, Any]:
            async with asyncio.timeout(600):
                return await administer(args.config, args.model, args.action)

        print(json.dumps(asyncio.run(run())))
    except (BotError, TimeoutError) as error:
        print(str(error) or "CLI account operation timed out.", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception:
        print(
            "CLI account operation failed; check the isolated runtime privately.", file=sys.stderr
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
