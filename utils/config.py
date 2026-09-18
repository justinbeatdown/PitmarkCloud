from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

PITMARK_RELEASE_VERSION = "0.21.46"


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
    discord_hq_guild_id: str = ""
    discord_owner_user_id: str = ""
    discord_hq_install_permissions: int = 8
    discord_support_automation_enabled: bool = True
    discord_bug_forum_name: str = "prt-bug-reports"
    discord_audit_logging_enabled: bool = True
    discord_flood_protection_enabled: bool = True
    discord_flood_message_limit: int = 8
    discord_flood_window_seconds: int = 10
    discord_flood_timeout_minutes: int = 10
    discord_privileged_intents_enabled: bool = False
    prt_release_announcements_enabled: bool = True
    prt_release_manifest_url: str = "https://prt.pitmarkracing.com/downloads/latest.json"
    prt_release_announcement_channel: str = "prt-announcements"
    prt_release_poll_seconds: int = 120
    pitmark_admin_key: str = ""
    pitmark_ai_provider: str = "openai"
    pitmark_ai_model: str = "gpt-5.6-luna"
    pitmark_ai_timeout_seconds: float = 30.0
    openai_api_key: str = ""
    astra_director_enabled: bool = True
    astra_director_model: str = "gpt-6-astra"
    astra_director_mode: str = "operator"
    astra_director_reasoning_effort: str = "medium"
    astra_director_max_output_tokens: int = 1800
    astra_director_timeout_seconds: float = 90.0
    astra_director_self_test: bool = False
    pitmark_image_model: str = "gpt-image-2"
    pitmark_image_timeout_seconds: float = 90.0
    pitmark_image_size: str = "1536x1024"
    pitmark_image_quality: str = "medium"
    pitmark_image_max_attempts: int = 2
    pitmark_blog_image_ttl_seconds: int = 3600
    autopilot_intelligence_enabled: bool = True
    autopilot_scan_hours: int = 1
    autopilot_scan_minutes: int = 15
    social_realtime_max_age_hours: int = 4
    opportunity_discovery_max_age_hours: int = 72
    autopilot_scan_query: str = (
        "grassroots racing OR dirt track racing OR short track racing "
        "OR sim racing OR motorsports"
    )

    # Social Operations owns one coherent campaign per Pitmark local day.
    # Legacy generic gap-filler posts stay available as an opt-in fallback, but
    # are disabled by default so they cannot race or duplicate the Daily Campaign.
    social_operator_enabled: bool = True
    social_operator_auto_reply_enabled: bool = True
    social_operator_growth_posts_enabled: bool = False
    social_operator_autopublish_low_risk: bool = True
    social_operator_poll_seconds: int = 300
    social_operator_min_facebook_posts_daily: int = 1
    social_operator_min_instagram_posts_daily: int = 1
    social_operator_min_x_posts_daily: int = 1
    social_daily_campaign_enabled: bool = True
    social_daily_image_generation_enabled: bool = True
    social_daily_image_batch_size: int = 2

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_id: str = ""
    meta_page_access_token: str = ""
    meta_system_user_access_token: str = ""
    meta_instagram_account_id: str = ""
    meta_graph_version: str = "v26.0"
    pitmark_timezone: str = "America/New_York"
    pitmark_public_store_url: str = "https://pitmarkracing.com"
    pitmark_cloud_public_url: str = "https://pcc.pitmarkracing.com"
    prt_early_access_form_url: str = ""
    # Cloudflare R2 public-download rollout. No R2 credentials are stored in Pitmark Cloud;
    # Cloud only redirects the heavy installer to the configured public/custom-domain URL.
    prt_r2_enabled: bool = False
    prt_r2_public_base_url: str = ""
    prt_r2_installer_key: str = "prt/PRT-Setup-Latest.exe"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_realtime_max_age_minutes: int = 60
    # Pitmark's connected X account has Premium. Keep this configurable in case
    # the connected publishing account changes later.
    x_post_max_characters: int = 25000
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
