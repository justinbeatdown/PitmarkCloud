# v0.17.5 — PRT Mobile Asset Hotfix

Root cause:
- PRT routes were falling into the global `default-src 'none'` CSP.
- A desktop browser could appear healthy from cached assets, while a fresh mobile browser blocked PRT CSS, JS, logo and screenshot assets.
- The v0.17.4 package attempted to bump a non-existent `app_version = "..."` literal instead of the real `PITMARK_RELEASE_VERSION` constant.

Fix:
- Add a strict same-origin CSP policy for the `/prt*` route/asset family.
- Restore CSS, JS, logos and the real PRT screenshot on fresh/mobile loads.
- Set the real Pitmark Cloud release constant to 0.17.5.
- Keep all four PRT service/version indicators in a deliberate grid: one row on desktop, 2x2 on smaller screens, 1-column only on very narrow screens.
