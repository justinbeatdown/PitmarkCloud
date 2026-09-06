# Pitmark Cloud v0.21.31

## Mobile Control Center — Command Deck redesign

- Reworked the dedicated `/control/mobile` surface so it reads as a phone-native Pitmark command app rather than a compressed desktop dashboard.
- Added a stronger Pitmark mobile operations hero, live status strip, and clearer mobile-first hierarchy.
- Reworked quick actions into a touch-first command deck with Review as the primary action.
- Tightened dashboard metrics into compact 2x2 operator cards.
- Refined cards, forms, buttons, workspaces, and the floating bottom navigation for smaller screens.
- Removed the stale Mail quick-action tile from the mobile command deck now that Control Center no longer acts as an email client.
- Updated the displayed mobile operations version to v0.21.31.
- Bumped the mobile service-worker cache so installed PWA sessions refresh into the new interface instead of holding older shell assets.

Desktop Control Center behavior and existing backend workflows are unchanged.
