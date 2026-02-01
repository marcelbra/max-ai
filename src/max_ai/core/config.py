from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str = "maxai"
    postgres_password: str = "maxai"
    postgres_db: str = "maxai"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # Application
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return self.async_database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
