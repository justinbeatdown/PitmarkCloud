# Pitmark Control Center Task-First UX Design

## Purpose

Replace the current card-heavy Control Center refresh with a task-first operations console that makes the work Justin actually performs faster and more obvious. The Control Center should feel like a premium 2026 operations product rather than a collection of dashboards.

## Success Criteria

The finished Control Center must let an authenticated operator quickly:

- review and act on Autopilot-generated social posts;
- review PRT tester applications;
- inspect active PRT testers;
- check Founder’s Race standings and pending referrals;
- review PRT feedback and blockers;
- manage editorial/blog work;
- inspect Pitmark relationships and outreach;
- inspect platform/system status.

The operator should not need to hunt through vague categories or oversized summary cards to reach those tasks.

## Non-Negotiable Product Rules

1. Email is not a Control Center product area. Remove the mail client, inbox/thread UI, and generic Comms navigation from the new shell.
2. Autopilot is a first-class product area, not buried under a generic Content section.
3. The same feature set and live data must be available on desktop and mobile. Mobile may change layout, not capability.
4. Existing working backend behavior must be preserved rather than replaced.
5. The new shell must not load legacy Control Center enhancement bundles (`control-center-v19`, `v191`, `v195`, `v201`, `v202`, `control.js`, or old mobile bundles).
6. Direct deep links to full PRT administration pages remain available where useful.
7. The interface should prefer compact actionable queues and dense information over giant hero cards and decorative empty space.
8. No fake tiles, dead controls, placeholder data, or looks-clickable-but-does-nothing UI.

## Primary Navigation

The desktop rail and mobile navigation use these six operating areas:

1. **Overview**
2. **Autopilot**
3. **PRT**
4. **Editorial**
5. **Relationships**
6. **Systems**

There is no Email/Comms navigation item.

## Overview

Overview is an action-oriented command page, not a marketing-style dashboard.

It contains:

- a compact top command/search bar;
- a single "Needs Attention" work queue containing actionable items from Autopilot, PRT applications, PRT blockers, Founder’s Race pending referrals, editorial work, and systems alerts;
- small operational counters for pending Autopilot posts, new PRT applications, blockers, Founder’s Race pending, and editorial drafts;
- a lightweight system-health strip;
- no oversized hero card.

Each queue row must show the source, title, status, age, and one obvious next action.

## Autopilot

Autopilot is a dedicated workspace with these states/tabs:

- **Generated** — posts created by Autopilot/social tooling that are still in the working queue;
- **Needs Approval** — pending posts awaiting operator action;
- **Scheduled** — scheduled posts;
- **Published** — recent published posts;
- **Archived** — archived/rejected history when explicitly requested.

The list uses compact rows/cards showing platform, title/topic, body preview, source, age, status, scheduled time where applicable, and media presence.

Selecting a post opens a detail side panel on desktop and a full-screen sheet on mobile. The detail view supports:

- full post preview;
- inline body/title editing;
- approve;
- reject;
- schedule;
- archive;
- copy text;
- open media link when present.

The existing composer remains available, but it opens in a side drawer/sheet instead of occupying permanent page space.

The frontend must use the existing backend endpoints:

- `GET /api/control/autopilot/posts`
- `POST /api/control/autopilot/composer/generate`
- `POST /api/control/autopilot/posts`
- `PATCH /api/control/autopilot/posts/{post_id}`
- `POST /api/control/autopilot/posts/{post_id}/decision`

## PRT

PRT uses four primary tabs with counts:

- **Applications**
- **Active Testers**
- **Founder’s Race**
- **Feedback**

### Applications

Show applicant name, role, iRacing/org identity, submitted age, status, and quick actions for Accept, Hold, Decline, and Full Record.

### Active Testers

Show tester identity, activation state, invite state, device binding where available, and last-seen/redeemed age.

### Founder’s Race

Show standings in a compact table/list with position, tester, qualified referrals, pending referrals, flagged referrals, and milestone status. Keep a direct link to the full Founder’s Race admin page.

### Feedback

Show kind, severity, tester, age, status, title, and quick actions for Reviewing/Resolve. Blockers should be visually obvious without overwhelming the page.

The frontend must use the authenticated `/api/control/ops/*` endpoints already added by the prior overhaul.

## Editorial

Editorial owns content that is not the Autopilot social queue.

Primary surfaces:

- blog drafts;
- article/editorial work;
- publish-state visibility;
- links into full publishing workflows where needed.

The section should not duplicate Autopilot post approval controls.

## Relationships

Relationships consolidates Pitmark’s real-world and sim-racing relationship management:

- tracks;
- leagues/clubs;
- partners;
- outreach contacts;
- supporter/partner state;
- next follow-up where available.

It should be a usable operating list rather than a decorative directory.

## Systems

Systems is limited to operational/infrastructure information and controls:

- command brief;
- notifications/signals;
- platform health;
- relevant service status;
- autonomy/settings links where applicable.

Mail/inbox functionality does not belong here.

## Desktop UX

Desktop layout uses:

- a compact persistent left rail;
- a compact header with current section, search/command affordance, refresh, and account controls;
- one primary work surface;
- tabs/filters where the task has multiple states;
- dense rows or tables for queues;
- slide-over detail panels for selected items;
- restrained use of cards and borders;
- information-rich above-the-fold layout.

The visual style remains Pitmark dark/orange, but prioritizes hierarchy, whitespace discipline, typography, and interactive clarity over decoration.

## Mobile UX

Mobile uses the same six operating areas and the same backend data.

Navigation may use bottom tabs plus a More/overflow entry if needed, but every desktop function remains reachable. Detail panels become full-screen sheets. Touch targets must be at least 44px, layouts must honor safe-area insets, and reduced-motion preferences must be respected.

There is no separate feature-poor mobile application.

## Error Handling

- A failure in one source must not blank the entire page.
- Overview should degrade per-module and identify which source could not load.
- Autopilot/PRT tab failures should show actionable inline errors with retry controls.
- Authentication expiry should redirect to `/control` login as today.
- No generic red banner should claim PRT is unavailable when the individual PRT endpoints succeeded.

## Legacy Isolation

`/control` and `/control/mobile` must serve only the new shell plus explicitly shared safe utilities. The route must not inject old Control Center CSS/JS enhancement generations over the new DOM.

A regression test must fail if the authenticated shell contains references to:

- `/control.js`
- `/control-mobile.js`
- `control-center-v19`
- `control-center-v191`
- `control-center-v195`
- `control-center-v201`
- `control-center-v202`
- legacy mail-client assets in the new shell.

## Testing Contract

Automated contract tests must verify:

- desktop and mobile expose the same six operating areas;
- Email/Comms is absent from the shell;
- Autopilot exists as first-class navigation and includes Generated, Needs Approval, Scheduled, Published, and Archived states;
- PRT exposes Applications, Active Testers, Founder’s Race, and Feedback;
- Autopilot uses the existing real post endpoints;
- the legacy enhancement bundles are not injected;
- no mail-client assets are loaded by the new shell;
- responsive CSS includes safe-area, 44px touch-target, and reduced-motion handling;
- JavaScript syntax and Python routing compile cleanly.

## Deployment and Verification

Work is developed on a feature branch, verified by CI, merged into `main`, and allowed to auto-deploy through Render. Do not manually trigger a deploy when Render auto-deploy is enabled.

After the production deploy reaches `live`, verify:

1. Render is serving the expected commit.
2. `/api/control/ops/overview`, `/testers`, `/founders-race`, and `/feedback` return success for an authenticated session.
3. The production shell no longer loads legacy enhancement bundles.
4. Autopilot generated/pending/scheduled/published records render in the new workspace.
5. Mobile and desktop expose the same operating areas.
