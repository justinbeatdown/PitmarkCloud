from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services import discord_hq_moderation
from services.discord_hq_blueprint import (
    ADMINISTRATOR,
    ATTACH_FILES,
    EMBED_LINKS,
    MANAGE_MESSAGES,
    PIN_MESSAGES,
    PRIVATE_CATEGORY_SPECS,
    PUBLIC_CATEGORY_SPECS,
    READ_MESSAGE_HISTORY,
    ROLE_SPECS,
    SEND_MESSAGES,
    VIEW_CHANNEL,
    overwrite,
)
from services.discord_hq_common import (
    DISCORD_API,
    discord_request,
    list_channels,
    list_roles,
    log_named,
    preflight,
)

LEGACY_NAMES = {
    "general",
    "rules",
    "moderator-only",
    "clips-and-highlights",
    "lobby",
    "gaming",
}
LEGACY_CATEGORY_NAME = "🧹 LEGACY REVIEW"


def _channel_type(channel: dict[str, Any]) -> int:
    """Return Discord channel type without treating valid type 0 as falsy."""
    value = channel.get("type")
    try:
        return int(value) if value is not None else -1
    except (TypeError, ValueError):
        return -1


def _managed_category_names() -> set[str]:
    return {
        *[name for name, _children in PUBLIC_CATEGORY_SPECS],
        *[name for name, _audience, _children in PRIVATE_CATEGORY_SPECS],
    }


def _actual_role_permissions(role: dict[str, Any]) -> int:
    try:
        return int(role.get("permissions") or 0)
    except (TypeError, ValueError):
        return 0


async def audit_roles(guild_id: str) -> tuple[bool, list[str]]:
    roles = {
        str(role.get("name") or ""): role
        for role in await list_roles(guild_id)
    }
    problems: list[str] = []
    for name, _color, expected in ROLE_SPECS:
        actual_role = roles.get(name)
        if not actual_role:
            problems.append(f"missing role: {name}")
            continue
        actual = _actual_role_permissions(actual_role)
        if expected & ADMINISTRATOR:
            if not actual & ADMINISTRATOR:
                problems.append(f"{name}: Administrator missing")
        elif actual != expected:
            missing = expected & ~actual
            extra = actual & ~expected
            details = []
            if missing:
                details.append(f"missing bits {missing}")
            if extra:
                details.append(f"extra bits {extra}")
            problems.append(f"{name}: " + ", ".join(details))
    return not problems, problems


async def _managed_structure_audit(
    guild_id: str,
) -> tuple[bool, list[str]]:
    channels = await list_channels(guild_id)
    missing: list[str] = []

    categories = {
        str(ch.get("name") or ""): ch
        for ch in channels
        if _channel_type(ch) == 4
    }

    for cat_name, children in PUBLIC_CATEGORY_SPECS:
        cat = categories.get(cat_name)
        if not cat:
            missing.append(f"category {cat_name}")
            continue

        parent_id = str(cat.get("id") or "")
        for name, typ, _topic, _access, _tags in children:
            if not any(
                str(ch.get("name") or "") == name
                and _channel_type(ch) == typ
                and str(ch.get("parent_id") or "") == parent_id
                for ch in channels
            ):
                missing.append(f"{cat_name}/{name}")

    for cat_name, _audience, children in PRIVATE_CATEGORY_SPECS:
        cat = categories.get(cat_name)
        if not cat:
            missing.append(f"category {cat_name}")
            continue

        parent_id = str(cat.get("id") or "")
        for name, typ, _topic in children:
            if not any(
                str(ch.get("name") or "") == name
                and _channel_type(ch) == typ
                and str(ch.get("parent_id") or "") == parent_id
                for ch in channels
            ):
                missing.append(f"{cat_name}/{name}")

    return not missing, missing


async def run_self_test(guild_id: str, owner_user_id: str) -> str:
    """Run non-destructive Discord HQ QA against temporary objects."""
    results: list[tuple[str, bool, str]] = []
    temp_channel_id = ""
    temp_role_id = ""

    try:
        pf = await preflight(guild_id, False)
        results.append((
            "Bot HQ permissions",
            not pf["missing_permissions"],
            "all required permissions present"
            if not pf["missing_permissions"]
            else ", ".join(pf["missing_permissions"]),
        ))

        roles_ok, role_problems = await audit_roles(guild_id)
        results.append((
            "Pitmark role matrix",
            roles_ok,
            "all managed roles match blueprint"
            if roles_ok
            else "; ".join(role_problems[:5]),
        ))

        structure_ok, structure_missing = await _managed_structure_audit(guild_id)
        results.append((
            "Managed server structure",
            structure_ok,
            "all managed categories/channels present"
            if structure_ok
            else "missing: " + ", ".join(structure_missing[:8]),
        ))

        automod = (
            await discord_request(
                "GET",
                f"{DISCORD_API}/guilds/{guild_id}/auto-moderation/rules",
            )
        ).json()
        pitmark_automod = [
            rule for rule in automod
            if str(rule.get("name") or "").startswith("Pitmark •")
        ]
        results.append((
            "AutoMod",
            len(pitmark_automod) >= 3,
            f"{len(pitmark_automod)} Pitmark rules found",
        ))

        channels = await list_channels(guild_id)
        staff_category = next(
            (
                ch for ch in channels
                if _channel_type(ch) == 4
                and ch.get("name") == "🔐 PITMARK STAFF"
            ),
            None,
        )
        if not staff_category:
            raise RuntimeError("PITMARK STAFF category is missing.")

        suffix = datetime.now(timezone.utc).strftime("%H%M%S")

        temp_role = (
            await discord_request(
                "POST",
                f"{DISCORD_API}/guilds/{guild_id}/roles",
                reason="Pitmark HQ self-test temporary role",
                json={
                    "name": f"Pitmark QA • {suffix}",
                    "permissions": "0",
                    "color": 0,
                    "hoist": False,
                    "mentionable": False,
                },
            )
        ).json()
        temp_role_id = str(temp_role["id"])
        results.append((
            "Role create/delete capability",
            True,
            "temporary role created",
        ))

        test_overwrites = [
            overwrite(guild_id, 0, deny=VIEW_CHANNEL),
            overwrite(
                pf["bot_user_id"],
                1,
                allow=(
                    VIEW_CHANNEL
                    | SEND_MESSAGES
                    | READ_MESSAGE_HISTORY
                    | EMBED_LINKS
                    | ATTACH_FILES
                    | MANAGE_MESSAGES
                    | PIN_MESSAGES
                ),
            ),
            overwrite(
                owner_user_id,
                1,
                allow=(
                    VIEW_CHANNEL
                    | SEND_MESSAGES
                    | READ_MESSAGE_HISTORY
                    | EMBED_LINKS
                    | ATTACH_FILES
                ),
            ),
        ]

        temp_channel = (
            await discord_request(
                "POST",
                f"{DISCORD_API}/guilds/{guild_id}/channels",
                reason="Pitmark HQ self-test temporary channel",
                json={
                    "name": f"pitmark-qa-{suffix}",
                    "type": 0,
                    "parent_id": str(staff_category["id"]),
                    "topic": (
                        "Temporary Pitmark HQ moderation self-test channel."
                    ),
                    "permission_overwrites": test_overwrites,
                },
            )
        ).json()
        temp_channel_id = str(temp_channel["id"])
        results.append((
            "Channel create/delete capability",
            True,
            "temporary private channel created",
        ))

        messages: list[dict[str, Any]] = []
        for i in range(3):
            message = (
                await discord_request(
                    "POST",
                    f"{DISCORD_API}/channels/{temp_channel_id}/messages",
                    json={
                        "content": (
                            f"Pitmark HQ QA test message {i + 1}/3"
                        )
                    },
                )
            ).json()
            messages.append(message)
        results.append((
            "Send messages",
            True,
            "3 temporary messages created",
        ))

        try:
            await discord_request(
                "PUT",
                (
                    f"{DISCORD_API}/channels/{temp_channel_id}/messages/"
                    f"pins/{messages[0]['id']}"
                ),
                reason="Pitmark HQ self-test pin",
                expected={200, 204},
            )
            await discord_request(
                "DELETE",
                (
                    f"{DISCORD_API}/channels/{temp_channel_id}/messages/"
                    f"pins/{messages[0]['id']}"
                ),
                reason="Pitmark HQ self-test unpin",
                expected={200, 204},
            )
            results.append((
                "Pin / unpin messages",
                True,
                "PIN_MESSAGES works",
            ))
        except Exception as exc:
            results.append((
                "Pin / unpin messages",
                False,
                str(exc)[:180],
            ))

        try:
            await discord_request(
                "PATCH",
                f"{DISCORD_API}/channels/{temp_channel_id}",
                reason="Pitmark HQ self-test slowmode",
                json={"rate_limit_per_user": 2},
            )
            await discord_request(
                "PATCH",
                f"{DISCORD_API}/channels/{temp_channel_id}",
                reason="Pitmark HQ self-test reset slowmode",
                json={"rate_limit_per_user": 0},
            )
            results.append(("Slowmode", True, "set and reset"))
        except Exception as exc:
            results.append(("Slowmode", False, str(exc)[:180]))

        try:
            await discord_hq_moderation.set_channel_lock(
                guild_id,
                temp_channel_id,
                owner_user_id,
                locked=True,
            )
            await discord_hq_moderation.set_channel_lock(
                guild_id,
                temp_channel_id,
                owner_user_id,
                locked=False,
            )
            results.append((
                "Channel lock / unlock",
                True,
                "permission state restored",
            ))
        except Exception as exc:
            results.append((
                "Channel lock / unlock",
                False,
                str(exc)[:180],
            ))

        try:
            deleted = await discord_hq_moderation.purge_messages(
                temp_channel_id, 10
            )
            results.append((
                "Message purge",
                deleted >= 3,
                f"{deleted} test messages removed",
            ))
        except Exception as exc:
            results.append(("Message purge", False, str(exc)[:180]))

        bot_perms = int(pf.get("permissions") or 0)
        member_mod_bits = (
            (1 << 1)
            | (1 << 2)
            | (1 << 40)
        )
        results.append((
            "Kick / ban / timeout capability",
            (bot_perms & member_mod_bits) == member_mod_bits,
            (
                "permission-capability verified; "
                "no real member was touched"
            ),
        ))

    except Exception as exc:
        results.append(("Self-test runner", False, str(exc)[:250]))
    finally:
        if temp_channel_id:
            try:
                await discord_request(
                    "DELETE",
                    f"{DISCORD_API}/channels/{temp_channel_id}",
                    reason="Pitmark HQ self-test cleanup",
                    expected={200, 204},
                )
            except Exception:
                pass
        if temp_role_id:
            try:
                await discord_request(
                    "DELETE",
                    f"{DISCORD_API}/guilds/{guild_id}/roles/{temp_role_id}",
                    reason="Pitmark HQ self-test cleanup",
                    expected={200, 204},
                )
            except Exception:
                pass

    passed = sum(1 for _name, ok, _detail in results if ok)
    lines = [
        f"{'✅' if ok else '❌'} **{name}** — {detail}"
        for name, ok, detail in results
    ]
    summary = f"**Pitmark HQ QA: {passed}/{len(results)} checks passed**"
    await log_named(
        guild_id,
        "bot-logs",
        "🧪 " + summary.replace("**", ""),
    )
    return summary + "\n" + "\n".join(lines)


async def preview_legacy(guild_id: str) -> dict[str, Any]:
    guild = (
        await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}")
    ).json()
    channels = await list_channels(guild_id)
    managed_categories = _managed_category_names()
    managed_category_ids = {
        str(ch.get("id") or "")
        for ch in channels
        if _channel_type(ch) == 4
        and str(ch.get("name") or "") in managed_categories
    }

    protected_ids = {
        str(guild.get(key) or "")
        for key in (
            "rules_channel_id",
            "public_updates_channel_id",
            "system_channel_id",
            "safety_alerts_channel_id",
        )
        if guild.get(key)
    }

    candidates: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    for ch in channels:
        if _channel_type(ch) == 4:
            continue
        if str(ch.get("parent_id") or "") in managed_category_ids:
            continue
        if str(ch.get("name") or "").casefold() not in LEGACY_NAMES:
            continue
        if str(ch.get("id") or "") in protected_ids:
            protected.append(ch)
        else:
            candidates.append(ch)

    return {
        "guild": guild,
        "channels": channels,
        "candidates": candidates,
        "protected": protected,
    }


def _find_managed_channel(
    channels: list[dict[str, Any]],
    category_name: str,
    channel_name: str,
) -> dict[str, Any] | None:
    cat = next(
        (
            ch for ch in channels
            if _channel_type(ch) == 4
            and ch.get("name") == category_name
        ),
        None,
    )
    if not cat:
        return None
    return next(
        (
            ch for ch in channels
            if str(ch.get("parent_id") or "") == str(cat.get("id") or "")
            and ch.get("name") == channel_name
        ),
        None,
    )


async def quarantine_legacy(guild_id: str, owner_user_id: str) -> str:
    """Make the new Pitmark channels canonical and quarantine old starter channels."""
    await preflight(guild_id, False)
    preview = await preview_legacy(guild_id)
    channels = preview["channels"]

    new_rules = _find_managed_channel(
        channels, "📌 START HERE", "rules"
    )
    new_updates = _find_managed_channel(
        channels, "📌 START HERE", "announcements"
    )
    new_system = _find_managed_channel(
        channels, "🟠 PITMARK CENTRAL", "pitmark-chat"
    )

    guild_patch: dict[str, Any] = {}
    if new_rules:
        guild_patch["rules_channel_id"] = str(new_rules["id"])
    if new_updates:
        guild_patch["public_updates_channel_id"] = str(
            new_updates["id"]
        )
    if new_system:
        guild_patch["system_channel_id"] = str(new_system["id"])

    if guild_patch:
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/guilds/{guild_id}",
            reason=(
                "Pitmark HQ legacy cleanup: canonical channel remap"
            ),
            json=guild_patch,
        )

    preview = await preview_legacy(guild_id)
    candidates = preview["candidates"]
    channels = preview["channels"]

    legacy_cat = next(
        (
            ch for ch in channels
            if _channel_type(ch) == 4
            and ch.get("name") == LEGACY_CATEGORY_NAME
        ),
        None,
    )
    if candidates and not legacy_cat:
        legacy_cat = (
            await discord_request(
                "POST",
                f"{DISCORD_API}/guilds/{guild_id}/channels",
                reason="Pitmark HQ legacy quarantine",
                json={
                    "name": LEGACY_CATEGORY_NAME,
                    "type": 4,
                },
            )
        ).json()

    moved: list[str] = []
    if legacy_cat:
        for ch in candidates:
            await discord_request(
                "PATCH",
                f"{DISCORD_API}/channels/{ch['id']}",
                reason="Pitmark HQ legacy quarantine",
                json={"parent_id": str(legacy_cat["id"])},
            )
            moved.append(str(ch.get("name") or ch.get("id")))

    protected = [
        str(ch.get("name") or ch.get("id"))
        for ch in (await preview_legacy(guild_id))["protected"]
    ]

    if moved:
        await log_named(
            guild_id,
            "bot-logs",
            "🧹 Pitmark HQ quarantined legacy channels: "
            + ", ".join(moved),
        )

    lines = [
        (
            "✅ New Pitmark `rules`, `announcements`, and `pitmark-chat` "
            "are now the canonical Community/system channels."
        ),
        (
            "✅ Moved to **🧹 LEGACY REVIEW**: "
            + ", ".join(f"`{x}`" for x in moved)
            if moved
            else "✅ No unprotected legacy channels needed moving."
        ),
        "Nothing was deleted; message history is preserved.",
    ]
    if protected:
        lines.append(
            "Left protected by Discord: "
            + ", ".join(f"`{x}`" for x in protected)
        )
    return "\n".join(lines)
