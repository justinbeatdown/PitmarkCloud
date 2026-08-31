from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    app_version: str = "0.14.3"
    cors_origins: str = ""

    pitmark_signing_secret: str = "development-only"

    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = ""
    discord_bot_token: str = ""
    discord_public_key: str = ""
    discord_guild_id: str = ""
    discord_support_invite_url: str = ""
    discord_gateway_enabled: bool = True
    discord_presence_text: str = "Pitmark Racing Tools"
    discord_presence_type: str = "watching"
    discord_command_scope: str = "global"
    discord_install_permissions: int = 117760
    pitmark_admin_key: str = ""

    pitmark_ai_provider: str = "openai"
    pitmark_ai_model: str = "gpt-5.6-luna"
    pitmark_ai_timeout_seconds: float = 30.0
    openai_api_key: str = ""
    autopilot_intelligence_enabled: bool = True
    autopilot_scan_hours: int = 6
    autopilot_scan_query: str = "grassroots racing OR dirt track racing OR short track racing OR sim racing OR motorsports"

    # Social publishing credentials stay server-side.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_id: str = ""
    meta_page_access_token: str = ""
    meta_graph_version: str = "v24.0"
    pitmark_timezone: str = "America/New_York"

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""

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
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
