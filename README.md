# Pitmark Cloud v0.8.1 — Security Foundation + OAuth Polish

This package is the coordinated backend for Pitmark Racing Tools v0.16.4. See `SECURITY.md` and `SECURITY_DEPLOY_CHECKLIST.md` before deploying.

**Important:** v0.8.0 requires the new per-device credential on sensitive desktop endpoints. Older Pitmark desktop builds are intentionally incompatible with those endpoints after this deploy.

# Pitmark Cloud v0.7.0

Pitmark Cloud is the always-on backend for Pitmark Racing Tools.

## Current architecture

- FastAPI web service on Render
- Discord HTTP Interactions for slash commands
- Discord Gateway connection for continuous Online presence
- Public/global Discord commands
- Discord user OAuth with `identify guilds`
- Per-guild Pitmark configuration
- SQLAlchemy persistence for guild settings, Discord links/tokens, and published race results
- Live iRacing session bridge for `/session`
- Completed-result bridge for `/driver`, `/results`, `/racecard`, and desktop Race Card sharing

## Public Discord setup

The bot is designed to be installable in any Discord server.

`GET /api/discord/install` returns the public installation URL using the minimum Pitmark permission set.

Server managers configure their own server:

- `/pitmark setup channel:#channel` — choose the channel used by the Windows app's Share to Discord action.
- `/pitmark config` — show the server's current Pitmark configuration.
- `/pitmark reset` — remove the saved configuration.

Only members with **Manage Server** or **Administrator** can change setup/reset. `/pitmark config`
is readable by normal members.

Regular slash commands such as `/session`, `/driver`, `/results`, and `/racecard` respond in the
channel where invoked, subject to Discord's own command/channel permissions.

## Desktop sharing

Pitmark Racing Tools links Discord using OAuth scopes:

- `identify`
- `guilds`

Pitmark Cloud compares the linked user's Discord server list with guilds that have completed
`/pitmark setup`. The Race Card screen then shows only valid Pitmark-enabled destinations the user
actually belongs to. There is no global hard-coded Discord channel.

Existing users upgrading from an older OAuth link should disconnect/reconnect Discord once so the
new `guilds` scope is granted.

## Always-on Render environment

The paid Render web service keeps the Pitmark Discord Gateway connected continuously, so the bot can
remain visibly Online instead of depending on a sleeping free service.

Always-on compute does **not** make the service filesystem durable across deploys/restarts.

Before public multi-server launch, configure:

`DATABASE_URL=<persistent PostgreSQL connection string>`

Pitmark supports standard `postgres://` and `postgresql://` connection strings and normalizes them
for psycopg automatically. Render Postgres or another persistent PostgreSQL provider is appropriate.

If `DATABASE_URL` is absent, local SQLite is used only as a development fallback. `/api/discord/bot/status`
and `/` expose the database readiness state so this cannot be mistaken for production persistence.

Keep `PITMARK_SIGNING_SECRET` stable. Discord OAuth refresh tokens are encrypted using a key derived
from that secret; rotating it invalidates stored OAuth tokens and users would need to reconnect.

## Required Render environment variables

```text
ENVIRONMENT=production
PITMARK_SIGNING_SECRET=<stable strong secret>
PITMARK_ADMIN_KEY=<strong admin key>

DISCORD_CLIENT_ID=<Discord application ID>
DISCORD_CLIENT_SECRET=<Discord OAuth client secret>
DISCORD_REDIRECT_URI=https://pitmarkcloud.onrender.com/api/discord/oauth/callback
DISCORD_BOT_TOKEN=<Discord bot token>
DISCORD_PUBLIC_KEY=<Discord application public key>
DISCORD_SUPPORT_INVITE_URL=<optional support server invite>

DISCORD_GATEWAY_ENABLED=true
DISCORD_PRESENCE_TEXT=Pitmark Racing Tools
DISCORD_PRESENCE_TYPE=watching

DISCORD_COMMAND_SCOPE=global
DISCORD_INSTALL_PERMISSIONS=117760

DATABASE_URL=<persistent PostgreSQL URL>
```

`DISCORD_GUILD_ID` is only useful if `DISCORD_COMMAND_SCOPE=guild` is intentionally used for a
development-only command deployment. Production should remain `global`.

## Deploy / update

1. Push the Pitmark Cloud files to the connected GitHub repository.
2. Let Render deploy the new commit.
3. Check `GET /api/discord/bot/status`.
4. Confirm:
   - interaction endpoint configured = true
   - command registration configured = true
   - Gateway connected = true
   - command scope = global
   - database durable_for_render = true
5. Run `POST /api/discord/bot/register` with the current `X-Pitmark-Admin-Key`.
6. Existing desktop testers should reconnect Discord once for the `guilds` OAuth scope.
7. Install the bot in a second test server and run `/pitmark setup` there to verify multi-server behavior.

## Current command set

- `/pitmark about`
- `/pitmark setup`
- `/pitmark config`
- `/pitmark reset`
- `/status`
- `/download`
- `/support`
- `/account`
- `/session`
- `/driver`
- `/results`
- `/racecard`

## Security

- Discord bot token and client secret never ship in the Windows app.
- Interaction requests are Ed25519 signature-verified.
- OAuth state is HMAC-signed and expires.
- OAuth access/refresh tokens are encrypted at rest in the database.
- Bot command registration is protected by `X-Pitmark-Admin-Key`.
- No privileged Discord Gateway intents are required for the current feature set.

## v0.12.0 Control Center additions

- Desktop Control Center: `/control`
- Mobile/PWA Control Center: `/control/mobile`
- Shield synthetic test harness verifies Legit / Review / Spam / System behavior before mailbox integration.
- Outreach supports contact method/handle, stage, supporter status, follow-up and notes using the existing durable schema.
- Blog supports AI-assisted Track/Partner Spotlight drafting and approval/scheduling.
- Social account cards report OAuth app readiness; live provider authorization/publishing remains intentionally disabled until provider apps are configured.
