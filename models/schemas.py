from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PitmarkPlan(str, Enum):
    free = "free"
    pro = "pro"
    league_team = "league_team"


class FeatureEntitlements(BaseModel):
    live_telemetry: bool = True
    basic_overlays: bool = True
    logbook: bool = True
    basic_race_card: bool = True

    advanced_overlays: bool = False
    analyze_pro: bool = False
    setup_vault_pro: bool = False
    race_card_pro: bool = False
    planner: bool = False
    crew_chief: bool = False

    league_tools: bool = False


class EntitlementResponse(BaseModel):
    development_mode: bool = True
    customer_id: str = "development-user"
    display_name: str = "Development User"
    plan: PitmarkPlan = PitmarkPlan.pro
    status: str = "active"
    offline_grace_until: datetime
    features: FeatureEntitlements


class DiscordStatusResponse(BaseModel):
    configured: bool
    connected: bool = False
    message: str


class ShopifyStatusResponse(BaseModel):
    configured: bool
    message: str


class HealthResponse(BaseModel):
    service: str = "Pitmark Cloud"
    status: str = "online"
    environment: str
    version: str
    timestamp: datetime
