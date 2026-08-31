PITMARK CLOUD v0.14.7 COMPLETE BUILD

HOTFIX / ROOT-CAUSE REPAIR
- Fixes Social Timeline HTTP 500 caused by a missing OpportunitySourceMeta import.
- Recalculates source freshness at request time instead of displaying stale stored labels.
- Social freshness remains: <=2h realtime, <=4h recent, >4h excluded from reactive social, older material remains usable for long-form/blog.
- No database migration required.

DEPLOY THE COMPLETE BUILD.
1. Replace the project with this full package.
2. Confirm footer reads v0.14.7.
3. Open Autopilot and confirm Social Timeline loads.
4. Confirm old Intelligence items show BACKGROUND or LONGFORM, not FRESH/RECENT.
