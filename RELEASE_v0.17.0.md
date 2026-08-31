# Pitmark Cloud v0.17.0 — PRT Web Foundation

First public-facing Pitmark Racing Tools web foundation.

- Adds `/prt` responsive desktop/mobile PRT interface.
- Adds `prt.pitmarkracing.com` host-aware root routing to `/prt`.
- Adds PRT status endpoint.
- Adds a real “Add Pitmark Bot to Discord” button using the existing `/api/discord/install` flow.
- Uses the existing Discord client ID / permissions configuration; no new Discord secrets are exposed to the browser.
- Keeps `dashboard.pitmarkracing.com` routed to the internal Control Center.
- Keeps the generic Render/API hostname root response unchanged.
- Marks the PRT web product as Early Access and surfaces `prt@mail.pitmarkracing.com` support.
