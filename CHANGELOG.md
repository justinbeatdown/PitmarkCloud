## v0.12.0 — Mobile Control + Workflow Test Harness

- Replaces the older circular Control Center badge with the new official Pitmark badge asset.
- Adds `/control/mobile`, a phone-first installable PWA using the same signed Control Center session.
- Adds mobile quick status, Autopilot approvals, intelligence trigger, Shield review/test, Outreach list, and infrastructure links.
- Adds a repeatable Shield synthetic test harness for Legit / Review / Spam / System classifications.
- Expands Outreach UI around contact method/handle, relationship stage, supporter status, follow-up, and notes using the existing durable schema.
- Adds AI-assisted Blog / Track Spotlight draft generation plus approve/reject/schedule/archive workflow.
- Improves Autopilot Intelligence scan results so a zero-candidate run clearly reports that the scan completed.
- Adds server-side social OAuth readiness status without storing social passwords in the browser or Control Center.
- Adds mobile/PWA CSP allowances while keeping inline scripts/styles blocked.

## v0.10.0 — Private Control Center + Real Views
- Added first-time Control Center admin bootstrap using the existing Pitmark Admin Key once.
- Added username/password login with scrypt password hashing and signed HttpOnly session cookies.
- Added logout and in-dashboard password change.
- Protected /control with a server-side login gate.
- Preserved X-Pitmark-Admin-Key as emergency/service API authentication.
- Converted sidebar anchors into real Control Center views.
- Added Autopilot Posts & Queue with status filters, approve/reject/schedule/archive actions.
- Added Dashboard status cards and live views for Shield, Outreach, Blog, Directory, and Settings.
- Removed the Control Center URL advertisement from the public root payload.

# Pitmark Cloud v0.9.3 — Autopilot AI Composer

- Replaced Manual Composer's canned-first behavior with the real AI provider path.
- Added OpenAI Responses API adapter using `gpt-5.6-luna` by default for low-cost social generation.
- Added Pitmark-specific brand, racing-culture, platform, and anti-hallucination writing rules.
- Kept deterministic fallback generation only as an outage/configuration fallback.
- Added official supplied Pitmark wide logo and badge assets to the Control Center UI.
- No social-platform passwords are stored or required.

## v0.9.2
- Control Center CSP-safe frontend assets; restored styling and JavaScript without unsafe-inline.
- Fixed admin-key Connect flow by permitting same-origin API fetches.
- Applied Pitmark Control Center UI Bible styling.
- Added Pitmark Directory and Connected Accounts foundations.

# v0.8.1 - OAuth Polish

- Restored the branded Pitmark Discord OAuth success/failure page.
- CSP now permits inline CSS only on the OAuth callback page; scripts, images, frames, forms, and external resources remain blocked.
- OAuth callback validation/errors render through the same safe branded page.
- Security Foundation behavior is otherwise unchanged.

# v0.8.0 — Security Foundation

- Added per-device credential registration + authentication.
- Device secrets are hashed server-side; the raw secret is not persisted.
- Added strict device ID validation and rate limiting.
- Added security headers and request-size defenses.
- Disabled CORS by default and production API docs when `ENVIRONMENT=production`.
- Added OAuth callback escaping and Discord signature timestamp freshness validation.
- Added credential/query log redaction.
- Added `/api/security/status` readiness endpoint.
- Shopify webhook remains intentionally 501 until HMAC verification is implemented.


## v0.9.0 — Autopilot + Shield Integration
- Added Pitmark Control Center at `/control`.
- Migrated Autopilot approval queue/manual composer into Pitmark Cloud persistent database.
- Added Pitmark Shield deterministic classification/history/review API.
- Added outreach relationship pipeline and Shopify blog/Track Spotlight draft models.
- All Control Center API endpoints require the existing X-Pitmark-Admin-Key.
- Live social publishing, Gmail mailbox mutation, and Shopify article publishing remain connector-gated and are not silently enabled.

## v0.12.1 — Opportunity Engine Foundation
- Explainable scoring layer on top of existing Racing Intelligence; original discovery/blog workflows preserved.
- Scores Pitmark relevance, relationship relevance, story strength, verification, timeliness, content balance and risk.
- Rookie/first-season detection can recommend research + personalized outreach drafting.
- Cross-checks existing Outreach relationships and exposes WHY PITMARK CARES / weaknesses in Control Center.
- No automatic outreach or publishing.

## v0.12.3 — Rookie Year + Campaign Manager V1
- Added durable Campaign and CampaignParticipant models.
- Added Rookie Year 2026 campaign API and participant pipeline.
- Added Campaigns / Rookie Year Control Center view.
- Added participant stage, intake, verification, media-permission and guardian-status foundation.
- Added Research & Prepare action from Rookie Year participants using the durable Research Agent job foundation.
- Publication remains approval-first; Research & Prepare does not send outreach.
