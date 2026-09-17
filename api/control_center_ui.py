from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from services.control_auth import user_from_request

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
PRT_DOWNLOAD_DIR = ASSET_DIR / 'downloads'

# Shared safety utility only. The 2026 Control Center owns its own DOM, styles,
# state, and navigation; no legacy enhancement bundle is injected at runtime.
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
    const lockIds = new Set(['ryName','oname','oorg','ocontact']);
    if (lockIds.has(el.id) && !el.dataset.userUnlocked) {
      el.readOnly = true;
      const unlock = () => { el.dataset.userUnlocked='1'; el.readOnly=false; };
      el.addEventListener('pointerdown', unlock, {once:true, capture:true});
      el.addEventListener('focus', unlock, {once:true, capture:true});
    }
    el.setAttribute('autocomplete', 'off');
    el.setAttribute('data-lpignore', 'true');
    el.setAttribute('data-1p-ignore', 'true');
    el.setAttribute('data-form-type', 'other');
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


def _guarded_html(filename: str, *, guard: bool) -> HTMLResponse:
    html = (ASSET_DIR / filename).read_text(encoding='utf-8')
    if guard:
        html = html.replace('</body>', AUTOFILL_GUARD + '</body>')
    return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control(request: Request):
    filename = 'control_center.html' if user_from_request(request) else 'control_login.html'
    return _guarded_html(filename, guard=filename == 'control_center.html')


@router.get('/control/mobile', response_class=HTMLResponse, include_in_schema=False)
def control_mobile(request: Request):
    # Mobile and desktop intentionally run the same authenticated app. Responsive
    # presentation belongs to one feature registry rather than a second product.
    filename = 'control_center.html' if user_from_request(request) else 'control_mobile_login.html'
    return _guarded_html(filename, guard=filename == 'control_center.html')


def _text_asset(filename: str, media_type: str, *, cache: str = 'no-store') -> Response:
    return Response(
        (ASSET_DIR / filename).read_text(encoding='utf-8'),
        media_type=media_type,
        headers={'Cache-Control': cache},
    )


# Current Control Center assets.
@router.get('/control-center-overhaul.js', include_in_schema=False)
def control_center_overhaul_js():
    return _text_asset('control_center_overhaul.js', 'application/javascript')


@router.get('/control-center-overhaul.css', include_in_schema=False)
def control_center_overhaul_css():
    return _text_asset('control_center_overhaul.css', 'text/css')


# Login/PWA assets still used by the current authentication entry points.
@router.get('/control.css', include_in_schema=False)
def control_css():
    return _text_asset('control_center.css', 'text/css')


@router.get('/control-login.js', include_in_schema=False)
def control_login_js():
    return _text_asset('control_login.js', 'application/javascript')


@router.get('/control-mobile.css', include_in_schema=False)
def control_mobile_css():
    return _text_asset('control_mobile.css', 'text/css')


@router.get('/control-mobile-login.js', include_in_schema=False)
def control_mobile_login_js():
    return _text_asset('control_mobile_login.js', 'application/javascript')


@router.get('/control.webmanifest', include_in_schema=False)
def control_manifest():
    return _text_asset('control.webmanifest', 'application/manifest+json')


@router.get('/control-sw.js', include_in_schema=False)
def control_sw():
    return Response(
        (ASSET_DIR / 'control_sw.js').read_text(encoding='utf-8'),
        media_type='application/javascript',
        headers={'Service-Worker-Allowed': '/control/', 'Cache-Control': 'no-store'},
    )


# Compatibility asset routes. These are deliberately NOT injected into the 2026
# app. They remain temporarily reachable until repository-wide reference audit
# proves which deep/legacy pages no longer consume them.
@router.get('/control.js', include_in_schema=False)
def control_js():
    return _text_asset('control_center.js', 'application/javascript')


@router.get('/control-email.css', include_in_schema=False)
def control_email_css():
    return _text_asset('control_email.css', 'text/css')


@router.get('/control-email.js', include_in_schema=False)
def control_email_js():
    return _text_asset('control_email.js', 'application/javascript')


@router.get('/control-email-identity.js', include_in_schema=False)
def control_email_identity_js():
    return _text_asset('control_email_identity.js', 'application/javascript')


@router.get('/control-email-shield.css', include_in_schema=False)
def control_email_shield_css():
    return _text_asset('control_email_shield.css', 'text/css')


@router.get('/control-email-shield.js', include_in_schema=False)
def control_email_shield_js():
    return _text_asset('control_email_shield.js', 'application/javascript')


@router.get('/control-shield-mail-status.js', include_in_schema=False)
def control_shield_mail_status_js():
    return _text_asset('control_shield_mail_status.js', 'application/javascript')


@router.get('/control-email-spam-training.js', include_in_schema=False)
def control_email_spam_training_js():
    return _text_asset('control_email_spam_training.js', 'application/javascript')


@router.get('/control-mail-client.js', include_in_schema=False)
def control_mail_client_js():
    return _text_asset('control_mail_client.js', 'application/javascript')


@router.get('/control-mail-client.css', include_in_schema=False)
def control_mail_client_css():
    return _text_asset('control_mail_client.css', 'text/css')


@router.get('/control-center-v19.js', include_in_schema=False)
def control_center_v19_js():
    return _text_asset('control_center_v19.js', 'application/javascript')


@router.get('/control-center-v19.css', include_in_schema=False)
def control_center_v19_css():
    return _text_asset('control_center_v19.css', 'text/css')


@router.get('/control-center-v191.js', include_in_schema=False)
def control_center_v191_js():
    return _text_asset('control_center_v191.js', 'application/javascript')


@router.get('/control-center-v191.css', include_in_schema=False)
def control_center_v191_css():
    return _text_asset('control_center_v191.css', 'text/css')


@router.get('/control-center-v195.js', include_in_schema=False)
def control_center_v195_js():
    return _text_asset('control_center_v195.js', 'application/javascript')


@router.get('/control-center-v195.css', include_in_schema=False)
def control_center_v195_css():
    return _text_asset('control_center_v195.css', 'text/css')


@router.get('/control-center-v201.css', include_in_schema=False)
def control_center_v201_css():
    return _text_asset('control_center_v201.css', 'text/css')


@router.get('/control-center-v202.css', include_in_schema=False)
def control_center_v202_css():
    return _text_asset('control_center_v202.css', 'text/css')


@router.get('/control-center-v202.js', include_in_schema=False)
def control_center_v202_js():
    return _text_asset('control_center_v202.js', 'application/javascript')


@router.get('/control-mobile.js', include_in_schema=False)
def control_mobile_js():
    return _text_asset('control_mobile.js', 'application/javascript')


@router.get('/control-mobile-blog.js', include_in_schema=False)
def control_mobile_blog_js():
    return _text_asset('control_mobile_blog.js', 'application/javascript')


@router.get('/control-mobile-mail-identity.js', include_in_schema=False)
def control_mobile_mail_identity_js():
    return _text_asset('control_mobile_mail_identity.js', 'application/javascript')


@router.get('/control-mobile-v2.css', include_in_schema=False)
def control_mobile_v2_css():
    return _text_asset('control_mobile_v2.css', 'text/css')


@router.get('/control-mobile-v2.js', include_in_schema=False)
def control_mobile_v2_js():
    return _text_asset('control_mobile_v2.js', 'application/javascript')


@router.get('/control-runtime-v194.js', include_in_schema=False)
def control_runtime_v194_js():
    return _text_asset('control_runtime_v194.js', 'application/javascript')


@router.get('/control-logo-wide.png', include_in_schema=False)
def control_logo_wide():
    return FileResponse(ASSET_DIR / 'pitmark_logo_wide.png', media_type='image/png')


@router.get('/control-logo-badge.png', include_in_schema=False)
def control_logo_badge():
    return FileResponse(ASSET_DIR / 'pitmark_badge.png', media_type='image/png')


@router.get('/control-favicon.png', include_in_schema=False)
def control_favicon():
    return FileResponse(
        ASSET_DIR / 'pitmark_favicon.png',
        media_type='image/png',
        headers={'Cache-Control': 'public, max-age=3600'},
    )


@router.get('/favicon.ico', include_in_schema=False)
def favicon_ico():
    return FileResponse(
        ASSET_DIR / 'pitmark_favicon.ico',
        media_type='image/x-icon',
        headers={'Cache-Control': 'public, max-age=3600'},
    )


@router.get('/downloads/PRT-Setup-Latest.exe', include_in_schema=False)
def prt_windows_installer():
    return FileResponse(
        PRT_DOWNLOAD_DIR / 'PRT-Setup-Latest.exe',
        media_type='application/vnd.microsoft.portable-executable',
        filename='PRT-Setup-Latest.exe',
        headers={'Cache-Control': 'no-store'},
    )


@router.get('/downloads/latest.json', include_in_schema=False)
def prt_update_manifest():
    return FileResponse(
        PRT_DOWNLOAD_DIR / 'latest.json',
        media_type='application/json',
        headers={'Cache-Control': 'no-store'},
    )
