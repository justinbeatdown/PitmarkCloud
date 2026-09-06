# Pitmark Cloud v0.21.30

Coordinated release for **Pitmark Racing Tools v0.16.78**.

## Changed
- Bumped Pitmark Cloud release identity to `0.21.30`.
- Updated the public PRT Early Access page to advertise Windows build `v0.16.78`.
- Confirmed the existing R2 bridge remains the release path: `/downloads/latest.json` is served from the Cloudflare R2 manifest and `/downloads/PRT-Setup-Latest.exe` uses the R2 installer path.

## PRT release workflow
The v0.16.78 desktop build no longer needs a per-release Cloud source bundle. Build the Windows installer, then run `Publish-R2.cmd` to publish the versioned installer, stable installer, and `latest.json` to Cloudflare R2.
