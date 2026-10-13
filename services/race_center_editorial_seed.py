"""Source-backed editorial additions to Race Center's public entity graph.

These unclaimed racing identities are curated from first-party interviews
provided directly to Pitmark by the Matthews Racing family.
"""
import re

def identity_key(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).lower())

FEATURE_URL = "https://pitmarkracing.com/blogs/racing-culture/matthews-racing-noah-tyler-vmcra-family-feature-2026"


def add_matthews_vmcra(series_items, drivers, teams):
    series_key = "vmcra"
    if not any(str(s.get("key")) == series_key for s in series_items):
        series_items.append({
            "key": series_key,
            "name": "Virginia Mini Cup Racing Association",
            "short_name": "VMCRA",
            "group": "Grassroots / Mini Cup",
            "season": 2026,
            "status": "editorial",
            "stale": False,
            "leader": None,
            "field_size": None,
            "official_url": FEATURE_URL,
            "schedule_url": None,
            "logo_url": None,
            "standings_available": False,
            "schedule_available": False,
            "event_count": 0,
            "data_coverage": {"standings": False, "schedule": False, "events": False, "identity": True},
        })
    team = teams.setdefault("matthews-racing", {
        "key": "matthews-racing",
        "name": "Matthews Racing",
        "manufacturer": None,
        "drivers": [],
        "series": set(),
    })
    team["series"].add(series_key)
    for name, number, bio in (
        ("Noah Matthews", None, "Matthews Racing VMCRA Mini Cup driver. 2023 Rookie of the Year; nine victories reported by the family earlier in the 2026 season. Led the 2026 championship by 17 points entering the October 24 Langley finale."),
        ("Tyler Matthews", "05", "Matthews Racing VMCRA Mini Cup driver. 2025 Rookie of the Year and third in championship points in his debut season. Earned his second and third wins of 2026 at Dominion Raceway in October."),
    ):
        key = identity_key(name)
        driver = drivers.setdefault(key, {
            "key": key, "name": name, "number": number,
            "team": "Matthews Racing", "manufacturer": None,
            "photo_url": None, "series": [],
        })
        driver["team"] = "Matthews Racing"
        driver["bio"] = bio
        if number and not driver.get("number"):
            driver["number"] = number
        driver["grassroots"] = True
        urls = driver.setdefault("grassroots_source_urls", [])
        if FEATURE_URL not in urls:
            urls.append(FEATURE_URL)
        if not any(s.get("series_key") == series_key for s in driver["series"]):
            driver["series"].append({
                "series_key": series_key,
                "series_name": "Virginia Mini Cup Racing Association",
                "position": None, "points": None, "starts": None, "wins": None,
                "official_url": FEATURE_URL, "schedule_url": None,
            })
        if not any(row.get("driver_key") == key for row in team["drivers"]):
            team["drivers"].append({"name": name, "driver_key": key, "number": number, "series_key": series_key})
