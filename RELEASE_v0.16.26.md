# Pitmark Cloud v0.16.26 — Shield Communications Status Race Fix

Fixes the Shield page status being overwritten by the legacy Shield renderer after the Pitmark Mail-aware status had already loaded.

- Re-applies the live Pitmark Mail protection state after Shield refresh/render.
- Uses a mutation observer so the stale “production mailbox not connected” text cannot overwrite the real Pitmark Mail status.
- Applies to desktop and mobile.
- No changes to Resend, DNS, identities, routing, Shield classifications, or stored mail.
