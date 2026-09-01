# Pitmark Cloud v0.20.2 — Control Center Sidebar Recovery

## Outcome

This focused repair restores the desktop Control Center sidebar that remained
blank in v0.20.1. Gmail, Shield, labels, filters, and automatic replies are
preserved without behavioral changes.

## Root fix

- Adds a final authoritative sidebar stylesheet that owns desktop rail geometry.
- Adds a runtime recovery layer that restores missing sidebar markup, navigation,
  branding, and footer content after the existing access/runtime scripts finish.
- Preserves role-based navigation permissions.
- Cache-busts every Control Center UI bundle so the repair cannot be masked by an
  older browser asset.
- Leaves the existing mobile bottom navigation unchanged.

## Deploy check

After deployment, set `APP_VERSION=0.20.2` in Render, hard-refresh Control Center,
and confirm the left navigation contains Dashboard, Autopilot, Mail, Shield,
Campaigns, Outreach, Blog, PRT Analytics, Directory, and Settings.
