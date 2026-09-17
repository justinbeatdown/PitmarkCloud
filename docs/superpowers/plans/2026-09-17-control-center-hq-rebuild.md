# Pitmark Control Center HQ Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Pitmark Control Center into a fast, premium, task-first corporate operating system driven by real Pitmark data, while removing legacy bundle collisions and preserving working business logic.

**Architecture:** Replace the current layered Control Center frontend with one authenticated responsive application shell shared by desktop and mobile. Add a focused HQ/Work API layer that aggregates existing domain services and the live Pitmark Master Checklist without shadow state. Existing Autopilot, PRT, relationships, editorial, and system services remain authoritative; the new frontend consumes them through a centralized API client and isolates failures per module.

**Tech Stack:** FastAPI/Python, SQLAlchemy-backed existing services, Google Sheets REST API through existing Google Workspace OAuth credentials, vanilla ES modules, HTML/CSS, GitHub Actions, Render auto-deploy.

**Spec:** `docs/superpowers/specs/2026-09-17-control-center-task-first-ux-design.md`

## Global Constraints

- No Email/Comms inbox/thread UI in the new Control Center.
- No finance/banking/accounting UI.
- Pitmark Master Checklist remains the operational source of truth; do not create a competing task database.
- Existing PRT, Founder's Race, Autopilot/content, relationship, editorial, authentication, and system services remain authoritative.
- `/control` and authenticated `/control/mobile` must use the same application shell and feature registry.
- Do not load `/control.js`, `/control-mobile.js`, `control-center-v19`, `v191`, `v195`, `v201`, `v202`, old runtime bundles, or legacy mail-client assets in the authenticated shell.
- Social Operations remains disabled; the UI may manage stored/manual generated posts without re-enabling autonomous publishing.
- Use module-level failure isolation; one broken source cannot blank the app.
- Minimum touch target is 44px; support safe-area insets and reduced motion.
- Render auto-deploys `main`; never manually redeploy immediately after a merge.

---

### Task 1: Regression contract and legacy-shell isolation

**Files:**
- Modify: `scripts/test_control_center_2026_contract.py`
- Modify: `api/control_center_ui.py`
- Modify: `api/control_mobile.html` or remove authenticated dependence on it
- Modify: `.github/workflows/control-center-2026-verify.yml`

**Interfaces:**
- Consumes: current authenticated `/control` and `/control/mobile` route behavior.
- Produces: a single new-shell route contract with no legacy enhancement injections.

- [ ] **Step 1: Add failing regression assertions**

Extend the contract test so authenticated shell source must not contain or receive injected references to:

```python
LEGACY_ASSETS = (
    '/control.js',
    '/control-mobile.js',
    'control-center-v19',
    'control-center-v191',
    'control-center-v195',
    'control-center-v201',
    'control-center-v202',
    'control-runtime-v194',
    'control-mail-client',
    'control-email.js',
)
```

Assert `control_center_ui.py` does not inject any of them and both authenticated routes use `control_center.html`.

- [ ] **Step 2: Run CI and confirm RED**

Commit only the test changes to the feature branch and confirm `Control Center 2026 Verify` fails because `control_center_ui.py` still injects legacy bundles.

- [ ] **Step 3: Remove legacy injection**

Change authenticated `/control` to serve the new shell with only the safe autofill guard. Change authenticated `/control/mobile` to serve the same `control_center.html` shell. Keep login behavior intact. Do not delete legacy asset routes yet; first remove all production references.

- [ ] **Step 4: Verify GREEN**

Run contract test, Python compile, and JS syntax checks in CI.

- [ ] **Step 5: Commit**

Commit as `fix: isolate Control Center from legacy bundles`.

### Task 2: Shared Google Workspace auth and Master Checklist service

**Files:**
- Create: `services/google_workspace_auth.py`
- Modify: `services/google_gmail.py`
- Create: `services/master_checklist.py`
- Create: `scripts/test_master_checklist_contract.py`

**Interfaces:**
- Produces: `access_token() -> str`, `list_items(force=False) -> dict`, `update_item(row_number, updates) -> dict`.
- Authoritative sheet: spreadsheet `18k0Lnc4Dh8WsWssLDbOobE5lCXIQO1FjlAEKcHJ-UtI`, tab `Master Checklist`, header row 7, columns A:H.

- [ ] **Step 1: Write failing service contract tests**

Test parsing of rows shaped as:

```python
['FALSE','Monitoring','P1','PRT','PRT Early Access bug monitoring','Keep collecting tester reports','Notes','2026-09-15']
```

Expected normalized item:

```python
{
  'row_number': 8,
  'done': False,
  'status': 'Monitoring',
  'priority': 'P1',
  'area': 'PRT',
  'task': 'PRT Early Access bug monitoring',
  'next_action': 'Keep collecting tester reports',
  'notes': 'Notes',
  'last_updated': '2026-09-15',
}
```

Test status buckets (`active`, `waiting`, `monitoring`, `blocked`, `completed`, `roadmap`) and explicit device-context detection (`desktop_required`, `phone_actionable`) without inventing a value when evidence is absent.

- [ ] **Step 2: Verify RED**

CI must fail because `services/master_checklist.py` does not yet exist.

- [ ] **Step 3: Centralize Workspace OAuth refresh**

Move the shared Google token refresh/cache behavior from `google_gmail.py` into `google_workspace_auth.py`, preserving the existing environment variable contract:

```text
GOOGLE_GMAIL_CLIENT_ID
GOOGLE_GMAIL_CLIENT_SECRET
GOOGLE_GMAIL_REFRESH_TOKEN
```

Keep Gmail behavior unchanged by importing the shared token function.

- [ ] **Step 4: Implement read-through Master Checklist client**

Call Google Sheets v4 values API for:

```text
'Master Checklist'!A7:H1000
```

Use a short in-process cache (default 60 seconds), include `fetched_at`, `source='google_sheets'`, `stale=False`, and on a transient fetch failure return the last successful cache as `stale=True` when available. Never fabricate rows.

- [ ] **Step 5: Implement safe row updates**

Allow only `status`, `priority`, `next_action`, and `notes`. Use the row number to update B/C/F/G only. Do not permit task/area/deletion changes through this endpoint. Invalidate the cache after success.

- [ ] **Step 6: Verify GREEN and Gmail regression**

Run Master Checklist tests plus existing import/compile checks.

- [ ] **Step 7: Commit**

Commit as `feat: add authoritative Master Checklist service`.

### Task 3: HQ / Work API layer

**Files:**
- Create: `api/control_center_hq.py`
- Modify: `api/__init__.py`
- Modify: `scripts/test_control_center_2026_contract.py`

**Interfaces:**
- `GET /api/control/hq/overview`
- `GET /api/control/work?view=<now|today|active|waiting|monitoring|blocked|desktop|phone|completed|roadmap>`
- `PATCH /api/control/work/{row_number}`
- `GET /api/control/search?q=<query>`

- [ ] **Step 1: Add failing route contract tests**

Assert all four route families exist, require Control Center authentication, and use the Master Checklist service rather than defining a new SQL task model.

- [ ] **Step 2: Verify RED**

CI fails because `control_center_hq.py` is missing.

- [ ] **Step 3: Implement Work views**

Filter normalized checklist rows without copying them into another persistence layer. `now` prioritizes blockers/P0/P1/actionable rows; `today` excludes completed/later and favors explicit phone/desktop context only when relevant; the other views map directly to normalized state.

- [ ] **Step 4: Implement HQ aggregation**

Return independently guarded modules for checklist summary, PRT summary, Autopilot pending count, editorial drafts, relationship count, system version/status, and notifications. Each module returns `{ok, data, error}` so one failure cannot break the response.

- [ ] **Step 5: Implement grouped search**

Search current checklist rows plus readily available PRT applications/testers, Founder's Race rows, outreach contacts, and content records. Return grouped results with `kind`, `title`, `subtitle`, `target_view`, and optional `target_id`.

- [ ] **Step 6: Verify GREEN**

Run route contracts and Python compile.

- [ ] **Step 7: Commit**

Commit as `feat: add HQ and Work operating APIs`.

### Task 4: Replace the application shell and design system

**Files:**
- Replace: `api/control_center.html`
- Replace: `api/control_mobile.html` with a lightweight compatibility shell or stop serving it authenticated
- Replace: `api/control_center_overhaul.css`
- Create: `api/control_center_app.js`
- Create: `api/control_center_api.js`
- Create: `api/control_center_views.js`
- Modify: `api/control_center_ui.py` to serve the new module assets

**Interfaces:**
- Desktop/mobile share one DOM/application shell.
- Primary domains: `hq`, `work`, `prt`, `partnerships`, `content`, `store`, `people`, `systems`, `insights`.
- Sub-workspaces render contextually rather than expanding the persistent rail indefinitely.

- [ ] **Step 1: Add failing shell assertions**

Require all nine domain identifiers, command bar, mobile bottom navigation, global detail-sheet container, and no Comms/Email/finance labels.

- [ ] **Step 2: Verify RED**

CI fails against the current six-item card shell.

- [ ] **Step 3: Build premium compact shell**

Use centralized CSS custom properties for color, spacing, type, radius, elevation, and motion. Desktop uses a compact rail + top command strip + content workspace. Mobile uses bottom navigation plus a More sheet and the same view registry.

- [ ] **Step 4: Add shared API client**

`control_center_api.js` handles JSON, auth expiry, request cancellation, consistent errors, and mutation calls. Do not duplicate `fetch()` wrappers across views.

- [ ] **Step 5: Add view registry/router**

`control_center_app.js` owns navigation, URL hash state, command palette, refresh, sheet/drawer lifecycle, and top-level loading/error isolation.

- [ ] **Step 6: Verify shell GREEN**

Run HTML contract, JS syntax, responsive CSS contract.

- [ ] **Step 7: Commit**

Commit as `feat: replace Control Center with HQ application shell`.

### Task 5: HQ and Work user experience

**Files:**
- Modify: `api/control_center_views.js`
- Modify: `api/control_center_overhaul.css`

**Interfaces:**
- Consumes `/api/control/hq/overview`, `/api/control/work`, `/api/control/search`, and safe work mutations.

- [ ] **Step 1: Add failing frontend contract assertions**

Require `Today`, `Needs Attention`, `Waiting`, `Pitmark Pulse`, `Recent Activity`, and Work views `Now/Today/Active/Waiting/Monitoring/Blocked/Desktop/Phone/Completed/Roadmap`.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement HQ**

Render one compact operating brief, one prioritized action queue, small pulse/status strips, recent progress/activity, and useful freshness/error state. No oversized hero card.

- [ ] **Step 4: Implement Work**

Render dense checklist rows with priority/status/area, next action, notes preview, last-updated state, responsive filters, and safe quick status actions. Mutation failure must leave the authoritative row unchanged in UI.

- [ ] **Step 5: Implement command/search**

Desktop shortcut `/` or `Ctrl/Cmd+K`; mobile search button. Group results and navigate directly to the relevant workspace/context.

- [ ] **Step 6: Verify GREEN**

- [ ] **Step 7: Commit**

Commit as `feat: add HQ and Master Checklist workspaces`.

### Task 6: Content / Autopilot and Editorial

**Files:**
- Modify: `api/control_center_views.js`
- Modify: `api/control_center_overhaul.css`
- Modify: `scripts/test_control_center_2026_contract.py`

**Interfaces:**
- Existing Autopilot post/composer/update/decision endpoints.
- Existing blog/editorial endpoints.

- [ ] **Step 1: Add failing contract for Autopilot states**

Require Generated, Needs Approval, Scheduled, Published, Archived and detail actions edit/approve/reject/schedule/archive/copy/media.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement Social Manager**

Use compact queue rows and a side detail panel/full-screen mobile sheet. Keep the composer in a drawer. Read real stored posts only; do not re-enable autonomous Social Operations.

- [ ] **Step 4: Implement Editorial**

Separate blog/news draft workflow from social posts. Show real draft/publication state and supported actions/links.

- [ ] **Step 5: Verify GREEN**

- [ ] **Step 6: Commit**

Commit as `feat: restore first-class Autopilot and editorial operations`.

### Task 7: PRT, Founder's Race, Partnerships, People, Store/Brand, Systems, Insights

**Files:**
- Modify: `api/control_center_views.js`
- Modify: `api/control_center_overhaul.css`
- Modify: `scripts/test_control_center_2026_contract.py`

**Interfaces:**
- `/api/control/ops/overview`
- `/api/control/ops/testers`
- `/api/control/ops/founders-race`
- `/api/control/ops/feedback`
- existing outreach/community/status/brief/notifications endpoints
- Master Checklist area-filtered rows for Store/Brand and project context

- [ ] **Step 1: Add failing domain contract assertions**

Require PRT tabs Applications/Testers/Founder's Race/Feedback; Partnerships operating list; People aggregation; Store & Brand work view; Systems health; Insights backed by real counts.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement PRT**

Dense actionable application/tester/feedback surfaces and Founder's Race standings with direct links to existing full admin pages.

- [ ] **Step 4: Implement Partnerships and People**

Use existing outreach/community data. Do not invent relationship state. Provide operational rows and next-action emphasis.

- [ ] **Step 5: Implement Store & Brand**

Use real Master Checklist rows matching Store/Web/Brand/Commerce plus supported store connection state. No finance metrics.

- [ ] **Step 6: Implement Systems and Insights**

Systems renders service/deploy/notification/automation state in human language. Insights derives only real operating counts/momentum from checklist, PRT, content, and relationships.

- [ ] **Step 7: Verify GREEN**

- [ ] **Step 8: Commit**

Commit as `feat: complete Pitmark operating domains`.

### Task 8: Performance, resilience, cleanup, and production verification

**Files:**
- Modify: `api/control_center_app.js`
- Modify: `api/control_center_api.js`
- Modify: `api/control_center_views.js`
- Modify: `api/control_center_overhaul.css`
- Modify: `scripts/test_control_center_2026_contract.py`
- Modify: `.github/workflows/control-center-2026-verify.yml`
- Delete legacy Control Center assets only after reference audit proves they are unused by every remaining route.

**Interfaces:**
- Produces a release-ready exact-head commit.

- [ ] **Step 1: Add resilience/performance regression checks**

Assert one module failure does not prevent unrelated view rendering, duplicate global listeners are not registered, mobile safe-area/touch/reduced-motion rules exist, and the new shell does not reference legacy assets.

- [ ] **Step 2: Audit references before deletion**

Search the repository for every legacy Control Center asset and route. Delete only files with no remaining consumers; otherwise leave them unreferenced and document the dependency.

- [ ] **Step 3: Optimize requests and lifecycle**

Parallelize independent loads, avoid duplicate fetches within a view, abort stale requests on navigation, use short-lived in-memory view caches where appropriate, and clean up listeners/observers.

- [ ] **Step 4: Run exact-head quality gate**

Run:

```bash
python scripts/test_control_center_2026_contract.py -v
python scripts/test_master_checklist_contract.py -v
python -m py_compile api/control_center_hq.py api/control_center_2026.py api/control_center_ui.py api/__init__.py services/google_workspace_auth.py services/master_checklist.py services/google_gmail.py
node --check api/control_center_app.js
node --check api/control_center_api.js
node --check api/control_center_views.js
```

- [ ] **Step 5: Open PR and inspect complete diff**

Confirm no email/finance UI, no accidental Social Operations reactivation, no old bundle injection, and no PRT/Autopilot regression.

- [ ] **Step 6: Merge only after exact-head CI succeeds**

Use squash merge into `main`.

- [ ] **Step 7: Verify Render production**

Confirm auto-deploy is `live` on the merge SHA. Verify new shell assets are served, Master Checklist API returns live or clearly identified stale/unavailable state, PRT ops endpoints return success, Autopilot records render, and desktop/mobile share the same domains.

- [ ] **Step 8: Update the Pitmark Master Checklist**

Record the completed Control Center rebuild and any remaining monitoring item in the authoritative checklist rather than maintaining a separate completion record.
