from __future__ import annotations

from typing import Any

from utils.config import settings

PITMARK_ORANGE = 0xFF5500

# Discord permission flags, kept explicit so Pitmark role definitions remain
# readable and stay aligned with Discord's current granular permission model.
CREATE_INSTANT_INVITE = 1 << 0
KICK_MEMBERS = 1 << 1
BAN_MEMBERS = 1 << 2
ADMINISTRATOR = 1 << 3
MANAGE_CHANNELS = 1 << 4
MANAGE_GUILD = 1 << 5
ADD_REACTIONS = 1 << 6
VIEW_AUDIT_LOG = 1 << 7
PRIORITY_SPEAKER = 1 << 8
STREAM = 1 << 9
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
SEND_TTS_MESSAGES = 1 << 12
MANAGE_MESSAGES = 1 << 13
EMBED_LINKS = 1 << 14
ATTACH_FILES = 1 << 15
READ_MESSAGE_HISTORY = 1 << 16
MENTION_EVERYONE = 1 << 17
USE_EXTERNAL_EMOJIS = 1 << 18
VIEW_GUILD_INSIGHTS = 1 << 19
CONNECT = 1 << 20
SPEAK = 1 << 21
MUTE_MEMBERS = 1 << 22
DEAFEN_MEMBERS = 1 << 23
MOVE_MEMBERS = 1 << 24
USE_VAD = 1 << 25
CHANGE_NICKNAME = 1 << 26
MANAGE_NICKNAMES = 1 << 27
MANAGE_ROLES = 1 << 28
MANAGE_WEBHOOKS = 1 << 29
MANAGE_GUILD_EXPRESSIONS = 1 << 30
USE_APPLICATION_COMMANDS = 1 << 31
REQUEST_TO_SPEAK = 1 << 32
MANAGE_EVENTS = 1 << 33
MANAGE_THREADS = 1 << 34
CREATE_PUBLIC_THREADS = 1 << 35
CREATE_PRIVATE_THREADS = 1 << 36
USE_EXTERNAL_STICKERS = 1 << 37
SEND_MESSAGES_IN_THREADS = 1 << 38
USE_EMBEDDED_ACTIVITIES = 1 << 39
MODERATE_MEMBERS = 1 << 40
VIEW_CREATOR_MONETIZATION_ANALYTICS = 1 << 41
USE_SOUNDBOARD = 1 << 42
CREATE_GUILD_EXPRESSIONS = 1 << 43
CREATE_EVENTS = 1 << 44
USE_EXTERNAL_SOUNDS = 1 << 45
SEND_VOICE_MESSAGES = 1 << 46
SET_VOICE_CHANNEL_STATUS = 1 << 48
SEND_POLLS = 1 << 49
USE_EXTERNAL_APPS = 1 << 50
PIN_MESSAGES = 1 << 51
BYPASS_SLOWMODE = 1 << 52

# Normal Pitmark member experience. We intentionally define this on the roles
# themselves instead of relying on @everyone inheritance so each role is
# self-contained and its Discord permission page accurately reflects what a
# member with that role should normally be able to do.
MEMBER_BASE = (
    ADD_REACTIONS
    | STREAM
    | VIEW_CHANNEL
    | SEND_MESSAGES
    | EMBED_LINKS
    | ATTACH_FILES
    | READ_MESSAGE_HISTORY
    | USE_EXTERNAL_EMOJIS
    | CONNECT
    | SPEAK
    | USE_VAD
    | CHANGE_NICKNAME
    | USE_APPLICATION_COMMANDS
    | REQUEST_TO_SPEAK
    | CREATE_PUBLIC_THREADS
    | CREATE_PRIVATE_THREADS
    | USE_EXTERNAL_STICKERS
    | SEND_MESSAGES_IN_THREADS
    | USE_EMBEDDED_ACTIVITIES
    | USE_SOUNDBOARD
    | CREATE_EVENTS
    | USE_EXTERNAL_SOUNDS
    | SEND_VOICE_MESSAGES
    | SET_VOICE_CHANNEL_STATUS
    | SEND_POLLS
    | USE_EXTERNAL_APPS
)

# Common trusted-staff conveniences. Destructive server-management permissions
# are still layered separately by job.
STAFF_BASE = (
    MEMBER_BASE
    | CREATE_INSTANT_INVITE
    | PIN_MESSAGES
    | BYPASS_SLOWMODE
)

MODERATOR_PERMISSIONS = (
    STAFF_BASE
    | KICK_MEMBERS
    | BAN_MEMBERS
    | MANAGE_CHANNELS
    | VIEW_AUDIT_LOG
    | PRIORITY_SPEAKER
    | MANAGE_MESSAGES
    | MENTION_EVERYONE
    | MUTE_MEMBERS
    | DEAFEN_MEMBERS
    | MOVE_MEMBERS
    | MANAGE_NICKNAMES
    | MANAGE_EVENTS
    | MANAGE_THREADS
    | MODERATE_MEMBERS
)

SUPPORT_PERMISSIONS = (
    STAFF_BASE
    | MANAGE_MESSAGES
    | MUTE_MEMBERS
    | DEAFEN_MEMBERS
    | MOVE_MEMBERS
    | MANAGE_THREADS
)

DEVELOPER_PERMISSIONS = (
    STAFF_BASE
    | MANAGE_CHANNELS
    | VIEW_AUDIT_LOG
    | MANAGE_WEBHOOKS
    | MANAGE_GUILD_EXPRESSIONS
    | MANAGE_EVENTS
    | MANAGE_THREADS
    | CREATE_GUILD_EXPRESSIONS
)

PARTNERSHIPS_PERMISSIONS = (
    STAFF_BASE
    | MANAGE_MESSAGES
    | MANAGE_EVENTS
)

MARKETING_PERMISSIONS = (
    STAFF_BASE
    | MANAGE_MESSAGES
    | MENTION_EVERYONE
    | MANAGE_WEBHOOKS
    | MANAGE_EVENTS
    | CREATE_GUILD_EXPRESSIONS
)

# The official HQ bot is intentionally Administrator inside the one configured
# Pitmark guild. Public/community installs remain lightweight and separate.
HQ_REQUIRED_BOT_PERMISSIONS = ADMINISTRATOR

ROLE_SPECS = [
    ("Pitmark Owner", PITMARK_ORANGE, ADMINISTRATOR),
    ("Pitmark Administrator", 0xE67E22, ADMINISTRATOR),
    ("Pitmark Developer", 0x3498DB, DEVELOPER_PERMISSIONS),
    ("Pitmark Moderator", 0x9B59B6, MODERATOR_PERMISSIONS),
    ("Pitmark Support", 0x2ECC71, SUPPORT_PERMISSIONS),
    ("Partnerships Team", 0xF1C40F, PARTNERSHIPS_PERMISSIONS),
    ("Marketing Team", 0xE91E63, MARKETING_PERMISSIONS),

    # Community/status roles receive a complete normal-member baseline.
    ("Official Partner", PITMARK_ORANGE, MEMBER_BASE),
    ("League Organizer", 0x95A5A6, MEMBER_BASE),
    ("Content Creator", 0x1ABC9C, MEMBER_BASE),
    ("Verified Driver", 0xECF0F1, MEMBER_BASE),
    ("PRT Pro", PITMARK_ORANGE, MEMBER_BASE),
    ("PRT League", 0xF39C12, MEMBER_BASE),
    ("Verified Customer", 0x27AE60, MEMBER_BASE),
    ("Beta Tester", 0x8E44AD, MEMBER_BASE),
    ("Oval Racer", 0, MEMBER_BASE),
    ("Dirt Racer", 0, MEMBER_BASE),
    ("Road Racer", 0, MEMBER_BASE),
    ("Formula Racer", 0, MEMBER_BASE),
    ("Off-Road Racer", 0, MEMBER_BASE),
    ("iRacing", 0, MEMBER_BASE),
    ("League Racer", 0, MEMBER_BASE),
    ("Setup Nerd", 0, MEMBER_BASE),
    ("Telemetry Nerd", 0, MEMBER_BASE),
]

INTEREST_ROLES = [
    "Oval Racer",
    "Dirt Racer",
    "Road Racer",
    "Formula Racer",
    "Off-Road Racer",
    "iRacing",
    "League Racer",
    "Setup Nerd",
    "Telemetry Nerd",
]

PUBLIC_CATEGORY_SPECS = [
    (
        "📌 START HERE",
        [
            ("welcome", 0, "Welcome to Pitmark Racing Co. — racing community, support, tools, leagues and events.", "readonly", None),
            ("rules", 0, "Pitmark community rules and safety guidance.", "readonly", None),
            ("announcements", 5, "Official Pitmark Racing Co. announcements.", "readonly", None),
            ("pitmark-links", 0, "Official Pitmark links and resources.", "readonly", None),
            ("choose-your-roles", 0, "Choose your racing interests and personalize the server.", "readonly", None),
        ],
    ),
    (
        "🟠 PITMARK CENTRAL",
        [
            ("pitmark-chat", 0, "The main Pitmark community paddock.", "public", None),
            ("showcase", 0, "Share rigs, wins, paints, screenshots, clips and Pitmark gear.", "public", None),
            ("ideas-and-feedback", 15, "Ideas and feedback for the Pitmark ecosystem.", "public", ["Idea", "Racing Tools", "Pitmark Cloud", "Store", "Discord", "Website", "Reviewing", "Planned", "In Progress"]),
        ],
    ),
    (
        "🛟 SUPPORT CENTER",
        [
            ("support-start-here", 0, "Open a private Pitmark support ticket here.", "readonly", None),
            ("service-status", 0, "Current Pitmark service status and incident notices.", "readonly", None),
            ("common-questions", 0, "Common Pitmark support answers and troubleshooting.", "readonly", None),
            ("Support Waiting Room", 2, None, "support_waiting", None),
        ],
    ),
    (
        "🏎️ RACING TOOLS",
        [
            ("prt-announcements", 0, "Pitmark Racing Tools releases and updates.", "readonly", None),
            ("prt-discussion", 0, "Pitmark Racing Tools community discussion.", "public", None),
            ("prt-bug-reports", 15, "Report reproducible Pitmark Racing Tools issues.", "public", ["Overlay", "Telemetry", "Logbook", "Setup Tools", "Licensing", "Discord", "Updater", "UI", "Crash", "Other"]),
            ("prt-feature-requests", 15, "Suggest and discuss Racing Tools improvements.", "public", ["Overlay", "Telemetry", "Coaching", "League Tools", "Setup Tools", "UI", "Integrations", "Other"]),
        ],
    ),
    (
        "🏆 RACING COMMUNITY",
        [
            ("racing-chat", 0, "Talk racing — sim, grassroots and motorsports.", "public", None),
            ("race-results", 0, "Share race results and Pitmark race cards.", "public", None),
            ("setups-and-tips", 0, "Setup discussion, driving tips and racecraft.", "public", None),
            ("community-events", 0, "Community race nights, events and meetups.", "public", None),
            ("Pitmark Paddock", 2, None, "public", None),
            ("Garage Talk", 2, None, "public", None),
        ],
    ),
    (
        "🏆 LEAGUES",
        [
            ("find-a-league", 15, "Find leagues that fit your racing style.", "public", ["Oval", "Dirt Oval", "Sports Car", "Formula", "Off-Road", "Beginner Friendly", "Broadcast", "Recruiting"]),
            ("league-promotions", 15, "One post per league for recruitment and promotion.", "public", ["Oval", "Dirt Oval", "Sports Car", "Formula", "Off-Road", "Recruiting"]),
        ],
    ),
    (
        "🤝 PARTNERSHIPS",
        [
            ("become-a-partner", 0, "How to join the Pitmark partnership program.", "readonly", None),
            ("partner-showcase", 0, "Pitmark partners, drivers, leagues, tracks and creators.", "public", None),
        ],
    ),
]

PRIVATE_CATEGORY_SPECS = [
    ("🔒 PARTNER LOUNGE", "partner", [("partner-chat", 0, "Private Pitmark partner discussion."), ("partner-resources", 0, "Assets, resources and partner materials.")]),
    ("🎫 OPEN SUPPORT TICKETS", "support", []),
    ("🗄️ SUPPORT ARCHIVE", "support", []),
    (
        "🔐 PITMARK STAFF",
        "staff",
        [
            ("staff-chat", 0, "Private Pitmark staff room."),
            ("support-escalations", 0, "Escalated support cases and handoffs."),
            ("known-bugs", 0, "Confirmed product issues and workarounds."),
            ("moderation-log", 0, "Pitmark moderation and AutoMod log."),
            ("bot-logs", 0, "Pitmark bot operations and audit events."),
            ("Staff Office", 2, None),
        ],
    ),
    (
        "🔒 PITMARK OPERATIONS",
        "operations",
        [
            ("operations", 0, "Pitmark operating discussion."),
            ("development", 0, "Product and platform development."),
            ("cloud-status", 0, "Pitmark Cloud technical status."),
            ("security", 0, "Security operations and incident handling."),
            ("marketing", 0, "Marketing and content operations."),
            ("partnership-ops", 0, "Partnership operations."),
        ],
    ),
]


def configured() -> bool:
    return bool(
        settings.discord_bot_token
        and settings.discord_client_id
        and settings.discord_hq_guild_id
        and settings.discord_owner_user_id
    )


def overwrite(target_id: str, kind: int, allow: int = 0, deny: int = 0) -> dict[str, Any]:
    return {"id": target_id, "type": kind, "allow": str(allow), "deny": str(deny)}


def private_overwrites(
    guild_id: str,
    role_map: dict[str, dict[str, Any]],
    bot_user_id: str,
    audience: str,
) -> list[dict[str, Any]]:
    base = (
        VIEW_CHANNEL
        | SEND_MESSAGES
        | READ_MESSAGE_HISTORY
        | EMBED_LINKS
        | ATTACH_FILES
        | CONNECT
        | SPEAK
    )
    result = [
        overwrite(guild_id, 0, deny=VIEW_CHANNEL),
        overwrite(bot_user_id, 1, allow=base | MANAGE_MESSAGES | MANAGE_THREADS),
    ]
    groups = {
        "partner": ["Official Partner", "Pitmark Owner", "Pitmark Administrator", "Partnerships Team", "Pitmark Moderator"],
        "support": ["Pitmark Owner", "Pitmark Administrator", "Pitmark Moderator", "Pitmark Support", "Pitmark Developer"],
        "operations": ["Pitmark Owner", "Pitmark Administrator", "Pitmark Developer", "Partnerships Team", "Marketing Team"],
        "staff": ["Pitmark Owner", "Pitmark Administrator", "Pitmark Developer", "Pitmark Moderator", "Pitmark Support", "Partnerships Team", "Marketing Team"],
    }
    for name in groups[audience]:
        if name in role_map:
            result.append(overwrite(str(role_map[name]["id"]), 0, allow=base))
    return result


def channel_overwrites(
    guild_id: str,
    role_map: dict[str, dict[str, Any]],
    bot_user_id: str,
    access: str,
) -> list[dict[str, Any]]:
    if access == "public":
        return []

    if access == "readonly":
        result = [
            overwrite(guild_id, 0, deny=SEND_MESSAGES),
            overwrite(
                bot_user_id,
                1,
                allow=(
                    SEND_MESSAGES
                    | VIEW_CHANNEL
                    | READ_MESSAGE_HISTORY
                    | EMBED_LINKS
                    | ATTACH_FILES
                    | PIN_MESSAGES
                ),
            ),
        ]
        for name in [
            "Pitmark Owner",
            "Pitmark Administrator",
            "Pitmark Developer",
            "Pitmark Moderator",
            "Pitmark Support",
            "Partnerships Team",
            "Marketing Team",
        ]:
            if name in role_map:
                result.append(
                    overwrite(
                        str(role_map[name]["id"]),
                        0,
                        allow=(
                            SEND_MESSAGES
                            | VIEW_CHANNEL
                            | READ_MESSAGE_HISTORY
                            | EMBED_LINKS
                            | ATTACH_FILES
                            | PIN_MESSAGES
                            | BYPASS_SLOWMODE
                        ),
                    )
                )
        return result

    if access == "support_waiting":
        result = [
            overwrite(guild_id, 0, allow=VIEW_CHANNEL | CONNECT, deny=SPEAK),
            overwrite(
                bot_user_id,
                1,
                allow=VIEW_CHANNEL | CONNECT | SPEAK | MOVE_MEMBERS,
            ),
        ]
        for name in [
            "Pitmark Owner",
            "Pitmark Administrator",
            "Pitmark Moderator",
            "Pitmark Support",
        ]:
            if name in role_map:
                result.append(
                    overwrite(
                        str(role_map[name]["id"]),
                        0,
                        allow=VIEW_CHANNEL | CONNECT | SPEAK | MOVE_MEMBERS,
                    )
                )
        return result

    return []
