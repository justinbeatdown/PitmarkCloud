# Pitmark Cloud v0.21.29 — Team Access Account Creation Fix

Cloud-only fix for Control Center Team Access.

## Fixed
- Creating a Control Center user no longer surfaces FastAPI validation details as `[object Object]`.
- Username validation now returns a clear message when the username is outside the 2–80 character range.
- Temporary passwords shorter than 12 characters now return: `Password must be at least 12 characters.`
- Passwords over 200 characters return a clear validation message.
- Password reset uses the same human-readable validation path.

## Why this happened
The Team Access UI expected API errors to contain a simple string. FastAPI's automatic request validation returned a structured array for short passwords/usernames, which JavaScript converted to `[object Object]` in the error toast.

## Mobile parity
Team Access on desktop and mobile uses the same Control Center access API, so this server-side fix covers both interfaces without duplicating the logic.

## Notes
- No permissions or role defaults were changed.
- No existing Control Center accounts were modified.
- PRT desktop remains unchanged.

Pitmark Cloud: **0.21.29**
PRT desktop: **unchanged**
