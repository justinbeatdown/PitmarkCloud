(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  let identities = [];

  async function api(url) {
    const r = await fetch(url, {credentials:'same-origin'});
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (!r.ok) throw Error((d && d.detail) || t || 'Request failed');
    return d;
  }

  function safeUrl(raw) {
    try {
      const u = new URL(raw, location.origin);
      return ['http:','https:','mailto:'].includes(u.protocol) ? u.href : '';
    } catch { return ''; }
  }

  function sanitizedEmailHtml(raw) {
    const doc = new DOMParser().parseFromString(String(raw || ''), 'text/html');
    doc.querySelectorAll('script,iframe,object,embed,form,input,button,textarea,select,meta,base,link').forEach(x => x.remove());
    doc.querySelectorAll('*').forEach(el => {
      [...el.attributes].forEach(attr => {
        const name = attr.name.toLowerCase();
        const value = attr.value || '';
        if (name.startsWith('on') || name === 'srcdoc') el.removeAttribute(attr.name);
        if (name === 'style') {
          const cleaned = value
            .replace(/url\s*\([^)]*\)/gi, '')
            .replace(/expression\s*\([^)]*\)/gi, '')
            .replace(/behavior\s*:[^;]+;?/gi, '');
          el.setAttribute('style', cleaned);
        }
      });
      if (el.tagName === 'A') {
        const href = safeUrl(el.getAttribute('href') || '');
        if (!href) el.removeAttribute('href');
        else {
          el.setAttribute('href', href);
          el.setAttribute('target', '_blank');
          el.setAttribute('rel', 'noopener noreferrer');
        }
      }
      if (el.tagName === 'IMG') {
        const src = safeUrl(el.getAttribute('src') || '');
        if (!src) el.remove();
        else {
          el.setAttribute('src', src);
          el.setAttribute('loading', 'lazy');
          el.setAttribute('referrerpolicy', 'no-referrer');
          el.style.maxWidth = '100%';
          el.style.height = 'auto';
        }
      }
    });
    doc.querySelectorAll('style').forEach(style => {
      style.textContent = String(style.textContent || '')
        .replace(/@import[^;]+;?/gi, '')
        .replace(/url\s*\([^)]*\)/gi, '');
    });
    const css = `<style>
      html,body{margin:0;padding:0;background:transparent;color:#efefef;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55}
      body{overflow-wrap:anywhere} a{color:#ff7a2f} img{max-width:100%;height:auto}
      table{max-width:100%!important} pre{white-space:pre-wrap}
    </style>`;
    return `<!doctype html><html><head><meta charset="utf-8">${css}</head><body>${doc.body.innerHTML}</body></html>`;
  }

  function htmlFrame(html) {
    const frame = document.createElement('iframe');
    frame.className = 'pm-mail-html-frame';
    frame.setAttribute('sandbox', 'allow-same-origin allow-popups allow-popups-to-escape-sandbox');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.srcdoc = sanitizedEmailHtml(html);
    frame.addEventListener('load', () => {
      try {
        const h = Math.max(120, Math.min(1400, frame.contentDocument?.documentElement?.scrollHeight || 180));
        frame.style.height = `${h + 12}px`;
      } catch {}
    });
    return frame;
  }

  function pitmarkAddress(value) {
    const raw = String(value || '').toLowerCase();
    return identities.some(x => raw.includes(String(x.address || '').toLowerCase())) ||
      raw.includes('@mail.pitmarkracing.com');
  }

  function replyPayload(message, all=false) {
    const cc = all
      ? [...(message.to || []), ...(message.cc || [])]
          .filter(x => !pitmarkAddress(x) && String(x).toLowerCase() !== String(message.from || '').toLowerCase())
      : [];
    return {
      to: [message.from],
      cc,
      subject: message.subject || '',
      reply_to_message_id: message.id
    };
  }

  function addActionButton(parent, label, cls, payload) {
    const b = document.createElement('button');
    b.className = cls;
    b.textContent = label;
    if (payload) b.dataset.mailReply = encodeURIComponent(JSON.stringify(payload));
    parent.appendChild(b);
    return b;
  }

  function forwardMessage(message, mobile=false) {
    const trigger = mobile ? $('mMailCompose') : $('mailComposeBtn');
    trigger?.click();
    setTimeout(() => {
      const subject = `Fwd: ${String(message.subject || '').replace(/^fwd?:\s*/i, '')}`;
      const body = `\n\n---------- Forwarded message ----------\nFrom: ${message.from || ''}\nDate: ${message.created_at ? new Date(message.created_at).toLocaleString() : ''}\nSubject: ${message.subject || ''}\n\n${message.text || ''}`;
      const subjectBox = mobile ? $('mMailSubject') : $('mailSubject');
      const bodyBox = mobile ? $('mMailBody') : $('mailBody');
      if (subjectBox) subjectBox.value = subject;
      if (bodyBox) bodyBox.value = body;
    }, 30);
  }

  function messageArticle(message, mobile=false) {
    const article = document.createElement('article');
    article.className = mobile ? 'm-item pm-mail-message' : `mail-thread-message ${message.direction || ''} pm-mail-message`;

    const meta = document.createElement('div');
    meta.className = mobile ? 'top pm-mail-meta' : 'mail-meta pm-mail-meta';
    meta.innerHTML = `<strong>${esc(message.direction === 'inbound' ? message.from : (message.to || []).join(', '))}</strong><span>${esc(message.created_at ? new Date(message.created_at).toLocaleString() : '')}</span>`;
    article.appendChild(meta);

    const recipientMeta = document.createElement('div');
    recipientMeta.className = 'pm-mail-recipient-meta';
    const to = (message.to || []).join(', ');
    const cc = (message.cc || []).join(', ');
    recipientMeta.innerHTML = `${to ? `<span>To: ${esc(to)}</span>` : ''}${cc ? `<span>CC: ${esc(cc)}</span>` : ''}`;
    if (recipientMeta.textContent.trim()) article.appendChild(recipientMeta);

    const body = document.createElement('div');
    body.className = mobile ? 'body mail-body pm-mail-body' : 'mail-body pm-mail-body';
    if (message.html) body.appendChild(htmlFrame(message.html));
    else {
      const pre = document.createElement('div');
      pre.className = 'pm-mail-plain';
      pre.textContent = message.text || '(no message body)';
      body.appendChild(pre);
    }
    article.appendChild(body);

    const actions = document.createElement('div');
    actions.className = 'pm-mail-actions';
    if (message.direction === 'inbound') {
      addActionButton(actions, 'Reply', mobile ? 'm-orange' : 'btn secondary mini', replyPayload(message, false));
      addActionButton(actions, 'Reply All', mobile ? 'm-ghost' : 'btn ghost mini', replyPayload(message, true));
    }
    const forward = addActionButton(actions, 'Forward', mobile ? 'm-ghost' : 'btn ghost mini');
    forward.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      forwardMessage(message, mobile);
    });
    article.appendChild(actions);
    return article;
  }

  async function renderThread(id, mobile=false) {
    const box = mobile ? $('mMailThread') : $('mailThread');
    if (!box || !id) return;
    try {
      const data = await api(`/api/control/email/threads/${id}`);
      const messages = data.messages || [];
      box.innerHTML = '';

      const head = document.createElement('div');
      head.className = mobile ? 'm-card pm-mail-thread-head' : 'record-row pm-mail-thread-head';
      head.innerHTML = `<strong>${esc(data.thread?.subject || 'Conversation')}</strong><span>${messages.length} message${messages.length === 1 ? '' : 's'}</span>`;
      box.appendChild(head);

      messages.forEach(message => box.appendChild(messageArticle(message, mobile)));
    } catch (err) {
      box.innerHTML = `<div class="${mobile ? 'm-card bad' : 'error-box'}">${esc(err.message)}</div>`;
    }
  }

  function installSearch(mobile=false) {
    const toolbar = mobile
      ? document.querySelector('[data-mview="email"] .m-actions, [data-mview="email"] .m-toolbar')
      : document.querySelector('[data-view-section="email"] .email-toolbar');
    const list = mobile ? $('mMailList') : $('mailList');
    if (!toolbar || !list || toolbar.querySelector('.pm-mail-search')) return;

    const input = document.createElement('input');
    input.className = mobile ? 'm-input pm-mail-search' : 'input pm-mail-search';
    input.type = 'search';
    input.placeholder = 'Search this mailbox…';
    input.autocomplete = 'off';
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      list.querySelectorAll(mobile ? '[data-mmail-thread], [data-mmail-draft]' : '[data-mail-thread], [data-mail-draft]').forEach(row => {
        row.hidden = !!q && !row.textContent.toLowerCase().includes(q);
      });
    });
    toolbar.insertBefore(input, toolbar.firstChild);
  }

  document.addEventListener('click', e => {
    const desktop = e.target.closest?.('[data-mail-thread]');
    if (desktop) {
      const id = Number(desktop.dataset.mailThread);
      setTimeout(() => renderThread(id, false), 80);
    }
    const mobile = e.target.closest?.('[data-mmail-thread]');
    if (mobile) {
      const id = Number(mobile.dataset.mmailThread);
      setTimeout(() => renderThread(id, true), 80);
    }
  }, true);

  document.addEventListener('DOMContentLoaded', async () => {
    try { identities = await api('/api/control/email/identities'); } catch {}
    setTimeout(() => {
      installSearch(false);
      installSearch(true);
    }, 150);
  });
})();