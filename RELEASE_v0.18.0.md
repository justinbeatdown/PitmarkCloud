# Pitmark Cloud v0.18.0 — Discord HQ

## What ships
- Guild-only Pitmark HQ command surface with a hard owner-ID gate for infrastructure actions.
- Idempotent Discord server bootstrap/sync: roles, categories, text/voice/forum channels and permissions.
- Private Pitmark Support Desk tickets with category buttons, modal intake, staff ping, claim, participant management, close/archive flow and duplicate-ticket protection.
- Pitmark moderation commands: warn, timeout, kick, ban/unban, history, purge, lock/unlock and slowmode.
- Native Discord AutoMod sync for mention spam, generic spam and sexual/slur safety presets with alerts to the moderation log.
- Self-service racing-interest role selector.
- HQ ticket/moderation persistence in the existing Pitmark database.
- Public Pitmark Racing Tools Discord commands remain global and keep the lightweight public bot permission request.

## Required Render settings
- `DISCORD_HQ_GUILD_ID` — the official Pitmark Racing Co. server ID.
- `DISCORD_OWNER_USER_ID` — Justin's Discord user ID.

After deploy, re-register bot commands through the existing protected bot registration endpoint. Then run `/hq status`; if the HQ bot role needs elevated permissions, the command returns the server-locked re-authorization link. Enable Discord Community mode before `/hq bootstrap` so Forum channels can be created.
