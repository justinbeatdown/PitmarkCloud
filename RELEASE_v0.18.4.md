# Pitmark Cloud v0.18.4 — Full Discord Permission Model

## Why this release exists
Previous HQ builds treated Pitmark roles as delta roles: they relied on `@everyone`
for ordinary Discord permissions and only stored job-specific additions on each
role. That is valid in Discord's cumulative permission model, but it makes the
role permission pages look incomplete and does not match Pitmark's preferred
server-administration model.

## Changes
- Define a full self-contained normal-member permission baseline.
- Apply that baseline to every Pitmark community/status/interest role.
- Apply the same baseline to all staff roles before layering job permissions.
- Moderator now has the full everyday baseline plus channel/message/thread/user/
  event/voice moderation tools, audit log, pinning, slowmode bypass, kick and ban.
- Support now has the full everyday baseline plus message/thread/pin/voice support tools.
- Developer now has the full everyday baseline plus channels, audit log, webhooks,
  expressions, events and thread management.
- Partnerships and Marketing receive complete staff baselines and job-appropriate
  content/event permissions.
- Owner and Administrator remain Discord Administrator.
- Keep destructive server controls such as Manage Server/Manage Roles restricted
  to Administrator unless a role explicitly needs them.
- Official Pitmark HQ bot authorization now requests Administrator rather than a
  hand-maintained permission integer. This applies only to the configured Pitmark
  guild; public Pitmark bot installs remain lightweight.
- `/hq sync` repairs the entire existing role/channel permission matrix in place.
