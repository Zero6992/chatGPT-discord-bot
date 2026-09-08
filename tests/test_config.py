from pathlib import Path

import pytest

from src.config import load_settings
from src.domain import BotError, Capability

EXAMPLE = Path("config.example.toml").read_text()


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_example_and_local(tmp_path):
    settings = load_settings(write(tmp_path, EXAMPLE))
    assert settings.models["local"].backend.auth == "none"
    assert settings.models["local"].backend.key() == ""
    assert settings.models["image"].capabilities == {
        Capability.TEXT_TO_IMAGE,
        Capability.IMAGE_TO_IMAGE,
    }
    assert settings.models["video"].capabilities == {
        Capability.TEXT_TO_VIDEO,
        Capability.IMAGE_TO_VIDEO,
    }
    assert settings.database.parent == tmp_path / "data"


@pytest.mark.parametrize(
    "before,after",
    [
        ('kind = "compatible"', 'kind = "free"'),
        ('kind = "compatible"', 'kind = "g4f"'),
        ('auth = "none"', 'auth = "cookie"'),
        ("127.0.0.1:11434/v1", "example.org:11434/v1"),
        ("127.0.0.1:11434/v1", "user:password@localhost/v1"),
        ('capabilities = ["chat"]', 'capabilities = ["vision"]'),
        ('capabilities = ["chat"]', 'capabilities = ["text-to-video"]'),
        ("max_output_tokens = 2048", "invented_parameter = 2048"),
        ("max_output_tokens = 2048", "max_output_tokens = -1"),
        ("max_pending = 32", "max_pending = 0"),
        ("retention_days = 30", "retention_days = -1"),
        ('size = "1024x1024"', 'size = "1792x1024"'),
        ('kind = "openai"', 'kind = "openai"\nbase_url = "https://other.example/v1"'),
    ],
)
def test_reject_invalid_and_obsolete_configuration(tmp_path, before, after):
    with pytest.raises(BotError):
        load_settings(write(tmp_path, EXAMPLE.replace(before, after, 1)))


@pytest.mark.parametrize(
    "key",
    [
        "DEFAULT_PROVIDER",
        "BING_COOKIE",
        "GOOGLE_PSID",
        "OPENAI_ENABLED",
        "G4F_PROVIDER",
        "OPENAI_KEY",
    ],
)
def test_reject_legacy_env(tmp_path, monkeypatch, key):
    monkeypatch.setenv(key, "obsolete")
    with pytest.raises(BotError, match="Outdated"):
        load_settings(write(tmp_path, EXAMPLE))


def test_cli_fail_closed_configuration(tmp_path):
    text = EXAMPLE.replace('kind = "compatible"', 'kind = "claude-cli"', 1)
    with pytest.raises(BotError, match="API authentication"):
        load_settings(write(tmp_path, text))


@pytest.mark.parametrize(
    "before,after",
    [
        ('resolution = "480p"', 'resolution = "1080p"'),
        ("duration_seconds = 1,", "duration_seconds = true,"),
        ("duration_seconds = 1,", "duration_seconds = 16,"),
        ('capabilities = ["text-to-video"]', 'capabilities = ["image-to-video"]'),
    ],
)
def test_xai_video_config_rejects_unimplemented_operations_and_invalid_parameters(
    tmp_path, before, after
):
    with pytest.raises(BotError):
        load_settings(write(tmp_path, EXAMPLE.replace(before, after)))


def test_custom_key_and_new_model_id(tmp_path, monkeypatch):
    text = (
        EXAMPLE.replace('auth = "none"', 'auth = "api"\napi_key_env = "CUSTOM_KEY"', 1)
        .replace("your-installed-model", "new-model-without-code-changes")
        .replace("http://127.0.0.1:11434/v1", "https://inference.example/v1")
    )
    settings = load_settings(write(tmp_path, text))
    with pytest.raises(BotError, match="credential"):
        settings.models["local"].backend.key()
    monkeypatch.setenv("CUSTOM_KEY", "example")
    assert settings.models["local"].backend.key() == "example"
    assert settings.models["local"].model == "new-model-without-code-changes"
