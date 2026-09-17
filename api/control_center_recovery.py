from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_RECOVERY_RELEASE = "20260917hq3"


@router.get('/control-reset', response_class=HTMLResponse, include_in_schema=False)
def control_reset():
    # Intentionally outside the old /control/ service-worker scope so stale
    # installed PWAs cannot intercept this recovery page.
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
  <meta name=\"theme-color\" content=\"#090a0c\">
  <title>Refreshing Pitmark Control Center</title>
  <style>
    html,body{{height:100%;margin:0;background:#090a0c;color:#fff;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
    body{{display:grid;place-items:center;padding:24px;text-align:center}}
    .card{{max-width:420px}}
    .dot{{width:12px;height:12px;border-radius:50%;background:#ff5500;margin:0 auto 18px;box-shadow:0 0 24px #ff5500}}
    p{{color:#aeb2b8;line-height:1.5}}
  </style>
</head>
<body>
  <main class=\"card\">
    <div class=\"dot\"></div>
    <h1>Refreshing Control Center</h1>
    <p>Removing the retired mobile shell and loading the current Pitmark HQ.</p>
  </main>
  <script>
    (async () => {{
      try {{
        if ('serviceWorker' in navigator) {{
          const registrations = await navigator.serviceWorker.getRegistrations();
          await Promise.all(registrations.map(registration => registration.unregister()));
        }}
        if ('caches' in window) {{
          const keys = await caches.keys();
          await Promise.all(keys
            .filter(key => key.startsWith('pitmark-mobile-') || key.startsWith('pitmark-control-'))
            .map(key => caches.delete(key)));
        }}
      }} finally {{
        location.replace('/control/mobile?fresh={_RECOVERY_RELEASE}');
      }}
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(html, headers={'Cache-Control': 'no-store, max-age=0'})
