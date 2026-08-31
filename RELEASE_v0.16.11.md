# Pitmark Cloud v0.16.11

## Dashboard root routing

- `https://dashboard.pitmarkracing.com/` now routes to the Pitmark Control Center.
- Desktop browsers are sent to `/control`.
- Mobile browsers are sent to `/control/mobile`.
- The existing PitmarkCloud API root JSON remains unchanged on the Render hostname and all other hosts.
- No Control Center UI, source reader, Shield, Shopify, mail, or API behavior was otherwise changed.
