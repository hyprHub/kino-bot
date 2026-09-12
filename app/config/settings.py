from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    database_channel_ids: list[int] = Field(default_factory=list, alias="DATABASE_CHANNEL_IDS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    timezone: str = Field("Asia/Tashkent", alias="TIMEZONE")
    user_rate_limit: int = Field(5, alias="USER_RATE_LIMIT")
    user_rate_window: int = Field(10, alias="USER_RATE_WINDOW")
    admin_rate_limit: int = Field(30, alias="ADMIN_RATE_LIMIT")
    admin_rate_window: int = Field(10, alias="ADMIN_RATE_WINDOW")
    broadcast_rate_limit: float = Field(25.0, alias="BROADCAST_RATE_LIMIT")
    broadcast_batch_size: int = Field(50, alias="BROADCAST_BATCH_SIZE")
    broadcast_retry_limit: int = Field(5, alias="BROADCAST_RETRY_LIMIT")
    movie_cache_ttl: int = Field(300, alias="MOVIE_CACHE_TTL")
    settings_cache_ttl: int = Field(60, alias="SETTINGS_CACHE_TTL")
    health_host: str = Field("0.0.0.0", alias="HEALTH_HOST")
    health_port: int = Field(8080, alias="PORT")
    environment: str = Field("production", alias="ENVIRONMENT")
    webhook_url: str | None = Field(None, alias="WEBHOOK_URL")
    webhook_secret: str | None = Field(None, alias="WEBHOOK_SECRET")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore", populate_by_name=True)

    @field_validator("admin_ids", "database_channel_ids", mode="before")
    @classmethod
    def parse_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(x) for x in value]
        return [int(x.strip()) for x in str(value).split(",") if x.strip()]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, value):
        value = str(value)
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://"):]
        if value.startswith("postgresql+psycopg://"):
            return "postgresql+asyncpg://" + value[len("postgresql+psycopg://"):]
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()
