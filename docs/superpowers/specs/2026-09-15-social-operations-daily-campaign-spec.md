# Social Operations Daily Campaign Spec

Pitmark Social Operations becomes the single daily marketing coordinator.

## Required behavior

- Exactly one idempotent Daily Campaign per Pitmark local calendar day.
- Select the strongest recent verified first-party Pitmark event when available: PRT release, Racing Culture blog, product, partnership, Street Team or meaningful milestone.
- If no meaningful verified event exists, use deterministic community-growth content.
- Generate one coherent package containing Facebook copy, Instagram copy, X copy, Discord copy, TikTok/Reels copy, six Instagram 4:5 visual slots, and vertical TikTok/Reels visual slots.
- Existing first-party scanners, AI composition, image generation, asset storage, scheduler/publishers, Discord and engagement systems are reused rather than replaced.
- Re-running, restarting or clicking Run Operator Now must not duplicate campaigns, posts or asset slots.
- TikTok/Reels remains ready-to-post until a supported direct publisher exists.
- Current Facebook/Instagram/X publishing safety boundaries remain unchanged.
- AI image generation must not redraw or approximate the official Pitmark logo. Images must reserve branding-safe/text-safe composition space.
- Social Operations UI must report campaign topic and package completeness before engagement metrics: IG slides, vertical assets, platform copy, and queue/publish readiness.
- Existing engagement review/reply guardrails remain intact below the campaign controls.
