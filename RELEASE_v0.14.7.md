# Pitmark Cloud v0.14.7 — Timeline + Freshness Root-Cause Repair

- Fixed `/api/control/autopilot/posts` 500 caused by a missing `OpportunitySourceMeta` import.
- Timeline source ages are recalculated from `published_at` against the current UTC clock.
- Intelligence freshness labels are also recalculated dynamically, eliminating stale labels such as a 44-hour-old article still appearing fresh.
- Reactive social cutoff remains 4 hours; older material is background/long-form only.
- No schema migration required.
