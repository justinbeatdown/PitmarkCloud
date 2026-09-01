from __future__ import annotations

from typing import Any

def command_definitions() -> list[dict[str, Any]]:
    user_option = {"name": "user", "description": "Discord member.", "type": 6, "required": True}
    reason_option = {"name": "reason", "description": "Reason for this action.", "type": 3, "required": False, "max_length": 500}
    return [
        {
            "name": "hq",
            "description": "Pitmark HQ infrastructure controls. Owner only.",
            "type": 1,
            "options": [
                {"name": "bootstrap", "description": "Build the Pitmark Discord HQ structure.", "type": 1},
                {"name": "sync", "description": "Repair/sync the managed Pitmark Discord HQ structure.", "type": 1},
                {"name": "status", "description": "Check Pitmark HQ configuration and bot permissions.", "type": 1},
                {"name": "support-panel", "description": "Post or repair the Pitmark Support Desk panel.", "type": 1},
            ],
        },
        {
            "name": "ticket",
            "description": "Pitmark Support Desk ticket controls.",
            "type": 1,
            "options": [
                {"name": "open", "description": "Open a private Pitmark support ticket.", "type": 1},
                {"name": "claim", "description": "Claim the current support ticket.", "type": 1},
                {"name": "close", "description": "Close and archive the current support ticket.", "type": 1},
                {"name": "add", "description": "Add a participant to the current ticket.", "type": 1, "options": [user_option]},
                {"name": "remove", "description": "Remove a participant from the current ticket.", "type": 1, "options": [user_option]},
            ],
        },
        {
            "name": "mod",
            "description": "Pitmark moderation tools.",
            "type": 1,
            "options": [
                {"name": "warn", "description": "Warn a member and log the case.", "type": 1, "options": [user_option, reason_option]},
                {"name": "timeout", "description": "Timeout a member.", "type": 1, "options": [user_option, {"name": "minutes", "description": "Timeout length in minutes (1-40320).", "type": 4, "required": True, "min_value": 1, "max_value": 40320}, reason_option]},
                {"name": "kick", "description": "Kick a member.", "type": 1, "options": [user_option, reason_option]},
                {"name": "ban", "description": "Ban a member.", "type": 1, "options": [user_option, reason_option]},
                {"name": "unban", "description": "Remove a ban by user ID.", "type": 1, "options": [{"name": "user-id", "description": "Discord user ID to unban.", "type": 3, "required": True}, reason_option]},
                {"name": "history", "description": "Show recent moderation history for a member.", "type": 1, "options": [user_option]},
                {"name": "purge", "description": "Bulk-delete recent messages from this channel.", "type": 1, "options": [{"name": "amount", "description": "Messages to remove (1-100).", "type": 4, "required": True, "min_value": 1, "max_value": 100}]},
                {"name": "lock", "description": "Lock the current text channel.", "type": 1},
                {"name": "unlock", "description": "Restore the channel permissions saved by Pitmark lock.", "type": 1},
                {"name": "slowmode", "description": "Set channel slowmode in seconds (0 disables).", "type": 1, "options": [{"name": "seconds", "description": "0-21600 seconds.", "type": 4, "required": True, "min_value": 0, "max_value": 21600}]},
            ],
        },
    ]

