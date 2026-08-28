# Pitmark Cloud v0.4.0

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


## Discord OAuth v0.2.0

New development flow:

- `GET /api/discord/status`
- `POST /api/discord/link/start?device_id=...`
- `GET /api/discord/link/status?device_id=...`
- `POST /api/discord/link/disconnect?device_id=...`
- `GET /api/discord/oauth/callback`

Required Render environment variables:

- `PITMARK_SIGNING_SECRET` — strong random value
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI=https://pitmarkcloud.onrender.com/api/discord/oauth/callback`

The desktop app never receives the Discord client secret. OAuth `state` is HMAC signed and expires
after 10 minutes. v0.2 stores linked identities in memory only, so Render restarts/spin-downs clear
the development link. Persistent account linking comes with the database milestone.


## Discord Bot v0.3.0

Pitmark now supports Discord HTTP Interactions, which fits Render's web-service model better than
depending on a permanently connected Gateway process.

New endpoints:

- `GET /api/discord/bot/status`
- `POST /api/discord/bot/register` — protected by `X-Pitmark-Admin-Key`
- `POST /api/discord/interactions` — Discord Interactions Endpoint URL

Required Render environment variables:

- `DISCORD_PUBLIC_KEY`
- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `PITMARK_ADMIN_KEY`
- optional `DISCORD_SUPPORT_INVITE_URL`

Existing OAuth variables remain required for desktop account linking.

Initial slash commands:

- `/pitmark`
- `/status`
- `/download`
- `/support`
- `/account`

No privileged Gateway intents are needed for these first commands.


## v0.4.0 — Live Session Discord Bridge

New development endpoints:

- `POST /api/discord/session/update?device_id=...`
- `POST /api/discord/session/clear?device_id=...`

The update endpoint only accepts a device that currently has a connected Discord OAuth link.

New Discord command:

- `/session` — shows the invoking user's live Pitmark/iRacing session as a Discord embed.

The command registry now uses Discord's bulk-overwrite guild command endpoint, so re-registering also
cleans up stale development commands.

Current live session storage is in memory. Render restarts/spin-downs clear it; persistent account
and session state comes with the database milestone.


## Discord Gateway presence — working source

A lightweight Discord Gateway connection now runs alongside the existing HTTP Interactions system
solely to give the Pitmark bot a visible Online presence/status.

Optional Render variables:

- `DISCORD_GATEWAY_ENABLED=true`
- `DISCORD_PRESENCE_TEXT=Pitmark Racing Tools`
- `DISCORD_PRESENCE_TYPE=watching`

Supported presence types: `watching`, `playing`, `listening`, `competing`.

Important: Render Free can suspend the service after inactivity. If Render sleeps, the Gateway
connection closes and Discord shows the bot Offline until Pitmark Cloud wakes again. Slash commands
continue to use the HTTP Interactions architecture.
