(() => {
  'use strict';

  const state = {
    mobile: false,
    folder: 'inbox',
    identities: [],
    preferences: {},
    threads: [],
    activeThreadId: null,
    activeDraftId: null,
    replyToMessageId: null,
    quote: null,
    attachments: [],
    composerDirty: false,
    autosaveTimer: null,
  };

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }[c]));

  async function api(url, opt = {}) {
    const headers = {...(opt.headers || {})};
    if (!(opt.body instanceof FormData) && opt.body != null) headers['Content-Type'] = 'application/json';
    const r = await fetch(url, {credentials:'same-origin', ...opt, headers});
    const t = await r.text();
    let d;
    try { d = JSON.parse(t); } catch { d = t; }
    if (r.status === 401) {
      location.href = '/control';
      throw new Error('Session expired.');
    }
    if (!r.ok) throw new Error((d && d.detail) || t || `HTTP ${r.status}`);
    return d;
  }

  function parseList(value) {
    return String(value || '').split(',').map(x => x.trim()).filter(Boolean);
  }

  function dateLabel(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    return sameDay
      ? d.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'})
      : d.toLocaleDateString([], {month:'short', day:'numeric'});
  }

  function fullDate(value) {
    if (!value) return '';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString();
  }

  function safeUrl(raw) {
    try {
      const u = new URL(raw, location.origin);
      return ['http:','https:','mailto:'].includes(u.protocol) ? u.href : '';
    } catch { return ''; }
  }

  function sanitizedEmailHtml(raw) {
    const doc = new DOMParser().parseFromString(String(raw || ''), 'text/html');
    doc.querySelectorAll('script,iframe,object,embed,form,input,button,textarea,select,meta,base').forEach(x => x.remove());
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
    doc.documentElement.removeAttribute('style');
    const css = `<style>
      html{margin:0;padding:0;background:#fff;color-scheme:light;overflow-x:hidden}
      body{margin:0;padding:18px;box-sizing:border-box;max-width:100%;overflow-wrap:anywhere;line-height:1.5}
      body:not([style*="background"]){background:#fff}
      body:not([style*="color"]){color:#202124}
      body:not([style*="font-family"]){font-family:Arial,Helvetica,sans-serif}
      a{color:#0b57d0}
      img{max-width:100%!important;height:auto!important}
      table{max-width:100%!important}
      td,th{max-width:100%}
      pre{white-space:pre-wrap}
    </style>`;
    return `<!doctype html><html><head><meta charset="utf-8">${css}</head><body>${doc.body.innerHTML}</body></html>`;
  }

  function emailHtmlHasContent(raw) {
    const source = String(raw || '').trim();
    if (!source) return false;
    const doc = new DOMParser().parseFromString(source, 'text/html');
    doc.querySelectorAll('style,script,meta,link,title').forEach(x => x.remove());
    const text = String(doc.body?.innerText || doc.body?.textContent || '').replace(/\s+/g, ' ').trim();
    if (text) return true;
    return !!doc.body?.querySelector('img[src],svg,video,audio,hr,blockquote');
  }

  function makeEmailFrame(html) {
    const frame = document.createElement('iframe');
    frame.className = 'pm19-email-frame';
    frame.sandbox = 'allow-same-origin allow-popups allow-popups-to-escape-sandbox';
    frame.referrerPolicy = 'no-referrer';
    frame.srcdoc = sanitizedEmailHtml(html);
    frame.scrolling = 'auto';
    frame.addEventListener('load', () => {
      try {
        const doc = frame.contentDocument;
        if (doc?.documentElement) {
          doc.documentElement.style.overflowX = 'hidden';
          doc.documentElement.style.overflowY = 'auto';
        }
        const h = Math.max(130, Math.min(900, doc?.documentElement?.scrollHeight || 180));
        frame.style.height = `${h + 4}px`;
      } catch {}
    });
    return frame;
  }

  function messagePlainText(message) {
    const raw = String(message?.text || '').trim();
    const htmlish = /<\/?[a-z][\s\S]*>/i.test(raw);
    if (raw && !htmlish) return raw;
    const source = String(message?.html || raw || '');
    if (!source) return '';
    const doc = new DOMParser().parseFromString(source, 'text/html');
    return String(doc.body?.innerText || doc.body?.textContent || '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function quoteFromMessage(message, kind='reply') {
    return {
      kind,
      from: message?.from || '',
      date: fullDate(message?.created_at),
      subject: message?.subject || '',
      text: messagePlainText(message),
    };
  }

  function quoteHtmlForPayload(quote) {
    if (!quote) return '';
    const title = quote.kind === 'forward' ? 'Forwarded message' : 'Quoted message';
    return `<div class="pm19-sent-quote" style="margin-top:18px;padding-left:12px;border-left:2px solid #d0d0d0;color:#666">
      <div><strong>${esc(title)}</strong></div>
      ${quote.from ? `<div>From: ${esc(quote.from)}</div>` : ''}
      ${quote.date ? `<div>Date: ${esc(quote.date)}</div>` : ''}
      ${quote.subject ? `<div>Subject: ${esc(quote.subject)}</div>` : ''}
      <br><div style="white-space:pre-wrap">${esc(quote.text || '')}</div>
    </div>`;
  }

  function quoteTextForPayload(quote) {
    if (!quote) return '';
    const title = quote.kind === 'forward' ? '---------- Forwarded message ----------' : '---------- Quoted message ----------';
    return `\n\n${title}\n${quote.from ? `From: ${quote.from}\n` : ''}${quote.date ? `Date: ${quote.date}\n` : ''}${quote.subject ? `Subject: ${quote.subject}\n` : ''}\n${quote.text || ''}`;
  }

  function renderQuoteTray() {
    const tray = $('pm19QuoteTray');
    if (!tray) return;
    if (!state.quote) {
      tray.innerHTML = '';
      tray.hidden = true;
      return;
    }
    tray.hidden = false;
    tray.innerHTML = `<details>
      <summary><span>•••</span> ${state.quote.kind === 'forward' ? 'Forwarded message' : 'Quoted message'} <button type="button" id="pm19RemoveQuote">Remove</button></summary>
      <div class="pm19-quote-preview">${esc(state.quote.text || '(empty quoted message)')}</div>
    </details>`;
    $('pm19RemoveQuote')?.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      state.quote = null;
      renderQuoteTray();
      markDirty();
    });
  }

  function installDesktopNav() {
    const nav = $('nav');
    if (!nav || nav.querySelector('[data-view="email"]')) return;
    const b = document.createElement('button');
    b.dataset.view = 'email';
    b.innerHTML = '<span class="ico">✉</span><span>Mail<small>Inbox & Compose</small></span>';
    const blog = nav.querySelector('[data-view="blog"]');
    nav.insertBefore(b, blog || null);
    b.addEventListener('click', () => {
      if (window.setView) window.setView('email');
      loadMailbox();
    });
  }

  function desktopMailMarkup() {
    return `
      <section class="view pm19-mail-view" data-view-section="email">
        <div class="pm19-page-head">
          <div>
            <span class="pm19-kicker">PITMARK MAIL</span>
            <h1>Email without leaving Control Center.</h1>
            <p>Full conversations, rich compose, attachments, signatures and every Pitmark identity.</p>
          </div>
          <button class="pm19-primary" data-pm19-compose>Compose</button>
        </div>
        <div class="pm19-mail-app">
          <aside class="pm19-mail-nav">
            <button class="pm19-compose-main" data-pm19-compose><span>＋</span> Compose</button>
            <button class="active" data-pm19-folder="inbox"><span>Inbox</span><b id="pm19InboxCount"></b></button>
            <button data-pm19-folder="sent"><span>Sent</span></button>
            <button data-pm19-folder="drafts"><span>Drafts</span></button>
            <div class="pm19-mail-identities" id="pm19IdentitySummary"></div>
          </aside>
          <section class="pm19-mail-list-pane">
            <div class="pm19-mail-searchbar">
              <span>⌕</span>
              <input id="pm19MailSearch" name="pm19_mail_search_${Date.now()}" type="search"
                readonly autocomplete="new-password" placeholder="Search this mailbox">
              <button id="pm19MailRefresh" title="Refresh">↻</button>
            </div>
            <div id="pm19MailList" class="pm19-mail-list"><div class="pm19-loading">Loading mail…</div></div>
          </section>
          <section class="pm19-mail-thread-pane" id="pm19MailThread">
            <div class="pm19-thread-empty">
              <span>✉</span><strong>Select a conversation</strong>
              <p>Messages open here without squeezing the rest of the inbox.</p>
            </div>
          </section>
        </div>
      </section>`;
  }

  function mobileMailMarkup() {
    return `
      <div class="pm19-mobile-mail-head">
        <div><span class="pm19-kicker">PITMARK MAIL</span><h1>Mail</h1></div>
        <button class="pm19-primary" data-pm19-compose>Compose</button>
      </div>
      <div class="pm19-mobile-folders">
        <button class="active" data-pm19-folder="inbox">Inbox</button>
        <button data-pm19-folder="sent">Sent</button>
        <button data-pm19-folder="drafts">Drafts</button>
      </div>
      <div class="pm19-mail-searchbar mobile">
        <span>⌕</span>
        <input id="pm19MailSearch" name="pm19_mobile_search_${Date.now()}" type="search"
          readonly autocomplete="new-password" placeholder="Search mail">
        <button id="pm19MailRefresh">↻</button>
      </div>
      <div id="pm19MailList" class="pm19-mail-list mobile"><div class="pm19-loading">Loading mail…</div></div>
      <div id="pm19MailThread" class="pm19-mobile-thread hidden"></div>`;
  }

  function installMailUI() {
    const desktopContent = document.querySelector('.content');
    const mobileView = document.querySelector('[data-mview="email"]');
    state.mobile = !!mobileView && !desktopContent;

    if (desktopContent) {
      installDesktopNav();
      document.querySelector('[data-view-section="email"]')?.remove();
      const anchor = document.querySelector('[data-view-section="blog"]');
      const wrapper = document.createElement('div');
      wrapper.innerHTML = desktopMailMarkup().trim();
      desktopContent.insertBefore(wrapper.firstElementChild, anchor || null);
    } else if (mobileView) {
      mobileView.innerHTML = mobileMailMarkup();
    }

    wireMailUI();
  }

  function unlockSearch() {
    const input = $('pm19MailSearch');
    if (!input) return;
    const unlock = () => {
      input.readOnly = false;
      if (!input.dataset.pm19UserTouched) input.value = '';
    };
    input.addEventListener('pointerdown', unlock, {once:true, capture:true});
    input.addEventListener('focus', unlock, {once:true, capture:true});
    input.addEventListener('input', () => {
      input.dataset.pm19UserTouched = '1';
      filterMailbox();
    });
    // Browser autofill cannot own this field before the user intentionally opens it.
    input.value = '';
  }

  function wireMailUI() {
    unlockSearch();
    document.querySelectorAll('[data-pm19-compose]').forEach(b => b.addEventListener('click', () => openComposer()));
    document.querySelectorAll('[data-pm19-folder]').forEach(b => b.addEventListener('click', () => {
      state.folder = b.dataset.pm19Folder;
      document.querySelectorAll('[data-pm19-folder]').forEach(x => x.classList.toggle('active', x === b));
      state.activeThreadId = null;
      loadMailbox();
    }));
    $('pm19MailRefresh')?.addEventListener('click', loadMailbox);
    $('pm19MailList')?.addEventListener('click', e => {
      const row = e.target.closest('[data-pm19-thread]');
      if (row) openThread(Number(row.dataset.pm19Thread));
      const draft = e.target.closest('[data-pm19-draft]');
      if (draft) {
        const x = JSON.parse(decodeURIComponent(draft.dataset.pm19Draft));
        openComposer({draft:x});
      }
    });
  }

  async function loadBootstrap() {
    try {
      const [identities, preferences] = await Promise.all([
        api('/api/control/email/identities'),
        api('/api/control/email/preferences')
      ]);
      state.identities = identities || [];
      state.preferences = preferences || {};
      const summary = $('pm19IdentitySummary');
      if (summary) {
        summary.innerHTML = `<span>Sending as</span>${state.identities.map(x => `<small>${esc(x.label)}</small>`).join('')}`;
      }
    } catch (err) {
      console.warn('Pitmark Mail bootstrap:', err);
    }
  }

  async function loadMailbox() {
    const list = $('pm19MailList');
    if (!list) return;
    list.innerHTML = '<div class="pm19-loading">Loading mail…</div>';
    try {
      if (!state.identities.length) await loadBootstrap();
      const rows = await api(`/api/control/email/threads?folder=${encodeURIComponent(state.folder)}&limit=150`);
      state.threads = rows || [];
      renderMailbox();
      if (state.folder === 'inbox') {
        const unread = state.threads.reduce((n, x) => n + Number(x.thread?.unread_count || 0), 0);
        const count = $('pm19InboxCount');
        if (count) count.textContent = unread ? String(unread) : '';
      }
    } catch (err) {
      list.innerHTML = `<div class="pm19-error">${esc(err.message)}</div>`;
    }
  }

  function rowPreview(x) {
    const text = String(x.text || '').replace(/\s+/g, ' ').trim();
    if (text) return text.slice(0, 145);
    if (x.html) {
      const d = document.createElement('div');
      d.innerHTML = x.html;
      return String(d.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 145);
    }
    return 'No message preview';
  }

  function renderMailbox() {
    const list = $('pm19MailList');
    if (!list) return;
    if (!state.threads.length) {
      list.innerHTML = `<div class="pm19-empty-mail"><strong>Nothing here.</strong><span>${esc(state.folder)} is clear.</span></div>`;
      return;
    }
    list.innerHTML = state.threads.map(x => {
      const t = x.thread || {};
      const draft = state.folder === 'drafts';
      const who = state.folder === 'inbox' ? x.from : (x.to || []).join(', ');
      const unread = state.folder === 'inbox' && Number(t.unread_count || 0) > 0;
      const attr = draft
        ? `data-pm19-draft="${encodeURIComponent(JSON.stringify(x))}"`
        : `data-pm19-thread="${x.thread_id}"`;
      return `<button class="pm19-mail-row ${unread ? 'unread' : ''} ${state.activeThreadId === x.thread_id ? 'selected' : ''}" ${attr}>
        <div class="pm19-row-top"><strong>${esc(who || 'Unknown')}</strong><time>${esc(dateLabel(x.created_at))}</time></div>
        <div class="pm19-row-subject">${esc(x.subject || '(no subject)')}</div>
        <div class="pm19-row-preview">${esc(rowPreview(x))}</div>
        ${x.shield ? `<span class="pm19-shield ${esc(String(x.shield.classification || '').toLowerCase())}">Shield ${esc(x.shield.classification || '')}</span>` : ''}
      </button>`;
    }).join('');
    filterMailbox();
  }

  function filterMailbox() {
    const q = String($('pm19MailSearch')?.value || '').trim().toLowerCase();
    document.querySelectorAll('.pm19-mail-row').forEach(row => {
      row.hidden = !!q && !row.textContent.toLowerCase().includes(q);
    });
  }

  async function openThread(id) {
    state.activeThreadId = id;
    renderMailbox();
    const box = $('pm19MailThread');
    if (!box) return;
    box.classList.remove('hidden');
    box.innerHTML = '<div class="pm19-loading">Opening conversation…</div>';
    try {
      const data = await api(`/api/control/email/threads/${id}`);
      const messages = data.messages || [];
      box.innerHTML = `
        <div class="pm19-thread-head">
          <button class="pm19-back ${state.mobile ? '' : 'desktop-hide'}" id="pm19ThreadBack">←</button>
          <div><span>${messages.length} message${messages.length === 1 ? '' : 's'}</span><h2>${esc(data.thread?.subject || 'Conversation')}</h2></div>
          <div class="pm19-thread-tools">
            <button id="pm19ThreadSpam">Mark spam</button>
            <button id="pm19ThreadDelete">Delete</button>
          </div>
        </div>
        <div id="pm19ThreadMessages" class="pm19-thread-messages"></div>`;
      $('pm19ThreadBack')?.addEventListener('click', () => box.classList.add('hidden'));
      $('pm19ThreadDelete')?.addEventListener('click', () => deleteThread(id));
      $('pm19ThreadSpam')?.addEventListener('click', () => markSpam(id));
      const messagesBox = $('pm19ThreadMessages');
      for (let i = 0; i < messages.length; i++) {
        messagesBox.appendChild(await renderMessage(messages[i], messages, i === messages.length - 1));
      }
      await loadMailbox();
    } catch (err) {
      box.innerHTML = `<div class="pm19-error">${esc(err.message)}</div>`;
    }
  }

  async function renderMessage(m, allMessages, expanded=true) {
    const article = document.createElement('article');
    article.className = `pm19-message ${m.direction === 'outbound' ? 'outbound' : 'inbound'} ${expanded ? 'expanded' : 'collapsed'}`;

    const top = document.createElement('div');
    top.className = 'pm19-message-head';
    const from = m.direction === 'inbound' ? m.from : (m.to || []).join(', ');
    top.innerHTML = `<div><strong>${esc(from || 'Unknown')}</strong>
      <span>${esc(m.direction === 'inbound' ? `to ${(m.to || []).join(', ')}` : `from ${m.from || ''}`)}</span></div>
      <time>${esc(fullDate(m.created_at))}</time>`;
    article.appendChild(top);
    top.title = expanded ? '' : 'Click to expand message';
    top.addEventListener('click', () => {
      const isCollapsed = article.classList.toggle('collapsed');
      article.classList.toggle('expanded', !isCollapsed);
      top.title = isCollapsed ? 'Click to expand message' : '';
    });

    if (m.shield) {
      const shield = document.createElement('div');
      shield.className = `pm19-shield-banner ${esc(String(m.shield.classification || '').toLowerCase())}`;
      shield.innerHTML = `<strong>◈ PITMARK SHIELD</strong><span>${esc(m.shield.classification || '')} · ${Math.round(Number(m.shield.confidence || 0) * 100)}%</span>`;
      article.appendChild(shield);
    }

    const body = document.createElement('div');
    body.className = 'pm19-message-body';
    const hasHtml = emailHtmlHasContent(m.html);
    const plainText = String(m.text || '').trim();
    if (hasHtml) {
      body.appendChild(makeEmailFrame(m.html));
    } else if (plainText) {
      const plain = document.createElement('div');
      plain.className = 'pm19-plain-email';
      plain.textContent = plainText;
      body.appendChild(plain);
    } else {
      const empty = document.createElement('div');
      empty.className = 'pm195-empty-email';
      empty.innerHTML = '<strong>No message body</strong><span>This email arrived without readable body content.</span>';
      body.appendChild(empty);
    }
    article.appendChild(body);

    const attachments = document.createElement('div');
    attachments.className = 'pm19-message-attachments';
    article.appendChild(attachments);
    loadMessageAttachments(m.id, attachments);

    const actions = document.createElement('div');
    actions.className = 'pm19-message-actions';
    if (m.direction === 'inbound') {
      actions.innerHTML += '<button data-action="reply">Reply</button><button data-action="replyall">Reply all</button>';
    }
    actions.innerHTML += '<button data-action="forward">Forward</button>';
    actions.addEventListener('click', e => {
      const action = e.target.closest('button')?.dataset.action;
      if (!action) return;
      if (action === 'reply') openReply(m, false);
      if (action === 'replyall') openReply(m, true);
      if (action === 'forward') openForward(m);
    });
    article.appendChild(actions);
    return article;
  }

  async function loadMessageAttachments(messageId, container) {
    try {
      const rows = await api(`/api/control/email/messages/${messageId}/attachments`);
      if (!rows?.length) return;
      container.innerHTML = rows.map(x => {
        const url = safeUrl(x.download_url || x.url || '');
        const tag = url ? 'a' : 'span';
        return `<${tag} class="pm19-attachment-chip" ${url ? `href="${esc(url)}" target="_blank" rel="noopener"` : ''}>
          <b>▱</b><span>${esc(x.filename || x.name || 'attachment')}</span>
          ${x.size ? `<small>${Math.ceil(Number(x.size)/1024)} KB</small>` : ''}
        </${tag}>`;
      }).join('');
    } catch {}
  }

  function confirmDialog({title='Confirm action', message='', confirmLabel='Confirm', danger=false} = {}) {
    return new Promise(resolve => {
      document.getElementById('pm195ConfirmOverlay')?.remove();
      const overlay = document.createElement('div');
      overlay.id = 'pm195ConfirmOverlay';
      overlay.className = 'pm195-confirm-overlay';
      overlay.innerHTML = `<section class="pm195-confirm-card">
        <div class="pm195-confirm-icon ${danger ? 'danger' : ''}">${danger ? '!' : '?'}</div>
        <h2>${esc(title)}</h2>
        <p>${esc(message)}</p>
        <div><button type="button" data-confirm-cancel>Cancel</button><button type="button" class="${danger ? 'danger' : 'primary'}" data-confirm-ok>${esc(confirmLabel)}</button></div>
      </section>`;
      const finish = value => { overlay.remove(); resolve(value); };
      overlay.querySelector('[data-confirm-cancel]').addEventListener('click', () => finish(false));
      overlay.querySelector('[data-confirm-ok]').addEventListener('click', () => finish(true));
      overlay.addEventListener('click', e => { if (e.target === overlay) finish(false); });
      const key = e => {
        if (e.key === 'Escape') { document.removeEventListener('keydown', key); finish(false); }
        if (e.key === 'Enter') { document.removeEventListener('keydown', key); finish(true); }
      };
      document.addEventListener('keydown', key);
      document.body.appendChild(overlay);
      overlay.querySelector('[data-confirm-cancel]')?.focus();
    });
  }

  async function deleteThread(id) {
    const approved = await confirmDialog({
      title:'Delete conversation?',
      message:'This removes the entire Pitmark Mail conversation from the live mailbox. Shield audit history is kept separately.',
      confirmLabel:'Delete conversation',
      danger:true
    });
    if (!approved) return;
    await api(`/api/control/email/threads/${id}`, {method:'DELETE'});
    state.activeThreadId = null;
    const box = $('pm19MailThread');
    if (box) box.innerHTML = '<div class="pm19-thread-empty"><strong>Conversation deleted.</strong></div>';
    await loadMailbox();
  }

  async function markSpam(id) {
    await api(`/api/control/email/threads/${id}/spam`, {method:'POST'});
    await openThread(id);
  }

  function identityKeyFromAddress(value) {
    const raw = String(value || '').toLowerCase();
    return state.identities.find(x => raw.includes(String(x.address || '').toLowerCase()))?.key || '';
  }

  function pitmarkAddress(value) {
    const raw = String(value || '').toLowerCase();
    return state.identities.some(x => raw.includes(String(x.address || '').toLowerCase())) || raw.includes('@pitmarkracing.com');
  }

  function openReply(m, replyAll) {
    const cc = replyAll
      ? [...(m.to || []), ...(m.cc || [])].filter(x => !pitmarkAddress(x) && String(x).toLowerCase() !== String(m.from || '').toLowerCase())
      : [];
    openComposer({
      to:[m.from],
      cc,
      subject:/^re:/i.test(m.subject || '') ? m.subject : `Re: ${m.subject || ''}`,
      replyToMessageId:m.id,
      inheritedIdentity:'',
      quoteObj:quoteFromMessage(m, 'reply')
    });
  }

  function openForward(m) {
    openComposer({
      subject:`Fwd: ${String(m.subject || '').replace(/^fwd?:\s*/i, '')}`,
      quoteObj:quoteFromMessage(m, 'forward')
    });
  }

  function composerMarkup() {
    const identityOptions = state.identities.map(x => `<option value="${esc(x.key)}" ${x.default ? 'selected' : ''}>${esc(x.label)} · ${esc(x.address)}</option>`).join('');
    return `<div class="pm19-compose-overlay" id="pm19ComposeOverlay">
      <section class="pm19-compose-window">
        <header>
          <div><span class="pm19-kicker">PITMARK MAIL</span><strong id="pm19ComposeTitle">New message</strong></div>
          <button id="pm19ComposeClose">×</button>
        </header>
        <div class="pm19-compose-fields">
          <label><span>From</span><select id="pm19From">${identityOptions}</select></label>
          <label><span>To</span><input id="pm19To" autocomplete="new-password"></label>
          <div class="pm19-ccrow">
            <label><span>CC</span><input id="pm19Cc" autocomplete="off"></label>
            <label><span>BCC</span><input id="pm19Bcc" autocomplete="off"></label>
          </div>
          <label><span>Subject</span><input id="pm19Subject" autocomplete="off"></label>
        </div>
        <div class="pm19-editor-toolbar" id="pm19Toolbar">
          <button data-cmd="bold"><b>B</b></button>
          <button data-cmd="italic"><i>I</i></button>
          <button data-cmd="underline"><u>U</u></button>
          <button data-cmd="insertUnorderedList">• List</button>
          <button data-cmd="insertOrderedList">1. List</button>
          <button data-cmd="createLink">Link</button>
          <span></span>
          <select id="pm19MacroSelect" title="Insert a Pitmark quick reply">
            <option value="">Quick reply…</option>
            <option value="order_lookup">Order · Look up order</option>
            <option value="order_delay">Order · Production / shipping</option>
            <option value="return_exchange">Order · Return / exchange</option>
            <option value="partnership_received">Partnership · Application received</option>
            <option value="prt_support">PRT · Support information</option>
            <option value="need_info">General · Need more information</option>
            <option value="thanks_close">General · Thanks / resolved</option>
          </select>
          <button id="pm19SignatureBtn">Signature</button>
        </div>
        <div id="pm19Editor" class="pm19-rich-editor" contenteditable="true" spellcheck="true" data-placeholder="Write your message…"></div>
        <div id="pm19QuoteTray" class="pm19-quote-tray" hidden></div>
        <div class="pm19-attach-row">
          <label class="pm19-attach-button">📎 Attach files<input id="pm19Files" type="file" multiple hidden></label>
          <span>Up to 8 files / 12 MB total</span>
        </div>
        <div id="pm19AttachmentList" class="pm19-compose-attachments"></div>
        <footer>
          <div><button class="pm19-primary" id="pm19Send">Send</button><button id="pm19SaveDraft">Save draft</button></div>
          <span id="pm19ComposeStatus">Draft autosave ready</span>
          <button class="pm19-trash" id="pm19Discard">Discard</button>
        </footer>
      </section>
    </div>`;
  }

  async function openComposer(prefill = {}) {
    if (!state.identities.length) await loadBootstrap();
    $('pm19ComposeOverlay')?.remove();
    document.body.insertAdjacentHTML('beforeend', composerMarkup());
    state.attachments = [];
    state.activeDraftId = prefill.draft?.id || null;
    state.replyToMessageId = prefill.replyToMessageId || null;
    state.quote = prefill.quoteObj || null;
    state.composerDirty = false;

    $('pm19To').value = (prefill.draft?.to || prefill.to || []).join(', ');
    $('pm19Cc').value = (prefill.draft?.cc || prefill.cc || []).join(', ');
    $('pm19Bcc').value = (prefill.draft?.bcc || prefill.bcc || []).join(', ');
    $('pm19Subject').value = prefill.draft?.subject || prefill.subject || '';

    const identityKey = prefill.inheritedIdentity === ''
      ? ''
      : (identityKeyFromAddress(prefill.draft?.from) || state.identities.find(x => x.default)?.key || 'mail');
    if (identityKey && $('pm19From')) $('pm19From').value = identityKey;

    const editor = $('pm19Editor');
    if (prefill.draft?.html) editor.innerHTML = prefill.draft.html;
    else if (prefill.draft?.text) editor.textContent = prefill.draft.text;
    else {
      editor.innerHTML = '<div><br></div>';
      await applySignature();
    }
    renderQuoteTray();

    if (prefill.draft?.id) {
      try {
        state.attachments = await api(`/api/control/email/drafts/${prefill.draft.id}/attachments`);
        renderComposeAttachments();
      } catch {}
      $('pm19ComposeTitle').textContent = 'Edit draft';
    } else if (state.replyToMessageId) {
      $('pm19ComposeTitle').textContent = 'Reply';
    }

    wireComposer();
    editor.focus();
    try {
      const range = document.createRange();
      const sel = window.getSelection();
      range.selectNodeContents(editor);
      range.collapse(true);
      sel.removeAllRanges();
      sel.addRange(range);
    } catch {}
    scheduleAutosave();
  }

  const MAIL_MACROS = {
    order_lookup: `<p>Hi there,</p><p>Thanks for reaching out to Pitmark Racing Co. I’d be happy to look into this for you. Please reply with your order number and the email address used at checkout.</p><p>Once we have that, we can check the order details for you.</p>`,
    order_delay: `<p>Hi there,</p><p>Thanks for checking in. Pitmark products are produced through our fulfillment workflow, so production and carrier scans can take a little time to update.</p><p>If you send us your order number, we’ll check the current status and let you know what we can see.</p>`,
    return_exchange: `<p>Hi there,</p><p>Thanks for reaching out. Please send us your order number, the item involved, and a quick description of what you need changed or resolved.</p><p>We’ll review the order and walk you through the best next step.</p>`,
    partnership_received: `<p>Hi there,</p><p>Thanks for your interest in working with Pitmark Racing Co. We received your partnership message and appreciate you reaching out.</p><p>We’re reviewing the details and will follow up if we need anything else or when we’re ready for the next step.</p>`,
    prt_support: `<p>Hi there,</p><p>Thanks for contacting Pitmark Racing Tools support. To help us narrow this down, please send the PRT version you’re running, what you were doing when the issue occurred, and a screenshot or diagnostic log if one is available.</p><p>We’ll take it from there.</p>`,
    need_info: `<p>Hi there,</p><p>Thanks for reaching out. We can help — could you send us a little more information about what you’re trying to do or what happened?</p><p>The more detail you can provide, the faster we can point you in the right direction.</p>`,
    thanks_close: `<p>Thanks for the update. We’re glad we could help.</p><p>If anything else comes up, just reply here and we’ll pick the conversation back up.</p>`
  };

  function insertMailMacro(key) {
    const html = MAIL_MACROS[key];
    const editor = $('pm19Editor');
    if (!html || !editor) return;
    const sig = editor.querySelector('[data-pm19-signature]');
    const blank = editor.children.length === 1 && !String(editor.innerText || '').trim();
    if (blank) editor.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'pm195-macro-body';
    wrap.innerHTML = html;
    if (sig && sig.parentNode === editor) editor.insertBefore(wrap, sig);
    else editor.appendChild(wrap);
    markDirty();
    editor.focus();
  }

  function wireComposer() {
    $('pm19ComposeClose').addEventListener('click', closeComposer);
    $('pm19ComposeOverlay').addEventListener('click', e => {
      if (e.target.id === 'pm19ComposeOverlay') closeComposer();
    });
    ['pm19To','pm19Cc','pm19Bcc','pm19Subject'].forEach(id => $(id)?.addEventListener('input', markDirty));
    $('pm19Editor').addEventListener('input', markDirty);
    $('pm19From').addEventListener('change', async () => {
      await applySignature();
      markDirty();
    });
    $('pm19Toolbar').addEventListener('click', e => {
      const b = e.target.closest('[data-cmd]');
      if (!b) return;
      e.preventDefault();
      $('pm19Editor').focus();
      const cmd = b.dataset.cmd;
      if (cmd === 'createLink') {
        const href = prompt('Link URL');
        if (href && safeUrl(href)) document.execCommand(cmd, false, href);
      } else {
        document.execCommand(cmd, false, null);
      }
      markDirty();
    });
    $('pm19MacroSelect')?.addEventListener('change', e => {
      const key = e.target.value;
      if (key) insertMailMacro(key);
      e.target.value = '';
    });
    $('pm19SignatureBtn').addEventListener('click', openSignatureEditor);
    $('pm19Files').addEventListener('change', addFiles);
    $('pm19Send').addEventListener('click', sendCompose);
    $('pm19SaveDraft').addEventListener('click', () => saveComposeDraft(false));
    $('pm19Discard').addEventListener('click', discardCompose);
  }

  function markDirty() {
    state.composerDirty = true;
    $('pm19ComposeStatus').textContent = 'Unsaved changes';
  }

  function closeComposer() {
    clearTimeout(state.autosaveTimer);
    $('pm19ComposeOverlay')?.remove();
  }

  function plainTextFromEditor() {
    return String($('pm19Editor')?.innerText || '').trim();
  }

  async function applySignature() {
    const editor = $('pm19Editor');
    if (!editor) return;
    editor.querySelector('[data-pm19-signature]')?.remove();
    const key = $('pm19From')?.value || state.identities.find(x => x.default)?.key || 'mail';
    const pref = state.preferences[key] || {};
    if (!pref.signature_enabled || !pref.signature_html) return;
    const wrap = document.createElement('div');
    wrap.dataset.pm19Signature = '1';
    wrap.className = 'pm19-signature';
    wrap.innerHTML = `<br><div>—</div>${pref.signature_html}`;
    editor.appendChild(wrap);
  }

  function openSignatureEditor() {
    const key = $('pm19From')?.value || 'mail';
    const pref = state.preferences[key] || {signature_html:'', signature_enabled:true};
    const overlay = document.createElement('div');
    overlay.className = 'pm19-mini-overlay';
    overlay.innerHTML = `<section class="pm19-signature-modal">
      <header><strong>Signature · ${esc(state.identities.find(x=>x.key===key)?.label || key)}</strong><button>×</button></header>
      <label class="pm19-check"><input type="checkbox" id="pm19SigEnabled" ${pref.signature_enabled !== false ? 'checked' : ''}> Use this signature</label>
      <div id="pm19SigEditor" class="pm19-signature-editor" contenteditable="true">${pref.signature_html || ''}</div>
      <footer><button id="pm19SigCancel">Cancel</button><button class="pm19-primary" id="pm19SigSave">Save signature</button></footer>
    </section>`;
    document.body.appendChild(overlay);
    overlay.querySelector('header button').onclick = () => overlay.remove();
    $('pm19SigCancel').onclick = () => overlay.remove();
    $('pm19SigSave').onclick = async () => {
      const payload = {
        signature_html:$('pm19SigEditor').innerHTML,
        signature_enabled:$('pm19SigEnabled').checked
      };
      const saved = await api(`/api/control/email/preferences/${encodeURIComponent(key)}`, {method:'PUT', body:JSON.stringify(payload)});
      state.preferences[key] = saved;
      overlay.remove();
      await applySignature();
      markDirty();
    };
  }

  async function addFiles(e) {
    const files = [...(e.target.files || [])];
    let total = state.attachments.reduce((n, x) => n + Number(x.size || 0), 0);
    for (const file of files) {
      if (state.attachments.length >= 8) break;
      total += file.size;
      if (total > 12 * 1024 * 1024) {
        $('pm19ComposeStatus').textContent = 'Attachments exceed 12 MB total.';
        break;
      }
      const content = await fileToBase64(file);
      state.attachments.push({
        filename:file.name,
        content_type:file.type || 'application/octet-stream',
        content,
        size:file.size
      });
    }
    e.target.value = '';
    renderComposeAttachments();
    markDirty();
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result || '').split(',')[1] || '');
      r.onerror = reject;
      r.readAsDataURL(file);
    });
  }

  function renderComposeAttachments() {
    const box = $('pm19AttachmentList');
    if (!box) return;
    box.innerHTML = state.attachments.map((x, i) => `<button class="pm19-compose-attachment" data-remove="${i}">
      <b>▱</b><span>${esc(x.filename)}</span><small>${Math.ceil(Number(x.size || 0)/1024)} KB</small><em>×</em>
    </button>`).join('');
    box.querySelectorAll('[data-remove]').forEach(b => b.addEventListener('click', () => {
      state.attachments.splice(Number(b.dataset.remove), 1);
      renderComposeAttachments();
      markDirty();
    }));
  }

  function composePayload() {
    const editorText = plainTextFromEditor();
    const editorHtml = $('pm19Editor').innerHTML;
    return {
      to:parseList($('pm19To').value),
      cc:parseList($('pm19Cc').value),
      bcc:parseList($('pm19Bcc').value),
      from_identity:$('pm19From').value || '',
      subject:$('pm19Subject').value.trim(),
      text:editorText + quoteTextForPayload(state.quote),
      html:editorHtml + quoteHtmlForPayload(state.quote),
      reply_to_message_id:state.replyToMessageId,
      attachments:state.attachments.map(x => ({
        filename:x.filename,
        content_type:x.content_type,
        content:x.content
      }))
    };
  }

  async function sendCompose() {
    const b = $('pm19Send');
    const status = $('pm19ComposeStatus');
    b.disabled = true;
    b.textContent = 'Sending…';
    try {
      const result = await api('/api/control/email/send-rich', {method:'POST', body:JSON.stringify(composePayload())});
      status.textContent = `Sent from ${result.from || 'Pitmark Mail'} ✓`;
      state.composerDirty = false;
      setTimeout(closeComposer, 450);
      state.folder = 'sent';
      document.querySelectorAll('[data-pm19-folder]').forEach(x => x.classList.toggle('active', x.dataset.pm19Folder === 'sent'));
      await loadMailbox();
    } catch (err) {
      status.textContent = err.message;
    } finally {
      b.disabled = false;
      b.textContent = 'Send';
    }
  }

  async function saveComposeDraft(silent = false) {
    if (!state.composerDirty && silent) return;
    const p = composePayload();
    p.id = state.activeDraftId;
    delete p.reply_to_message_id;
    try {
      const result = await api('/api/control/email/drafts-rich', {method:'POST', body:JSON.stringify(p)});
      state.activeDraftId = result.id;
      state.composerDirty = false;
      const status = $('pm19ComposeStatus');
      if (status) status.textContent = silent ? `Draft saved ${new Date().toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})}` : 'Draft saved ✓';
    } catch (err) {
      if (!silent && $('pm19ComposeStatus')) $('pm19ComposeStatus').textContent = err.message;
    }
  }

  function scheduleAutosave() {
    clearTimeout(state.autosaveTimer);
    state.autosaveTimer = setInterval(() => {
      if ($('pm19ComposeOverlay') && state.composerDirty) saveComposeDraft(true);
    }, 15000);
  }

  async function discardCompose() {
    if (state.activeDraftId && confirm('Discard this draft?')) {
      try { await api(`/api/control/email/drafts/${state.activeDraftId}`, {method:'DELETE'}); } catch {}
    }
    closeComposer();
    if (state.folder === 'drafts') loadMailbox();
  }

  function overhaulDashboard() {
    const dashboard = document.querySelector('[data-view-section="dashboard"]');
    if (!dashboard || dashboard.dataset.pm19Built) return;
    dashboard.dataset.pm19Built = '1';

    const heading = dashboard.querySelector('.view-heading');
    if (heading) {
      heading.classList.add('pm19-dashboard-heading');
      const h1 = heading.querySelector('h1');
      const p = heading.querySelector('p');
      if (h1) h1.textContent = 'Command Center';
      if (p) p.textContent = 'What needs attention right now. Everything else stays quiet.';
    }

    const stat = dashboard.querySelector('.stat-grid');
    if (stat) {
      stat.classList.add('pm19-status-deck');
      const labels = {
        statPosts:'Posts to review',
        statShield:'Security review',
        statOutreach:'Follow-ups due',
        statBlog:'Draft articles'
      };
      Object.entries(labels).forEach(([id, label]) => {
        const el = $(id);
        const span = el?.closest('.stat-card')?.querySelector('span');
        if (span) span.textContent = label;
      });
    }

    const quick = [...dashboard.querySelectorAll('.panel')].find(x => x.textContent.includes('Quick Actions'));
    quick?.remove();

    const intro = document.createElement('section');
    intro.className = 'pm19-command-hero';
    intro.innerHTML = `<div>
      <span class="pm19-kicker">PITMARK OPERATIONS</span>
      <h2>One place to run the whole thing.</h2>
      <p>Mail, publishing, security, partnerships and content — each tool gets a real workspace instead of a cramped widget.</p>
    </div><div class="pm19-command-launch">
      <button data-pm19-go="email">Open Mail</button>
      <button data-pm19-go="autopilot">Create Content</button>
      <button data-pm19-go="shield">Review Shield</button>
    </div>`;
    heading?.after(intro);
    intro.querySelectorAll('[data-pm19-go]').forEach(b => b.addEventListener('click', () => {
      const target = b.dataset.pm19Go;
      if (target === 'email') {
        if (window.setView) window.setView('email');
        loadMailbox();
      } else if (window.setView) window.setView(target);
    }));

    const notifications = dashboard.querySelector('.notification-center');
    const count = $('notificationCount');
    const sync = () => {
      const n = parseInt(String(count?.textContent || '0'), 10) || 0;
      notifications?.classList.toggle('pm19-no-notifications', n === 0);
    };
    sync();
    if (count) new MutationObserver(sync).observe(count, {childList:true,subtree:true,characterData:true});
  }

  function fixOutreachStatus() {
    const label = $('statOutreach')?.closest('.stat-card')?.querySelector('span');
    if (label) label.textContent = 'Follow-ups due';
    const m = $('mOutreach');
    if (m) {
      const span = m.closest('button')?.querySelector('span');
      if (span) span.textContent = 'Follow-ups';
    }
  }

  function guardAutofill() {
    const ids = ['ryName','oname','oorg','ocontact','pm19MailSearch'];
    ids.forEach(id => {
      const el = $(id);
      if (!el || el.dataset.pm19AutofillGuard) return;
      el.dataset.pm19AutofillGuard = '1';
      el.setAttribute('autocomplete','new-password');
      if (!el.matches(':focus')) el.readOnly = true;
      const unlock = () => {
        el.readOnly = false;
        if (!el.dataset.pm19UserTouched) el.value = '';
      };
      el.addEventListener('pointerdown', unlock, {once:true,capture:true});
      el.addEventListener('focus', unlock, {once:true,capture:true});
      el.addEventListener('input', e => {
        if (e.isTrusted) el.dataset.pm19UserTouched = '1';
      });
      if (!el.dataset.pm19UserTouched) el.value = '';
    });
  }

  function modernizeNavigation() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
      sidebar.classList.add('pm19-sidebar');
      const nav = $('nav');
      if (nav && !nav.querySelector('.pm19-nav-label')) {
        const label = document.createElement('div');
        label.className = 'pm19-nav-label';
        label.textContent = 'WORKSPACES';
        nav.prepend(label);
      }
    }
  }

  function wireMobileMailLaunch() {
    const openMobileMail = e => {
      e?.preventDefault();
      document.querySelectorAll('[data-mview]').forEach(x => x.classList.toggle('active', x.dataset.mview === 'email'));
      document.querySelectorAll('[data-mnav]').forEach(x => x.classList.toggle('active', x.dataset.mnav === 'email'));
      setTimeout(loadMailbox, 30);
    };
    const nav = document.querySelector('[data-mnav="email"]');
    if (nav) nav.onclick = openMobileMail;
    document.querySelectorAll('[data-mgo="email"]').forEach(b => b.onclick = openMobileMail);
  }

  async function boot() {
    state.mobile = !document.querySelector('.content');
    modernizeNavigation();
    overhaulDashboard();
    fixOutreachStatus();
    installMailUI();
    guardAutofill();
    wireMobileMailLaunch();
    await loadBootstrap();

    if (location.hash === '#email') {
      if (!state.mobile && window.setView) window.setView('email');
      loadMailbox();
    }

    setTimeout(guardAutofill, 300);
    setTimeout(guardAutofill, 1200);
    setTimeout(fixOutreachStatus, 600);
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 20));
})();
