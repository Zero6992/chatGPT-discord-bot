"""Strict administrator-owned configuration. Discord selects aliases only."""

import hashlib
import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.domain import BotError, Capability

OFFICIAL_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "xai": "https://api.x.ai/v1",
    "deepseek": "https://api.deepseek.com",
}
CLI_KINDS = {"claude-cli", "codex-cli", "grok-cli"}
LEGACY_ENV = {
    "BING_COOKIE",
    "GOOGLE_PSID",
    "OPENAI_ENABLED",
    "OPENAI_KEY",
    "CLAUDE_KEY",
    "GEMINI_KEY",
    "GROK_KEY",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL",
    "MODEL",
    "OPENAI_TEMPERTUARES",
    "REPLYING_ALL",
    "REPLYING_ALL_DISCORD_CHANNEL_ID",
    "MAX_CONVERSATION_LENGTH",
    "CONVERSATION_TRIM_SIZE",
    "DISCORD_CHANNEL_ID",
    "LOGGING",
    "ADMIN_USER_IDS",
}
CHAT_PARAMS = {
    "openai": {"max_output_tokens", "reasoning_effort"},
    "xai": {"max_output_tokens", "reasoning_effort"},
    "anthropic": {"max_output_tokens"},
    "gemini": {"max_output_tokens", "temperature", "top_p"},
    "deepseek": {"max_output_tokens", "reasoning_effort", "thinking"},
    "compatible": {"max_output_tokens", "temperature", "top_p"},
    **{kind: set() for kind in CLI_KINDS},
}


@dataclass(frozen=True)
class Backend:
    name: str
    kind: str
    base_url: str = ""
    api_key_env: str = ""
    account: str = "default"
    auth: str = "api"
    owner_id: int = 0
    image: str = ""
    network: str = ""
    cli_version: str = ""
    proxy_url: str = ""
    docker_socket: str = ""
    auth_profile: str = ""

    def key(self) -> str:
        value = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if self.auth == "api" and not value:
            raise BotError(f"Backend {self.name} needs its configured API credential.")
        return value


@dataclass(frozen=True)
class Model:
    name: str
    backend: Backend
    model: str
    capabilities: frozenset[Capability]
    parameters: dict[str, Any] = field(default_factory=dict)

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise BotError(f"Model {self.name} does not support {capability.value}.")

    def fingerprint(self) -> str:
        # Rotating a credential/account/endpoint must invalidate native sessions.
        identity = [self.backend.__dict__, self.model, self.parameters, self.backend.key()]
        if self.backend.auth == "account":
            from src.cli_accounts import AccountProfile

            identity.append(AccountProfile(self.backend).revision())
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Settings:
    models: dict[str, Model]
    default_model: str
    database: Path = Path("data/conversations.sqlite3")
    context_bytes: int = 24000
    max_turns: int = 100
    retention_days: int = 30
    max_conversations: int = 10000
    max_jobs: int = 1000
    concurrency: int = 4
    max_pending: int = 32
    request_timeout: float = 180
    media_timeout: float = 600
    poll_interval: float = 10
    attachment_bytes: int = 8 * 1024 * 1024
    input_chars: int = 4000
    reply_channels: tuple[int, ...] = ()
    allowed_user_ids: tuple[int, ...] = ()
    admin_user_ids: tuple[int, ...] = ()
    system_prompt: str = "You are a helpful assistant."


def _keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    if set(data) - allowed:
        raise BotError(f"Unknown {label} configuration field; see docs/migration.md.")


def load_settings(path: Path) -> Settings:
    if any(os.environ.get(key) for key in LEGACY_ENV) or any(
        key.startswith("G4F_") for key in os.environ
    ):
        raise BotError("Outdated environment configuration; follow docs/migration.md.")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        _keys(data, {"bot", "backends", "models"}, "root")
        backends = {}
        for name, values in data["backends"].items():
            _keys(values, set(Backend.__dataclass_fields__) - {"name"}, "backend")
            kind = values["kind"]
            if kind not in {*OFFICIAL_URLS, "compatible", *CLI_KINDS}:
                raise BotError("Unsupported backend kind; see docs/migration.md.")
            backend = Backend(name=name, **values)
            url = backend.base_url or OFFICIAL_URLS.get(kind, "")
            backend = Backend(**{**backend.__dict__, "base_url": url.rstrip("/")})
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
                raise BotError(
                    "Backend aliases must be short letters, numbers, underscores or hyphens."
                )
            if kind in CLI_KINDS:
                if (
                    backend.auth not in {"api", "account"}
                    or type(backend.owner_id) is not int
                    or backend.owner_id <= 0
                ):
                    raise BotError(
                        "CLI backends require API authentication or account login, and one explicit owner."
                    )
                if backend.auth == "account":
                    if backend.api_key_env or not backend.auth_profile or backend.base_url:
                        raise BotError(
                            "Account login requires auth_profile and must not configure API keys or endpoints."
                        )
                    profile = (path.parent / backend.auth_profile).absolute()
                    backend = Backend(**{**backend.__dict__, "auth_profile": str(profile)})
                if not re.fullmatch(r"(?:[a-zA-Z0-9./:_-]+@)?sha256:[a-f0-9]{64}", backend.image):
                    raise BotError(
                        "CLI backends require an administrator-built image pinned by digest."
                    )
                if not re.fullmatch(r"[a-zA-Z0-9_-]+", backend.network) or not backend.cli_version:
                    raise BotError(
                        "CLI backends require an isolated internal proxy network and version."
                    )
                if not re.fullmatch(r"/run/user/[0-9]+/docker\.sock", backend.docker_socket):
                    raise BotError("CLI backends require an explicit rootless Docker socket.")
                proxy = urlsplit(backend.proxy_url)
                if (
                    proxy.scheme != "http"
                    or not proxy.hostname
                    or proxy.username
                    or proxy.password
                    or proxy.path not in {"", "/"}
                    or proxy.query
                    or proxy.fragment
                ):
                    raise BotError("CLI backends require an internal HTTP CONNECT proxy URL.")
            else:
                parsed = urlsplit(url)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise BotError("Invalid administrator base URL.")
                if kind != "compatible" and url.rstrip("/") != OFFICIAL_URLS[kind]:
                    raise BotError(
                        "Official backends use official origins; configure custom servers as compatible."
                    )
                if parsed.scheme != "https" and parsed.hostname not in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }:
                    raise BotError("Remote custom endpoints require HTTPS.")
                if backend.auth not in ({"api", "none"} if kind == "compatible" else {"api"}):
                    raise BotError("Unsupported authentication mode.")
            if backend.auth == "api" and not re.fullmatch(r"[A-Z][A-Z0-9_]*", backend.api_key_env):
                raise BotError("API backends require an environment variable name for credentials.")
            if backend.auth == "none" and backend.api_key_env:
                raise BotError("No-key endpoints must not specify a credential variable.")
            if backend.auth != "account" and backend.auth_profile:
                raise BotError("auth_profile is only supported for CLI account login.")
            backends[name] = backend
        models = {}
        for name, values in data["models"].items():
            _keys(values, {"backend", "model", "capabilities", "parameters"}, "model")
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
                raise BotError("Invalid model alias.")
            backend = backends[values["backend"]]
            caps = frozenset(Capability(x) for x in values["capabilities"])
            if not caps or not isinstance(values["model"], str) or not values["model"].strip():
                raise BotError("A model needs an explicit ID and capabilities.")
            implemented = {Capability.CHAT}
            if backend.kind == "openai":
                implemented |= {Capability.TEXT_TO_IMAGE, Capability.IMAGE_TO_IMAGE}
            if backend.kind == "gemini":
                implemented |= {Capability.TEXT_TO_VIDEO, Capability.IMAGE_TO_VIDEO}
            if backend.kind == "xai":
                implemented |= {Capability.TEXT_TO_VIDEO, Capability.IMAGE_SEARCH}
            if not caps <= implemented or (
                caps & {Capability.CHAT, Capability.IMAGE_SEARCH} and len(caps) != 1
            ):
                raise BotError(
                    "Unsupported capability combination; configure separate chat/search/media aliases."
                )
            params = values.get("parameters", {})
            allowed = (
                {"max_output_tokens", "max_turns"}
                if Capability.IMAGE_SEARCH in caps
                else CHAT_PARAMS[backend.kind]
                if Capability.CHAT in caps
                else (
                    {"size", "quality"}
                    if backend.kind == "openai"
                    else (
                        {"aspect_ratio", "duration_seconds", "resolution"}
                        if backend.kind == "xai"
                        else {"aspect_ratio", "duration_seconds"}
                    )
                )
            )
            if set(params) - allowed:
                raise BotError(f"Unsupported parameters for model {name}.")
            if "max_turns" in params and (
                type(params["max_turns"]) is not int or not 1 <= params["max_turns"] <= 3
            ):
                raise BotError("Image search max_turns must be an integer between 1 and 3.")
            if "max_output_tokens" in params and (
                type(params["max_output_tokens"]) is not int
                or not 1 <= params["max_output_tokens"] <= 32768
            ):
                raise BotError("max_output_tokens must be an integer between 1 and 32768.")
            for key, maximum in (("temperature", 2), ("top_p", 1)):
                if key in params and (
                    type(params[key]) not in (int, float) or not 0 <= params[key] <= maximum
                ):
                    raise BotError(f"Invalid {key} parameter.")
            if "reasoning_effort" in params and params["reasoning_effort"] not in {
                "low",
                "medium",
                "high",
            }:
                raise BotError("Unsupported reasoning effort.")
            if "thinking" in params and params["thinking"] not in {"enabled", "disabled"}:
                raise BotError("Invalid thinking parameter.")
            if "size" in params and params["size"] not in {
                "auto",
                "1024x1024",
                "1536x1024",
                "1024x1536",
            }:
                raise BotError("Unsupported image size.")
            if "quality" in params and params["quality"] not in {"auto", "low", "medium", "high"}:
                raise BotError("Unsupported image quality.")
            if "aspect_ratio" in params and params["aspect_ratio"] not in {"16:9", "9:16"}:
                raise BotError("Unsupported video aspect ratio.")
            durations = set(range(1, 16)) if backend.kind == "xai" else {4, 6, 8}
            if "duration_seconds" in params and (
                type(params["duration_seconds"]) is not int
                or params["duration_seconds"] not in durations
            ):
                raise BotError("Unsupported video duration.")
            if "resolution" in params and params["resolution"] not in {"480p", "720p"}:
                raise BotError("Unsupported video resolution.")
            models[name] = Model(name, backend, values["model"], caps, params)
        bot = data["bot"]
        _keys(bot, set(Settings.__dataclass_fields__) - {"models"}, "bot")
        bot["database"] = path.parent / bot.get("database", "data/conversations.sqlite3")
        for key in ("reply_channels", "allowed_user_ids", "admin_user_ids"):
            bot[key] = tuple(bot.get(key, []))
            if any(type(x) is not int or x <= 0 for x in bot[key]):
                raise BotError(f"{key} must contain positive Discord IDs.")
        settings = Settings(models=models, **bot)
        account_backends = [backend for backend in backends.values() if backend.auth == "account"]
        if any(settings.allowed_user_ids != (backend.owner_id,) for backend in account_backends):
            raise BotError(
                "CLI account login requires a personal bot: allowed_user_ids must contain only the account owner."
            )
        profiles = [str(Path(backend.auth_profile).resolve()) for backend in account_backends]
        if len(profiles) != len(set(profiles)):
            raise BotError(
                "Each CLI backend needs its own auth_profile; model aliases may share a backend."
            )
        if settings.default_model not in models:
            raise BotError("Default model alias is not configured.")
        models[settings.default_model].require(Capability.CHAT)
        for key in (
            "context_bytes",
            "max_turns",
            "retention_days",
            "max_conversations",
            "max_jobs",
            "concurrency",
            "max_pending",
            "attachment_bytes",
            "input_chars",
        ):
            if type(getattr(settings, key)) is not int or getattr(settings, key) <= 0:
                raise BotError(f"{key} must be a positive integer.")
        if (
            settings.max_pending < settings.concurrency
            or settings.attachment_bytes > 25 * 1024 * 1024
        ):
            raise BotError("Invalid concurrency or attachment bounds.")
        for key in ("request_timeout", "media_timeout", "poll_interval"):
            if not 0 < getattr(settings, key) <= 600:
                raise BotError(f"{key} must be between zero and 600 seconds.")
        if (
            not isinstance(settings.system_prompt, str)
            or len(settings.system_prompt.encode()) >= settings.context_bytes
        ):
            raise BotError("System prompt exceeds context budget.")
        return settings
    except BotError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BotError("Invalid configuration; see config.example.toml.") from exc
