# Pitmark Cloud v0.21.14 — PRT In-App Tester Feedback + Header Spacing

## PRT tester feedback workflow
- PRT v0.16.50 submits Early Access feedback directly to the existing secure `/api/entitlements/feedback` route.
- Control Center PRT feedback queue identifies report source as `PRT APP` or `MANUAL`.
- Manual entry remains available and is explicitly labeled `Add Manual Feedback`.
- Acceptance copy now directs testers to PRT → Support → Early Access Feedback.

## Public PRT site
- Includes the unpushed v0.21.13 header correction.
- Restores the smaller logo footprint and adds breathing room using header top padding rather than logo scaling.
- Retains Early Access application CTAs and updates the public Windows build badge to v0.16.50. The preview image itself is unchanged.

## Security
- No Shield/CSP weakening.
- PRT app submissions use the existing device credential and require an active redeemed Early Access invite.
- Manual Control Center feedback remains protected by Control Center admin/owner authorization.
