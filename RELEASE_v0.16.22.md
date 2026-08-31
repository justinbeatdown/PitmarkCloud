# Pitmark Cloud v0.16.22 — Shield UI Refresh Fix

Fixes the stale Shield markup bug in Pitmark Mail.

The backend was correctly rescanning mail, but the desktop/mobile Shield decorator skipped badges and detail panels that already existed in the DOM. That allowed an old `Review 40%` display to remain visible after the API had already reclassified the message as `Unverified 40%`.

v0.16.22 replaces existing Shield badges, detail panels, and status text with fresh API values on each decoration pass. The same logic is used on desktop and mobile.
