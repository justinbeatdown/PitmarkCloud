# Pitmark Cloud v0.21.5 — Control Center Hang Fix

- Removes the v0.21.4 whole-page MutationObserver that could create a self-triggering desktop DOM loop.
- Stops deleting Mail DOM nodes while legacy Control Center bundles are initializing.
- Keeps Mail hidden and unreachable on desktop and mobile using a passive presentation guard.
- Keeps Google Workspace / Gmail backend connectivity intact for Pitmark Shield and server-side automation.
- Preserves Control Center API loading, notifications, Command Brief, dashboard stats, and navigation initialization.
