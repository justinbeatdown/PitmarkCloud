# Pitmark Cloud v0.1.1

Server-side backend foundation for Pitmark Racing Tools.

## What works now

- FastAPI app
- `/health`
- `/docs`
- development entitlement endpoint
- Discord integration status scaffold
- Discord OAuth route scaffold
- Shopify integration status scaffold
- Shopify webhook route scaffold that intentionally rejects processing until HMAC verification exists
- environment-variable configuration
- Render-ready deployment

Nothing in this starter package pretends Shopify or Discord are connected before credentials and
secure verification are actually configured.


## v0.1.1 Render compatibility patch

This patch changes dependency/runtime handling for Render:

- pins Python to `3.12.8` via `.python-version`
- uses flexible compatible package ranges instead of the original exact pins
- uses plain `uvicorn` instead of `uvicorn[standard]` to avoid unnecessary native build extras
- keeps the same Render commands

Build:

```bash
pip install -r requirements.txt
```

Start:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```


## Render

Language:

`Python 3`

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Choose the Free instance while developing.

## First test

After deployment:

```text
https://YOUR-SERVICE.onrender.com/health
```

Expected shape:

```json
{
  "service": "Pitmark Cloud",
  "status": "online",
  "environment": "development",
  "version": "0.1.1",
  "timestamp": "..."
}
```

Interactive API documentation is available at:

```text
/docs
```

## Current development endpoints

- `GET /`
- `GET /health`
- `GET /api/entitlements/development`
- `GET /api/discord/status`
- `GET /api/discord/oauth/start`
- `GET /api/shopify/status`
- `POST /api/shopify/webhooks` — returns `501` until Shopify HMAC verification is implemented

## Security rules

- Never put Shopify Admin credentials in Pitmark Racing Tools.
- Never put a Discord bot token in Pitmark Racing Tools.
- Secrets belong only in Render environment variables / Pitmark Cloud.
- Never commit a real `.env`.
- Shopify webhooks must be HMAC verified before any entitlement is changed.
- Desktop entitlements should eventually use signed short-lived responses plus an offline grace period.

## Next backend milestones

1. Deploy v0.1.0 to Render.
2. Register/configure Discord application and OAuth callback.
3. Create the Pitmark Discord bot as a separate server process/worker.
4. Configure Shopify app/webhook credentials.
5. Add persistent database.
6. Replace development entitlements with real customer/device entitlements.
7. Connect Pitmark Racing Tools `EntitlementService` to Pitmark Cloud.
