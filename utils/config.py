from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

PITMARK_RELEASE_VERSION = "0.16.11"


class Settings(BaseSettings):
    environment: str = "development"
    app_version: str = PITMARK_RELEASE_VERSION
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
    pitmark_image_model: str = "gpt-image-2"
    pitmark_image_timeout_seconds: float = 90.0
    autopilot_intelligence_enabled: bool = True
    autopilot_scan_hours: int = 1
    autopilot_scan_minutes: int = 15
    social_realtime_max_age_hours: int = 4
    opportunity_discovery_max_age_hours: int = 72
    autopilot_scan_query: str = "grassroots racing OR dirt track racing OR short track racing OR sim racing OR motorsports"

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_id: str = ""
    meta_page_access_token: str = ""
    meta_system_user_access_token: str = ""
    meta_instagram_account_id: str = ""
    meta_graph_version: str = "v26.0"
    pitmark_timezone: str = "America/New_York"
    pitmark_public_store_url: str = "https://pitmarkracing.com"

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_realtime_max_age_minutes: int = 60

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
    configured = Settings()
    configured.app_version = PITMARK_RELEASE_VERSION
    return configured


settings = get_settings()
