from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIDIGEST_",
        case_sensitive=False,
        populate_by_name=True,
        env_file=".env",
    )

    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    database_url: str = "sqlite:///ai_trend_digest.db"
    enabled_sources_raw: str = Field(
        default="github_trending,hf_models,hf_papers,arxiv",
        validation_alias="AIDIGEST_ENABLED_SOURCES",
    )
    digest_send_time: str = "09:00"

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
