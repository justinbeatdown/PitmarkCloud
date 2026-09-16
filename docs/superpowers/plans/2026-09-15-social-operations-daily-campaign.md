# Social Operations Daily Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Pitmark Social Operations into the single daily marketing coordinator that produces one coherent, idempotent cross-platform content package instead of only filling isolated posting gaps.

**Architecture:** Reuse existing Pitmark first-party scanners, AI composition, image generation, social asset storage, scheduling, publishing, Discord, and engagement systems. Add a small Daily Campaign domain layer that owns one campaign per Pitmark local day, selects a verified topic or community-growth fallback, tracks package completeness, and exposes status to Social Operator. Keep direct publishing limited to already-supported safe channels; TikTok/Reels remain ready-to-post assets/copy.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PostgreSQL, existing OpenAI text/image services, existing Meta/X/Discord publishing services, vanilla JavaScript Control Center UI.

**Spec:** Conversation-approved design from 2026-09-15: Social Operations is the single front door; one idempotent Daily Campaign per day; strongest verified Pitmark topic first, community-growth fallback; Facebook, Instagram, X, Discord, TikTok/Reels package; six IG slides; vertical 9:16 assets; existing official-logo-safe visual rules; package status surfaced in Social Operations.

## Global Constraints

- Do not replace existing Autopilot scanners, first-party event ingestion, publishers, or engagement systems.
- Do not create duplicate campaigns or duplicate platform posts when the operator runs repeatedly or the service restarts.
- Keep autonomous direct publishing limited to channels already supported by existing safe publishing paths.
- TikTok/Reels output is ready-to-post only until a supported direct publisher exists.
- Do not redraw or approximate the Pitmark logo; generated images must reserve branding-safe space and use existing official logo assets only when an approved existing overlay path is available.
- Preserve current Social Operator engagement guardrails.
- Preserve existing first-party events and social-post history.
- Prefer verified first-party events over generic community-growth content.

---

### Task 1: Daily Campaign Domain and Selection Logic

**Files:**
- Create: `services/social_daily_campaign.py`
- Test: `tests/test_social_daily_campaign.py`

**Interfaces:**
- Consumes: `FirstPartyEvent`, `SocialPost`, `SessionLocal`, `utcnow`, `settings.pitmark_timezone`.
- Produces: `DailyCampaign`, `DailyCampaignAsset`, `campaign_day_key(now=None) -> str`, `select_campaign_topic() -> dict`, `ensure_daily_campaign() -> dict`, `campaign_status() -> dict`.

- [ ] **Step 1: Write failing tests**
  - One campaign key is produced per Pitmark local calendar day.
  - Repeated `ensure_daily_campaign()` calls return the same campaign id.
  - A recent verified first-party event is selected before fallback content.
  - Fallback campaign is created when no eligible verified event exists.
  - Campaign status reports copy/assets per required platform.

- [ ] **Step 2: Run the targeted tests and verify they fail for missing implementation.**

- [ ] **Step 3: Implement the minimal Daily Campaign models and selection functions.**
  - Store `day_key`, `topic_type`, `topic_ref`, `title`, `summary`, `url`, `status`, `package_json`, timestamps.
  - Store campaign assets with `campaign_id`, `platform`, `slot`, `aspect`, `url`, `status`, timestamps.
  - Prefer newest processed/queued verified first-party event from the last 72 hours that is meaningful for public marketing.
  - Otherwise create a deterministic community-growth fallback keyed by local day.

- [ ] **Step 4: Run the targeted tests and verify they pass.**

- [ ] **Step 5: Commit the domain layer.**

### Task 2: Cross-Platform Package Generation

**Files:**
- Create: `services/social_daily_package.py`
- Modify: `services/openai_image_service.py`
- Test: `tests/test_social_daily_package.py`

**Interfaces:**
- Consumes: `ensure_daily_campaign()`, existing `compose_with_ai`, existing `generate_image`, existing social asset upload/public URL path, `SocialPost`.
- Produces: `generate_daily_package(campaign_id: int) -> dict`, package JSON containing copy and asset status for `facebook`, `instagram`, `x`, `discord`, `tiktok_reels`.

- [ ] **Step 1: Write failing tests**
  - Package generation creates exactly one copy variant per required platform without duplicating existing rows.
  - Instagram package declares six 4:5 slides.
  - TikTok/Reels package declares vertical 9:16 scenes/assets.
  - Re-running package generation is idempotent.
  - Failed image generation records an actionable partial state instead of duplicating or falsely marking complete.

- [ ] **Step 2: Run targeted tests and verify failure.**

- [ ] **Step 3: Implement package copy generation using verified campaign context only.**
  - Facebook: community-native finished caption.
  - Instagram: finished caption plus six-slide narrative outline.
  - X: concise platform-native copy.
  - Discord: concise Markdown update.
  - TikTok/Reels: caption plus vertical scene copy.

- [ ] **Step 4: Implement asset generation requests.**
  - Add `1024x1536` portrait support where already available.
  - Generate six portrait-safe source images for Instagram and vertical source images for TikTok/Reels.
  - Prompts must avoid fake people/cars/details and reserve safe branding/text space.
  - Persist each generated image through the existing upload/public serving mechanism and record its URL on `DailyCampaignAsset`.

- [ ] **Step 5: Run targeted tests and verify pass.**

- [ ] **Step 6: Commit package generation.**

### Task 3: SocialPost Queue Integration

**Files:**
- Modify: `services/social_daily_package.py`
- Test: `tests/test_social_daily_queue.py`

**Interfaces:**
- Consumes: generated campaign package.
- Produces: one idempotent `SocialPost` row per supported queue platform, source prefix `dailycampaign:<id>`.

- [ ] **Step 1: Write failing tests**
  - Facebook, Instagram, X, and Discord queue rows are created once.
  - TikTok/Reels remains in campaign package state and is not sent to unsupported direct publisher.
  - Instagram queue row references a campaign-approved lead image while full carousel assets remain attached to campaign status.
  - Re-run does not duplicate rows.

- [ ] **Step 2: Verify test failure.**

- [ ] **Step 3: Implement idempotent queue synchronization.**

- [ ] **Step 4: Verify test pass.**

- [ ] **Step 5: Commit queue integration.**

### Task 4: Make Social Operator Own the Daily Campaign

**Files:**
- Modify: `services/social_operator.py`
- Modify: `api/social_operator.py`
- Test: `tests/test_social_operator_daily_campaign.py`

**Interfaces:**
- Consumes: `ensure_daily_campaign`, `generate_daily_package`, queue sync, existing engagement scanner/growth-post fallback.
- Produces: operator run/status payload with `daily_campaign` details.

- [ ] **Step 1: Write failing tests**
  - `run_operator_once()` ensures/generates the daily campaign before generic gap fillers.
  - Generic growth posts only fill platforms not covered by the daily campaign.
  - Status payload includes campaign topic, completeness, asset counts, platform-copy counts, ready/scheduled/published state, and errors.
  - Existing engagement scan/reply behavior remains unchanged.

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Wire the campaign coordinator into Social Operator.**

- [ ] **Step 4: Verify tests pass including existing Social Operator regressions.**

- [ ] **Step 5: Commit operator integration.**

### Task 5: Social Operations Control Center UI

**Files:**
- Modify: `api/control_social_operator.js`
- Modify: `api/control_social_operator.css`
- Test: `tests/test_social_operator_ui_contract.py`

**Interfaces:**
- Consumes: `daily_campaign` status payload.
- Produces: visible “Today’s Campaign” panel and package progress summary.

- [ ] **Step 1: Write failing contract tests**
  - JS contains UI bindings for topic, package state, IG slide count, vertical asset count, platform-copy count, and ready/scheduled/published states.
  - Existing engagement review queue remains present.

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement the panel**
  - Show topic/title and source type.
  - Show `Instagram 0/6`, `Vertical 0/N`, `Platform copy 0/5` style progress.
  - Show “Ready to post” for TikTok/Reels and scheduler states for supported channels.
  - Keep engagement/replies below campaign operations.

- [ ] **Step 4: Verify contract tests pass.**

- [ ] **Step 5: Commit UI integration.**

### Task 6: Scheduler/Startup Integration and Verification

**Files:**
- Modify: existing startup/scheduler registration file only if Social Operator is not already started there.
- Modify: `utils/config.py` only for new safe defaults that are actually required.
- Test: existing scheduler/startup tests plus new daily-campaign smoke tests.

**Interfaces:**
- Consumes: Social Operator loop already polling on configured interval.
- Produces: one automatically maintained daily campaign per local day without additional duplicate worker loops.

- [ ] **Step 1: Confirm Social Operator loop is already registered exactly once.**

- [ ] **Step 2: Add no new loop if the existing Social Operator loop can own the coordinator.**

- [ ] **Step 3: Run full relevant test set: daily campaign, package, queue, operator, UI contract, existing Social Operator tests.**

- [ ] **Step 4: Inspect branch diff for accidental PRT or unrelated Cloud changes.**

- [ ] **Step 5: Commit any final integration-only changes.**

## Self-Review

- Spec coverage: daily campaign, verified-topic selection, fallback, FB/IG/X/Discord/TikTok-Reels copy, six IG slides, vertical assets, idempotency, reuse of existing services, Social Operations status, engagement preservation, safe publishing boundaries are all mapped to tasks.
- Placeholder scan: no implementation placeholders are intentionally left in the execution steps.
- Type consistency: `campaign_id`, `dailycampaign:<id>`, `ensure_daily_campaign`, `generate_daily_package`, and `daily_campaign` status naming are used consistently across tasks.
