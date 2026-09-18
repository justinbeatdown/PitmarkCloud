# Pitmark Racing Tools — Android Companion

Native Android companion for PRT. This is intentionally an information/control app rather than a phone version of the desktop overlays.

## v0.1 scope
- Driver dashboard backed by Pitmark Cloud
- Recent race/session history
- Live-session telemetry snapshot
- Basic control action: share latest Race Card to the configured Pitmark Discord destination
- Encrypted local storage for the PRT device credential
- Android 16 / API 36 target for current Google Play submission requirements

## Pairing
The first build uses the same device ID + PRT device token already trusted by Pitmark Cloud. A dedicated QR/deep-link pairing flow should replace manual entry before public release.

## Before Play production
- App icon, feature graphic, screenshots
- QR/deep-link pairing
- Push notifications
- Full race detail and telemetry charts
- Driver DNA trends
- Setup Vault browsing and remote desktop controls
- Privacy policy and Data safety review
- Internal testing track, signed AAB, crash/ANR verification
