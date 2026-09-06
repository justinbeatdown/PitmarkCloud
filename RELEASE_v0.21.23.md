# Pitmark Cloud v0.21.23

PRT coordinated Early Access + Cloudflare R2 rollout patch.

- Coordinates the public PRT site with Windows build v0.16.77.
- Removes the extra trust-badge halo/double-circle treatment from the PRT footer.
- Keeps the supplied Pitmark Cloud / Pitmark Shield service artwork and cleans the presentation around it.
- Adds Cloudflare R2-aware installer delivery at the existing stable `/downloads/PRT-Setup-Latest.exe` URL.
- Uses a 307 redirect to the configured R2 public/custom domain when `PRT_R2_ENABLED=true`.
- Preserves a local installer fallback during migration so testers are not stranded if R2 is not configured yet.
- Keeps `/downloads/latest.json` on Pitmark Cloud for a tiny, stable auto-update manifest.
- Adds R2 configuration fields without storing any Cloudflare secret/API credential in the repository.
- Retains the Race Card upload body-limit fix and leaves Shield, licensing, Autopilot, Discord, and unrelated Control Center behavior intact.
