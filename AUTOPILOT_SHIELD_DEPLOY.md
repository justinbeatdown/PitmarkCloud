# Pitmark Cloud v0.9.0 — Autopilot + Shield

This build merges the existing Pitmark Autopilot Dev1 concepts into Pitmark Cloud instead of running them as a separate product.

## What is live in the code
- `/control` Pitmark Control Center UI.
- Persistent social approval queue and manual composer.
- Shield ingest/classification/history/review queue.
- Outreach pipeline with stages, supporter status and follow-up date.
- Shopify blog / Track Spotlight draft store with approval state.
- Uses the existing Pitmark Cloud `DATABASE_URL` and `PITMARK_ADMIN_KEY`.

## Intentionally connector-gated
- Gmail read/label/archive/reply adapter.
- OpenAI/other AI provider adapter for richer manual generation.
- Shopify Admin API article create/publish adapter.
- Meta, TikTok and X live publish adapters.

Those actions require production OAuth/API credentials and should be connected after this v0.9.0 foundation deploy. Nothing in this package deletes Gmail messages or publishes social/blog content automatically.

## Deploy
1. Back up current Render environment variable names/values.
2. Deploy this package over the current Pitmark Cloud service.
3. Keep existing DATABASE_URL, PITMARK_ADMIN_KEY, Discord and signing secrets unchanged.
4. Set APP_VERSION=0.9.0.
5. Visit `/health`, `/api/security/status`, then `/control`.
6. Enter the existing Pitmark admin key in Control Center and click Connect.
