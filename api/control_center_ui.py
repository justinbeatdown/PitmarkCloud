from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from services.control_auth import user_from_request
from utils.config import settings

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent

AUTOFILL_GUARD = r"""
<script>
(() => {
  const BAD = new Set(['justin', 'admin']);
  const selector = 'input:not([type="password"]):not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="file"]), textarea';
  const normalize = v => String(v || '').trim().toLowerCase().replace(/[.!]+$/,'');
  const bad = el => BAD.has(normalize(el.value));
  const trustedIntent = new WeakSet();

  function protect(el) {
    if (!el || el.dataset.pitmarkAutofillGuard) return;
    el.dataset.pitmarkAutofillGuard = '1';
    el.setAttribute('autocomplete', 'off');
    el.setAttribute('data-lpignore', 'true');
    el.setAttribute('data-1p-ignore', 'true');
    el.setAttribute('data-form-type', 'other');
    // Browser/password-manager autofill often emits input/change events. Those
    // are NOT proof of user intent. Only trusted typing/paste marks a value as
    // intentional, so a real manually typed "Justin" is preserved.
    el.addEventListener('keydown', ev => { if (ev.isTrusted) trustedIntent.add(el); }, true);
    el.addEventListener('paste', ev => { if (ev.isTrusted) trustedIntent.add(el); }, true);
    el.addEventListener('drop', ev => { if (ev.isTrusted) trustedIntent.add(el); }, true);
    el.addEventListener('focus', () => setTimeout(() => scrubOne(el), 60));
  }
  function scrubOne(el) {
    protect(el);
    if (trustedIntent.has(el)) return;
    if (bad(el)) {
      el.value = '';
      el.dispatchEvent(new Event('change', {bubbles:true}));
    }
  }
  function scrub() { document.querySelectorAll(selector).forEach(scrubOne); }
  document.addEventListener('DOMContentLoaded', () => {
    scrub();
    [50,150,350,750,1500,3000,5000].forEach(ms => setTimeout(scrub, ms));
    new MutationObserver(() => setTimeout(scrub, 30)).observe(document.documentElement,{childList:true,subtree:true});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) setTimeout(scrub, 50); });
    window.addEventListener('pageshow', () => setTimeout(scrub, 50));
  });
})();
</script>
"""

EMAIL_ASSETS = """
<link rel="stylesheet" href="/control-email.css">
<script src="/control-email.js" defer></script>
"""


@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control(request: Request):
    filename = 'control_center.html' if user_from_request(request) else 'control_login.html'
    html = (ASSET_DIR / filename).read_text(encoding='utf-8')
    if filename == 'control_center.html':
        import re
        html = re.sub(r'PITMARK CLOUD v[0-9]+(?:\.[0-9]+)*', f'PITMARK CLOUD v{settings.app_version}', html, flags=re.IGNORECASE)
        html = html.replace('</head>', '<link rel="stylesheet" href="/control-email.css">\n</head>')
        html = html.replace('</body>', AUTOFILL_GUARD + '\n<script src="/control-email.js" defer></script>\n</body>')
    return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


@router.get('/control.css', include_in_schema=False)
def control_css(): return Response((ASSET_DIR / 'control_center.css').read_text(encoding='utf-8'), media_type='text/css')

@router.get('/control.js', include_in_schema=False)
def control_js(): return Response((ASSET_DIR / 'control_center.js').read_text(encoding='utf-8'), media_type='application/javascript')

@router.get('/control-email.css', include_in_schema=False)
def control_email_css(): return Response((ASSET_DIR / 'control_email.css').read_text(encoding='utf-8'), media_type='text/css', headers={'Cache-Control':'no-store'})

@router.get('/control-email.js', include_in_schema=False)
def control_email_js(): return Response((ASSET_DIR / 'control_email.js').read_text(encoding='utf-8'), media_type='application/javascript', headers={'Cache-Control':'no-store'})

@router.get('/control-login.js', include_in_schema=False)
def control_login_js(): return Response((ASSET_DIR / 'control_login.js').read_text(encoding='utf-8'), media_type='application/javascript')

@router.get('/control/mobile', response_class=HTMLResponse, include_in_schema=False)
def control_mobile(request: Request):
    filename = 'control_mobile.html' if user_from_request(request) else 'control_mobile_login.html'
    html = (ASSET_DIR / filename).read_text(encoding='utf-8')
    if filename == 'control_mobile.html':
        html = html.replace('</body>', AUTOFILL_GUARD + '\n</body>')
    return HTMLResponse(html, headers={'Cache-Control':'no-store'})

@router.get('/control-mobile.css', include_in_schema=False)
def control_mobile_css(): return Response((ASSET_DIR / 'control_mobile.css').read_text(encoding='utf-8'), media_type='text/css')

@router.get('/control-mobile.js', include_in_schema=False)
def control_mobile_js(): return Response((ASSET_DIR / 'control_mobile.js').read_text(encoding='utf-8'), media_type='application/javascript', headers={'Cache-Control':'no-store'})

@router.get('/control-mobile-login.js', include_in_schema=False)
def control_mobile_login_js(): return Response((ASSET_DIR / 'control_mobile_login.js').read_text(encoding='utf-8'), media_type='application/javascript')

@router.get('/control.webmanifest', include_in_schema=False)
def control_manifest(): return Response((ASSET_DIR / 'control.webmanifest').read_text(encoding='utf-8'), media_type='application/manifest+json')

@router.get('/control-sw.js', include_in_schema=False)
def control_sw(): return Response((ASSET_DIR / 'control_sw.js').read_text(encoding='utf-8'), media_type='application/javascript', headers={'Service-Worker-Allowed':'/control/'})

@router.get('/control-logo-wide.png', include_in_schema=False)
def control_logo_wide(): return FileResponse(ASSET_DIR / 'pitmark_logo_wide.png', media_type='image/png')

@router.get('/control-logo-badge.png', include_in_schema=False)
def control_logo_badge(): return FileResponse(ASSET_DIR / 'pitmark_badge.png', media_type='image/png')

@router.get('/control-favicon.png', include_in_schema=False)
def control_favicon(): return FileResponse(ASSET_DIR / 'pitmark_favicon.png', media_type='image/png', headers={'Cache-Control':'public, max-age=3600'})

@router.get('/favicon.ico', include_in_schema=False)
def favicon_ico(): return FileResponse(ASSET_DIR / 'pitmark_favicon.ico', media_type='image/x-icon', headers={'Cache-Control':'public, max-age=3600'})
