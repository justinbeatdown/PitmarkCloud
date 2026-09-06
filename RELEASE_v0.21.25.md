# Pitmark Cloud v0.21.25 — First-Party Autopilot

This Cloud-only release makes Autopilot watch Pitmark's own ecosystem instead of relying only on outside racing news.

## Automatic first-party triggers

- **New Shopify products:** scans recently published products and creates platform-native launch drafts using the real product image and product URL.
- **PRT releases:** watches the authoritative Cloudflare R2 update manifest (with local manifest fallback), detects version changes, and creates update content. PRT releases also receive a copy-only Discord draft.
- **Published Pitmark blogs:** detects newly published Shopify/Pitmark blog drafts and creates promotion copy, resolving the public article URL/image when possible.
- **Partnership / Street Team changes:** detects recent confirmed outreach-status changes and creates approval drafts without exposing contact email details.
- **Milestones:** watches PRT install milestones and Street Team member milestones while baselining existing counts to avoid historical spam.

## Safety / behavior

- First-party events are persisted and **deduped**, so repeated scans do not create duplicate campaigns.
- Generated content lands in the existing **Control Center pending/approval queue**.
- This patch does **not** auto-publish first-party content.
- If the AI provider is temporarily unavailable, event-specific fallback copy is generated so the content pipeline does not silently fail.
- Recent-product/blog/outreach backfill defaults to 72 hours, allowing newly added items that predate this deploy to be picked up automatically.
- The existing external racing-news Intelligence system remains intact.

## Version

Pitmark Cloud: **0.21.25**
PRT desktop: **unchanged**
