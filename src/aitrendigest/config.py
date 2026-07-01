from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIDIGEST_",
        case_sensitive=False,
        populate_by_name=True,
        env_file=".env",
        extra="ignore",
    )

    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    enabled_sources_raw: str = Field(
        default="github_trending,hf_models,hf_papers,arxiv",
        validation_alias="AIDIGEST_ENABLED_SOURCES",
    )
    digest_send_time: str = "09:00"
    default_period_days: int = Field(default=1, ge=1)
    timezone_name: str = "Asia/Seoul"

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid timezone: {value}") from exc
        return value

    @property
    def enabled_sources(self) -> list[str]:
        return [
            value.strip()
            for value in self.enabled_sources_raw.split(",")
            if value.strip()
        ]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
