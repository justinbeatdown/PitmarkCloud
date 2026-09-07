# Pitmark Cloud v0.21.38

## PRT Early Access recovery hotfix

- Fixed Early Access offline grace being treated as a one-time three-day expiration.
- Successful authenticated entitlement checks now renew the three-day offline grace for active Early Access testers.
- Revoked or inactive Early Access entitlements are not renewed.
- This is the server-side half of the PRT v0.16.79 activation-persistence recovery patch.

### Incident
Older activated PRT clients could return to the Early Access gate once their originally cached three-day grace elapsed even though their tester entitlement remained active.
