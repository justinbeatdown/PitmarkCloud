# Pitmark Cloud v0.12.6

Pitmark Cloud is the shared backend and operations layer for the Pitmark Racing ecosystem. The Control Center, Autopilot, Pitmark Shield, Campaigns, Outreach, Racing Community, and Pitmark Racing Tools foundations are designed to share the same data, security, relationship, and entitlement infrastructure rather than evolve as separate products.

## Current ecosystem

- **Pitmark Control Center** — desktop/mobile operations UI for the whole ecosystem.
- **Autopilot** — content generation, racing intelligence, research, opportunity evaluation, approval queues, and Outreach Prep.
- **Pitmark Shield** — ecosystem security layer. Communications classification is one capability; Shield is also the home for account, device, API, integration, request, token, and audit protection as those layers come online.
- **Campaign Manager** — durable campaign workflows including Rookie Year 2026.
- **Racing Community** — shared relationship/entity layer for racers, teams, tracks, leagues, series, organizations, and crossover real/sim communities.
- **Outreach** — relationship pipeline for tracks, leagues, teams, partners, and community contacts.
- **Pitmark Racing Tools foundations** — licensing, device security, Discord, race-result services, and future profile/league APIs.

## v0.12.6 — Daily Command Brief + Shield ecosystem pass

This release advances the ecosystem together instead of treating modules as isolated projects.

### Daily Command Brief

The Control Center Dashboard now answers **“Does Pitmark need me right now?”** using live cross-module data. The brief groups current state into:

- Critical
- Action Required
- Opportunities
- Info
- Caught Up

It currently surfaces real Shield review items, Autopilot post approvals, Outreach Prep approvals, failed research jobs, returned Rookie Year intakes, new racing opportunities, active research, blog drafts, and core security/database posture. Items deep-link to the relevant Control Center area.

### Pitmark Shield

Shield is now explicitly presented as **Ecosystem Security**, not only email protection.

Current visible controls include signed Control Center sessions, security headers, rate limiting, request-size limits, device identity validation, Discord signature verification, OAuth-token encryption readiness, persistent-database readiness, and communications protection status.

Synthetic Shield harness messages are excluded from production Review Queue counts, Shield production queues, and the Daily Command Brief. The harness remains available for safe classifier testing.

The production mailbox connector is still not connected; the UI now says so clearly instead of making an empty queue look like a live inbox.

### Campaigns / Autopilot fixes

- Restored **View Research / Check Research** on Rookie Year participant cards after the v0.12.5 UI regression.
- Preserved Research Agent and Outreach Prep workflows.
- New Rookie prospects default to **Intake Not Sent** unless explicitly created at the Intake Sent stage.
- Research/Outreach remains approval-first; nothing is sent automatically.

### Deployment hygiene

- `README.md` and `CHANGELOG.md` are versioned with every ecosystem release.
- Runtime `data/`, `__pycache__/`, `.pyc`, and other local test artifacts are excluded from release ZIPs and Git commits.
- Production persistence must come from `DATABASE_URL`, never a bundled local database.

## Architecture rules

1. **Build a capability once and reuse it across Pitmark.** Identity verification, permissions, relationships, assets, notifications, security, and analytics should be shared services where practical.
2. **Every release gets an ecosystem pass.** A feature is checked for effects on Autopilot, Shield, Control Center, Campaigns, Racing Community, Outreach, PRT-facing architecture, shared security/data, and documentation.
3. **Security is part of feature design.** New external actions and data paths must fit the Shield security model rather than bolt security on later.
4. **Uncertainty reduces autonomy.** Research may discover broadly, but unverified facts are not treated as true and external communication remains approval-first.
5. **Secrets stay server-side.** Desktop clients must never contain Shopify Admin secrets, OpenAI keys, Discord bot secrets, or equivalent privileged credentials.

## Production

Pitmark Cloud production service:

`https://pitmarkcloud.onrender.com`

Control Center:

`https://pitmarkcloud.onrender.com/control`

### Required production foundation

- `ENVIRONMENT=production`
- strong stable `PITMARK_SIGNING_SECRET`
- strong `PITMARK_ADMIN_KEY`
- durable PostgreSQL `DATABASE_URL`
- provider credentials only where the corresponding integration is enabled

See `.env.example`, `SECURITY.md`, and the deployment checklists for detailed configuration.

## Current integration status

- Persistent PostgreSQL: supported and required for production durability.
- Control Center authentication: live.
- Discord backend / gateway foundations: live where configured.
- Autopilot AI composer: live where OpenAI credentials are configured.
- Racing Intelligence: live public-news foundation.
- Research Agent: live background research workflow; discovery quality continues to improve.
- Outreach Prep: live, approval-only.
- Shopify publishing: scaffolded, not yet live.
- Meta / TikTok / X publishing: OAuth readiness only; publishing not yet live.
- Shield mailbox connector: not yet live.
- PRT public/community APIs: foundation stage; dedicated scoped customer auth remains future work.

## Release workflow

1. Unzip the release package locally.
2. Upload the release files to the `PitmarkCloud` GitHub repository root.
3. Do **not** upload a local `data/` folder if one exists outside the release package.
4. Commit the changes.
5. Let Render deploy the commit.
6. Confirm the Control Center footer version.
7. Run the short release smoke test in the UI.

Pitmark Racing Co. — **Leave Your Mark.**
