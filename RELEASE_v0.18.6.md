# Pitmark Cloud v0.18.6 — Discord HQ QA Type Fix

- Fix the Discord HQ self-test falsely reporting normal text channels as missing.
- Discord text channels use type `0`; the previous audit used `value or -1`,
  which incorrectly converted valid type `0` to `-1`.
- Add a shared `_channel_type()` parser and use it throughout the maintenance
  audit/legacy helpers so valid zero-valued Discord enum fields stay intact.
- No server permissions, roles, channels, support behavior, moderation behavior,
  or production Discord structure are changed by this release.
