# Pitmark Cloud v0.21.37 — First-Party Autopilot Scheduling

## What changed

- Added a dedicated `first_party_social_publish` autonomy policy for verified Pitmark-owned events.
- New first-party campaigns can automatically move from detection and draft generation into scheduled Facebook, Instagram, and X posts.
- Existing pending posts are preserved on first boot and are never bulk-released by this change.
- Manual posts, reactive Intelligence content, TikTok, and Discord remain human-controlled.
- Auto-scheduling avoids existing scheduled-post windows and uses conservative default Pitmark posting slots at 10 AM, 2 PM, and 6 PM America/New_York time.

## Scope

This is a backend Autopilot release. It does not add a new visible Control Center panel or redesign existing UI.

## Verification target

The next newly detected first-party event should create and schedule its eligible Facebook, Instagram, and X campaign automatically without manual approval/scheduling.
