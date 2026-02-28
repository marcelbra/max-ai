from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAX_AI_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    database_url: str = f"sqlite+aiosqlite:///{Path.home()}/.max-ai/max_ai.db"

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"

    # Web search (built-in Anthropic server tool — $10/1k searches)
    enable_web_search: bool = True
    web_search_max_uses: int = 5

    # LangWatch
    langwatch_api_key: str = ""


settings = Settings()
