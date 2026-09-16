from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.early_access_admin import _application_cards


def row(placement: str, identity: str, disciplines: str, frequency: str, tools: str) -> dict:
    return {
        "id": 999,
        "full_name": "Test Applicant",
        "email": "test@example.com",
        "discord_username": "tester",
        "iracing_name": identity,
        "disciplines": disciplines,
        "race_frequency": frequency,
        "current_tools": tools,
        "goals": "Useful feedback",
        "source": "website",
        "asset": "",
        "placement": placement,
        "status": "new",
        "created_at": "2026-09-16T20:00:00+00:00",
    }


def main() -> None:
    driver = _application_cards([row("quick-apply-driver", "Driver Name", "Asphalt Oval", "1–2 days per week", "Crew Chief")])
    assert '<span class="label">iRACING</span>' in driver
    assert '<span class="label">RACES</span>' in driver
    assert '<span class="label">DISCIPLINES</span>' in driver
    assert '<span class="label">CURRENT TOOLS</span>' in driver

    broadcaster = _application_cards([row("quick-apply-broadcaster", "Odyssey Motorsport TV", "Broadcaster / Production", "Every week", "OBS / ATVO")])
    assert '<span class="label">BROADCAST / PRODUCTION</span>' in broadcaster
    assert '<span class="label">PRODUCTION FREQUENCY</span>' in broadcaster
    assert '<span class="label">APPLICANT ROLE</span>' in broadcaster
    assert '<span class="label">BROADCAST TOOLS</span>' in broadcaster
    assert '<span class="label">iRACING</span>' not in broadcaster

    league = _application_cards([row("quick-apply-league", "Test League", "League / Club", "Every week", "Race Control")])
    assert '<span class="label">LEAGUE / CLUB</span>' in league
    assert '<span class="label">RACE-NIGHT FREQUENCY</span>' in league
    assert '<span class="label">ADMIN TOOLS</span>' in league

    media = _application_cards([row("quick-apply-media", "Test Outlet", "Media / Developer", "Occasionally / special events", "Telemetry API")])
    assert '<span class="label">OUTLET / PROJECT</span>' in media
    assert '<span class="label">WORKFLOW FREQUENCY</span>' in media
    assert '<span class="label">WORKFLOW TOOLS</span>' in media

    print("PRT role-aware Applicant Center contract OK")


if __name__ == "__main__":
    main()
