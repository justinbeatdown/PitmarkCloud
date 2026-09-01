from __future__ import annotations

import asyncio
from typing import Any

import httpx

from services import (
    discord_hq_content,
    discord_hq_maintenance,
    discord_hq_moderation,
    discord_hq_store,
    discord_hq_support,
)
from services.discord_hq_common import (
    ADMINISTRATOR,
    BAN_MEMBERS,
    MANAGE_GUILD,
    MANAGE_MESSAGES,
    MODERATE_MEMBERS,
    DISCORD_API,
    configured,
    edit_original,
    ensure_structure,
    headers,
    hq_install_url,
    log_named,
    preflight,
)
from utils.config import settings

HQ_COMMANDS = {"hq", "ticket", "mod"}

from services.discord_hq_commands import command_definitions


async def register_commands() -> dict[str, Any]:
    if not configured():
        return {
            "registered": [],
            "configured": False,
            "reason": "DISCORD_HQ_GUILD_ID / DISCORD_OWNER_USER_ID not configured.",
        }
    url = (
        f"{DISCORD_API}/applications/{settings.discord_client_id}/guilds/"
        f"{settings.discord_hq_guild_id}/commands"
    )
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.put(
            url, headers=headers(), json=command_definitions()
        )
        response.raise_for_status()
        payload = response.json()
    return {
        "configured": True,
        "guild_id": settings.discord_hq_guild_id,
        "registered": [
            {"name": item.get("name"), "id": item.get("id")}
            for item in payload
        ],
    }


def _user(payload: dict[str, Any]) -> dict[str, Any]:
    return (
        (payload.get("member") or {}).get("user")
        or payload.get("user")
        or {}
    )


def _user_id(payload: dict[str, Any]) -> str:
    return str(_user(payload).get("id") or "")


def _guild_id(payload: dict[str, Any]) -> str:
    return str(payload.get("guild_id") or "")


def _channel_id(payload: dict[str, Any]) -> str:
    return str(payload.get("channel_id") or "")


def _permissions(payload: dict[str, Any]) -> int:
    try:
        return int((payload.get("member") or {}).get("permissions") or 0)
    except (TypeError, ValueError):
        return 0


def _is_hq(payload: dict[str, Any]) -> bool:
    return bool(
        settings.discord_hq_guild_id
        and _guild_id(payload) == settings.discord_hq_guild_id
    )


def _is_owner(payload: dict[str, Any]) -> bool:
    return bool(
        settings.discord_owner_user_id
        and _user_id(payload) == settings.discord_owner_user_id
    )


def _is_staff(payload: dict[str, Any]) -> bool:
    return _is_owner(payload) or bool(
        _permissions(payload)
        & (
            MANAGE_MESSAGES
            | MODERATE_MEMBERS
            | MANAGE_GUILD
            | ADMINISTRATOR
        )
    )


def _is_moderator(payload: dict[str, Any]) -> bool:
    return _is_owner(payload) or bool(
        _permissions(payload)
        & (MODERATE_MEMBERS | MANAGE_GUILD | ADMINISTRATOR)
    )


def _can_ban(payload: dict[str, Any]) -> bool:
    return _is_owner(payload) or bool(
        _permissions(payload) & (BAN_MEMBERS | ADMINISTRATOR)
    )


def _content(text: str, ephemeral: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"content": text}
    if ephemeral:
        data["flags"] = 64
    return {"type": 4, "data": data}


def _content_with_components(
    text: str,
    components: list[dict[str, Any]],
    *,
    ephemeral: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "content": text,
        "components": components,
    }
    if ephemeral:
        data["flags"] = 64
    return {"type": 4, "data": data}


def _defer() -> dict[str, Any]:
    return {"type": 5, "data": {"flags": 64}}


def _subcommand(
    data: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    options = data.get("options") or []
    if not options:
        return "", []
    first = options[0] or {}
    return str(first.get("name") or ""), list(first.get("options") or [])


def _option(options: list[dict[str, Any]], name: str) -> Any:
    return next(
        (x.get("value") for x in options if x.get("name") == name),
        None,
    )


async def handle_command(payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_hq(payload):
        return _content(
            "This command is only available inside the official "
            "Pitmark Racing Co. Discord.",
            True,
        )

    data = payload.get("data") or {}
    name = str(data.get("name") or "")
    sub, options = _subcommand(data)

    if name == "hq":
        if not _is_owner(payload):
            await _log_denied(payload, f"/hq {sub}")
            return _content(
                "Pitmark HQ infrastructure commands are owner-locked.",
                True,
            )
        if sub == "status":
            return await _status(payload)
        if sub in {"bootstrap", "sync", "support-panel"}:
            asyncio.create_task(
                _owner_job(payload, sub),
                name=f"pitmark-hq-{sub}",
            )
            return _defer()
        return _content("Unknown Pitmark HQ action.", True)

    if name == "ticket":
        if sub == "open":
            existing = discord_hq_store.open_ticket_for_user(
                _guild_id(payload), _user_id(payload)
            )
            if existing:
                return _content(
                    f"You already have an open ticket: "
                    f"<#{existing['channel_id']}>",
                    True,
                )
            return discord_hq_support.modal("other")

        if sub == "claim":
            if not _is_staff(payload):
                return _content(
                    "Only Pitmark staff can claim tickets.", True
                )
            claimed = await discord_hq_support.claim_ticket(
                _guild_id(payload),
                _channel_id(payload),
                _user_id(payload),
            )
            return _content(
                (
                    f"Ticket #{claimed['id']:04d} assigned to you."
                    if claimed
                    else "This channel is not an open Pitmark ticket."
                ),
                True,
            )

        if sub == "close":
            asyncio.create_task(
                discord_hq_support.close_ticket(
                    payload,
                    _guild_id(payload),
                    _channel_id(payload),
                    _user_id(payload),
                    _is_staff(payload),
                ),
                name="pitmark-ticket-close",
            )
            return _defer()

        if sub in {"add", "remove"}:
            if not _is_staff(payload):
                return _content(
                    "Only Pitmark staff can change ticket participants.",
                    True,
                )
            ticket = discord_hq_store.ticket_by_channel(
                _channel_id(payload)
            )
            if not ticket or ticket.get("status") == "closed":
                return _content(
                    "This channel is not an open Pitmark ticket.", True
                )
            target = str(_option(options, "user") or "")
            await discord_hq_support.update_participant(
                _guild_id(payload),
                _channel_id(payload),
                target,
                sub == "add",
            )
            return _content("Ticket participant updated.", True)

    if name == "mod":
        if not _is_moderator(payload):
            await _log_denied(payload, f"/mod {sub}")
            return _content(
                "You do not have Pitmark moderation access.", True
            )
        try:
            target = str(
                _option(options, "user")
                or _option(options, "user-id")
                or ""
            )
            result = await discord_hq_moderation.handle_action(
                guild_id=_guild_id(payload),
                channel_id=_channel_id(payload),
                moderator_id=_user_id(payload),
                action=sub,
                target_user_id=target,
                reason=str(
                    _option(options, "reason")
                    or "No reason provided."
                )[:500],
                minutes=int(_option(options, "minutes") or 0),
                amount=int(_option(options, "amount") or 0),
                seconds=int(_option(options, "seconds") or 0),
                can_ban=_can_ban(payload),
                owner_user_id=settings.discord_owner_user_id,
            )
            return _content(result, True)
        except (ValueError, PermissionError) as exc:
            return _content(str(exc), True)
        except Exception as exc:
            return _content(
                f"Moderation action failed: `{str(exc)[:1000]}`", True
            )

    return _content("Unknown Pitmark HQ command.", True)


async def handle_interaction(payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_hq(payload):
        return _content(
            "This Pitmark control only works in the official Pitmark Discord.",
            True,
        )

    typ = int(payload.get("type") or 0)
    data = payload.get("data") or {}
    custom = str(data.get("custom_id") or "")

    if typ == 3:
        if custom in {
            "pitmark_hq_selftest",
            "pitmark_hq_legacy_preview",
            "pitmark_hq_legacy_apply",
            "pitmark_hq_legacy_cancel",
            "pitmark_hq_content_refresh",
        }:
            if not _is_owner(payload):
                await _log_denied(payload, custom)
                return _content(
                    "Pitmark HQ maintenance controls are owner-locked.",
                    True,
                )

            if custom == "pitmark_hq_selftest":
                asyncio.create_task(
                    _maintenance_job(payload, "selftest"),
                    name="pitmark-hq-selftest",
                )
                return _defer()

            if custom == "pitmark_hq_content_refresh":
                asyncio.create_task(
                    _maintenance_job(payload, "content"),
                    name="pitmark-hq-content-refresh",
                )
                return _defer()

            if custom == "pitmark_hq_legacy_preview":
                preview = await discord_hq_maintenance.preview_legacy(
                    _guild_id(payload)
                )
                names = [
                    str(ch.get("name") or ch.get("id"))
                    for ch in (
                        preview["candidates"] + preview["protected"]
                    )
                ]
                summary = (
                    "No old starter channels were found."
                    if not names
                    else "Legacy starter channels detected: "
                    + ", ".join(f"`{name}`" for name in names)
                    + ".\n\n"
                    "Apply will **not delete anything**. It will make the "
                    "new Pitmark rules/announcements/chat canonical, then "
                    "move old starter channels into **🧹 LEGACY REVIEW**."
                )
                return _content_with_components(
                    summary,
                    [
                        {
                            "type": 1,
                            "components": [
                                {
                                    "type": 2,
                                    "style": 4,
                                    "label": "Quarantine Legacy",
                                    "custom_id": "pitmark_hq_legacy_apply",
                                    "emoji": {"name": "🧹"},
                                },
                                {
                                    "type": 2,
                                    "style": 2,
                                    "label": "Cancel",
                                    "custom_id": "pitmark_hq_legacy_cancel",
                                },
                            ],
                        }
                    ],
                )

            if custom == "pitmark_hq_legacy_apply":
                asyncio.create_task(
                    _maintenance_job(payload, "legacy"),
                    name="pitmark-hq-legacy-cleanup",
                )
                return _defer()

            return _content("Legacy cleanup cancelled.", True)

        if custom.startswith("pitmark_ticket_open:"):
            existing = discord_hq_store.open_ticket_for_user(
                _guild_id(payload), _user_id(payload)
            )
            if existing:
                return _content(
                    f"You already have an open ticket: "
                    f"<#{existing['channel_id']}>",
                    True,
                )
            return discord_hq_support.modal(custom.split(":", 1)[1])

        if custom == "pitmark_ticket_claim":
            if not _is_staff(payload):
                return _content(
                    "Only Pitmark staff can claim tickets.", True
                )
            claimed = await discord_hq_support.claim_ticket(
                _guild_id(payload),
                _channel_id(payload),
                _user_id(payload),
            )
            return _content(
                (
                    f"Ticket #{claimed['id']:04d} assigned to you."
                    if claimed
                    else "This is not an open ticket."
                ),
                True,
            )

        if custom == "pitmark_ticket_close":
            asyncio.create_task(
                discord_hq_support.close_ticket(
                    payload,
                    _guild_id(payload),
                    _channel_id(payload),
                    _user_id(payload),
                    _is_staff(payload),
                ),
                name="pitmark-ticket-close-button",
            )
            return _defer()

        if custom == "pitmark_interest_roles":
            await discord_hq_support.sync_interest_roles(
                _guild_id(payload),
                _user_id(payload),
                [
                    str(x)
                    for x in (payload.get("member") or {}).get("roles")
                    or []
                ],
                [str(x) for x in data.get("values") or []],
            )
            return _content(
                "✅ Your Pitmark racing roles were updated.", True
            )

    if typ == 5 and custom.startswith("pitmark_ticket_modal:"):
        category = custom.split(":", 1)[1]
        subject = discord_hq_support.modal_value(data, "subject")
        details = discord_hq_support.modal_value(data, "details")
        asyncio.create_task(
            discord_hq_support.create_ticket(
                payload,
                category,
                subject,
                details,
                _guild_id(payload),
                _user_id(payload),
            ),
            name="pitmark-ticket-create",
        )
        return _defer()

    return _content("Unsupported Pitmark control.", True)


async def _status(payload: dict[str, Any]) -> dict[str, Any]:
    if not configured():
        return _content(
            "Pitmark HQ is not fully configured in Render yet.", True
        )
    try:
        pf = await preflight(_guild_id(payload), False)
        state = discord_hq_store.get_hq_state(_guild_id(payload))
        if pf["missing_permissions"]:
            return _content(
                "⚠️ **Pitmark HQ needs additional bot permissions.**\n"
                "Missing: "
                + ", ".join(pf["missing_permissions"])
                + f"\n\nRe-authorize for the Pitmark server only:\n"
                f"{hq_install_url()}",
                True,
            )

        text = (
            "✅ **Pitmark HQ security boundary is active.**\n"
            f"Guild lock: `{settings.discord_hq_guild_id}`\n"
            f"Owner lock: `{settings.discord_owner_user_id}`\n"
            f"Bootstrapped: "
            f"{'Yes' if state and state.get('bootstrapped') else 'No'}\n"
            f"Community mode: {'Yes' if pf['community'] else 'No'}"
        )

        return _content_with_components(
            text,
            [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 3,
                            "label": "Refresh Server Content",
                            "custom_id": "pitmark_hq_content_refresh",
                            "emoji": {"name": "✨"},
                        },
                        {
                            "type": 2,
                            "style": 1,
                            "label": "Run HQ Self-Test",
                            "custom_id": "pitmark_hq_selftest",
                            "emoji": {"name": "🧪"},
                        },
                        {
                            "type": 2,
                            "style": 2,
                            "label": "Review Legacy Channels",
                            "custom_id": "pitmark_hq_legacy_preview",
                            "emoji": {"name": "🧹"},
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        return _content(
            f"HQ status check failed: `{str(exc)[:1000]}`", True
        )


async def _owner_job(payload: dict[str, Any], action: str) -> None:
    try:
        if action == "support-panel":
            result = await discord_hq_support.post_support_panel(
                _guild_id(payload)
            )
            text = (
                f"✅ Support Desk panel repaired in "
                f"<#{result['channel_id']}>."
            )
        else:
            state = discord_hq_store.get_hq_state(_guild_id(payload))
            if (
                action == "bootstrap"
                and state
                and state.get("bootstrapped")
            ):
                text = (
                    "Pitmark HQ has already been bootstrapped. "
                    "Use `/hq sync` for safe repairs and updates."
                )
            else:
                structure = await ensure_structure(
                    _guild_id(payload),
                    _user_id(payload),
                    repair_existing=(action == "sync"),
                )
                await discord_hq_support.post_support_panel(
                    _guild_id(payload)
                )
                await discord_hq_support.post_interest_role_panel(
                    _guild_id(payload)
                )
                content_result = await discord_hq_content.sync_server_content(
                    _guild_id(payload)
                )
                automod = await discord_hq_moderation.sync_automod(
                    _guild_id(payload),
                    structure["role_map"],
                    structure["channel_map"],
                )
                discord_hq_store.mark_bootstrapped(
                    _guild_id(payload), _user_id(payload)
                )
                await log_named(
                    _guild_id(payload),
                    "bot-logs",
                    f"✅ Pitmark HQ {action} completed by "
                    f"<@{_user_id(payload)}>.",
                )
                text = (
                    f"✅ **Pitmark Discord HQ "
                    f"{'built' if action == 'bootstrap' else 'synced'}.**\n"
                    f"Roles created: {structure['roles_created']} • "
                    f"Categories created: {structure['categories_created']} • "
                    f"Channels created: {structure['channels_created']} • "
                    f"AutoMod rules synced: {automod}\n"
                    f"✨ Content panels synced: "
                    f"{content_result['panels_synced']} • "
                    f"Forum channels styled: "
                    f"{content_result['forum_channels_styled']}\n"
                    "No unrelated channels or roles were deleted."
                )
    except Exception as exc:
        text = (
            f"❌ Pitmark HQ {action} failed: `{str(exc)[:1200]}`"
        )
    await edit_original(payload, text)


async def _maintenance_job(
    payload: dict[str, Any],
    action: str,
) -> None:
    try:
        if action == "selftest":
            text = await discord_hq_maintenance.run_self_test(
                _guild_id(payload), _user_id(payload)
            )
        elif action == "legacy":
            text = await discord_hq_maintenance.quarantine_legacy(
                _guild_id(payload), _user_id(payload)
            )
        elif action == "content":
            await discord_hq_support.post_support_panel(
                _guild_id(payload)
            )
            await discord_hq_support.post_interest_role_panel(
                _guild_id(payload)
            )
            result = await discord_hq_content.sync_server_content(
                _guild_id(payload)
            )
            text = (
                "✨ **Pitmark server content refreshed.**\n"
                f"Branded panels: {result['panels_synced']}\n"
                f"Forum channels styled: "
                f"{result['forum_channels_styled']}\n"
                f"Old bootstrap seed messages removed: "
                f"{result['legacy_seed_messages_removed']}\n"
                f"Community welcome screen: "
                f"{'Synced' if result['welcome_screen_synced'] else 'Skipped by Discord'}"
            )
            await log_named(
                _guild_id(payload),
                "bot-logs",
                f"✨ Pitmark server content refreshed by "
                f"<@{_user_id(payload)}>.",
            )
        else:
            text = "Unknown HQ maintenance action."
    except Exception as exc:
        text = (
            f"❌ Pitmark HQ maintenance failed: `{str(exc)[:1200]}`"
        )
    await edit_original(payload, text)


async def _log_denied(
    payload: dict[str, Any],
    action: str,
) -> None:
    try:
        await log_named(
            _guild_id(payload),
            "bot-logs",
            f"⚠️ Denied privileged command `{action}` from "
            f"<@{_user_id(payload)}> in <#{_channel_id(payload)}>.",
        )
    except Exception:
        pass
