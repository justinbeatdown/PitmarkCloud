from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models.schemas import EntitlementResponse, FeatureEntitlements, PitmarkPlan
from services import prt_licensing_store


def _features_for_plan(plan: PitmarkPlan, enabled: bool = True) -> FeatureEntitlements:
    if not enabled:
        return FeatureEntitlements(
            live_telemetry=False,
            basic_overlays=False,
            logbook=False,
            basic_race_card=False,
        )
    if plan == PitmarkPlan.league_team:
        return FeatureEntitlements(
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
        )
    if plan == PitmarkPlan.pro:
        return FeatureEntitlements(
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
            league_tools=False,
        )
    return FeatureEntitlements(
        live_telemetry=True,
        basic_overlays=True,
        logbook=True,
        basic_race_card=True,
    )


def development_entitlements(device_id: str = "") -> EntitlementResponse:
    return EntitlementResponse(
        development_mode=True,
        customer_id="development-user",
        display_name="Development User",
        plan=PitmarkPlan.pro,
        status="active",
        source="pitmark_cloud_development",
        device_id=device_id,
        offline_grace_until=datetime.now(timezone.utc) + timedelta(days=14),
        features=_features_for_plan(PitmarkPlan.pro),
    )


def free_entitlements(device_id: str = "") -> EntitlementResponse:
    return EntitlementResponse(
        development_mode=False,
        customer_id=device_id or "free-user",
        display_name="Pitmark Racer",
        plan=PitmarkPlan.free,
        status="active",
        source="pitmark_free",
        device_id=device_id,
        offline_grace_until=datetime.now(timezone.utc) + timedelta(days=3650),
        features=_features_for_plan(PitmarkPlan.free),
    )


def current_entitlements(device_id: str) -> EntitlementResponse:
    row = prt_licensing_store.get_entitlement(device_id)
    if row is None:
        # Early Access now uses explicit tester codes. Unlicensed devices retain
        # the permanent Free tier instead of inheriting the old development bridge.
        return free_entitlements(device_id=device_id)

    try:
        plan = PitmarkPlan(str(row.get("plan") or "free"))
    except ValueError:
        plan = PitmarkPlan.free

    status = str(row.get("status") or "inactive").strip().lower()
    active = status in {"active", "trialing", "grace"}
    raw_grace = str(row.get("offline_grace_until") or "")
    try:
        grace = datetime.fromisoformat(raw_grace.replace("Z", "+00:00"))
        if grace.tzinfo is None:
            grace = grace.replace(tzinfo=timezone.utc)
    except ValueError:
        grace = datetime.now(timezone.utc)

    return EntitlementResponse(
        development_mode=False,
        customer_id=str(row.get("customer_id") or device_id),
        display_name=str(row.get("display_name") or "Pitmark Racer"),
        plan=plan,
        status=status,
        source=str(row.get("source") or "pitmark_cloud"),
        device_id=device_id,
        offline_grace_until=grace,
        features=_features_for_plan(plan, enabled=active),
    )


def grant_manual_entitlement(
    *,
    device_id: str,
    customer_id: str,
    display_name: str,
    plan: PitmarkPlan,
    status: str,
    source: str,
    offline_grace_days: int,
) -> EntitlementResponse:
    grace = datetime.now(timezone.utc) + timedelta(days=offline_grace_days)
    prt_licensing_store.upsert_entitlement({
        "device_id": device_id,
        "customer_id": customer_id or device_id,
        "display_name": display_name or "Pitmark Racer",
        "plan": plan.value,
        "status": status.strip().lower() or "active",
        "source": source.strip().lower() or "manual",
        "offline_grace_until": grace.isoformat(),
    })
    return current_entitlements(device_id)
