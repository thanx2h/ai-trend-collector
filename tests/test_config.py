import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from aitrendigest.config import Settings


def test_settings_load_enabled_sources_from_env(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("AIDIGEST_ENABLED_SOURCES", "github_trending,hf_models,arxiv")

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_chat_id == "12345"
    assert settings.enabled_sources == ["github_trending", "hf_models", "arxiv"]


@pytest.mark.parametrize(
    ("bot_token", "chat_id"),
    [
        ("", "12345"),
        ("token", ""),
    ],
)
def test_settings_reject_empty_required_env_values(monkeypatch, bot_token, chat_id):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", bot_token)
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", chat_id)

    with pytest.raises(ValidationError):
        Settings.from_env()


def test_settings_enabled_sources_strip_whitespace(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv(
        "AIDIGEST_ENABLED_SOURCES",
        " github_trending, hf_models ,  arxiv  ",
    )

    settings = Settings.from_env()

    assert settings.enabled_sources == ["github_trending", "hf_models", "arxiv"]


def test_settings_load_from_dotenv_file(monkeypatch):
    temp_path = Path.cwd() / "_tmp_config_test_env"
    temp_path.mkdir(exist_ok=True)
    try:
        monkeypatch.chdir(temp_path)
        monkeypatch.delenv("AIDIGEST_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("AIDIGEST_TELEGRAM_CHAT_ID", raising=False)
        (temp_path / ".env").write_text(
            "AIDIGEST_TELEGRAM_BOT_TOKEN=token\nAIDIGEST_TELEGRAM_CHAT_ID=12345\n",
            encoding="utf-8",
        )

        settings = Settings.from_env()
    finally:
        monkeypatch.chdir(temp_path.parent)
        shutil.rmtree(temp_path, ignore_errors=True)

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_chat_id == "12345"
