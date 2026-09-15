# PRT Discord Release Announcements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically post exactly one branded PRT patch-note announcement to the Pitmark HQ `#prt-announcements` channel whenever the production PRT release version changes.

**Architecture:** Add a focused release-announcement service that polls the production PRT manifest, normalizes version-bound notes, persists the last announced version in PitmarkCloud's SQL-backed store, and sends through the existing always-on Discord gateway client. The first observed production version becomes a silent baseline so deploying the feature does not back-post an old release; only later version changes post to Discord.

**Tech Stack:** Python 3, asyncio, discord.py, httpx, SQLAlchemy, unittest, existing PitmarkCloud settings/database/gateway infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-15-prt-discord-release-announcements-design.md`

## Global Constraints

- The production PRT release state is authoritative; arbitrary PitmarkCloud deploys/commits must never trigger announcements.
- Target only the configured Pitmark HQ guild and canonical `prt-announcements` channel.
- Never create Discord channels automatically.
- Never send `@everyone`, role, or user mentions from release-note text; use disabled allowed mentions.
- Persist the announced version only after Discord confirms a successful send.
- If no state exists on first run, store the currently live version as the baseline without posting it.
- Manifest/notes/channel/API failures are non-fatal to the Discord gateway and retry on a later poll.
- Reuse the existing Discord bot token; introduce no webhook secret.
- Keep release fetching bounded by timeout and payload size.

---

## File Structure

- Create `services/prt_release_announcements.py` — release manifest fetch/parse, note normalization, embed construction, one-cycle decision logic, and polling loop.
- Modify `services/persistent_store.py` — generic durable runtime key/value state used for the last announced PRT version.
- Modify `services/discord_gateway_service.py` — start the release watcher after the bot is ready and stop it with the gateway lifecycle.
- Modify `utils/config.py` — watcher enable flag, production manifest URL, channel name, and polling interval defaults.
- Modify `.env.example` — document the new optional settings.
- Create `scripts/test_prt_release_announcements.py` — regression tests for bootstrap, idempotency, version mismatch/missing notes, send failure, channel failure, and embed safety.

---

### Task 1: Add Durable Runtime State

**Files:**
- Modify: `services/persistent_store.py`
- Test: `scripts/test_prt_release_announcements.py`

**Interfaces:**
- Produces: `get_runtime_state(key: str) -> str | None`
- Produces: `set_runtime_state(key: str, value: str) -> None`
- State key consumed later: `prt_release_last_announced_version`

- [ ] **Step 1: Write the failing durable-state test**

Add a unittest that imports `services.persistent_store`, writes a unique key/value through `set_runtime_state`, and asserts `get_runtime_state` returns the exact value. The test must use a unique key such as `test_prt_release_state_<pid>` so it does not collide with production-style state.

```python
class RuntimeStateTests(unittest.TestCase):
    def test_runtime_state_round_trip(self):
        key = f"test_prt_release_state_{os.getpid()}"
        persistent_store.set_runtime_state(key, "0.16.999")
        self.assertEqual(persistent_store.get_runtime_state(key), "0.16.999")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.RuntimeStateTests -v
```

Expected: FAIL because `set_runtime_state` / `get_runtime_state` do not exist.

- [ ] **Step 3: Add a focused SQLAlchemy runtime-state row and helpers**

In `services/persistent_store.py`, add:

```python
class RuntimeStateRow(Base):
    __tablename__ = "runtime_state"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


def get_runtime_state(key: str) -> str | None:
    with SessionLocal() as db:
        row = db.get(RuntimeStateRow, key)
        return row.value if row else None


def set_runtime_state(key: str, value: str) -> None:
    with SessionLocal() as db:
        row = db.get(RuntimeStateRow, key)
        if row is None:
            row = RuntimeStateRow(key=key)
            db.add(row)
        row.value = value
        row.updated_at = _now_iso()
        db.commit()
```

No extra migration wiring is needed because `services.database.init_database()` imports `persistent_store` before `Base.metadata.create_all()`.

- [ ] **Step 4: Run the durable-state test**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.RuntimeStateTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/persistent_store.py scripts/test_prt_release_announcements.py
git commit -m "feat: add durable runtime state"
```

---

### Task 2: Build Release Parsing, Validation, and Discord Payload

**Files:**
- Create: `services/prt_release_announcements.py`
- Test: `scripts/test_prt_release_announcements.py`

**Interfaces:**
- Produces: `normalize_release(manifest: dict[str, Any]) -> dict[str, Any]`
- Produces: `build_release_embed(release: dict[str, Any]) -> discord.Embed`
- Produces constant: `STATE_KEY = "prt_release_last_announced_version"`

- [ ] **Step 1: Write failing parser/payload tests**

Add tests covering these exact behaviors:

```python
def test_normalize_release_accepts_changes_list(self):
    release = normalize_release({
        "version": "0.16.82",
        "summary": "Radar and overlay fixes.",
        "changes": ["Fixed radar flashing.", "Improved track-map sizing."],
        "required": True,
    })
    self.assertEqual(release["version"], "0.16.82")
    self.assertEqual(len(release["changes"]), 2)


def test_normalize_release_accepts_notes_string(self):
    release = normalize_release({
        "version": "0.16.82",
        "notes": "Fixed radar flashing.\nImproved track-map sizing.",
    })
    self.assertEqual(release["changes"], [
        "Fixed radar flashing.",
        "Improved track-map sizing.",
    ])


def test_normalize_release_rejects_missing_notes(self):
    with self.assertRaises(ValueError):
        normalize_release({"version": "0.16.82"})


def test_embed_contains_branding_and_no_mentions(self):
    release = normalize_release({
        "version": "0.16.82",
        "notes": "Fixed @everyone radar spam.",
    })
    embed = build_release_embed(release)
    payload = embed.to_dict()
    self.assertIn("PRT v0.16.82 IS LIVE", payload["title"])
    self.assertIn("Pitmark Racing Co. • Leave Your Mark.", payload["footer"]["text"])
```

Mention safety is enforced at send time with `discord.AllowedMentions.none()`; release content itself is not rewritten.

- [ ] **Step 2: Run parser/payload tests and verify failure**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.ReleaseParsingTests -v
```

Expected: FAIL because the service/functions do not exist.

- [ ] **Step 3: Implement release normalization**

Create `services/prt_release_announcements.py` with:

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

import discord
import httpx

from services import persistent_store
from utils.config import settings

log = logging.getLogger("pitmark.discord.prt_release")
STATE_KEY = "prt_release_last_announced_version"
MAX_MANIFEST_BYTES = 64 * 1024


def _clean_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        lines = []
        for raw in value.replace("\r", "").split("\n"):
            line = raw.strip().lstrip("-•* ").strip()
            if line:
                lines.append(line)
        return lines
    return []


def normalize_release(manifest: dict[str, Any]) -> dict[str, Any]:
    version = str(manifest.get("version") or "").strip().lstrip("v")
    if not version:
        raise ValueError("PRT release manifest is missing version")

    changes = _clean_lines(manifest.get("changes")) or _clean_lines(manifest.get("notes"))
    if not changes:
        raise ValueError(f"PRT release {version} has no release notes")

    return {
        "version": version,
        "title": str(manifest.get("title") or f"PRT v{version}").strip(),
        "summary": str(manifest.get("summary") or "A new Pitmark Racing Tools build is available.").strip(),
        "changes": changes[:20],
        "required": bool(manifest.get("required", False)),
    }
```

The manifest itself is the version-bound release-note payload. It supports a structured `changes` list first and the updater-compatible `notes` field as a fallback, so the release pipeline does not need a second mandatory object.

- [ ] **Step 4: Implement the branded embed**

Add:

```python
def build_release_embed(release: dict[str, Any]) -> discord.Embed:
    version = release["version"]
    changes = release["changes"]
    body = "\n".join(f"• {item}" for item in changes)
    if len(body) > 3500:
        body = body[:3497].rstrip() + "..."

    embed = discord.Embed(
        title=f"🏁 PRT v{version} IS LIVE",
        description=release["summary"],
        color=0xFF5500,
    )
    embed.add_field(name="What changed", value=body, inline=False)
    embed.add_field(
        name="Update",
        value="Open PRT to update automatically, or download the latest Windows build from https://prt.pitmarkracing.com/",
        inline=False,
    )
    if release.get("required"):
        embed.add_field(name="Update status", value="This release is marked as a required update.", inline=False)
    embed.set_footer(text="Pitmark Racing Co. • Leave Your Mark.")
    return embed
```

- [ ] **Step 5: Run parser/payload tests**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.ReleaseParsingTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/prt_release_announcements.py scripts/test_prt_release_announcements.py
git commit -m "feat: parse PRT release announcements"
```

---

### Task 3: Implement One-Cycle Announcement Logic and Idempotency

**Files:**
- Modify: `services/prt_release_announcements.py`
- Test: `scripts/test_prt_release_announcements.py`

**Interfaces:**
- Produces: `async fetch_manifest(client: httpx.AsyncClient | None = None) -> dict[str, Any]`
- Produces: `async run_once(bot: discord.Client, *, fetcher=None, get_state=None, set_state=None) -> str`
- Return statuses used in tests/logging: `bootstrapped`, `unchanged`, `posted`, `no-channel`, `failed`

- [ ] **Step 1: Write failing one-cycle tests with fakes**

Create lightweight fake guild/channel/bot objects so tests do not call Discord. Cover:

```python
async def test_first_run_bootstraps_without_posting(self): ...
async def test_same_version_does_not_post(self): ...
async def test_new_version_posts_and_persists(self): ...
async def test_missing_channel_does_not_persist(self): ...
async def test_send_failure_does_not_persist(self): ...
```

The fake channel's `send()` must record the supplied embed and `allowed_mentions` and optionally raise an exception.

- [ ] **Step 2: Run one-cycle tests and verify failure**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.ReleaseDecisionTests -v
```

Expected: FAIL because `run_once` is not implemented.

- [ ] **Step 3: Implement bounded manifest fetching**

Add:

```python
async def fetch_manifest(client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        async with client.stream("GET", settings.prt_release_manifest_url, headers={"Cache-Control": "no-cache"}) as response:
            response.raise_for_status()
            raw = await response.aread()
            if len(raw) > MAX_MANIFEST_BYTES:
                raise ValueError("PRT release manifest exceeded 64 KiB")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("PRT release manifest must be a JSON object")
            return payload
    finally:
        if owns_client:
            await client.aclose()
```

If `httpx.Response.json()` cannot be used after `aread()` in the installed version, decode with `json.loads(raw.decode("utf-8-sig"))` instead; keep the same size bound and dictionary validation.

- [ ] **Step 4: Implement channel resolution and one-cycle behavior**

Add helpers:

```python
def _hq_guild(bot: discord.Client):
    target = (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()
    return next((guild for guild in bot.guilds if str(guild.id) == target), None)


def _announcement_channel(guild):
    wanted = (settings.prt_release_announcement_channel or "prt-announcements").strip().lower()
    return next(
        (
            channel for channel in guild.channels
            if str(getattr(channel, "name", "")).lower() == wanted
            and isinstance(channel, (discord.TextChannel, discord.ForumChannel, discord.VoiceChannel)) is False
            and hasattr(channel, "send")
        ),
        None,
    )
```

Prefer a safer implementation using `isinstance(channel, (discord.TextChannel, discord.StageChannel))` only where Discord type semantics are clear; tests should depend on `name` + `send`, while production should reject unsupported channel types. The final production implementation must accept normal text and announcement/news channels and reject forums/voice/stage categories.

Add `run_once(...)` with this exact decision order:

1. fetch + normalize current production release;
2. read `STATE_KEY`;
3. if no state: store current version and return `bootstrapped` without sending;
4. if stored version equals current version: return `unchanged`;
5. resolve HQ guild and announcement channel; if missing, return `no-channel` without state change;
6. `await channel.send(embed=build_release_embed(release), allowed_mentions=discord.AllowedMentions.none())`;
7. only after the send returns successfully, persist current version and return `posted`.

Dependency-injection defaults:

```python
async def run_once(
    bot: discord.Client,
    *,
    fetcher: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    get_state: Callable[[str], str | None] | None = None,
    set_state: Callable[[str, str], None] | None = None,
) -> str:
```

Use `fetcher or fetch_manifest`, `get_state or persistent_store.get_runtime_state`, and `set_state or persistent_store.set_runtime_state` so the decision logic can be tested without a live database/network.

- [ ] **Step 5: Run decision tests**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.ReleaseDecisionTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/prt_release_announcements.py scripts/test_prt_release_announcements.py
git commit -m "feat: post idempotent PRT release announcements"
```

---

### Task 4: Wire the Watcher Into the Discord Gateway Lifecycle

**Files:**
- Modify: `services/prt_release_announcements.py`
- Modify: `services/discord_gateway_service.py`
- Modify: `utils/config.py`
- Modify: `.env.example`
- Test: `scripts/test_prt_release_announcements.py`

**Interfaces:**
- Produces: `async watch(bot: discord.Client) -> None`
- Produces settings:
  - `prt_release_announcements_enabled: bool = True`
  - `prt_release_manifest_url: str = "https://prt.pitmarkracing.com/downloads/latest.json"`
  - `prt_release_announcement_channel: str = "prt-announcements"`
  - `prt_release_poll_seconds: int = 120`

- [ ] **Step 1: Write failing watcher lifecycle tests**

Add tests that patch `run_once` and `asyncio.sleep` or exercise one loop iteration with cancellation. Verify:

- watcher does nothing when `prt_release_announcements_enabled` is false;
- watcher catches a `run_once` exception instead of propagating and killing the gateway task;
- poll interval is clamped to at least 30 seconds.

- [ ] **Step 2: Run lifecycle tests and verify failure**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements.ReleaseWatcherTests -v
```

Expected: FAIL because watcher/settings do not exist.

- [ ] **Step 3: Add settings and env documentation**

In `utils/config.py` add near the existing Discord/PRT settings:

```python
prt_release_announcements_enabled: bool = True
prt_release_manifest_url: str = "https://prt.pitmarkracing.com/downloads/latest.json"
prt_release_announcement_channel: str = "prt-announcements"
prt_release_poll_seconds: int = 120
```

In `.env.example`, document:

```dotenv
PRT_RELEASE_ANNOUNCEMENTS_ENABLED=true
PRT_RELEASE_MANIFEST_URL=https://prt.pitmarkracing.com/downloads/latest.json
PRT_RELEASE_ANNOUNCEMENT_CHANNEL=prt-announcements
PRT_RELEASE_POLL_SECONDS=120
```

- [ ] **Step 4: Implement the non-fatal polling loop**

Add to `services/prt_release_announcements.py`:

```python
async def watch(bot: discord.Client) -> None:
    if not settings.prt_release_announcements_enabled:
        log.info("PRT release announcements disabled.")
        return

    interval = max(30, int(settings.prt_release_poll_seconds))
    while True:
        try:
            status = await run_once(bot)
            if status in {"posted", "bootstrapped"}:
                log.info("PRT release announcement watcher: %s", status)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("PRT release announcement watcher cycle failed")
        await asyncio.sleep(interval)
```

- [ ] **Step 5: Start the watcher from `PitmarkPresenceClient.on_ready` exactly once**

In `services/discord_gateway_service.py`:

- import `prt_release_announcements`;
- add `_release_watcher_task: asyncio.Task | None = None` beside the existing gateway task globals;
- in `on_ready`, if the watcher task is absent/done, create it with:

```python
_release_watcher_task = asyncio.create_task(
    prt_release_announcements.watch(self),
    name="pitmark-prt-release-announcements",
)
```

Because `on_ready` may fire more than once after reconnects, guard against duplicate watcher tasks.

In `stop()`, cancel and await `_release_watcher_task` before clearing globals so no poll survives a gateway shutdown.

- [ ] **Step 6: Run lifecycle and full release-announcement tests**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements -v
```

Expected: PASS.

- [ ] **Step 7: Run nearby Discord/PRT regression tests**

Run:

```bash
python -m unittest scripts.test_prt_release_announcements scripts.test_prt_support -v
python scripts/smoke_test.py
```

If `scripts.test_prt_support` is JavaScript-only in the checked-out revision, run the repository's existing Node command instead:

```bash
node scripts/test_prt_support.mjs
```

Expected: all applicable tests PASS.

- [ ] **Step 8: Commit**

```bash
git add services/prt_release_announcements.py services/discord_gateway_service.py utils/config.py .env.example scripts/test_prt_release_announcements.py
git commit -m "feat: watch PRT releases from Discord gateway"
```

---

### Task 5: Final Verification and Review

**Files:**
- Verify all files changed by Tasks 1-4.

**Interfaces:**
- No new interfaces; this task proves the feature satisfies the approved spec.

- [ ] **Step 1: Run the complete targeted suite**

```bash
python -m unittest scripts.test_prt_release_announcements -v
node scripts/test_prt_downloads.mjs
node scripts/test_prt_support.mjs
python scripts/smoke_test.py
```

Expected: all commands PASS. If an existing unrelated smoke test fails, capture the exact pre-existing failure and do not mask it.

- [ ] **Step 2: Inspect the final diff against the spec**

Verify explicitly:

- the trigger is the configured production manifest URL;
- first run silently bootstraps;
- duplicate/restart polling cannot repost a version;
- state is stored only after a successful send;
- only HQ `#prt-announcements` is targeted;
- no broad Discord mentions are allowed;
- Discord/channel/network failures do not stop the gateway;
- unrelated PitmarkCloud changes cannot trigger a PRT announcement.

- [ ] **Step 3: Perform a dry-run decision test for a synthetic next release**

Use the unit-test fakes with current state `0.16.82` and fetched version `0.16.83`; assert one send occurs and state becomes `0.16.83`. Do not post a synthetic message to the live Discord server.

- [ ] **Step 4: Commit any final test-only adjustments**

```bash
git add scripts/test_prt_release_announcements.py
git commit -m "test: verify PRT release announcement flow"
```

- [ ] **Step 5: Review branch before merge/deploy**

Compare `feat/prt-discord-release-announcements` against `main`. The branch is ready only if the targeted suite is green and the diff is limited to the approved release-announcement feature, its tests, config, and documentation.
