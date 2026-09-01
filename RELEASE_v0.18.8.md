# Pitmark Cloud v0.18.8 — Control Center / Mail Cleanup

Built from the current GitHub main branch (v0.18.7 baseline).

## Included
- PRT site Discord community invite updated to https://discord.gg/jP6fQuW7dr.
- Pitmark Mail deletes now remove linked live Shield review records while preserving audit history.
- One-time startup cleanup removes already-orphaned Pitmark Mail Shield queue records.
- Autopilot intelligence Facebook posts automatically receive platform-native Instagram and X approval-queue variants.
- Control Center dashboard outreach card now represents follow-ups actually due, not the total contact count.
- Dashboard cleanup hides redundant Quick Actions and collapses an empty Notification Center.
- Pitmark Mail client layer adds formatted/sanitized HTML email rendering, clickable safe links, remote email images with no-referrer, Reply All, Forward, and mailbox search.
- Desktop and mobile receive the same mail-client and dashboard cleanup layer.
- Current Support Hub category-filter code from GitHub is preserved; it already clears the search field rather than populating it.

## Safety
- Existing Discord bot/gateway/configuration files are not included in this patch.
- Resend DNS, webhook secrets, API keys, Shopify mail forwarding, and Discord environment variables are untouched.
