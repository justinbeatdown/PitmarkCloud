## Current release

**v0.14.6 — Real-Time Social Timeline + Instagram Asset Workflow**

Pitmark Autopilot now includes the first live social publishing path for Facebook: approved or scheduled Facebook posts can publish through Pitmark Cloud, scheduled posts are checked by a background worker, and Control Center only enables Publish when server-side Meta Page credentials are configured. This release also carries forward the verified Racing Culture Shopify routing fix and Control Center autofill guard.

# Pitmark Cloud v0.14.6

## v0.14.0 — Shared Intelligence Ledger

Pitmark's Research Agent now writes reusable, confidence-aware evidence into the shared Racing Community layer instead of leaving research trapped inside a single job. Campaigns, Outreach and future Pitmark Racing Tools clients can build on the same durable evidence without repeating discovery work.

- **Research Agent:** live background research, identity scoring, corroboration and durable evidence reuse.
- **Racing Community:** new `racing_community_evidence` ledger with source, domain, confidence, verification state and research-job provenance.
- **Safe reuse:** evidence remains explicitly `lead`, `supported`, or `verified`; uncertain search results never silently become facts.
- **Shield:** public research URLs now pass an ecosystem security gate before entering Pitmark memory. Local/private targets, credential-bearing URLs and non-web schemes are blocked and audited.
- **Campaigns + Outreach:** continue consuming the same Research Job and Community identity context; no duplicate subsystem research architecture.
- **PRT foundation:** entity detail API now exposes the reusable evidence ledger for future scoped Racing Tools clients.
- **Dashboard:** operational counters are clickable; non-zero counters receive a quiet orange attention state and route directly to the relevant module.
- **Mobile:** remains Cloud-first; the same backend intelligence/security records are available to mobile without duplicating logic.
- **Docs:** README and changelog advance with the ecosystem release.

The governing rule remains: **build the capability once in Pitmark Cloud, then expose it safely everywhere it belongs.**

## v0.13.1 — Autonomy Enforcement + Ecosystem Polish

Autonomy policies now begin enforcing execution boundaries in backend actions. Intelligence Discovery and Research Agent respect OFF/APPROVAL/AUTO policy, with uncertainty designed to downgrade autonomy only. The Control Center brand logo now uses the same dashboard router as sidebar navigation, and non-auth forms receive stronger browser/password-manager autofill suppression.

## v0.13.0 — Autopilot Planner + Autonomy UI

Pitmark now turns fresh intelligence, campaign state, relationship context and existing workload into a small prioritized daily plan. The Planner explicitly allows **no new content** when there is nothing useful to say, and suppresses busy-work generation when the approval queue is already full.

The Autonomy Control Center is now exposed directly inside Autopilot (while remaining available in Settings), so OFF → APPROVAL → AUTO policies and permanent HUMAN ONLY red-zone boundaries are visible where Autopilot work is managed.

This release preserves Intelligence freshness hardening, Notification Engine/mobile sync, Shield ecosystem security, Research Agent, Outreach Prep, Campaigns, Racing Community/PRT foundations, README/changelog continuity, and shared Cloud-first architecture.


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
