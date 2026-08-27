from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    app_version: str = "0.1.0"
    cors_origins: str = "*"

    pitmark_signing_secret: str = "development-only"

    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = ""
    discord_bot_token: str = ""

    shopify_shop_domain: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_webhook_secret: str = ""

    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
