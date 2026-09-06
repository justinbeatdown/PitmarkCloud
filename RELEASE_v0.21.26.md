# Pitmark Cloud v0.21.26 — X Premium Long Posts

Cloud-only patch for Pitmark's connected X Premium account.

## Fixed
- Removes the old hard-coded 280-character publishing guard.
- Allows X posts up to 25,000 characters, matching X Premium long-post capability.
- Keeps the maximum configurable with `X_POST_MAX_CHARACTERS` if the connected account changes later.
- Exposes the configured X post limit through social connection status.
- Updates Autopilot's X writing guidance so it stays concise by default but no longer throws away useful context just to fit 280 characters.

## Notes
- X itself remains the final authority on account eligibility and API acceptance.
- No PRT desktop code was changed.

Pitmark Cloud: **0.21.26**
PRT desktop: **unchanged**
