# Pitmark Cloud v0.7.0 — Public Discord Deploy Checklist

## Render environment

Keep the existing Discord secrets and add/confirm:

```text
ENVIRONMENT=production
DISCORD_GATEWAY_ENABLED=true
DISCORD_COMMAND_SCOPE=global
DISCORD_INSTALL_PERMISSIONS=117760
DATABASE_URL=<persistent PostgreSQL connection string>
```

Do not set a global Discord share channel. Each Discord server configures its own channel with:

`/pitmark setup channel:#channel`

## Deploy sequence

1. Push v0.7.0 to the PitmarkCloud GitHub repository.
2. Wait for Render to report Live.
3. Open `/api/discord/bot/status`.
4. Confirm:
   - `interaction_endpoint_configured = true`
   - `command_registration_configured = true`
   - `command_scope = global`
   - `gateway_presence.connected = true`
   - `database.durable_for_render = true`
5. Run `POST /api/discord/bot/register` with the current `X-Pitmark-Admin-Key`.
6. Open `/api/discord/install` to obtain the public bot install URL.
7. Install Pitmark in a second Discord test server.
8. In that server, an admin runs `/pitmark setup` and chooses a channel.
9. Run `/pitmark config` as a normal member and confirm it shows the chosen channel.
10. In Pitmark Racing Tools v0.14.0, disconnect/reconnect Discord once to grant the `guilds` OAuth scope.
11. Open Race Card → Refresh Servers.
12. Confirm both configured servers appear if the linked Discord user belongs to both.
13. Share a Race Card to each destination.

## Discord permissions

The install URL requests:

- View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History

Pitmark does not require Administrator, Message Content Intent, Server Members Intent, or Presence Intent.

If a configured channel has permission overrides that block the bot, app sharing will return a useful
error and the server manager can choose a different channel or fix that channel's permissions.
