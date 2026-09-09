# Pitmark Cloud v0.21.42

## PRT campaign attribution and application clarity

PRT campaign links now retain their public source and creative labels along the homepage/support path. Download clicks appear by source in the existing desktop PRT Analytics view, helping compare the September proof campaign without adding browser identifiers or a new analytics provider.

- Accept only campaign `prt_raceproof_202609`, the seven documented source labels, and `race`, `feedback`, or `invite` creative labels. Arbitrary URL parameters are not collected.
- Retain campaign labels only on same-origin PRT homepage, support, and application links. Installer, email, Discord, and external destinations keep their existing behavior.
- Summarize the top 20 download-click sources from the last seven days using the existing table. No database migration.
- Explain Google sign-in before the Early Access application and offer the existing PRT support email for application help.
- Use a generic Windows download label until the release manifest provides the actual desktop version; remove the stale hard-coded v0.16.79 fallback.
- Synchronize the mobile release label/cache to v0.21.42 while retaining the latest mobile fixes, paid activation, and Partner Paddock work.

## Verification and limits

- All 12 focused JavaScript checks passed via `node --test scripts/test_prt_downloads.mjs scripts/test_prt_support.mjs`, covering campaign validation, link propagation, privacy boundaries, non-blocking downloads, and FAQ behavior.
- Changed JavaScript passed syntax checks; changed Python modules compiled successfully.
- Verify live PRT homepage/support and campaign link propagation after deployment without creating synthetic production download events.
- Backend runtime tests were not run because SQLAlchemy, FastAPI, and pydantic-settings are unavailable locally. A natural download event remains the final production write-through check.
- These are clicks, not completed transfers, applications, unique installs, or returning testers. No campaign-to-device or league-adoption join is implemented. Google Forms does not automatically inherit completion attribution from these links.

## Campaign labels

`utm_source`: facebook, tiktok, instagram, x, discord, league, creator.

`utm_content`: race, feedback, invite.

Example: `/prt?utm_campaign=prt_raceproof_202609&utm_source=facebook&utm_medium=organic_social&utm_content=race`.
