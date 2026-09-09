from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from api import partner_ui
from services.prt_analytics import record_campaign_link

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
RACEPROOF_CAMPAIGN = "prt_raceproof_202609"
RACEPROOF_SOURCE = "facebook"
RACEPROOF_ASSET = "race"
RACEPROOF_TARGET = (
    "https://prt.pitmarkracing.com/prt"
    f"?utm_campaign={RACEPROOF_CAMPAIGN}"
    f"&utm_source={RACEPROOF_SOURCE}"
    "&utm_medium=organic_social"
    f"&utm_content={RACEPROOF_ASSET}"
)
_PREVIEW_BOT_TOKENS = (
    "facebookexternalhit",
    "facebot",
    "meta-externalagent",
    "meta-externalfetcher",
    "twitterbot",
    "discordbot",
    "slackbot",
    "linkedinbot",
    "googlebot",
    "bingbot",
)


def _html(name: str) -> HTMLResponse:
    return HTMLResponse(
        (ASSET_DIR / name).read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


def _campaign_traffic_type(request: Request) -> str:
    user_agent = (request.headers.get("user-agent") or "").lower()
    return "preview" if any(token in user_agent for token in _PREVIEW_BOT_TOKENS) else "visit"


@router.get("/links", response_class=HTMLResponse, include_in_schema=False)
def pitmark_links():
    return _html("links.html")


@router.get("/raceproof", include_in_schema=False)
def raceproof_redirect(request: Request):
    # Count first-party campaign traffic without storing IPs, user agents, cookies,
    # referrers, or browser identifiers. Known social/search preview crawlers are
    # separated from human-ish visits so link unfurling does not inflate the number.
    try:
        record_campaign_link(
            slug="raceproof",
            campaign=RACEPROOF_CAMPAIGN,
            source=RACEPROOF_SOURCE,
            asset=RACEPROOF_ASSET,
            traffic_type=_campaign_traffic_type(request),
        )
    except Exception:
        # Analytics must never prevent a visitor from reaching the campaign.
        pass

    return RedirectResponse(
        url=RACEPROOF_TARGET,
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/links.css", include_in_schema=False)
def pitmark_links_css():
    return Response(
        (ASSET_DIR / "links.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


# Keep public partner onboarding beside the public links hub so the same Cloud
# service exposes one stable, shareable Partner Paddock without Control Center auth.
router.include_router(partner_ui.router)
