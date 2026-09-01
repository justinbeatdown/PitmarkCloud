from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from services import discord_hq_store
from services.discord_hq_common import (
    ATTACH_FILES,
    DISCORD_API,
    EMBED_LINKS,
    INTEREST_ROLES,
    PITMARK_ORANGE,
    READ_MESSAGE_HISTORY,
    SEND_MESSAGES,
    VIEW_CHANNEL,
    edit_original,
    headers,
    list_channels,
    list_roles,
    log_named,
    overwrite,
    preflight,
    private_overwrites,
    send_message,
    upsert_panel,
)

ROLE_EMOJIS = {
    "Oval Racer": "🏁",
    "Dirt Racer": "🏜️",
    "Road Racer": "🛣️",
    "Formula Racer": "🏎️",
    "Off-Road Racer": "🌵",
    "iRacing": "🎮",
    "League Racer": "🏆",
    "Setup Nerd": "🔧",
    "Telemetry Nerd": "📊",
}


def modal(category: str = "other") -> dict[str, Any]:
    safe_category = (
        category
        if category in {"technical", "order", "partnership", "other"}
        else "other"
    )
    return {
        "type": 9,
        "data": {
            "custom_id": f"pitmark_ticket_modal:{safe_category}",
            "title": "Pitmark Support Desk",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "subject",
                            "label": "What do you need help with?",
                            "style": 1,
                            "required": True,
                            "max_length": 120,
                        }
                    ],
                },
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "details",
                            "label": "Tell us what happened",
                            "style": 2,
                            "required": True,
                            "max_length": 1800,
                        }
                    ],
                },
            ],
        },
    }


def modal_value(data: dict[str, Any], custom_id: str) -> str:
    for row in data.get("components") or []:
        for component in row.get("components") or []:
            if component.get("custom_id") == custom_id:
                return str(component.get("value") or "").strip()
    return ""


async def post_support_panel(guild_id: str) -> dict[str, Any]:
    channel = next(
        (
            c
            for c in await list_channels(guild_id)
            if c.get("type") == 0 and c.get("name") == "support-start-here"
        ),
        None,
    )
    if not channel:
        raise RuntimeError(
            "support-start-here is missing. Run /hq bootstrap first."
        )

    payload = {
        "embeds": [
            {
                "title": "🛟 PITMARK SUPPORT DESK",
                "description": (
                    "**Welcome to Pitmark's private support desk.**\n\n"
                    "Choose the closest category below and the bot will create a "
                    "**private ticket channel** visible only to you and Pitmark staff.\n\n"
                    "💡 **Before opening a ticket:** check **#common-questions** and "
                    "**#service-status** for quick answers or known incidents.\n\n"
                    "🔐 **Privacy:** never send passwords, full payment-card details, "
                    "authentication codes, or active license keys. Staff will ask only "
                    "for the information needed to help."
                ),
                "color": PITMARK_ORANGE,
                "fields": [
                    {
                        "name": "🛠️ Technical Support",
                        "value": (
                            "Racing Tools, Cloud, licensing, overlays, telemetry, "
                            "Discord integrations or account problems."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🛍️ Order / Billing",
                        "value": (
                            "Store orders, fulfillment, billing questions, returns or "
                            "other private purchase issues."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🤝 Partnership",
                        "value": (
                            "Drivers, leagues, tracks, series, creators, sponsorships "
                            "and collaboration."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🎫 Other",
                        "value": "Anything that doesn't cleanly fit another category.",
                        "inline": True,
                    },
                    {
                        "name": "⏱️ Response expectations",
                        "value": (
                            "Tickets are monitored by Pitmark staff. Response time can "
                            "vary depending on the issue and staff availability; opening "
                            "multiple tickets for the same problem will not make it faster."
                        ),
                        "inline": False,
                    },
                ],
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "Technical Support",
                        "custom_id": "pitmark_ticket_open:technical",
                        "emoji": {"name": "🛠️"},
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "Order / Billing",
                        "custom_id": "pitmark_ticket_open:order",
                        "emoji": {"name": "🛍️"},
                    },
                    {
                        "type": 2,
                        "style": 2,
                        "label": "Partnership",
                        "custom_id": "pitmark_ticket_open:partnership",
                        "emoji": {"name": "🤝"},
                    },
                    {
                        "type": 2,
                        "style": 2,
                        "label": "Other",
                        "custom_id": "pitmark_ticket_open:other",
                        "emoji": {"name": "🎫"},
                    },
                ],
            }
        ],
    }
    await upsert_panel(
        str(channel["id"]),
        "🛟 PITMARK SUPPORT DESK",
        payload,
    )
    return {"channel_id": str(channel["id"])}


async def post_interest_role_panel(guild_id: str) -> dict[str, Any]:
    channel = next(
        (
            c
            for c in await list_channels(guild_id)
            if c.get("type") == 0 and c.get("name") == "choose-your-roles"
        ),
        None,
    )
    if not channel:
        raise RuntimeError("choose-your-roles is missing.")

    options = [
        {
            "label": name,
            "value": name,
            "description": f"Add the {name} interest role."[:100],
            "emoji": {"name": ROLE_EMOJIS.get(name, "🏁")},
        }
        for name in INTEREST_ROLES
    ]

    payload = {
        "embeds": [
            {
                "title": "🎭 Choose Your Racing Roles",
                "description": (
                    "Tell the paddock what you're into. Pick as many as you want — "
                    "you can come back and change them at any time.\n\n"
                    "These are **interest/community roles**, not permissions or paid "
                    "subscription status."
                ),
                "color": PITMARK_ORANGE,
                "fields": [
                    {
                        "name": "🏁 Racing disciplines",
                        "value": (
                            "Oval • Dirt • Road • Formula • Off-Road"
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🎮 Community interests",
                        "value": (
                            "iRacing • League Racing • Setups • Telemetry"
                        ),
                        "inline": True,
                    },
                ],
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": "pitmark_interest_roles",
                        "placeholder": "🏁 Choose your racing interests",
                        "min_values": 0,
                        "max_values": len(options),
                        "options": options,
                    }
                ],
            }
        ],
    }

    await upsert_panel(
        str(channel["id"]),
        "🎭 Choose Your Racing Roles",
        payload,
    )
    return {"channel_id": str(channel["id"])}


async def create_ticket(
    payload: dict[str, Any],
    category: str,
    subject: str,
    details: str,
    guild_id: str,
    user_id: str,
) -> None:
    try:
        existing = discord_hq_store.open_ticket_for_user(guild_id, user_id)
        if existing:
            await edit_original(
                payload,
                f"You already have an open ticket: <#{existing['channel_id']}>",
            )
            return

        roles = {
            str(r.get("name")): r for r in await list_roles(guild_id)
        }
        category_channel = next(
            (
                c for c in await list_channels(guild_id)
                if c.get("type") == 4
                and c.get("name") == "🎫 OPEN SUPPORT TICKETS"
            ),
            None,
        )
        if not category_channel:
            raise RuntimeError(
                "Support ticket category is missing. "
                "Ask the Pitmark owner to run /hq sync."
            )

        bot_user_id = (await preflight(guild_id, False))["bot_user_id"]
        perms = private_overwrites(
            guild_id, roles, bot_user_id, "support"
        )
        perms.append(
            overwrite(
                user_id,
                1,
                allow=(
                    VIEW_CHANNEL
                    | SEND_MESSAGES
                    | READ_MESSAGE_HISTORY
                    | EMBED_LINKS
                    | ATTACH_FILES
                ),
            )
        )

        slug = (
            f"ticket-{user_id[-4:]}-"
            f"{int(datetime.now(timezone.utc).timestamp()) % 10000:04d}"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{DISCORD_API}/guilds/{guild_id}/channels",
                headers=headers("Pitmark Support Desk ticket opened"),
                json={
                    "name": slug,
                    "type": 0,
                    "parent_id": str(category_channel["id"]),
                    "topic": (
                        f"Pitmark Support • {category} • opened by {user_id}"
                    ),
                    "permission_overwrites": perms,
                },
            )
            r.raise_for_status()
            channel = r.json()

        ticket = discord_hq_store.create_ticket(
            {
                "guild_id": guild_id,
                "channel_id": str(channel["id"]),
                "opened_by_user_id": user_id,
                "category": category,
                "subject": subject[:180],
                "details": details[:4000],
            }
        )

        support_role = roles.get("Pitmark Support")
        ping = f"<@&{support_role['id']}> " if support_role else ""

        await send_message(
            str(channel["id"]),
            {
                "content": f"{ping}<@{user_id}>",
                "allowed_mentions": {
                    "roles": (
                        [str(support_role["id"])] if support_role else []
                    ),
                    "users": [user_id],
                },
                "embeds": [
                    {
                        "title": (
                            f"🎫 Ticket #{ticket['id']:04d} • "
                            f"{category.title()}"
                        ),
                        "description": details[:3900],
                        "color": PITMARK_ORANGE,
                        "fields": [
                            {
                                "name": "📝 Subject",
                                "value": subject[:1000],
                            },
                            {
                                "name": "👤 Opened by",
                                "value": f"<@{user_id}>",
                                "inline": True,
                            },
                            {
                                "name": "📌 Status",
                                "value": "🟠 Waiting for staff",
                                "inline": True,
                            },
                            {
                                "name": "💬 What happens next?",
                                "value": (
                                    "A Pitmark staff member can claim the ticket "
                                    "and reply here. Keep all details for this issue "
                                    "inside this private channel."
                                ),
                                "inline": False,
                            },
                        ],
                        "footer": {
                            "text": (
                                "Pitmark Support Desk • "
                                "Use Close when the issue is resolved."
                            )
                        },
                    }
                ],
                "components": [
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "style": 1,
                                "label": "Claim",
                                "custom_id": "pitmark_ticket_claim",
                                "emoji": {"name": "🙋"},
                            },
                            {
                                "type": 2,
                                "style": 4,
                                "label": "Close",
                                "custom_id": "pitmark_ticket_close",
                                "emoji": {"name": "🔒"},
                            },
                        ],
                    }
                ],
            },
        )

        await log_named(
            guild_id,
            "bot-logs",
            (
                f"🎫 Ticket #{ticket['id']:04d} opened by <@{user_id}> "
                f"in <#{channel['id']}> ({category})."
            ),
        )
        await edit_original(
            payload,
            f"✅ Your private support ticket is ready: <#{channel['id']}>",
        )
    except Exception as exc:
        await edit_original(
            payload,
            f"❌ Could not create your support ticket: `{str(exc)[:1000]}`",
        )


async def claim_ticket(
    guild_id: str,
    channel_id: str,
    staff_user_id: str,
) -> dict[str, Any] | None:
    ticket = discord_hq_store.ticket_by_channel(channel_id)
    if not ticket or ticket.get("status") == "closed":
        return None
    claimed = discord_hq_store.claim_ticket(channel_id, staff_user_id)
    await send_message(
        channel_id,
        {
            "content": (
                f"🙋 <@{staff_user_id}> claimed "
                f"Ticket #{claimed['id']:04d}."
            )
        },
    )
    return claimed


async def close_ticket(
    payload: dict[str, Any],
    guild_id: str,
    channel_id: str,
    actor_user_id: str,
    actor_is_staff: bool,
) -> None:
    try:
        ticket = discord_hq_store.ticket_by_channel(channel_id)
        if not ticket or ticket.get("status") == "closed":
            await edit_original(
                payload,
                "This channel is not an open Pitmark support ticket.",
            )
            return

        if not (
            actor_is_staff
            or ticket.get("opened_by_user_id") == actor_user_id
        ):
            await edit_original(
                payload,
                "Only the ticket opener or Pitmark staff can close this ticket.",
            )
            return

        archive = next(
            (
                c for c in await list_channels(guild_id)
                if c.get("type") == 4
                and c.get("name") == "🗄️ SUPPORT ARCHIVE"
            ),
            None,
        )
        if not archive:
            raise RuntimeError("Support archive category is missing. Run /hq sync.")

        closed = discord_hq_store.close_ticket(channel_id)
        roles = {
            str(r.get("name")): r for r in await list_roles(guild_id)
        }
        bot_id = (await preflight(guild_id, False))["bot_user_id"]
        archive_perms = private_overwrites(
            guild_id, roles, bot_id, "support"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.patch(
                f"{DISCORD_API}/channels/{channel_id}",
                headers=headers("Pitmark support ticket closed"),
                json={
                    "name": f"closed-{closed['id']:04d}",
                    "parent_id": str(archive["id"]),
                    "permission_overwrites": archive_perms,
                },
            )
            r.raise_for_status()

        await log_named(
            guild_id,
            "bot-logs",
            (
                f"🔒 Ticket #{closed['id']:04d} closed by "
                f"<@{actor_user_id}> and archived in <#{channel_id}>."
            ),
        )
        await edit_original(
            payload,
            f"✅ Ticket #{closed['id']:04d} closed and archived.",
        )
    except Exception as exc:
        await edit_original(
            payload,
            f"❌ Could not close this ticket: `{str(exc)[:1000]}`",
        )


async def update_participant(
    guild_id: str,
    channel_id: str,
    participant_id: str,
    add: bool,
) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        if add:
            r = await client.put(
                (
                    f"{DISCORD_API}/channels/{channel_id}/permissions/"
                    f"{participant_id}"
                ),
                headers=headers("Add Pitmark ticket participant"),
                json={
                    "type": 1,
                    "allow": str(
                        VIEW_CHANNEL
                        | SEND_MESSAGES
                        | READ_MESSAGE_HISTORY
                        | EMBED_LINKS
                        | ATTACH_FILES
                    ),
                    "deny": "0",
                },
            )
        else:
            r = await client.delete(
                (
                    f"{DISCORD_API}/channels/{channel_id}/permissions/"
                    f"{participant_id}"
                ),
                headers=headers("Remove Pitmark ticket participant"),
            )

        if r.status_code not in {200, 204}:
            r.raise_for_status()

    await send_message(
        channel_id,
        {
            "content": (
                f"{'➕ Added' if add else '➖ Removed'} <@{participant_id}> "
                f"{'to' if add else 'from'} this ticket."
            )
        },
    )


async def sync_interest_roles(
    guild_id: str,
    user_id: str,
    current_role_ids: list[str],
    selected_names: list[str],
) -> None:
    selected = {
        name for name in selected_names if name in INTEREST_ROLES
    }
    roles = {
        str(r.get("name")): r for r in await list_roles(guild_id)
    }
    current = {str(x) for x in current_role_ids}

    async with httpx.AsyncClient(timeout=20.0) as client:
        for name in INTEREST_ROLES:
            role = roles.get(name)
            if not role:
                continue

            role_id = str(role["id"])
            has = role_id in current
            wants = name in selected

            if wants and not has:
                r = await client.put(
                    (
                        f"{DISCORD_API}/guilds/{guild_id}/members/"
                        f"{user_id}/roles/{role_id}"
                    ),
                    headers=headers("Pitmark self-role selection"),
                )
            elif has and not wants:
                r = await client.delete(
                    (
                        f"{DISCORD_API}/guilds/{guild_id}/members/"
                        f"{user_id}/roles/{role_id}"
                    ),
                    headers=headers("Pitmark self-role selection"),
                )
            else:
                continue

            if r.status_code not in {200, 204}:
                r.raise_for_status()
