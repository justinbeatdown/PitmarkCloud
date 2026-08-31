# Pitmark Cloud v0.16.9 — Mobile Blog Boot Fix

Root cause:
v0.16.8 added /control-mobile-blog.js to the mobile HTML, but FastAPI had no route serving that asset.
The browser received a 404, so the Blog script never executed and Generate Article was a dead button.

Fix:
- Add explicit /control-mobile-blog.js asset route.
- Serve it as application/javascript with Cache-Control: no-store.
- No changes to source reading, Shield, existing mobile JS, Shopify, email, or secrets.
