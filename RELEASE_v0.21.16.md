# Pitmark Cloud v0.21.16 — PRT Public Installer Distribution

## Included
- Carries forward the v0.21.15 Control Center PRT Recent Connections cleanup.
- Adds the production PRT v0.16.61 Windows installer directly to Pitmark Cloud.
- Adds the matching `latest.json` update manifest.
- Serves the stable public release URLs expected by PRT:
  - `/downloads/PRT-Setup-Latest.exe`
  - `/downloads/latest.json`
- Updates the public PRT landing page from Windows build v0.16.50 to v0.16.61.
- Adds real Download PRT buttons to the hero and Early Access section.
- Keeps Early Access fail-closed: the installer is public, but PRT still requires a valid activation code.

## Release artifact verification
- PRT version: `0.16.61`
- Installer SHA-256: `8e59819467923f8133460f9fa011fb73ac52d1492a15bf766709fc9d4ab4eb99`
- `latest.json` contains the same SHA-256 and points to:
  `https://prt.pitmarkracing.com/downloads/PRT-Setup-Latest.exe`

## Files in this patch
- `api/control_center_ui.py`
- `api/control_center_v191.js`
- `api/prt.html`
- `api/downloads/PRT-Setup-Latest.exe`
- `api/downloads/latest.json`

## After deployment
1. Open `https://prt.pitmarkracing.com/prt` and confirm the page shows v0.16.61.
2. Click Download PRT and confirm the installer downloads.
3. Open `https://prt.pitmarkracing.com/downloads/latest.json` and confirm version 0.16.61 is returned.
4. Confirm Control Center shows Recent PRT Connections rather than lap-by-lap clutter.
5. Do not change the installer or manifest independently; they are a matched release pair.
