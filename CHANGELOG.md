# Changelog

## 0.21.15

- Added the public Pitmark-branded links hub to the Cloud release.
- Added `links.pitmarkracing.com` host routing so the custom subdomain can land directly on the links hub once DNS/custom-domain setup is completed.
- Preserved Shop, PRT, PRT Early Access, and Contact as stable Pitmark-owned destinations on the links page.
- Preserved Autopilot intelligence, multiplatform scheduling, research, and social publishing workers.
- Preserved Pitmark Shield/Gmail protection, Discord integrations, Control Center access controls, and existing security middleware.
- Kept this release Cloud-only: no PRT Windows installer, updater manifest, or desktop app version changes.

## 0.20.2

- Restored the missing desktop Control Center sidebar with an authoritative,
  post-initialization navigation recovery layer.
- Preserved role-based navigation permissions and all v0.20.1 Gmail/Shield
  automation behavior.
- Cache-busted the full Control Center asset chain.

## 0.20.1
- Added idempotent Google Workspace provisioning for eight department labels, four Shield verdict labels, and eight alias-routing Gmail filters.
- Expanded the default business-only Gmail sync to include provider Spam for Shield auditing while excluding personal-only mail, sent mail, drafts, and trash.
- Mirrored Shield Review, Protected, Unverified, and Spam verdicts into Gmail labels and synchronized user spam actions back to Gmail.
- Added 24/7 Shield-gated per-alias acknowledgments with no-reply, automated-mail, mailing-list, own-domain, activation-time, 24-hour, retry-limit, and one-per-Gmail-conversation safeguards.
- Added Auto Reply template controls, Gmail setup status, and a Spam folder to desktop and mobile Control Center mail.
- Added the `outreach@pitmarkracing.com` send identity to complete parity with the configured Workspace aliases.
- Restored the desktop Control Center sidebar with one final layout owner and fresh asset cache keys; mobile navigation remains unchanged.
- Added exact Google Cloud OAuth, Render environment, provisioning, and smoke-test steps.

## 0.20.0
- Replaced the legacy Resend/subdomain mail transport with Google Workspace Gmail API OAuth.
- Added background Gmail inbox synchronization and Shield protection for newly synchronized messages.
- Restricted default sync to approved `@pitmarkracing.com` delivery identities so personal Gmail traffic is excluded.
- Loaded approved Gmail send-as identities for Pitmark department routing.
- Reflected read, spam and trash actions back to Gmail so Cloud and Gmail remain in sync.
- Added authenticated Gmail attachment downloads in desktop and mobile Control Center.
- Replaced `@mail.pitmarkracing.com` support references with root-domain Google Workspace addresses.
- Removed the obsolete public Resend webhook route and provider-specific UI copy.
- Preserved the v0.19.10 Race Card upload dependency fix and all Discord/Autopilot/PRT behavior.

## 0.14.7
- Root-cause fix for Social Timeline 500 (`OpportunitySourceMeta` import).
- Dynamic source freshness calculation for Timeline and Intelligence UI.
- Preserves 4-hour reactive social cutoff.


## 0.14.6
- Rebuilt social queue as a source-time chronological real-time timeline.
- Added backend social freshness enforcement and hourly intelligence scans.
- Added native Instagram composer asset selection and image upload workflow.
- Added durable public uploaded-image serving backed by Pitmark Cloud database.
- Kept blog content on a separate long-form lane.
# v0.14.5 — Instagram Autopilot + Asset Pool + Mobile Publish

- Adds Instagram Graph API publishing using the linked Pitmark professional account.
- Adds Shopify-backed social image asset pool with automatic selection and reuse tracking.
- Adds real Facebook/Instagram Connected Accounts status.
- Adds expanded mobile Autopilot generate/edit/approve/schedule/publish workflow.
- Broadens Control Center autofill protection.
- Makes displayed release version derive from the code-owned release version.

# Pitmark Cloud Changelog

## v0.14.4 — Direct Facebook Publish Integration
- Moved Facebook publishing readiness and click handling directly into `control_center.js`.
- Queue rendering now enables Publish only for APPROVED/SCHEDULED Facebook posts when Meta Page credentials are configured.
- Publish action now calls the server-side social publishing endpoint directly from the standard queue action flow.
- Removed the v0.14.3 injected social-publish UI workaround to eliminate duplicate/fragile handlers.
- Fixed the Control Center footer version, which was still hardcoded to v0.14.0.
- Runtime/default version advanced consistently to `0.14.4`.

## v0.14.3 — Facebook Publish UI Fix
- Fixed Control Center Facebook Publish buttons remaining disabled after Meta credentials were configured.
- Added live `/api/control/social/status` readiness detection to the authenticated Control Center.
- Approved and scheduled Facebook posts now enable Publish only when Meta Page publishing is configured.
- Publish clicks call the existing server-side Facebook publishing endpoint directly from the standard queue action flow.
- Preserved the v0.14.2 Meta publisher, scheduled worker, Shopify routing fix, and autofill protection.

## v0.14.2 — Facebook Autopilot Publishing
- Added server-side Facebook Page publishing through the Meta Graph API.
- Added `/api/control/social/status` and approval-gated live publish endpoint.
- Added background worker that checks scheduled Facebook posts every minute.
- Control Center Publish activates only when Facebook publishing is configured.
- Added `META_PAGE_ID`, `META_PAGE_ACCESS_TOKEN`, configurable Graph API version, and Pitmark timezone settings.
- Preserved the verified Shopify Racing Culture hard-priority routing fix.
- Preserved the Control Center autofill guard that prevents username/password-manager bleed into content fields.
- Runtime/package version advanced consistently to `0.14.2`.

## v0.14.1 — Shopify Live Publishing Foundation