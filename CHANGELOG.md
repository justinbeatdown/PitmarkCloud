# v0.8.0 — Security Foundation

- Added per-device credential registration + authentication.
- Device secrets are hashed server-side; the raw secret is not persisted.
- Added strict device ID validation and rate limiting.
- Added security headers and request-size defenses.
- Disabled CORS by default and production API docs when `ENVIRONMENT=production`.
- Added OAuth callback escaping and Discord signature timestamp freshness validation.
- Added credential/query log redaction.
- Added `/api/security/status` readiness endpoint.
- Shopify webhook remains intentionally 501 until HMAC verification is implemented.
