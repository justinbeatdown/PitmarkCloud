# Pitmark Cloud v0.14.2 — Facebook Autopilot Publishing

This full replacement build includes:
- Facebook Page publishing from approved/scheduled Autopilot posts.
- Automatic scheduled Facebook publishing worker.
- Control Center live Publish-button readiness check.
- Shopify Racing Culture routing fix verified during live testing.
- Control Center anti-autofill fix verified during live testing.
- Version metadata updated to 0.14.2.

## New Render environment variables
Required for Facebook publishing:
- META_PAGE_ID
- META_PAGE_ACCESS_TOKEN

Optional/defaulted:
- META_GRAPH_VERSION=v24.0
- PITMARK_TIMEZONE=America/New_York

Do not commit live access tokens to GitHub.
