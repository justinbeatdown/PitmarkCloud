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
