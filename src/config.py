"""Runtime settings from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .extract import ExtractConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    fetch_timeout_seconds: float = 15.0
    max_response_bytes: int = 2_097_152
    user_agent: str = "ToolFarm-AgentExtract/0.1"
    api_key: str = ""

    def extract_config(self) -> ExtractConfig:
        return ExtractConfig(
            timeout_seconds=self.fetch_timeout_seconds,
            max_response_bytes=self.max_response_bytes,
            user_agent=self.user_agent,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
