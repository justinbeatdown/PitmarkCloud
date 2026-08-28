# Pitmark Cloud v0.8.0 — Security Foundation

This release is the server-side half of Pitmark Racing Tools v0.16.0.

Implemented:

- per-device 256-bit credential registration and hashed server-side storage
- device credential required for Discord link status/start/disconnect, live telemetry, result publishing, destination discovery, and direct Race Card sharing
- signed Discord OAuth state with expiration
- encrypted Discord OAuth access/refresh tokens at rest
- Discord interaction Ed25519 signature verification plus 5-minute timestamp freshness window
- strict device/Discord identifier validation
- request body ceiling
- endpoint/IP rate limiting as defense in depth
- security headers, no-store responses, clickjacking/MIME/referrer protections
- CORS disabled by default; exact origins only when configured
- OpenAPI/Swagger disabled when `ENVIRONMENT=production`
- admin command registration protected by constant-time admin-key comparison and rate limiting
- OAuth callback HTML escaping
- log redaction for common credential fields/query values
- PostgreSQL-backed durable device credentials

Before public production launch, keep `ENVIRONMENT=production`, use long random `PITMARK_SIGNING_SECRET` and `PITMARK_ADMIN_KEY`, keep `CORS_ORIGINS` empty unless a real browser origin needs access, and keep all Discord/Shopify/database secrets server-side only.

The current Shopify webhook remains intentionally non-functional (HTTP 501) until HMAC verification is implemented in the Shopify phase. This is safer than processing unverified webhook data.
