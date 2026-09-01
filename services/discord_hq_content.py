from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.discord_hq_blueprint import PITMARK_ORANGE
from services.discord_hq_common import (
    DISCORD_API,
    discord_request,
    list_channels,
)

MANAGED_PANEL_PREFIX = "Pitmark • "

LEGACY_SEED_PREFIXES = (
    "🏁 **Welcome to Pitmark Racing Co.**",
    "📜 **Pitmark Community Rules**",
    "🔗 **Pitmark Racing Co.**",
    "🟢 **Pitmark services operational**",
    "❓ **Common Questions**",
    "🤝 **Become a Pitmark Partner**",
    "🏎️ **Pitmark Racing Tools**",
)

FORUM_TAG_EMOJIS = {
    "Idea": "💡",
    "Racing Tools": "🏎️",
    "Pitmark Cloud": "☁️",
    "Store": "🛍️",
    "Discord": "🤖",
    "Website": "🌐",
    "Reviewing": "👀",
    "Planned": "✅",
    "In Progress": "🚧",
    "Overlay": "🖥️",
    "Telemetry": "📊",
    "Logbook": "📓",
    "Setup Tools": "🔧",
    "Licensing": "🔑",
    "Updater": "⬆️",
    "UI": "🎨",
    "Crash": "💥",
    "Other": "❓",
    "Coaching": "🧠",
    "League Tools": "🏆",
    "Integrations": "🔌",
    "Oval": "🏁",
    "Dirt Oval": "🏜️",
    "Sports Car": "🏎️",
    "Formula": "🏎️",
    "Off-Road": "🌵",
    "Beginner Friendly": "🌱",
    "Broadcast": "📺",
    "Recruiting": "📣",
}


def _channel_type(channel: dict[str, Any]) -> int:
    value = channel.get("type")
    try:
        return int(value) if value is not None else -1
    except (TypeError, ValueError):
        return -1


def _channel_url(guild_id: str, channel: dict[str, Any] | None) -> str:
    if not channel:
        return "https://pitmarkracing.com"
    return f"https://discord.com/channels/{guild_id}/{channel['id']}"


def _button(label: str, url: str, emoji: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": 2,
        "style": 5,
        "label": label,
        "url": url,
    }
    if emoji:
        item["emoji"] = {"name": emoji}
    return item


def _embed(
    title: str,
    description: str,
    *,
    fields: list[dict[str, Any]] | None = None,
    footer: str = "Pitmark Racing Co. • Leave Your Mark.",
    timestamp: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": title,
        "description": description,
        "color": PITMARK_ORANGE,
        "footer": {"text": footer},
    }
    if fields:
        result["fields"] = fields
    if timestamp:
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


async def _recent_messages(channel_id: str) -> list[dict[str, Any]]:
    return list(
        (
            await discord_request(
                "GET",
                f"{DISCORD_API}/channels/{channel_id}/messages",
                params={"limit": 100},
            )
        ).json()
    )


async def _cleanup_legacy_seed(channel_id: str) -> int:
    removed = 0
    for message in await _recent_messages(channel_id):
        text = str(message.get("content") or "")
        if not any(text.startswith(prefix) for prefix in LEGACY_SEED_PREFIXES):
            continue
        try:
            await discord_request(
                "DELETE",
                f"{DISCORD_API}/channels/{channel_id}/messages/{message['id']}",
                reason="Pitmark launch polish: remove legacy bootstrap seed",
                expected={200, 204},
            )
            removed += 1
        except Exception:
            pass
    return removed


async def _upsert_panel(
    channel: dict[str, Any],
    *,
    key: str,
    embed: dict[str, Any],
    components: list[dict[str, Any]] | None = None,
    pin: bool = True,
) -> str:
    channel_id = str(channel["id"])
    title = f"{MANAGED_PANEL_PREFIX}{key}"
    embed = dict(embed)
    embed["title"] = title

    messages = await _recent_messages(channel_id)
    existing = next(
        (
            message
            for message in messages
            if (message.get("embeds") or [])
            and str(message["embeds"][0].get("title") or "") == title
        ),
        None,
    )

    payload: dict[str, Any] = {"embeds": [embed]}
    if components:
        payload["components"] = components

    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel_id}/messages/{existing['id']}",
            json=payload,
        )
        message = response.json()
    else:
        response = await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{channel_id}/messages",
            json=payload,
        )
        message = response.json()

    if pin:
        try:
            await discord_request(
                "PUT",
                f"{DISCORD_API}/channels/{channel_id}/messages/pins/{message['id']}",
                reason="Pitmark launch polish: pin managed intro",
                expected={200, 204},
            )
        except Exception:
            # A pin failure should not make the whole content sync fail.
            pass

    return str(message["id"])


def _public_cards(
    guild_id: str,
    channels: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    support = channels.get("support-start-here")
    roles = channels.get("choose-your-roles")
    chat = channels.get("pitmark-chat")
    prt = channels.get("prt-discussion")
    racing = channels.get("racing-chat")
    partner = channels.get("become-a-partner")

    return {
        "welcome": {
            "key": "🏁 WELCOME TO PITMARK RACING CO.",
            "embed": _embed(
                "",
                (
                    "**The official Pitmark community, live support hub, and racing paddock.**\n\n"
                    "Whether you're here for **Pitmark Racing Tools**, support, leagues, "
                    "partnerships, or just to talk racing — you're in the right place."
                ),
                fields=[
                    {
                        "name": "🚦 Start Here",
                        "value": (
                            "Read **#rules**, choose your racing interests in "
                            "**#choose-your-roles**, then introduce yourself in **#pitmark-chat**."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "🛟 Need Help?",
                        "value": (
                            "Open a **private support ticket** in **#support-start-here**. "
                            "Only you and Pitmark staff can see your ticket."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "🏎️ Pitmark Racing Tools",
                        "value": (
                            "Release news lives in **#prt-announcements**. Talk features, "
                            "telemetry, overlays and setups in **#prt-discussion**."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "🏆 Racing Community",
                        "value": (
                            "Share results, setups, clips and find leagues. "
                            "All racing disciplines are welcome."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "🤝 Work With Pitmark",
                        "value": (
                            "Drivers, leagues, tracks, series and creators can start in "
                            "**#become-a-partner**."
                        ),
                        "inline": False,
                    },
                ],
            ),
            "components": [
                {
                    "type": 1,
                    "components": [
                        _button("Choose Roles", _channel_url(guild_id, roles), "🎭"),
                        _button("Support Desk", _channel_url(guild_id, support), "🛟"),
                        _button("Pitmark Chat", _channel_url(guild_id, chat), "💬"),
                        _button("Website", "https://pitmarkracing.com", "🏁"),
                    ],
                }
            ],
        },
        "rules": {
            "key": "📜 COMMUNITY RULES",
            "embed": _embed(
                "",
                (
                    "We want this to feel like a good paddock: competitive, helpful, "
                    "fun, and welcoming. Keep it simple — **respect the people here.**"
                ),
                fields=[
                    {
                        "name": "1️⃣ Respect the paddock",
                        "value": (
                            "No harassment, hate speech, threats, targeted abuse, "
                            "doxxing, or deliberately making another member miserable."
                        ),
                    },
                    {
                        "name": "2️⃣ Keep it safe",
                        "value": (
                            "No scams, malware, piracy, credential theft, illegal content, "
                            "or attempts to compromise Pitmark or another member."
                        ),
                    },
                    {
                        "name": "3️⃣ Keep it reasonably clean",
                        "value": (
                            "No explicit NSFW content. Use common sense with language and "
                            "remember this is a mixed public racing community."
                        ),
                    },
                    {
                        "name": "4️⃣ Don't spam the grid",
                        "value": (
                            "No mass mentions, repeated ads, unsolicited DMs, invite spam, "
                            "or flooding channels."
                        ),
                    },
                    {
                        "name": "5️⃣ Promote in the right places",
                        "value": (
                            "League recruiting belongs in **#league-promotions**. "
                            "Partnership/business requests belong in the Partnership flow."
                        ),
                    },
                    {
                        "name": "6️⃣ Protect private information",
                        "value": (
                            "**Never post passwords, license keys, payment details, order "
                            "information, addresses, private emails, or other sensitive data "
                            "in a public channel.** Use a private support ticket."
                        ),
                    },
                    {
                        "name": "7️⃣ Staff moderation",
                        "value": (
                            "Pitmark staff may remove content or moderate accounts to keep "
                            "the community safe. If you think something went wrong, open a "
                            "support ticket instead of starting a public fight."
                        ),
                    },
                    {
                        "name": "8️⃣ Discord rules still apply",
                        "value": (
                            "Discord's Terms of Service and Community Guidelines apply "
                            "everywhere in this server."
                        ),
                    },
                ],
            ),
        },
        "pitmark-links": {
            "key": "🔗 OFFICIAL PITMARK LINKS",
            "embed": _embed(
                "",
                (
                    "Use these links when you need the real thing — no mystery downloads, "
                    "no random DMs, no sketchy mirrors."
                ),
                fields=[
                    {
                        "name": "🏁 Pitmark Racing Co.",
                        "value": "https://pitmarkracing.com",
                        "inline": False,
                    },
                    {
                        "name": "🏎️ Pitmark Racing Tools",
                        "value": "https://prt.pitmarkracing.com",
                        "inline": False,
                    },
                    {
                        "name": "🛟 Discord Support",
                        "value": "Use **#support-start-here** for private help.",
                        "inline": False,
                    },
                ],
            ),
            "components": [
                {
                    "type": 1,
                    "components": [
                        _button("Pitmark Website", "https://pitmarkracing.com", "🏁"),
                        _button("Racing Tools", "https://prt.pitmarkracing.com", "🏎️"),
                        _button("Support Desk", _channel_url(guild_id, support), "🛟"),
                    ],
                }
            ],
        },
        "service-status": {
            "key": "🟢 SERVICE STATUS",
            "embed": _embed(
                "",
                (
                    "**Pitmark Discord HQ is online and connected.**\n\n"
                    "Known incidents, maintenance windows, degraded services and "
                    "resolution updates will be posted in this channel."
                ),
                fields=[
                    {
                        "name": "🤖 Discord Bot",
                        "value": "🟢 Online",
                        "inline": True,
                    },
                    {
                        "name": "🎫 Support Desk",
                        "value": "🟢 Online",
                        "inline": True,
                    },
                    {
                        "name": "☁️ Pitmark Cloud",
                        "value": "🟢 Connected",
                        "inline": True,
                    },
                    {
                        "name": "📣 Incident updates",
                        "value": (
                            "If something breaks, staff will post the issue, current impact, "
                            "workarounds (if any), and resolution here."
                        ),
                        "inline": False,
                    },
                ],
                footer="Pitmark Racing Co. • Status refreshed by Pitmark HQ sync.",
                timestamp=True,
            ),
        },
        "common-questions": {
            "key": "❓ COMMON QUESTIONS",
            "embed": _embed(
                "",
                "A few quick answers before you open a ticket:",
                fields=[
                    {
                        "name": "🛠️ Racing Tools isn't working. Where do I go?",
                        "value": (
                            "Check **#prt-announcements** for known issues, then open a "
                            "Technical Support ticket if you still need help."
                        ),
                    },
                    {
                        "name": "🐛 I found a bug",
                        "value": (
                            "Use **#prt-bug-reports** for non-sensitive reproducible bugs. "
                            "If logs/account details are involved, use a private ticket."
                        ),
                    },
                    {
                        "name": "💡 I have a feature idea",
                        "value": (
                            "Post it in **#prt-feature-requests** so other racers can discuss it."
                        ),
                    },
                    {
                        "name": "🛍️ I have an order/billing issue",
                        "value": (
                            "Open **#support-start-here → Order / Billing**. "
                            "Do not post order numbers or personal info publicly."
                        ),
                    },
                    {
                        "name": "🏆 Can I promote my league?",
                        "value": (
                            "Yep — use **#league-promotions**. Keep one forum post per league "
                            "so recruiting stays organized."
                        ),
                    },
                    {
                        "name": "🤝 How do I partner with Pitmark?",
                        "value": (
                            "Read **#become-a-partner** and use the Partnership ticket option "
                            "if you want to start a conversation."
                        ),
                    },
                    {
                        "name": "🎭 How do I change my racing roles?",
                        "value": (
                            "Use the selector in **#choose-your-roles** any time. "
                            "Your choices are not permanent."
                        ),
                    },
                ],
            ),
            "components": [
                {
                    "type": 1,
                    "components": [
                        _button("Open Support Desk", _channel_url(guild_id, support), "🛟"),
                        _button("Choose Roles", _channel_url(guild_id, roles), "🎭"),
                    ],
                }
            ],
        },
        "become-a-partner": {
            "key": "🤝 BECOME A PITMARK PARTNER",
            "embed": _embed(
                "",
                (
                    "Pitmark partnerships are built around racing people and organizations "
                    "we can actually grow with — not just logo swaps."
                ),
                fields=[
                    {
                        "name": "🏎️ Drivers",
                        "value": (
                            "Grassroots racers, sim racers and developing drivers with a "
                            "story, program or audience we can help support."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🏆 Leagues & Series",
                        "value": (
                            "Organized communities looking for race sponsorship, tools, "
                            "promotion or a longer-term relationship."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🏁 Tracks & Organizations",
                        "value": (
                            "Real-world tracks, racing organizations and events that align "
                            "with Pitmark's community-first direction."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "🎥 Creators",
                        "value": (
                            "Racing-focused creators who make useful, entertaining, or "
                            "community-driven content."
                        ),
                        "inline": True,
                    },
                    {
                        "name": "📬 Ready to talk?",
                        "value": (
                            "Use the **Partnership** option in the Support Desk or visit "
                            "Pitmark Racing Co. online. Tell us who you are, what you race/do, "
                            "and what kind of partnership you're looking for."
                        ),
                        "inline": False,
                    },
                ],
            ),
            "components": [
                {
                    "type": 1,
                    "components": [
                        _button("Partnership Ticket", _channel_url(guild_id, support), "🤝"),
                        _button("Pitmark Website", "https://pitmarkracing.com", "🏁"),
                    ],
                }
            ],
        },
        "prt-announcements": {
            "key": "🏎️ RACING TOOLS ANNOUNCEMENTS",
            "embed": _embed(
                "",
                (
                    "Official releases, important fixes, service notices, beta calls and "
                    "major Pitmark Racing Tools updates live here.\n\n"
                    "For everyday discussion, use **#prt-discussion**. For bugs and ideas, "
                    "use the dedicated Forums."
                ),
            ),
            "components": [
                {
                    "type": 1,
                    "components": [
                        _button("Racing Tools", "https://prt.pitmarkracing.com", "🏎️"),
                        _button("PRT Discussion", _channel_url(guild_id, prt), "💬"),
                    ],
                }
            ],
        },
        "pitmark-chat": {
            "key": "💬 THE PITMARK PADDOCK",
            "embed": _embed(
                "",
                (
                    "This is the main lobby. Talk racing, Pitmark, what you're working on, "
                    "what you're watching, or what you're racing tonight.\n\n"
                    "**New here?** Drop your name, racing discipline, favorite track/car, "
                    "and what brought you to Pitmark. 👋"
                ),
            ),
        },
        "showcase": {
            "key": "📸 SHOWCASE",
            "embed": _embed(
                "",
                (
                    "Show us what you've got: **rigs, paint schemes, race wins, clips, "
                    "screenshots, builds, Pitmark gear and cool racing projects.**\n\n"
                    "Give people a little context with the post — screenshots are better "
                    "when we know what we're looking at. 😄"
                ),
            ),
        },
        "prt-discussion": {
            "key": "🔧 RACING TOOLS PADDOCK",
            "embed": _embed(
                "",
                (
                    "Talk Pitmark Racing Tools here: overlays, telemetry, logbook, setup "
                    "tools, coaching ideas, integrations and whatever you're experimenting with.\n\n"
                    "🐛 Reproducible bug? **#prt-bug-reports**\n"
                    "💡 Feature idea? **#prt-feature-requests**"
                ),
            ),
        },
        "racing-chat": {
            "key": "🏁 RACING CHAT",
            "embed": _embed(
                "",
                (
                    "**Oval, dirt, road, formula, off-road, sim or real-world — all of it counts.**\n\n"
                    "Bench racing is encouraged. Being a jerk because somebody likes a "
                    "different discipline is not. 😄"
                ),
            ),
        },
        "race-results": {
            "key": "🏆 RACE RESULTS",
            "embed": _embed(
                "",
                (
                    "Finished a race? Post it. Wins are cool, but so are comeback drives, "
                    "first clean races, personal bests and absolute disasters with a good story. 😂\n\n"
                    "Pitmark Racing Tools race cards are welcome here."
                ),
            ),
        },
        "setups-and-tips": {
            "key": "🔧 SETUPS & TIPS",
            "embed": _embed(
                "",
                (
                    "Share setup advice, driving technique, telemetry observations and "
                    "racecraft tips.\n\n"
                    "When asking for help, include the **car, track, conditions, discipline, "
                    "and what the car is doing**. “It sucks” is technically data, but not much. 😂"
                ),
            ),
        },
        "community-events": {
            "key": "📅 COMMUNITY EVENTS",
            "embed": _embed(
                "",
                (
                    "Pitmark community races, partner events, watch parties and special "
                    "activities will be posted here.\n\n"
                    "League owners: recruiting belongs in **#league-promotions**."
                ),
            ),
        },
        "partner-showcase": {
            "key": "🏁 PITMARK PARTNER SHOWCASE",
            "embed": _embed(
                "",
                (
                    "Meet the drivers, leagues, creators, tracks and organizations working "
                    "with Pitmark Racing Co.\n\n"
                    "Partner announcements and spotlights will live here."
                ),
            ),
        },
    }


def _staff_cards() -> dict[str, dict[str, Any]]:
    return {
        "partner-chat": {
            "key": "🤝 PARTNER LOUNGE",
            "embed": _embed(
                "",
                (
                    "Private partner room for quick coordination, questions, ideas and "
                    "cross-promotion. Keep sensitive business details in the appropriate "
                    "private support/business workflow."
                ),
            ),
        },
        "partner-resources": {
            "key": "📦 PARTNER RESOURCES",
            "embed": _embed(
                "",
                (
                    "Approved partner assets, campaign notes, useful links and current "
                    "Pitmark partner guidance belong here."
                ),
            ),
        },
        "staff-chat": {
            "key": "🔐 STAFF HQ",
            "embed": _embed(
                "",
                (
                    "General private staff coordination. Keep technical incidents in "
                    "**#known-bugs / #security**, support handoffs in **#support-escalations**, "
                    "and operating work in **PITMARK OPERATIONS**."
                ),
                footer="Pitmark Racing Co. • Staff only.",
            ),
        },
        "support-escalations": {
            "key": "🎫 SUPPORT ESCALATIONS",
            "embed": _embed(
                "",
                (
                    "Use this when a Support Desk case needs engineering, owner review, "
                    "billing/business input, or a cross-team handoff."
                ),
                footer="Pitmark Racing Co. • Staff only.",
            ),
        },
        "known-bugs": {
            "key": "🐛 KNOWN BUGS",
            "embed": _embed(
                "",
                (
                    "Confirmed product/service issues, workarounds and resolution notes. "
                    "Keep entries short enough that Support can actually use them."
                ),
                footer="Pitmark Racing Co. • Staff only.",
            ),
        },
        "moderation-log": {
            "key": "🛡️ MODERATION LOG",
            "embed": _embed(
                "",
                (
                    "Pitmark AutoMod events and staff moderation actions are logged here. "
                    "This channel is an audit trail — don't use it as general staff chat."
                ),
                footer="Pitmark Racing Co. • Staff only.",
            ),
        },
        "bot-logs": {
            "key": "🤖 BOT & HQ LOG",
            "embed": _embed(
                "",
                (
                    "Infrastructure syncs, ticket lifecycle events, security denials, QA "
                    "runs and other Pitmark bot operations are recorded here."
                ),
                footer="Pitmark Racing Co. • Staff only.",
            ),
        },
        "operations": {
            "key": "⚙️ OPERATIONS",
            "embed": _embed(
                "",
                "Cross-functional Pitmark operating decisions, priorities and internal coordination.",
                footer="Pitmark Racing Co. • Operations only.",
            ),
        },
        "development": {
            "key": "💻 DEVELOPMENT",
            "embed": _embed(
                "",
                (
                    "Pitmark Cloud, Control Center, Racing Tools and ecosystem development "
                    "coordination. Bugs belong in **#known-bugs** when Support needs visibility."
                ),
                footer="Pitmark Racing Co. • Operations only.",
            ),
        },
        "cloud-status": {
            "key": "☁️ CLOUD STATUS",
            "embed": _embed(
                "",
                (
                    "Internal Pitmark Cloud health, deploy notes, integrations and technical "
                    "service observations."
                ),
                footer="Pitmark Racing Co. • Operations only.",
            ),
        },
        "security": {
            "key": "🛡️ SECURITY",
            "embed": _embed(
                "",
                (
                    "Security incidents, suspicious behavior, credential rotation notes and "
                    "Pitmark Shield/security work. **Never paste active secrets into Discord.**"
                ),
                footer="Pitmark Racing Co. • Restricted operations.",
            ),
        },
        "marketing": {
            "key": "📣 MARKETING",
            "embed": _embed(
                "",
                "Campaign coordination, social content, promotions, launches and messaging.",
                footer="Pitmark Racing Co. • Operations only.",
            ),
        },
        "partnership-ops": {
            "key": "🤝 PARTNERSHIP OPS",
            "embed": _embed(
                "",
                (
                    "Applications, partner deliverables, sponsorship planning, outreach and "
                    "relationship management."
                ),
                footer="Pitmark Racing Co. • Operations only.",
            ),
        },
    }


async def _sync_forum_tag_emojis(channels: list[dict[str, Any]]) -> int:
    updated = 0
    for channel in channels:
        if _channel_type(channel) != 15:
            continue
        tags = list(channel.get("available_tags") or [])
        if not tags:
            continue

        changed = False
        next_tags: list[dict[str, Any]] = []
        for tag in tags:
            name = str(tag.get("name") or "")
            emoji = FORUM_TAG_EMOJIS.get(name)
            item: dict[str, Any] = {
                "id": str(tag.get("id") or ""),
                "name": name,
                "moderated": bool(tag.get("moderated")),
            }
            if tag.get("emoji_id"):
                item["emoji_id"] = str(tag["emoji_id"])
            elif emoji:
                item["emoji_name"] = emoji
                if tag.get("emoji_name") != emoji:
                    changed = True
            elif tag.get("emoji_name"):
                item["emoji_name"] = str(tag["emoji_name"])

            next_tags.append(item)

        if changed:
            await discord_request(
                "PATCH",
                f"{DISCORD_API}/channels/{channel['id']}",
                reason="Pitmark launch polish: forum tag emoji sync",
                json={"available_tags": next_tags},
            )
            updated += 1
    return updated


async def _sync_welcome_screen(
    guild_id: str,
    channels: dict[str, dict[str, Any]],
) -> bool:
    desired = []
    for name, description, emoji in [
        ("welcome", "Start here and learn your way around Pitmark.", "🏁"),
        ("pitmark-chat", "The main Pitmark community paddock.", "💬"),
        ("support-start-here", "Open a private support ticket.", "🛟"),
        ("prt-discussion", "Talk Pitmark Racing Tools.", "🏎️"),
        ("racing-chat", "Talk racing with the community.", "🏆"),
    ]:
        channel = channels.get(name)
        if channel:
            desired.append(
                {
                    "channel_id": str(channel["id"]),
                    "description": description,
                    "emoji_name": emoji,
                    "emoji_id": None,
                }
            )

    if not desired:
        return False

    try:
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/guilds/{guild_id}/welcome-screen",
            reason="Pitmark launch polish: welcome screen",
            json={
                "enabled": True,
                "description": (
                    "Welcome to Pitmark Racing Co. — racing community, "
                    "live support and Pitmark Racing Tools. Leave Your Mark."
                ),
                "welcome_channels": desired[:5],
            },
        )
        return True
    except Exception:
        # Some Discord Community configurations expose onboarding instead of
        # the legacy welcome-screen endpoint. Content sync should still succeed.
        return False


async def sync_server_content(guild_id: str) -> dict[str, Any]:
    channels_list = await list_channels(guild_id)
    channels = {
        str(channel.get("name") or ""): channel
        for channel in channels_list
        if _channel_type(channel) in {0, 5, 15}
    }

    # Give the Community page itself a real description.
    try:
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/guilds/{guild_id}",
            reason="Pitmark launch polish: guild description",
            json={
                "description": (
                    "Pitmark Racing Co. • Racing community, live support, "
                    "Pitmark Racing Tools, leagues and partners. Leave Your Mark."
                )
            },
        )
    except Exception:
        pass

    panels = 0
    legacy_removed = 0

    cards = {}
    cards.update(_public_cards(guild_id, channels))
    cards.update(_staff_cards())

    for channel_name, spec in cards.items():
        channel = channels.get(channel_name)
        if not channel or _channel_type(channel) not in {0, 5}:
            continue

        legacy_removed += await _cleanup_legacy_seed(str(channel["id"]))
        await _upsert_panel(
            channel,
            key=spec["key"],
            embed=spec["embed"],
            components=spec.get("components"),
            pin=True,
        )
        panels += 1

    forums = await _sync_forum_tag_emojis(channels_list)
    welcome_screen = await _sync_welcome_screen(guild_id, channels)

    return {
        "panels_synced": panels,
        "forum_channels_styled": forums,
        "legacy_seed_messages_removed": legacy_removed,
        "welcome_screen_synced": welcome_screen,
    }
