# Pitmark Cloud v0.21.8 — PRT Early Access Activation

## Added
- Persistent one-time PRT Early Access tester invite codes.
- Codes are high-entropy and stored only as SHA-256 hashes in Pitmark Cloud.
- Early Access redemption requires the existing authenticated PRT device credential.
- A redeemed code binds to one PRT device and activates the full current tester entitlement set.
- Tester access is independent of Shopify purchases and can be revoked without altering paid licensing.
- Early Access codes default to 14-day redemption validity.
- Early Access grants use a 3-day offline grace so temporary Cloud outages do not interrupt testing while revoked access does not linger indefinitely.
- Direct owner/admin page at `/control/early-access` for issuing and revoking tester codes. This page is not added to the approved Control Center navigation/UI.
- Acceptance message generator/copy action on the Early Access admin page. Gmail remains the mail client; Pitmark Cloud does not send tester email.

## Licensing cut-over
- Devices without an active entitlement now receive the permanent Free tier rather than the old all-features development bridge.
- `/api/entitlements/development` remains available for development diagnostics.
- Existing Shopify Pro / League-Team activation and subscription synchronization are unchanged.

## Security
- Existing PRT 256-bit DPAPI-protected device credential remains authoritative.
- No device credential overwrite or rotation endpoint was added.
- Codes become one-device once redeemed and may be revoked by an authenticated Control Center owner/admin.

## Deployment
Coordinated desktop: Pitmark Racing Tools v0.16.48 or newer.
