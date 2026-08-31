# Pitmark Cloud Changelog

## v0.14.3 — Facebook Publish UI Fix
- Fixed Control Center Facebook Publish buttons remaining disabled after Meta credentials were configured.
- Added live `/api/control/social/status` readiness detection to the authenticated Control Center.
- Approved and scheduled Facebook posts now enable Publish only when Meta Page publishing is configured.
- Publish clicks call the existing server-side Facebook publishing endpoint and refresh queue/status after success.
- Preserved the v0.14.2 Meta publisher, scheduled worker, Shopify routing fix, and autofill protection.

## v0.14.2 — Facebook Autopilot Publishing
- Added server-side Facebook Page publishing through the Meta Graph API.
- Added `/api/control/social/status` and approval-gated live publish endpoint.
- Added background worker that checks scheduled Facebook posts every minute.
- Control Center Publish activates only when Facebook publishing is configured.
- Added `META_PAGE_ID`, `META_PAGE_ACCESS_TOKEN`, configurable Graph API version, and Pitmark timezone settings.
- Preserved the verified Shopify Racing Culture hard-priority routing fix.
- Preserved the Control Center autofill guard that prevents username/password-manager bleed into content fields.
- Runtime/package version advanced consistently to `0.14.2`.

## v0.14.1 — Shopify Live Publishing Foundation
- Added real Shopify client-credentials authentication with 24-hour token caching and safe refresh.
- Added live Shopify connection test and blog discovery endpoints.
- Added approval-gated Shopify blog publishing from Control Center.
- Added durable Shopify publish records and Shield audit events for publish success/failure.
- Blog publish respects the existing `blog_publish` Autonomy policy.
- Updated Shopify status messaging to distinguish configured credentials from authenticated connectivity.

# v0.14.0 — Shared Intelligence Ledger

- Added durable `racing_community_evidence` shared intelligence ledger.
- Research Agent persists source provenance, identity score, confidence and verification state for safe reuse.
- Corroborated research can raise Community identity confidence without promoting uncertain evidence to fact.
- Shield now gates Research Agent URLs and audits blocked unsafe/local/non-web targets.
- Community entity detail API exposes reusable evidence for Campaigns, Outreach and future PRT clients.
- Dashboard counters are clickable and use a quiet orange attention state when non-zero.
- Mobile remains backed by the same Cloud services; no duplicated mobile intelligence logic.
- README/version metadata advanced with the ecosystem.

# v0.13.1 — Autonomy Enforcement + Ecosystem Polish

- Backend autonomy enforcement foundation added.
- Intelligence Discovery and Research Agent now honor autonomy policy.
- Uncertainty can downgrade AUTO to APPROVAL; it cannot increase autonomy.
- Brand logo uses the Control Center dashboard router directly.
- Stronger anti-autofill protection across Rookie Year and Outreach creation fields.
- README updated with every release.

# v0.13.0 — Autopilot Planner + Autonomy UI

## Added
- Durable Autopilot Planner plans stored in Pitmark Cloud.
- Planner prioritizes existing approvals, campaigns, fresh intelligence and relationship context.
- Explicit HOLD/no-content plan when Pitmark has nothing useful to add.
- Approval-queue pressure suppresses unnecessary content generation.
- Autonomy Control Center is now visible directly on the Autopilot page.

## Preserved / Integrated
- Freshness hardening for current opportunities.
- Notification Engine and shared mobile state.
- Shield ecosystem-security direction and audit layer.
- Research Agent, Outreach Prep, Campaign Manager, Racing Community and PRT foundations.
- Human-only red-zone boundaries for money, contracts, refunds, legal/tax, permission and security overrides.

# v0.12.9 — Ecosystem Notification Engine

## Added
- Durable Pitmark Cloud Notification Engine.
- Critical / Action / Opportunity / Info priority vocabulary.
- Notification deduplication, unread/read state, delivery field, action target, and notification rationale.
- Quiet-hours preference foundation (21:00–08:00 default) and opportunity-push opt-in foundation.
- Desktop Notification Center.
- Mobile Control Center notification summary backed by the same Cloud API.
- Notification API for current and future Pitmark clients.

## Improved
- Autopilot Intelligence v2.1 now enforces source freshness for current opportunities.
- 0–72 hour signals receive a freshness boost; 3–7 day signals are penalized; >7 day sources are excluded from current opportunities; undated sources are penalized.
- Freshness metadata is stored separately and displayed on new opportunity cards.
- Pitmark logo now navigates back to Dashboard.
- Shield Critical/Action conditions can surface through the shared Notification Engine.

## Preserved
- Command Brief priority aggregation.
- Research Agent and Outreach Prep approval boundaries.
- Shield synthetic-test isolation.
- Racing Community and PRT foundations.
- Production data persistence and existing records.
