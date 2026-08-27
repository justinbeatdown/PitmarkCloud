from __future__ import annotations

from datetime import datetime, timedelta, timezone
from models.schemas import EntitlementResponse, FeatureEntitlements, PitmarkPlan


def development_entitlements() -> EntitlementResponse:
    """
    Development-only entitlement payload.

    Everything is intentionally unlocked while Pitmark Racing Tools is under development.
    Production logic will be driven by Pitmark's server-side licensing datastore and Shopify-backed
    purchase verification. Shopify secrets never belong in the desktop client.
    """
    return EntitlementResponse(
        development_mode=True,
        customer_id="development-user",
        display_name="Development User",
        plan=PitmarkPlan.pro,
        status="active",
        offline_grace_until=datetime.now(timezone.utc) + timedelta(days=14),
        features=FeatureEntitlements(
            live_telemetry=True,
            basic_overlays=True,
            logbook=True,
            basic_race_card=True,
            advanced_overlays=True,
            analyze_pro=True,
            setup_vault_pro=True,
            race_card_pro=True,
            planner=True,
            crew_chief=True,
            league_tools=True,
        ),
    )
