# Pitmark Cloud v0.8.0 Security Deploy Checklist

1. Keep the existing `DATABASE_URL`, Discord credentials, `PITMARK_SIGNING_SECRET`, and `PITMARK_ADMIN_KEY` unchanged.
2. Add/update `ENVIRONMENT=production`.
3. Set `APP_VERSION=0.8.0` (optional if the code default is used, but recommended).
4. Set `CORS_ORIGINS=` to an empty value. The Windows desktop client does not use browser CORS.
5. Deploy v0.8.0.
6. Check `/health` and `/api/security/status`.
7. `/api/security/status` should report `ready: true`, `production_mode: true`, `wildcard_cors: false`, and hardened signing/admin keys.
8. Then launch Pitmark Racing Tools v0.16.0. On first cloud contact it creates a DPAPI-protected local device credential and registers its hash with Pitmark Cloud.
9. Verify Discord still shows connected. If needed, reconnect Discord once; the existing Discord link is still stored against the same device ID.
10. Re-test Race Card share and live session commands.

## Compatibility warning

After v0.8.0 is deployed, v0.15.x and older desktop builds cannot call the newly device-authenticated Discord/session/result endpoints. This is intentional security hardening. Use desktop v0.16.0 with Cloud v0.8.0.
