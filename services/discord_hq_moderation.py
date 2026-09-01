from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services import discord_hq_store
from services.discord_hq_common import (
    DISCORD_API,
    SEND_MESSAGES,
    discord_request,
    list_channels,
    log_named,
)


async def handle_action(
    *,
    guild_id: str,
    channel_id: str,
    moderator_id: str,
    action: str,
    target_user_id: str = "",
    reason: str = "No reason provided.",
    minutes: int = 0,
    amount: int = 0,
    seconds: int = 0,
    can_ban: bool = False,
    owner_user_id: str = "",
) -> str:
    if action == "history":
        history = discord_hq_store.moderation_history(guild_id, target_user_id, 10)
        if not history:
            return f"No Pitmark moderation history for <@{target_user_id}>."
        lines = [
            f"`#{case['id']}` **{case['action'].upper()}** — "
            f"{case['reason'][:160]} ({case['created_at'][:19]}Z)"
            for case in history
        ]
        return f"🛡️ **Moderation history for <@{target_user_id}>**\n" + "\n".join(lines)

    if action == "purge":
        deleted = await purge_messages(channel_id, amount)
        await log_mod(
            guild_id,
            moderator_id,
            "purge",
            "channel",
            f"Deleted {deleted} messages in <#{channel_id}>.",
        )
        return f"🧹 Deleted {deleted} recent messages."

    if action in {"lock", "unlock"}:
        await set_channel_lock(
            guild_id,
            channel_id,
            moderator_id,
            locked=action == "lock",
        )
        await log_mod(
            guild_id,
            moderator_id,
            action,
            "channel",
            f"<#{channel_id}> {action}ed.",
        )
        return f"🔐 Channel {'locked' if action == 'lock' else 'unlocked'}."

    if action == "slowmode":
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel_id}",
            reason="Pitmark moderation: slowmode",
            json={"rate_limit_per_user": seconds},
        )
        await log_mod(
            guild_id,
            moderator_id,
            "slowmode",
            "channel",
            f"Set <#{channel_id}> slowmode to {seconds}s.",
        )
        return f"⏱️ Slowmode set to {seconds} seconds."

    if action == "unban":
        if not can_ban:
            raise PermissionError("You need Ban Members permission for this action.")
        if not target_user_id.isdigit():
            raise ValueError("Enter a valid Discord user ID.")
        await discord_request(
            "DELETE",
            f"{DISCORD_API}/guilds/{guild_id}/bans/{target_user_id}",
            reason=reason,
            expected={200, 204},
        )
        case = discord_hq_store.add_moderation_case(
            guild_id, target_user_id, moderator_id, "unban", reason
        )
        await log_mod(guild_id, moderator_id, "unban", target_user_id, reason)
        return f"✅ Unbanned `{target_user_id}`. Case `#{case['id']}` logged."

    if not target_user_id:
        raise ValueError("Choose a member.")
    if target_user_id == moderator_id:
        raise PermissionError("You cannot use that moderation action on yourself.")
    if owner_user_id and target_user_id == owner_user_id:
        raise PermissionError(
            "The Pitmark owner is protected from bot moderation actions."
        )

    if action == "warn":
        pass
    elif action == "timeout":
        until = (
            datetime.now(timezone.utc) + timedelta(minutes=minutes)
        ).isoformat()
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/guilds/{guild_id}/members/{target_user_id}",
            reason=reason,
            json={"communication_disabled_until": until},
        )
    elif action == "kick":
        await discord_request(
            "DELETE",
            f"{DISCORD_API}/guilds/{guild_id}/members/{target_user_id}",
            reason=reason,
            expected={200, 204},
        )
    elif action == "ban":
        if not can_ban:
            raise PermissionError("You need Ban Members permission for this action.")
        await discord_request(
            "PUT",
            f"{DISCORD_API}/guilds/{guild_id}/bans/{target_user_id}",
            reason=reason,
            json={"delete_message_seconds": 0},
            expected={200, 204},
        )
    else:
        raise ValueError("Unknown moderation action.")

    duration = minutes if action == "timeout" else 0
    case = discord_hq_store.add_moderation_case(
        guild_id,
        target_user_id,
        moderator_id,
        action,
        reason,
        duration,
    )
    await dm_user(
        target_user_id,
        "🛡️ **Pitmark Moderation**\n"
        f"Action: **{action.title()}**\n"
        f"Reason: {reason}\n"
        f"Case: #{case['id']}",
    )
    await log_mod(
        guild_id,
        moderator_id,
        action,
        target_user_id,
        reason,
        duration,
    )
    return (
        f"✅ {action.title()} applied to <@{target_user_id}>. "
        f"Case `#{case['id']}` logged."
    )


async def set_channel_lock(
    guild_id: str,
    channel_id: str,
    moderator_id: str,
    locked: bool,
) -> None:
    channel = (
        await discord_request("GET", f"{DISCORD_API}/channels/{channel_id}")
    ).json()
    everyone = next(
        (
            o for o in channel.get("permission_overwrites") or []
            if str(o.get("id")) == guild_id
            and int(o.get("type") or 0) == 0
        ),
        None,
    )
    current_allow = int((everyone or {}).get("allow") or 0)
    current_deny = int((everyone or {}).get("deny") or 0)

    if locked:
        if discord_hq_store.get_channel_lock(channel_id):
            raise ValueError("This channel is already locked by Pitmark moderation.")
        discord_hq_store.save_channel_lock(
            guild_id,
            channel_id,
            current_allow,
            current_deny,
            moderator_id,
        )
        next_allow = current_allow & ~SEND_MESSAGES
        next_deny = current_deny | SEND_MESSAGES
    else:
        snapshot = discord_hq_store.get_channel_lock(channel_id)
        if not snapshot:
            raise ValueError(
                "Pitmark has no saved lock state for this channel, "
                "so it will not guess at the original permissions."
            )
        next_allow = int(snapshot["previous_allow"])
        next_deny = int(snapshot["previous_deny"])

    await discord_request(
        "PUT",
        f"{DISCORD_API}/channels/{channel_id}/permissions/{guild_id}",
        reason="Pitmark moderation channel lock",
        json={
            "type": 0,
            "allow": str(next_allow),
            "deny": str(next_deny),
        },
        expected={200, 204},
    )
    if not locked:
        discord_hq_store.delete_channel_lock(channel_id)


async def purge_messages(channel_id: str, amount: int) -> int:
    amount = max(1, min(int(amount), 100))
    messages = (
        await discord_request(
            "GET",
            f"{DISCORD_API}/channels/{channel_id}/messages",
            params={"limit": amount},
        )
    ).json()

    cutoff_ms = int(
        (
            datetime.now(timezone.utc) - timedelta(days=13, hours=23)
        ).timestamp()
        * 1000
    )
    ids = []
    for message in messages:
        snowflake = int(message.get("id") or 0)
        if ((snowflake >> 22) + 1420070400000) >= cutoff_ms:
            ids.append(str(snowflake))

    if len(ids) >= 2:
        await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{channel_id}/messages/bulk-delete",
            reason="Pitmark moderation purge",
            json={"messages": ids},
            expected={200, 204},
        )
    elif len(ids) == 1:
        await discord_request(
            "DELETE",
            f"{DISCORD_API}/channels/{channel_id}/messages/{ids[0]}",
            reason="Pitmark moderation purge",
            expected={200, 204},
        )
    return len(ids)


async def sync_automod(
    guild_id: str,
    role_map: dict[str, dict[str, Any]],
    channel_map: dict[str, dict[str, Any]],
) -> int:
    modlog = channel_map.get("moderation-log") or next(
        (
            c for c in await list_channels(guild_id)
            if c.get("name") == "moderation-log"
        ),
        None,
    )
    if not modlog:
        return 0

    exempt = [
        str(role_map[name]["id"])
        for name in [
            "Pitmark Owner",
            "Pitmark Administrator",
            "Pitmark Moderator",
        ]
        if name in role_map
    ]
    desired = [
        {
            "name": "Pitmark • Mention Spam",
            "event_type": 1,
            "trigger_type": 5,
            "trigger_metadata": {
                "mention_total_limit": 6,
                "mention_raid_protection_enabled": True,
            },
            "actions": [
                {
                    "type": 1,
                    "metadata": {
                        "custom_message": "Too many mentions. Please slow down."
                    },
                },
                {"type": 2, "metadata": {"channel_id": str(modlog["id"])}},
                {"type": 3, "metadata": {"duration_seconds": 600}},
            ],
            "enabled": True,
            "exempt_roles": exempt,
        },
        {
            "name": "Pitmark • Safety Presets",
            "event_type": 1,
            "trigger_type": 4,
            "trigger_metadata": {"presets": [2, 3]},
            "actions": [
                {
                    "type": 1,
                    "metadata": {
                        "custom_message": (
                            "That content is blocked by Pitmark community safety rules."
                        )
                    },
                },
                {"type": 2, "metadata": {"channel_id": str(modlog["id"])}},
            ],
            "enabled": True,
            "exempt_roles": exempt,
        },
        {
            "name": "Pitmark • Spam Filter",
            "event_type": 1,
            "trigger_type": 3,
            "actions": [
                {
                    "type": 1,
                    "metadata": {
                        "custom_message": "Discord detected this as spam."
                    },
                },
                {"type": 2, "metadata": {"channel_id": str(modlog["id"])}},
            ],
            "enabled": True,
            "exempt_roles": exempt,
        },
    ]

    existing_response = await discord_request(
        "GET",
        f"{DISCORD_API}/guilds/{guild_id}/auto-moderation/rules",
    )
    existing = {
        str(x.get("name")): x for x in existing_response.json()
    }
    for rule in desired:
        current = existing.get(rule["name"])
        if current:
            await discord_request(
                "PATCH",
                (
                    f"{DISCORD_API}/guilds/{guild_id}/auto-moderation/"
                    f"rules/{current['id']}"
                ),
                reason="Pitmark AutoMod sync",
                json=rule,
            )
        else:
            await discord_request(
                "POST",
                f"{DISCORD_API}/guilds/{guild_id}/auto-moderation/rules",
                reason="Pitmark AutoMod bootstrap",
                json=rule,
            )
    return len(desired)


async def log_mod(
    guild_id: str,
    moderator_id: str,
    action: str,
    target: str,
    reason: str,
    duration: int = 0,
) -> None:
    suffix = f" • {duration} min" if duration else ""
    target_text = f"<@{target}>" if target.isdigit() else target
    await log_named(
        guild_id,
        "moderation-log",
        f"🛡️ **{action.upper()}** • {target_text}{suffix}\n"
        f"Moderator: <@{moderator_id}>\nReason: {reason}",
    )


async def dm_user(user_id: str, content: str) -> None:
    try:
        dm = (
            await discord_request(
                "POST",
                f"{DISCORD_API}/users/@me/channels",
                json={"recipient_id": user_id},
                timeout=12.0,
            )
        ).json()
        await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{dm['id']}/messages",
            json={"content": content[:1900]},
            timeout=12.0,
        )
    except Exception:
        # DMs may be disabled by the user; moderation action itself should not fail.
        pass
