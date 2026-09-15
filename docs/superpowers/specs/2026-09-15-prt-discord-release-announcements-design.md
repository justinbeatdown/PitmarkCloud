# PRT Discord Release Announcements — Design

Date: 2026-09-15
Status: Approved design, pending implementation plan

## Goal

Automatically publish Pitmark Racing Tools release notes to the Pitmark Discord `#prt-announcements` channel whenever a new production PRT version is released.

The announcement must be driven by the real production PRT release state, not by arbitrary PitmarkCloud deploys or repository commits.

## Current Architecture

- PitmarkCloud already runs the Pitmark Discord gateway as a long-lived service.
- PRT update delivery is exposed through the stable Pitmark `/downloads/latest.json` endpoint.
- In production, that endpoint bridges to the R2-hosted release manifest so legacy and current PRT clients receive the live release state.
- The repository copy of `api/downloads/latest.json` is a fallback and may lag production, so it must not be treated as the authoritative release trigger.

## Recommended Architecture

Add a small release-announcement component inside the existing Discord gateway process.

The component will periodically inspect the same production release manifest used by PRT clients. A release is considered new when the manifest `version` differs from the last successfully announced PRT version.

For each new version, the bot will load version-matched release notes, validate that the notes belong to the exact manifest version, render a branded Discord embed, post it to `#prt-announcements`, and persist the announced version only after Discord confirms success.

This keeps the feature inside the existing Pitmark bot/runtime and avoids introducing a webhook service, Zapier-style bridge, or GitHub-only trigger.

## Data Flow

1. Discord gateway starts normally.
2. A release watcher runs on a modest polling interval while the gateway is online.
3. The watcher fetches the live production PRT manifest from the stable Pitmark release endpoint or the same production R2 source used by that endpoint.
4. The watcher extracts and normalizes the manifest version.
5. If the version has already been announced, no action is taken.
6. If the version is new, the watcher loads release notes for that exact version.
7. The watcher rejects the announcement if release-note version metadata does not match the manifest version.
8. The watcher resolves the Pitmark HQ guild and the `prt-announcements` text/announcement channel.
9. The bot posts one branded announcement embed.
10. Only after a successful Discord API response does the watcher persist the version as announced.
11. Failures are logged and retried on a later watcher cycle without duplicating successful posts.

## Release Notes Source

Release notes should be stored in a machine-readable companion payload associated with the production PRT release.

Preferred shape:

```json
{
  "version": "0.16.82",
  "title": "PRT v0.16.82",
  "summary": "Short release summary.",
  "changes": [
    "Fixed radar stability near overlapping cars.",
    "Improved track map sizing and driver-number readability."
  ],
  "required": true
}
```

The release notes version must match the live manifest version exactly before posting.

If the production release pipeline already publishes a suitable notes field alongside the manifest, implementation may reuse that instead of creating a second object, as long as the version binding remains explicit and testable.

## Discord Announcement Format

Target channel: `#prt-announcements`

Default embed structure:

- Title: `🏁 PRT v<version> IS LIVE`
- Short release summary
- `What changed` section containing the release-note items
- Update/download line pointing users to the normal PRT update/download flow
- Pitmark orange embed accent (`#FF5500`)
- Footer: `Pitmark Racing Co. • Leave Your Mark.`

No `@everyone` or role ping is sent by default.

Mentions must remain disabled unless a future explicit product decision enables a release role.

## Idempotency

The bot must never post the same release twice during normal operation.

Persist the last successfully announced version using PitmarkCloud's existing durable storage conventions. In-memory state alone is not sufficient because Render restarts or deploys would otherwise repost the current release.

The persisted version is written only after Discord accepts the announcement.

If a post fails, the version remains unannounced so the watcher can safely retry.

## Channel Resolution

Use the configured Pitmark HQ guild (`discord_hq_guild_id`, falling back to the existing guild setting where appropriate).

Resolve the channel by the canonical name `prt-announcements` unless an existing stable configured channel ID is already available in current Pitmark Discord configuration.

If the channel is missing, inaccessible, or not a supported text/announcement channel:

- do not mark the version as announced;
- log the failure clearly;
- retry on a later watcher cycle.

The release system must not create channels automatically.

## Error Handling

The watcher must be non-fatal to the Discord gateway.

Failures fetching the manifest, loading notes, resolving Discord state, or posting the message must be caught and logged without taking the bot offline.

Expected behavior:

- Manifest unavailable: log and retry later.
- Invalid manifest: log and retry later.
- Notes missing: log and retry later.
- Version mismatch: refuse to post and log mismatch.
- Discord channel missing: log and retry later.
- Discord permission/API failure: log and retry later.
- Gateway restart: load persisted announcement state and avoid duplicates.

## Polling Behavior

Use a conservative recurring interval suitable for release detection rather than real-time chat behavior. The exact interval can be chosen during implementation, but it should be frequent enough that a release appears in Discord shortly after publication without creating unnecessary traffic.

The watcher should perform an initial check after the gateway becomes ready.

To prevent an old production build from being announced merely because the feature was deployed for the first time, initialization must support a safe bootstrap rule. Preferred behavior: if no announcement state exists yet, record the currently live version as the baseline without posting it. Only subsequent version changes generate automatic announcements.

A one-time manual backfill should remain possible through code/config if Pitmark intentionally wants the current release announced after rollout.

## Files / Components Expected To Change

Likely implementation surface:

- `services/discord_gateway_service.py`
  - start/stop the release watcher with the existing gateway lifecycle, or call a focused release-announcement service.

- New focused service such as `services/prt_release_announcements.py`
  - manifest fetch/parse
  - release-note validation
  - Discord payload rendering
  - idempotency/state handling
  - one-cycle watcher logic

- Existing persistent storage layer (`services/persistent_store.py` or equivalent established store)
  - small durable key/value or release-announcement state entry.

- `utils/config.py` and `.env.example` only if implementation needs a configurable production manifest/notes URL or watcher interval.

- New regression tests under `scripts/` following the repository's existing contract-test pattern.

Do not mix this feature into unrelated Social Operator, PRT UI, or updater compatibility code.

## Tests

Minimum regression coverage:

1. New release version posts exactly one announcement.
2. Previously announced version posts nothing.
3. Restart with persisted announced version posts nothing.
4. First-run bootstrap records current version without back-posting an old release.
5. Release-note version mismatch refuses to post.
6. Missing release notes refuses to post.
7. Missing `#prt-announcements` channel does not mark the release announced.
8. Discord API/send failure does not mark the release announced.
9. Successful post persists the announced version.
10. Embed contains the version, release changes, Pitmark branding, and no broad mention ping.

## Security / Operational Constraints

- Reuse the existing Discord bot token; do not introduce a webhook token unless the architecture changes later.
- Do not expose bot credentials or R2 credentials in release-note payloads.
- Do not allow release-note text to inject broad Discord mentions; use disabled allowed-mentions behavior.
- Keep release fetching bounded by timeout and reasonable payload-size limits.
- A failure in this feature must never prevent the bot from connecting, handling support automation, or maintaining presence.

## Non-Goals

This change does not:

- announce every PitmarkCloud deploy;
- announce unrelated Pitmark site, Social Operator, Paint Studio, or Cloud changes;
- automatically generate release notes from arbitrary Git commits;
- create or reorganize Discord channels;
- publish announcements to external Discord servers where the public Pitmark bot may be installed;
- ping `@everyone` by default.

## Success Criteria

After rollout, publishing a new production PRT build and its matching notes causes exactly one branded patch-note announcement to appear in the Pitmark HQ `#prt-announcements` channel. Restarts, Cloud deploys, repeated polling, and unrelated repository changes do not create duplicate or false PRT release announcements.
