"""One-shot additive Pitmark Motorsports Discord setup.

Run deliberately against the existing Pitmark HQ bot environment.
No action without --apply. Never edits/deletes pre-existing objects.
"""
import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path

import httpx

BASE = "https://discord.com/api/v10"
CATEGORY = "🏁 PITMARK MOTORSPORTS"
ROLES = ["Pitmark Motorsports • Team Principal", "Pitmark Motorsports • Staff", "Pitmark Motorsports • Driver"]
CHANNELS = [
    ("motorsports-announcements", "Official Pitmark Motorsports team updates."),
    ("motorsports-general", "Pitmark Motorsports team and community conversation."),
    ("driver-paddock", "Team driver discussion and preparation."),
    ("race-operations", "Team operations, planning and coordination."),
    ("team-schedule", "Team events, schedules and session coordination."),
    ("team-media", "Authentic team imagery, race photos and approved media."),
]

async def request(client, method, path, **kwargs):
    response = await client.request(method, BASE + path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"Discord {method} {path} returned HTTP {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else {}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Explicitly authorize additive writes")
    parser.add_argument("--snapshot-dir", default="discord_snapshots")
    args = parser.parse_args()
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    gid = os.getenv("DISCORD_HQ_GUILD_ID") or os.getenv("DISCORD_GUILD_ID")
    if not token or not gid or not gid.isdigit():
        raise SystemExit("Missing bot token or configured HQ guild ID")
    async with httpx.AsyncClient(headers={"Authorization": f"Bot {token}"}, timeout=30.0) as client:
        guild = await request(client, "GET", f"/guilds/{gid}")
        roles = await request(client, "GET", f"/guilds/{gid}/roles")
        channels = await request(client, "GET", f"/guilds/{gid}/channels")
        snapshot = {
            "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "guild": {k: guild.get(k) for k in ("id", "name", "owner_id", "features")},
            "roles": roles,
            "channels": channels,
        }
        directory = Path(args.snapshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"pitmark_discord_before_{gid}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        with path.open("x", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        print(f"Backup: {path} | {len(roles)} roles | {len(channels)} channels")
        existing_roles = {r["name"]: r["id"] for r in roles}
        categories = [c for c in channels if c.get("type") == 4 and c.get("name") == CATEGORY]
        target_category = categories[0] if categories else None
        proposed = {"roles": [r for r in ROLES if r not in existing_roles],
                    "category": None if target_category else CATEGORY,
                    "channels": []}
        existing_in_category = {c["name"] for c in channels if target_category and str(c.get("parent_id")) == str(target_category["id"])}
        proposed["channels"] = [name for name, _ in CHANNELS if name not in existing_in_category]
        print(json.dumps({"would_create": proposed}, indent=2))
        if not args.apply:
            print("Read-only inventory complete. Run with --apply only after preserving the backup.")
            return
        # Do not write if destination is not persistently mounted; the inventory
        # must survive a redeploy. Operator explicitly chooses the persistent path.
        if not os.getenv("PITMARK_DISCORD_SNAPSHOT_PERSISTENT") == "1":
            raise SystemExit("Refusing writes: confirm snapshot persistence via PITMARK_DISCORD_SNAPSHOT_PERSISTENT=1")
        for name in proposed["roles"]:
            role = await request(client, "POST", f"/guilds/{gid}/roles",
                                 json={"name": name, "permissions": "0", "mentionable": False},
                                 headers={"X-Audit-Log-Reason": "Pitmark Motorsports additive team setup"})
            existing_roles[name] = role["id"]
        if not target_category:
            target_category = await request(client, "POST", f"/guilds/{gid}/channels",
                json={"name": CATEGORY, "type": 4},
                headers={"X-Audit-Log-Reason": "Pitmark Motorsports additive team setup"})
        parent_id = target_category["id"]
        # Re-fetch under the chosen category: restart-safe, no duplicates.
        channels = await request(client, "GET", f"/guilds/{gid}/channels")
        seen = {c["name"] for c in channels if str(c.get("parent_id")) == str(parent_id)}
        for name, topic in CHANNELS:
            if name in seen:
                continue
            await request(client, "POST", f"/guilds/{gid}/channels",
                json={"name": name, "type": 0, "parent_id": parent_id, "topic": topic},
                headers={"X-Audit-Log-Reason": "Pitmark Motorsports additive team setup"})
            seen.add(name)
        print("Additive setup finished; existing roles/channels and permissions were not changed.")

if __name__ == "__main__":
    asyncio.run(main())
