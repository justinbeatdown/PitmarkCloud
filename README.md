# Pitmark Cloud v0.12.9

Pitmark Cloud is the shared backend and operations layer for the Pitmark ecosystem: Control Center, Autopilot, Shield, Campaigns, Outreach, Racing Community, and the Pitmark Racing Tools architecture.

## v0.12.9 — Ecosystem Notification Engine

This release introduces a Cloud-owned Notification Engine designed once for desktop, mobile, and future Pitmark clients.

- **Notification Engine:** durable Critical / Action / Opportunity / Info priority model; deduplication; read state; reason/audit context; quiet-hours preference foundation; opportunities remain bundled by default instead of interrupting the user.
- **Desktop Control Center:** Notification Center on the Dashboard with `WHY PITMARK NOTIFIED YOU` context.
- **Mobile Control Center:** reads the same Cloud notification records and shows the same unread state. No separate mobile notification logic.
- **Autopilot Intelligence v2.1:** source freshness gate. Current opportunities have a seven-day hard ceiling, 0–72 hour sources receive a freshness boost, 3–7 day sources are penalized, and undated sources are penalized. Older material belongs in Research Agent background context, not the current opportunity feed.
- **Shield:** Critical/Action security and communications events feed the shared Notification Engine. Security remains an ecosystem layer rather than an email-only feature.
- **Navigation:** the top-left Pitmark logo returns to Dashboard.
- **Docs & deployment:** runtime data, local databases, caches and bytecode remain excluded from release packages.

## Architecture rule

Build a capability once in Pitmark Cloud, then expose it safely to every Pitmark client that needs it. Security, identity, notifications, relationships, verification, permissions, and analytics are shared ecosystem services rather than duplicated product logic.

## Safety / autonomy

Pitmark remains approval-first for external communication and publishing. Notification priority does not grant additional autonomy. Uncertainty reduces autonomy; it never increases it.


## v0.12.9 ecosystem release
- Autonomy Control Center provides shared OFF / APPROVAL / AUTO policies, with red-zone actions permanently HUMAN ONLY.
- Intelligence v2.2 uses strict current-source freshness: dated sources only, Google News `when:3d`, 96-hour ceiling, stale persisted opportunities archived/hidden from current views.
- Mobile notifications use the same Cloud sync endpoint as desktop and the PWA service worker is network-first with a versioned cache.
- Pitmark continues to advance Autopilot, Shield, Campaigns, Outreach, Racing Community, Control Center, mobile and PRT-facing architecture as one ecosystem.
