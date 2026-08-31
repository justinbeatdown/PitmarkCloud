# Pitmark Cloud v0.14.3 — Facebook Publish UI Fix

This full replacement build fixes the Control Center Publish button remaining disabled
after Meta Facebook Page credentials are configured.

It preserves:
- Facebook Page publishing backend
- Scheduled Facebook publishing worker
- Shopify Racing Culture live publishing routing
- Control Center autofill protection
- Existing Autopilot, Shield, Campaigns, Outreach, Blog, Community, and PRT foundation

Expected test after deploy:
1. Open Control Center → Autopilot.
2. Refresh Posts & Queue.
3. An APPROVED or SCHEDULED Facebook post should show an enabled PUBLISH button.
4. Clicking PUBLISH should post through Pitmark Cloud and change the record to PUBLISHED.
