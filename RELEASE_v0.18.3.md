# Pitmark Cloud v0.18.3 — Discord Permission Matrix Refresh

- Update the HQ permission map for Discord's 2026 granular permission changes.
- Add explicit `PIN_MESSAGES` and `BYPASS_SLOWMODE` support.
- Make the Moderator role a functional full moderation role: kick, ban, timeout, manage messages, pin messages, manage threads, manage nicknames, voice moderation, audit log, and slowmode bypass.
- Give Support the message/thread/pin/voice permissions needed for the Support Desk without Administrator.
- Give Developer audit-log/webhook/thread/pin permissions without broad server administration.
- Give Partnerships and Marketing explicit normal staff permissions plus pin/slowmode access; Marketing can create/manage scheduled events.
- Keep Owner and Administrator on Discord Administrator.
- Keep partner/customer/subscription/racing-interest roles non-privileged.
- `/hq sync` repairs the existing role and channel permission matrix in place.
