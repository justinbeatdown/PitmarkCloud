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


class LiveSessionUpdate(BaseModel):
    track_name: str = Field(default="iRacing Session", max_length=160)
    car_name: str = Field(default="Player Car", max_length=160)
    lap: int = Field(default=0, ge=0, le=100000)
    position: int = Field(default=0, ge=0, le=10000)
    current_lap_time: float = Field(default=0.0, ge=0.0, le=86400.0)
    best_lap_time: float = Field(default=0.0, ge=0.0, le=86400.0)
    delta: float = Field(default=0.0, ge=-86400.0, le=86400.0)
    speed_mph: float = Field(default=0.0, ge=0.0, le=1000.0)
    gear: int = Field(default=0, ge=-2, le=20)
    rpm: int = Field(default=0, ge=0, le=100000)
    fuel_gallons: float = Field(default=0.0, ge=0.0, le=10000.0)
    fuel_laps_remaining: float = Field(default=0.0, ge=0.0, le=100000.0)
    incident_count: int = Field(default=0, ge=0, le=100000)
    flag_text: str = Field(default="GREEN", max_length=80)
    track_temp_f: float = Field(default=0.0, ge=-200.0, le=1000.0)
    session_laps_remaining: int = Field(default=0, ge=0, le=100000)
