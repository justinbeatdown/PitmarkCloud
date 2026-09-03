# Pitmark Cloud v0.21.11 — PRT Hub Loader Fix

- Fixes the integrated PRT workspace remaining permanently on “Loading PRT access…” and “Loading PRT usage…”.
- Wires the PRT loader to an Analytics/PRT navigation button regardless of which Control Center bundle created that button.
- Wires the PRT Refresh button immediately instead of only after a successful data load.
- Hydrates the PRT hub automatically when Control Center is opened or refreshed directly on `#analytics`.
- Cache-busts Control Center JS/CSS assets so browsers cannot retain the broken v0.21.10 bundle.
- No licensing, Early Access, Shield, Shopify, or background-worker behavior is changed.
