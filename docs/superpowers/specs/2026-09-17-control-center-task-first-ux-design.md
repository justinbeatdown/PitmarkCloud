# Pitmark Control Center — Complete 2026 HQ Rebuild

## Product intent

Transform Pitmark Control Center into the central operating system and digital corporate headquarters for Pitmark Racing Co. This is not a cosmetic dashboard redesign. The application must make a one-person company feel like it has an entire operations department behind it while remaining extremely easy to operate.

The owner should be able to open Control Center and understand the state of Pitmark in under 30 seconds: what is happening, what needs attention, what moved forward, what is waiting, what is blocked, what opportunities exist, what PRT/testers/partners/content/store/systems are doing, and what action to take next.

The product must feel uniquely Pitmark: premium motorsports energy, enterprise-grade information design, fast modern interactions, restrained charcoal/black surfaces, Pitmark orange used for action/progress/priority, and no generic admin-template or AI-dashboard aesthetic.

## Governing UX rule

Complexity belongs in the system, not in the owner's workflow. Every screen must answer:

1. What is happening?
2. What matters?
3. What can I do about it?

Avoid giant walls of cards, meaningless analytics, endless menus, duplicated information, deeply nested navigation, dead widgets, technical jargon, tiny mobile controls, and display-only dashboards.

## Engineering mandate

Treat the rebuild as an engineering cleanup project as well as a UX rebuild.

- Audit before expanding.
- Prefer one authoritative implementation of each important behavior.
- Remove stale/duplicate/obsolete code after replacements are verified.
- Use Git history as the backup instead of preserving duplicate production systems.
- Do not layer another CSS/JS generation over the existing Control Center.
- Resolve competing state, duplicated listeners, duplicate API calls, stale caches, and overwrite races at the architectural source.
- Refactor a touched area first when building around it would materially worsen the architecture.
- Preserve good infrastructure and working integrations.
- Keep modules focused and maintainable.
- Centralize design tokens, API behavior, errors, auth conventions, loading states, and data-fetching conventions.
- Performance, observability, and regression prevention are first-class requirements.

## Explicit exclusions

Control Center is not an email client and is not a finance application.

Do not expose inbox/thread/mail-composer UI. Operational states such as "waiting for reply" are allowed, but Gmail remains Gmail.

Do not expose bank balances, transactions, budgets, accounting, personal finance, business banking, or financial dashboards.

## Authoritative data sources

Control Center consumes reliable sources rather than creating shadow copies.

- **Pitmark Master Checklist** — authoritative source for operational work status, priority, area/project, task, next action, notes, and completion.
- **PRT database/services** — applications, invites, tester state, feedback, bugs, release/testing state.
- **Founder's Race database/services** — competition standings/referrals/qualification state.
- **Pitmark Cloud system services** — deployment, automation, service health, notifications, runtime state.
- **Existing relationship/outreach data** — operational CRM/partner state.
- **Existing content/autopilot/editorial data** — generated posts, approvals, scheduling, published content, blog/editorial records.

Caching must identify the authoritative source, freshness, and stale-data behavior. Control Center must never silently present guessed data as live.

## Master Checklist integration

The live Master Checklist has the operational columns:

- Status
- Priority
- Area
- Task
- Next Action
- Notes
- Last Updated

The native UI must translate checklist data into useful operating views rather than embedding the spreadsheet.

Required views:

- Now
- Today
- Active
- Waiting
- Monitoring
- Blocked
- Desktop
- Phone
- Completed
- Roadmap

Checklist items should surface contextually across HQ and departmental workspaces. PRT items belong in PRT context, blocked items are promoted in HQ, waiting items appear in Waiting, completed work feeds progress/activity, and phone/desktop constraints must be obvious.

Where a safe authoritative write path exists, Control Center should support status/priority/note changes without creating a second source of truth. If a safe write path is unavailable, the UI must remain read-only for that action rather than faking success.

## Information architecture

The application shell must support growth without hard-coding today's organization. The target high-level domains are:

### HQ
Corporate operating brief, attention queue, Pitmark Pulse, progress, recent activity, and command/search.

### Work
Master Checklist operating views, projects, tasks, waiting, monitoring, completed work, roadmap, phone/desktop filters.

### PRT
PRT Operations, tester program, applications, active testers, feedback/bugs, releases/build state, Early Access, Founder's Race, Broadcast Studio context, support/community context, roadmap.

### Partnerships
Partners, tracks, series/leagues, broadcasters, creators, opportunities, active conversations, deliverables, history.

### Content
Social Manager/Autopilot, content queue, scheduled/published content, blog/news/editorial, campaigns, ideas, asset references. Image generation remains outside Control Center.

### Store & Brand
Store/product/collection/launch/brand/website initiatives sourced from real operational data such as Master Checklist and supported services. Do not invent commerce metrics that are not available.

### People
Operational people view spanning testers, partners, broadcasters, leads/community contacts, relationship state, projects, notes, last activity, next action, and links when backed by existing data.

### Systems
Services, automations, Discord bot, Pitmark Cloud, integrations, deployments, system health, human-readable automation activity, and relevant admin controls.

### Insights
Only useful derived operating trends: project velocity, PRT activity, content activity, relationship activity, completion/momentum, and other metrics backed by real source data. No vanity metrics.

Navigation may use compact grouped navigation, command palette, contextual tabs, and mobile bottom navigation. Do not force every subordinate workspace into the persistent rail.

## HQ experience

HQ is not a generic dashboard and must not start with an oversized hero card.

Above the fold should prioritize:

- a compact Today operating brief;
- meaningful Needs Attention queue;
- Waiting/Blocked visibility;
- real progress/momentum;
- Pitmark Pulse summary across major company areas;
- recent company activity;
- fast jump/search/command access.

Example HQ statements must derive from real data: "3 things need your attention", "5 projects moved forward today", "2 items are waiting", "PRT gained 2 testers", "Founder's Race standings changed".

## Global command/search

Provide a fast global command system accessible throughout the app. It should support fast navigation and search across available real entities such as tasks/checklist items, projects/areas, testers, applications, partners/outreach, feedback/bugs, articles, opportunities, Founder's Race participants, and systems.

Desktop should support a keyboard shortcut. Mobile should offer an obvious touch entry point. Results must be grouped by type and navigate to real working surfaces.

## Content / Autopilot workspace

Autopilot/social management must be a first-class operating workflow, not hidden behind a generic card.

Required post states/views:

- Generated / working queue
- Needs Approval
- Scheduled
- Published
- Archived/Rejected history

Rows must show platform, title/topic, body preview, source, age, status, schedule where applicable, and media presence.

Selecting a post opens a desktop side panel or mobile full-screen sheet with:

- full preview;
- edit title/body;
- approve;
- reject;
- schedule;
- archive;
- copy text;
- media link when present.

The composer opens in a drawer/sheet. It is not permanently embedded in the page.

Use the existing backend endpoints rather than duplicating post state:

- `GET /api/control/autopilot/posts`
- `POST /api/control/autopilot/composer/generate`
- `POST /api/control/autopilot/posts`
- `PATCH /api/control/autopilot/posts/{post_id}`
- `POST /api/control/autopilot/posts/{post_id}/decision`

The retired autonomous Social Operations system must remain disabled unless explicitly re-enabled; Control Center can manage existing/manual generated post workflows without reviving autonomous image/content automation.

## PRT operations

PRT must feel like a serious product-development environment.

Core actionable surfaces:

- applications;
- accepted/active testers;
- onboarding/invite state;
- feedback and bug reports;
- release readiness context;
- Founder's Race;
- direct links to full administrative views where deeper controls already exist.

Applications show name, role, iRacing/org identity, age, status, and safe quick actions.

Active testers show identity, activation/invite state, device binding when available, and last activity.

Feedback shows kind, severity, tester, age, status, title/detail, and reviewing/resolve actions. Blockers are visible without turning the entire product red.

Founder's Race gets a proper mobile-capable operational workspace showing leaderboard position, participant, qualified/pending/flagged referrals, milestone state, and a clear path to the full admin view.

Use the authenticated `/api/control/ops/*` services as the source instead of re-scraping old admin HTML.

## Partnerships / relationships

Provide a lightweight operational CRM, not Salesforce. Use the existing relationship/outreach source where possible.

Rows should emphasize organization/person, type, relationship stage, supporter/partner state, last activity, next follow-up, opportunity/ask, and the obvious next action.

Opportunity states should be actionable and readable (for example discovered/review/contacted/interested/active/waiting/won/passed when the underlying source supports them).

## Editorial

Blog/news/editorial is separate from the Autopilot social queue. Show real drafts, publication state, age, content type, and supported actions/links. Avoid duplicate social approval controls.

## Systems and observability

Systems translates technical state into human-readable operating information.

Include:

- current application version/deployment metadata;
- service/platform health;
- command brief;
- notifications/signals;
- automation state and recent results where available;
- relevant integration state;
- direct links/actions only where they are real.

One broken subsystem must not crash HQ. Failures are isolated by module, show what failed, and provide retry or a useful next step.

## Activity and progress

Using Pitmark should feel satisfying without becoming childish or game-like.

Use subtle progress feedback, completion summaries, project momentum, milestones, recent accomplishments, and timeline/activity. Activity should answer "What has Pitmark done lately?" using real events such as tester applications/approvals, feedback, bug resolution, releases, articles, partnerships, checklist completion, Founder's Race referrals, automations, and deploys when those events are available.

## Desktop experience

Desktop is the full operations center:

- compact persistent navigation;
- information-dense primary workspace;
- command palette;
- intelligent tables/lists;
- contextual side panels;
- split views where useful;
- quick actions;
- keyboard shortcuts;
- restrained card use;
- meaningful information above the fold.

Do not waste desktop space on giant decorative cards.

## Mobile experience

Mobile is a first-class product, not a shrunk desktop app and not a separate feature-poor codebase.

Use the same underlying feature registry/data sources with responsive mobile presentation:

- bottom navigation / compact overflow where appropriate;
- 44px+ touch targets;
- safe-area handling;
- sheets/drawers instead of giant modals;
- fast common actions;
- full-screen detail panels;
- reduced-motion support;
- no desktop-only workflows for ordinary admin tasks.

## Visual system

Use a centralized design-token system for color, typography, spacing, radii, elevation, motion, and responsive breakpoints.

Visual language:

- charcoal/black base;
- restrained white;
- Pitmark orange for activity/priority/interaction/progress/brand moments;
- subtle borders and layered depth;
- minimal glow;
- polished typography;
- smooth but lightweight micro-interactions;
- clear data hierarchy.

Beautiful must not mean heavy.

## Performance

The app should feel instant whenever technically possible.

- avoid duplicate requests;
- parallelize independent calls;
- progressively load modules;
- use skeletons instead of blank screens;
- cache intentionally with visible freshness where useful;
- lazy-load heavy/rare modules;
- debounce expensive search/filter operations;
- avoid oversized frontend bundles and heavy dependencies;
- keep list rendering efficient;
- clean up listeners/timers/observers and abort stale requests;
- avoid constant polling unless data genuinely benefits from it.

## Legacy cleanup

The authenticated `/control` and `/control/mobile` shell must not load or inject old Control Center generations on top of the new application.

The new shell must not reference:

- `/control.js`
- `/control-mobile.js`
- `control-center-v19`
- `control-center-v191`
- `control-center-v195`
- `control-center-v201`
- `control-center-v202`
- old runtime enhancement bundles
- legacy mail-client assets

Once the replacement is validated, obsolete route injection and unreachable enhancement code should be removed or left unreferenced with a deliberate follow-up deletion only when dependency checks show no consumers.

## Error resilience and data quality

- A failure in one source does not blank the application.
- Per-module errors identify the failing source.
- Authentication expiry redirects to login.
- Live/cached/stale/unavailable state is distinguishable when meaningful.
- No global red banner may claim an entire domain is unavailable if its individual sources succeeded.
- Dangerous/destructive actions require confirmation.
- Successful actions provide clear feedback.
- No visible control may be dead or decorative-only.

## Testing and quality gate

Regression coverage must include at minimum:

- new shell navigation and mobile parity;
- no Email/Comms product area;
- no finance product area;
- no legacy bundle injection;
- Autopilot post states and real endpoints;
- PRT applications/testers/Founder's Race/feedback;
- Master Checklist parsing/status categorization and failure behavior;
- authentication persistence/expiry;
- module-level network failure isolation;
- responsive safe-area/touch-target/reduced-motion rules;
- Python compile and JavaScript syntax;
- critical existing business logic affected by the rebuild.

Run lint/compile/tests, inspect duplicate/dead references, verify production data, test desktop/mobile/reload behavior, and confirm Render is running the intended commit before declaring completion.

## Deployment

Develop on the feature branch, verify CI on the exact head, review the diff for regressions and accidental legacy references, merge to `main`, and allow Render auto-deploy to handle production. Do not manually trigger a deploy when auto-deploy is enabled.

After Render reports the expected commit live, verify the production shell, new APIs, Autopilot, PRT, Master Checklist behavior, mobile parity, and legacy-bundle absence.

## Definition of success

The rebuild succeeds when:

- Pitmark is understandable in under 30 seconds;
- the owner rarely hunts for anything;
- Master Checklist work naturally flows into HQ and relevant domains;
- PRT/tester/Founder's Race operations are obvious;
- waiting/blocked work cannot disappear;
- mobile is genuinely useful;
- desktop feels powerful;
- the app feels uniquely Pitmark and dramatically more sophisticated;
- the codebase is cleaner, less duplicated, and more maintainable;
- recurring bugs caused by competing old/new implementations are removed at the root;
- new features can be added without stacking another patch layer;
- opening the app produces the feeling: **"This is where Pitmark gets run."**
