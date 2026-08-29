# Pitmark Cloud v0.12.0 — Mobile + Workflow Polish

No new required environment variables. Existing DATABASE_URL, PITMARK_SIGNING_SECRET, PITMARK_ADMIN_KEY, OPENAI_API_KEY, Discord, and Shopify values carry forward.

Optional social OAuth app credentials can be added later: META_APP_ID, META_APP_SECRET, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, X_CLIENT_ID, X_CLIENT_SECRET. These only change Connected Accounts readiness; they do not authorize a social account by themselves.

After deploy:
1. Sign into `/control` and verify the new circular badge.
2. Open Shield and run the Shield Test Harness; expect one Legit, one Review, one Spam, and one System event.
3. Open Outreach and correct existing contacts (for example Discord method + Partner stage).
4. Open Blog and try Generate Draft, then Save/Approve.
5. Open `/control/mobile` on a phone. Use the browser Add to Home Screen / Install option when offered.
6. Verify Autopilot Intelligence reports a descriptive scan result.

Safety: PWA caches only static assets, not authenticated API responses or Control Center HTML. Social publishing remains disabled until provider OAuth is completed.
