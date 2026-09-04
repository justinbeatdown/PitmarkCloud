# Pitmark Cloud v0.21.17 — PRT v0.16.62 Distribution Update

## Purpose
Publish the first Early Access feedback stabilization build of Pitmark Racing Tools.

## Included
- Replaces the public PRT Windows installer with v0.16.62.
- Replaces the production `latest.json` with the matching v0.16.62 update manifest.
- Updates the public PRT landing page build badge and Download PRT label to v0.16.62.
- Preserves the existing public download routes, Early Access activation gate, Control Center Recent Connections cleanup, and unrelated Cloud behavior.

## PRT v0.16.62 focus
- Improved Inputs and RPM responsiveness.
- Dynamic steering range based on iRacing telemetry when available.
- Player-preserving standings behavior.
- More stable Relative and Radar presentation.
- Clearer separation between Session and Black Box overlays.

## Release artifact verification
- PRT version: `0.16.62`
- Installer SHA-256: `2c9c1126f57055ffdb9c569df9ee5ec29aef425103e2b0accbb11d3f04224243`
- `latest.json` contains the same SHA-256 and points to:
  `https://prt.pitmarkracing.com/downloads/PRT-Setup-Latest.exe`
- Manifest marks this update as required for Early Access clients.

## Files in this patch
- `api/prt.html`
- `api/downloads/PRT-Setup-Latest.exe`
- `api/downloads/latest.json`

## After deployment
1. Open `https://prt.pitmarkracing.com/prt` and confirm the page shows v0.16.62.
2. Open `https://prt.pitmarkracing.com/downloads/latest.json` and confirm version 0.16.62.
3. Download the installer and confirm it is the current v0.16.62 build.
4. Launch an installed v0.16.61 client and confirm the updater detects the required v0.16.62 update.
