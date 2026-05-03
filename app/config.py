from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "A股复盘后端"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(default="sqlite:///./local.db", alias="DATABASE_URL")
    app_token: str | None = Field(default=None, alias="APP_TOKEN")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-pro", alias="DEEPSEEK_MODEL")
    deepseek_mock: bool = Field(default=False, alias="DEEPSEEK_MOCK")
    request_timeout_seconds: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")
    auto_create_tables: bool = Field(default=True, alias="AUTO_CREATE_TABLES")
    timezone: str = Field(default="Asia/Shanghai", alias="APP_TIMEZONE")

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def normalized_database_url(self) -> str:
        if self.database_url.startswith("postgres://"):
            return "postgresql://" + self.database_url.removeprefix("postgres://")
        return self.database_url

    @property
    def should_mock_deepseek(self) -> bool:
        return self.deepseek_mock or not self.deepseek_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
