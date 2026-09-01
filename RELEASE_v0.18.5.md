# Pitmark Cloud v0.18.5 — Discord HQ QA & Legacy Cleanup

## HQ QA
- Add owner-only **Run HQ Self-Test** control to `/hq status`.
- Create temporary private role/channel and automatically clean them up.
- Verify actual managed role permission bitfields against the Pitmark blueprint.
- Verify managed categories/channels and all 3 Pitmark AutoMod rules.
- Exercise Discord message creation, current PIN_MESSAGES pin/unpin API,
  slowmode set/reset, channel lock/unlock, bulk purge, channel management and
  role management.
- Capability-check kick, ban and timeout without applying moderation to a real user.

## Legacy cleanup
- Add owner-only **Review Legacy Channels** control to `/hq status`.
- Preview old starter channels before any change.
- On explicit confirmation, make the new Pitmark `rules`, `announcements` and
  `pitmark-chat` channels Discord's canonical Community/system channels.
- Move old `general`, old `rules`, `moderator-only`, `clips-and-highlights`,
  `Lobby` and `Gaming` into **🧹 LEGACY REVIEW**.
- Do not delete legacy channels or message history.

## Reliability
- Route moderation REST actions through Pitmark's 429-aware Discord request
  helper so slowmode, member moderation, locking, purging, AutoMod and DMs use
  the same retry/backoff behavior as HQ bootstrap/sync.
