# Pitmark Cloud v0.18.2 — Discord Role Permission Repair

## Fixes
- `Pitmark Owner` now receives Discord `Administrator`.
- `Pitmark Administrator` now receives Discord `Administrator`.
- `Pitmark Moderator` receives the intended moderation permissions without blanket Administrator access.
- `Pitmark Support` receives support-focused message/thread/voice permissions.
- `Pitmark Developer` receives audit-log visibility while private developer/operations access remains category-scoped.
- Identity, partner, customer, subscription and racing-interest roles intentionally remain free of dangerous server-level permissions.
- `/hq sync` repairs the permissions on existing Pitmark-managed roles in place; no re-bootstrap is required.
- Owner-only HQ command security still relies on the configured Discord user ID and guild ID, so giving the Administrator role to another staff member does not grant `/hq` infrastructure access.
