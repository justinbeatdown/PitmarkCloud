# Pitmark Cloud v0.21.7 — Optimization & Cleanup

This release freezes the approved Control Center UI and optimizes the Cloud runtime underneath it.

## Runtime optimization
- Bounds asyncio background worker threads to a small configurable pool (default 4).
- Adds periodic Python GC + Linux `malloc_trim()` maintenance to return unused heap pages to Render.
- Logs current RSS at memory-maintenance checkpoints for easier Render diagnosis.
- Changes the always-on Gmail/Shield worker from inbox-client behavior to a lean Shield/backend-automation worker.
- Enforces a minimum 120-second Gmail polling cadence and a maximum 25-message polling batch.
- Skips historical auto-reply scans when no new Gmail messages were ingested.
- Keeps auto-reply work proportional to the actual new-message batch.
- Reduces the PostgreSQL connection pool to a small-instance-friendly 3 pooled + 2 overflow connections, with recycling and LIFO reuse.

## Repository cleanup
The included `CLEAN_OLD_CLOUD_FILES.cmd` removes obsolete root deployment notes, historical release artifacts, the old v0.14.5 patch copy, and all tracked `__pycache__`/`.pyc` files.

`.gitignore` now keeps Python caches, local data, patch folders, ZIPs, and the local cleanup helper out of future commits.

## Preserved
- Current Control Center design and navigation.
- Pitmark Shield communications protection.
- Google Workspace/Gmail backend connection.
- Mail-based backend automation and safe auto-replies.
- Autopilot, research, social publishing, Discord, PRT analytics/licensing, Shopify integration, and PRT site functionality.

No paid infrastructure upgrade is required by this release.
