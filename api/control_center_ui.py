from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from services.control_auth import user_from_request

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent

AUTOFILL_GUARD = r"""
<script>
(() => {
  const protectedIds = [
    'bsubject', 'bnotes', 'btitle', 'bbody',
    'topic', 'ryName', 'oname', 'oorg', 'ocontact'
  ];

  function protectField(el) {
    if (!el) return;
    el.setAttribute('autocomplete', 'new-password');
    el.setAttribute('data-lpignore', 'true');
    el.setAttribute('data-1p-ignore', 'true');
    el.setAttribute('data-form-type', 'other');
    el.setAttribute('spellcheck', 'false');

    if (!el.dataset.pitmarkAutofillGuard) {
      el.dataset.pitmarkAutofillGuard = '1';
      el.dataset.pitmarkUserEdited = '0';

      const markEdited = () => {
        el.dataset.pitmarkUserEdited = '1';
      };
      el.addEventListener('input', markEdited, { once: true });
      el.addEventListener('keydown', markEdited, { once: true });
      el.addEventListener('paste', markEdited, { once: true });
    }
  }

  function clearBrowserAutofill() {
    for (const id of protectedIds) {
      const el = document.getElementById(id);
      if (!el) continue;
      protectField(el);

      if (el.dataset.pitmarkUserEdited === '1') continue;

      const value = String(el.value || '').trim().toLowerCase();
      if (value === 'justin' || value === 'admin') {
        el.value = '';
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    clearBrowserAutofill();

    // Browsers/password managers can inject values after DOMContentLoaded.
    [50, 150, 400, 900, 1600].forEach(delay => {
      window.setTimeout(clearBrowserAutofill, delay);
    });

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) window.setTimeout(clearBrowserAutofill, 50);
    });
  });
})();
</script>
"""



SOCIAL_PUBLISH_GUARD = r"""
<script>
(() => {
  let facebookReady = false;

  function publishButtons() {
    return Array.from(document.querySelectorAll('.queue-card')).map(card => {
      const button = Array.from(card.querySelectorAll('button')).find(
        b => b.textContent.trim().toLowerCase() === 'publish'
      );
      return { card, button };
    }).filter(x => x.button);
  }

  function updatePublishButtons() {
    for (const {card, button} of publishButtons()) {
      const header = (card.querySelector('.queue-card-top')?.textContent || '').toLowerCase();
      const status = (card.querySelector('.status-pill')?.textContent || '').trim().toLowerCase();
      const isFacebook = header.includes('facebook');
      const allowedState = status === 'approved' || status === 'scheduled';

      if (facebookReady && isFacebook && allowedState) {
        button.disabled = false;
        button.dataset.socialPublish = '1';
        button.title = 'Publish to Facebook';
      } else {
        button.disabled = true;
        delete button.dataset.socialPublish;
        if (isFacebook && !facebookReady) {
          button.title = 'Facebook publishing is not configured';
        }
      }
    }
  }

  async function refreshSocialStatus() {
    try {
      const response = await fetch('/api/control/social/status', {
        credentials: 'same-origin',
        cache: 'no-store'
      });
      if (!response.ok) {
        facebookReady = false;
      } else {
        const data = await response.json();
        facebookReady = Boolean(data?.facebook?.configured);
      }
    } catch (_) {
      facebookReady = false;
    }
    updatePublishButtons();
  }

  async function publishPost(button) {
    const card = button.closest('.queue-card');
    const postId = card?.dataset?.id;
    if (!postId) return;

    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'PUBLISHING…';

    try {
      const response = await fetch(`/api/control/social/posts/${postId}/publish`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'}
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);

      if (typeof showToast === 'function') {
        showToast('Published ✓', 'Facebook post is live.');
      }

      // Use the app's own queue renderer if present.
      if (typeof loadQueue === 'function') await loadQueue();
      if (typeof loadStatus === 'function') await loadStatus();
      await refreshSocialStatus();
    } catch (error) {
      button.textContent = original;
      button.disabled = false;
      if (typeof showToast === 'function') {
        showToast('Publish Failed', error.message, 'error');
      } else {
        alert(`Publish failed: ${error.message}`);
      }
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('button[data-social-publish="1"]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    publishPost(button);
  }, true);

  document.addEventListener('DOMContentLoaded', () => {
    refreshSocialStatus();

    const queue = document.getElementById('queueList');
    if (queue) {
      new MutationObserver(() => {
        updatePublishButtons();
      }).observe(queue, {childList: true, subtree: true});
    }

    window.setInterval(refreshSocialStatus, 30000);
  });
})();
</script>
"""


@router.get('/control', response_class=HTMLResponse, include_in_schema=False)
def control(request: Request):
    filename = 'control_center.html' if user_from_request(request) else 'control_login.html'
    html = (ASSET_DIR / filename).read_text(encoding='utf-8')
    if filename == 'control_center.html':
        html = html.replace('</body>', AUTOFILL_GUARD + SOCIAL_PUBLISH_GUARD + '\n</body>')
    return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


@router.get('/control.css', include_in_schema=False)
def control_css():
    return Response((ASSET_DIR / 'control_center.css').read_text(encoding='utf-8'), media_type='text/css')


@router.get('/control.js', include_in_schema=False)
def control_js():
    return Response((ASSET_DIR / 'control_center.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control-login.js', include_in_schema=False)
def control_login_js():
    return Response((ASSET_DIR / 'control_login.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control/mobile', response_class=HTMLResponse, include_in_schema=False)
def control_mobile(request: Request):
    filename = 'control_mobile.html' if user_from_request(request) else 'control_mobile_login.html'
    return HTMLResponse((ASSET_DIR / filename).read_text(encoding='utf-8'))


@router.get('/control-mobile.css', include_in_schema=False)
def control_mobile_css():
    return Response((ASSET_DIR / 'control_mobile.css').read_text(encoding='utf-8'), media_type='text/css')


@router.get('/control-mobile.js', include_in_schema=False)
def control_mobile_js():
    return Response((ASSET_DIR / 'control_mobile.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control-mobile-login.js', include_in_schema=False)
def control_mobile_login_js():
    return Response((ASSET_DIR / 'control_mobile_login.js').read_text(encoding='utf-8'), media_type='application/javascript')


@router.get('/control.webmanifest', include_in_schema=False)
def control_manifest():
    return Response((ASSET_DIR / 'control.webmanifest').read_text(encoding='utf-8'), media_type='application/manifest+json')


@router.get('/control-sw.js', include_in_schema=False)
def control_sw():
    return Response((ASSET_DIR / 'control_sw.js').read_text(encoding='utf-8'), media_type='application/javascript', headers={'Service-Worker-Allowed':'/control/'})


@router.get('/control-logo-wide.png', include_in_schema=False)
def control_logo_wide():
    return FileResponse(ASSET_DIR / 'pitmark_logo_wide.png', media_type='image/png')


@router.get('/control-logo-badge.png', include_in_schema=False)
def control_logo_badge():
    return FileResponse(ASSET_DIR / 'pitmark_badge.png', media_type='image/png')


@router.get('/control-favicon.png', include_in_schema=False)
def control_favicon():
    return FileResponse(ASSET_DIR / 'pitmark_favicon.png', media_type='image/png', headers={'Cache-Control':'public, max-age=3600'})


@router.get('/favicon.ico', include_in_schema=False)
def favicon_ico():
    return FileResponse(ASSET_DIR / 'pitmark_favicon.ico', media_type='image/x-icon', headers={'Cache-Control':'public, max-age=3600'})
