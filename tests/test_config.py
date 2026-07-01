import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from aitrendigest.config import Settings


def test_settings_load_enabled_sources_from_env(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")
    monkeypatch.setenv("AIDIGEST_ENABLED_SOURCES", "github_trending,hf_models,arxiv")

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_chat_id == "12345"
    assert settings.database_url == "sqlite:///ai_trend_digest.db"
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
        monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")
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
    assert settings.database_url == "sqlite:///ai_trend_digest.db"


def test_settings_load_subscriber_schedule_defaults(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "bootstrap-chat")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")

    settings = Settings.from_env()

    assert settings.default_period_days == 1
    assert settings.timezone_name == "Asia/Seoul"


def test_settings_load_subscriber_schedule_overrides_from_env(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "bootstrap-chat")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///custom.db")
    monkeypatch.setenv("AIDIGEST_DEFAULT_PERIOD_DAYS", "7")
    monkeypatch.setenv("AIDIGEST_TIMEZONE_NAME", "UTC")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite:///custom.db"
    assert settings.default_period_days == 7
    assert settings.timezone_name == "UTC"


def test_settings_reject_non_positive_default_period_days(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "bootstrap-chat")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")
    monkeypatch.setenv("AIDIGEST_DEFAULT_PERIOD_DAYS", "0")

    with pytest.raises(ValidationError):
        Settings.from_env()


def test_settings_reject_invalid_timezone_name(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "bootstrap-chat")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///ai_trend_digest.db")
    monkeypatch.setenv("AIDIGEST_TIMEZONE_NAME", "Not/A_Real_Timezone")

    with pytest.raises(ValidationError):
        Settings.from_env()
