# Pitmark Cloud v0.16.23 — Shield Verdict Source-of-Truth Fix

Fixes the actual stale classification source.

Pitmark Mail API decoration now reads the authoritative `ShieldEvent` record instead of trusting the historical Shield copy embedded in the Resend provider payload. Inbox/thread reads also rescan before decoration, so the API and Shield counters cannot disagree after a rules update.

Applies to desktop and mobile because both consume the same mail API.
