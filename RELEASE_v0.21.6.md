# Pitmark Cloud v0.21.6 — Remove Control Center Mail UI

- Fixes the CSS specificity conflict that allowed the legacy Mail sidebar entry to remain visible.
- Removes/hides Mail workspace surfaces on desktop and mobile Control Center.
- Removes the Open Mail command action from the visible dashboard UI.
- Redirects stale `#email` Control Center routes back to Dashboard.
- Stops legacy Mail identity/preferences bootstrap reads when Control Center opens.
- Keeps Google Workspace/Gmail backend connectivity available for Pitmark Shield and server-side automation.
- Does not disable the Shield Gmail status/protection endpoint or Gmail sync used by Shield.
