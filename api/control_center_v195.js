(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const q = (s, root=document) => root.querySelector(s);
  const qa = (s, root=document) => [...root.querySelectorAll(s)];
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  const selectedBlogSources = [];

  function cleanSocialText(value) {
    let text = String(value || '');
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '$1 $2');
    text = text.replace(/\*\*([^*\n]+)\*\*/g, '$1');
    text = text.replace(/__([^_\n]+)__/g, '$1');
    text = text.replace(/(^|\s)\*([^*\n]+)\*(?=\s|$)/g, '$1$2');
    text = text.replace(/(^|\s)_([^_\n]+)_(?=\s|$)/g, '$1$2');
    return text.trim();
  }

  function normalizeBlogHtml(value) {
    let text = String(value || '');
    text = text.replace(/^\s*#{1,4}\s*(sources?|references?)\s*:?\s*$/gim, '<h3>Sources</h3>');
    text = text.replace(/<p>\s*(?:#{1,4}\s*)?(sources?|references?)\s*:?\s*<\/p>/gi, '<h3>Sources</h3>');
    text = text.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return text;
  }

  function sourceBlock() {
    if (!selectedBlogSources.length) return '';
    const rows = selectedBlogSources.map(source =>
      `<li><a href="${h(source.url)}" target="_blank" rel="noopener noreferrer">${h(source.headline || source.url)}</a>${source.publisher ? ` <span>— ${h(source.publisher)}</span>` : ''}</li>`
    ).join('');
    return `<section class="pitmark-sources"><h3>Sources</h3><ul>${rows}</ul></section>`;
  }

  function workflowCard(post) {
    const status = String(post.status || '').toLowerCase();
    const platform = String(post.platform || '').toLowerCase();
    const body = cleanSocialText(post.body || '');
    const canApprove = status === 'pending';
    const canSchedule = ['pending','approved'].includes(status);
    let connected = true;
    try { connected = Boolean(socialPublishStatus?.[platform]); } catch {}
    const canPublish = ['facebook','instagram','x'].includes(platform) && connected && ['approved','scheduled'].includes(status);
    const stale = Boolean(post.stale_for_social);
    const age = post.source_age_minutes == null ? '' : ageLabel(post.source_age_minutes);
    const image = platform === 'instagram' && post.media_url
      ? `<img class="pm195-post-thumb" src="${h(post.media_url)}" alt="">`
      : '';
    const publish = canPublish ? `<button class="btn pm195-publish" data-action="publish">Publish now</button>` : '';
    const approve = canApprove ? `<button class="btn" data-action="approve">Approve</button>` : '';
    const schedule = canSchedule ? `<input class="input schedule-input" type="datetime-local"><button class="btn secondary" data-action="schedule">Schedule</button>` : '';
    const source = post.source_published_at
      ? `<span>Source ${h(new Date(post.source_published_at).toLocaleString())}${age ? ` · ${h(age)}` : ''}</span>`
      : `<span>${h(post.source || 'manual')}</span>`;
    return `<article class="queue-card pm195-post-card ${stale ? 'stale' : ''}" data-id="${post.id}">
      <header>
        <div><span class="pm195-platform ${h(platform)}">${h(platform === 'x' ? 'X' : platform)}</span><strong>#${post.id}</strong><span class="status-pill status-${h(status)}">${h(status)}</span></div>
        <time>${h(String(post.timeline_at || post.created_at || '').replace('T',' ').slice(0,16))}</time>
      </header>
      <div class="pm195-post-main">
        ${image}
        <div>
          <div class="queue-body">${h(body)}</div>
          <div class="pm195-source">${source}${stale ? '<b>Needs freshness review</b>' : ''}</div>
        </div>
      </div>
      <footer class="queue-actions">
        ${publish}${approve}
        <button class="btn secondary" data-action="reject">Reject</button>
        ${schedule}
        <button class="btn ghost" data-action="archive">Archive</button>
        ${platform === 'instagram' ? '<button class="btn ghost" data-action="asset">Generate Story Image</button>' : ''}
      </footer>
    </article>`;
  }

  function lane(title, subtitle, posts, kind) {
    return `<section class="pm195-lane ${kind}">
      <header><div><strong>${title}</strong><span>${subtitle}</span></div><b>${posts.length}</b></header>
      <div class="pm195-lane-list">${posts.length ? posts.map(workflowCard).join('') : '<div class="pm195-lane-empty">Nothing here right now.</div>'}</div>
    </section>`;
  }

  function renderWorkflow(posts) {
    if (!posts.length) return '<div class="empty-state">Your content desk is clear.</div>';
    const approved = posts.filter(p => p.status === 'approved');
    const pending = posts.filter(p => p.status === 'pending' && !p.stale_for_social);
    const stale = posts.filter(p => p.status === 'pending' && p.stale_for_social);
    const scheduled = posts.filter(p => p.status === 'scheduled');
    const published = posts.filter(p => p.status === 'published');
    const other = posts.filter(p => !['approved','pending','scheduled','published'].includes(p.status));
    return `<div class="pm195-workflow-summary">
        <div><strong>${approved.length}</strong><span>Ready to publish</span></div>
        <div><strong>${pending.length}</strong><span>Needs approval</span></div>
        <div><strong>${scheduled.length}</strong><span>Scheduled</span></div>
        <div><strong>${stale.length}</strong><span>Needs refresh</span></div>
      </div>
      <div class="pm195-workflow-grid">
        ${lane('READY TO PUBLISH','Approved — next action is Publish',approved,'ready')}
        ${lane('NEEDS APPROVAL','Review the copy, then approve or reject',pending,'approval')}
        ${lane('SCHEDULED','Already lined up',scheduled,'scheduled')}
        ${lane('NEEDS REFRESH','Older reactive stories — rewrite or archive',stale,'stale')}
        ${lane('RECENTLY PUBLISHED','What just went live',published,'published')}
        ${other.length ? lane('OTHER','Additional queue items',other,'other') : ''}
      </div>`;
  }

  function installWorkflowRenderer() {
    try { queueCard = workflowCard; } catch {}
    try { renderTimeline = renderWorkflow; } catch {}
  }

  function restructureAutopilot() {
    const view = q('[data-view-section="autopilot"]');
    if (!view || view.dataset.pm195) return;
    view.dataset.pm195 = '1';

    const overview = q('.autopilot-overview', view);
    const panels = qa(':scope > .panel', view);
    const composer = q('.social-composer-panel', view);
    const queue = panels.find(p => /Content Queue/i.test(p.textContent));
    const intelligence = panels.find(p => /What's Happening Now/i.test(p.textContent));

    if (overview && queue) overview.after(queue);

    function drawer(panel, title, subtitle, open=false) {
      if (!panel || panel.closest('.pm195-drawer')) return null;
      const d = document.createElement('details');
      d.className = 'pm195-drawer';
      d.open = open;
      const summary = document.createElement('summary');
      summary.innerHTML = `<div><strong>${title}</strong><span>${subtitle}</span></div><b>${open ? '−' : '+'}</b>`;
      d.addEventListener('toggle', () => { summary.querySelector('b').textContent = d.open ? '−' : '+'; });
      panel.before(d);
      d.append(summary, panel);
      return d;
    }

    drawer(composer, 'Create a new post', 'Manual composer, images and copy generation');
    drawer(intelligence, 'Story radar', 'Fresh racing opportunities Autopilot found');

    if (queue) {
      const title = q('.panel-head h2', queue);
      if (title) title.textContent = 'Content Desk';
      const meta = q('.panel-head .meta', queue);
      if (meta) meta.innerHTML = '<span>Approve → Publish</span><span>Schedule</span><span>Refresh stale stories</span>';
    }

    setTimeout(() => { try { loadQueue(); } catch {} }, 50);
  }

  function classifyPill(text) {
    const t = text.toLowerCase();
    if (/intake:\s*(sent|received)/.test(t) || /verification:\s*(verified|complete)/.test(t) || /media:\s*approved/.test(t) || /research\s+complete/.test(t)) return 'good';
    if (/interested|selected|published|partner/.test(t)) return 'accent';
    if (/pending|unverified|researching|queued|intake:\s*not_sent/.test(t)) return 'warn';
    if (/failed|rejected|denied/.test(t)) return 'bad';
    if (/guardian:\s*not_required/.test(t)) return 'info';
    return 'muted';
  }

  function paintRookiePills() {
    const root = $('rookieOutput');
    if (!root) return;
    root.querySelectorAll('.rookie-card .meta>span,.rookie-card .status-pill').forEach(pill => {
      pill.classList.remove('pm195-good','pm195-accent','pm195-warn','pm195-bad','pm195-info','pm195-muted');
      pill.classList.add(`pm195-${classifyPill(pill.textContent || '')}`);
    });
  }

  function observeRookies() {
    const root = $('rookieOutput');
    if (!root || root.dataset.pm195Observer) return;
    root.dataset.pm195Observer = '1';
    let scheduled = false;
    new MutationObserver(m => {
      if (!m.some(x => x.addedNodes.length || x.removedNodes.length)) return;
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => { scheduled = false; paintRookiePills(); });
    }).observe(root,{childList:true,subtree:true});
    paintRookiePills();
  }

  async function loadBlogResources() {
    const box = $('pm195BlogResources');
    if (!box) return;
    box.innerHTML = '<div class="pm195-resource-loading">Checking Pitmark’s racing intelligence…</div>';
    try {
      const items = await apiCall('/api/control/autopilot/opportunities');
      const rows = (items || []).slice(0,10);
      box.innerHTML = rows.length ? rows.map((item, i) => {
        const freshness = item.freshness?.status ? `<span>${h(item.freshness.status)}</span>` : '';
        return `<article class="pm195-resource-card" data-resource="${i}">
          <div><strong>${h(item.headline || 'Racing story')}</strong><p>${h(item.reason || item.relevance || '')}</p></div>
          <div class="pm195-resource-meta">${freshness}<a href="${h(item.source_url || '#')}" target="_blank" rel="noopener">Open source ↗</a><button type="button" data-add-source>Add source</button></div>
        </article>`;
      }).join('') : '<div class="pm195-lane-empty">No current story resources yet. Run Story Radar in Autopilot.</div>';

      rows.forEach((item, i) => {
        const card = box.querySelector(`[data-resource="${i}"]`);
        card?.querySelector('[data-add-source]')?.addEventListener('click', e => {
          const url = String(item.source_url || '').trim();
          if (!url) return;
          const existing = selectedBlogSources.find(x => x.url === url);
          if (existing) {
            selectedBlogSources.splice(selectedBlogSources.indexOf(existing),1);
            e.currentTarget.textContent = 'Add source';
            e.currentTarget.classList.remove('selected');
          } else {
            selectedBlogSources.push({headline:item.headline || url,url,publisher:item.publisher || '',reason:item.reason || ''});
            e.currentTarget.textContent = 'Added ✓';
            e.currentTarget.classList.add('selected');
            if ($('bsubject') && !$('bsubject').value.trim()) $('bsubject').value = item.headline || '';
          }
          const count = $('pm195SourceCount');
          if (count) count.textContent = `${selectedBlogSources.length} selected`;
        });
      });
    } catch (err) {
      box.innerHTML = `<div class="error-box">${h(err.message)}</div>`;
    }
  }

  function installBlogDesk() {
    const view = q('[data-view-section="blog"]');
    if (!view || view.dataset.pm195) return;
    view.dataset.pm195 = '1';
    const heading = q('.view-heading', view);
    const panel = document.createElement('section');
    panel.className = 'panel pm195-blog-resources';
    panel.innerHTML = `<div class="panel-head queue-head">
      <div class="panel-icon">⌕</div>
      <div><h2>Story Resources</h2><div class="meta"><span>Autopilot intelligence</span><span>Use verified source links in the article</span></div></div>
      <div class="queue-tools"><span id="pm195SourceCount" class="status-pill">0 selected</span><button class="btn secondary" id="pm195RefreshResources">Refresh</button></div>
    </div><p class="muted">Pick one or more current racing sources. Pitmark will pass them into the draft and build a clean, linked Sources section instead of dumping ugly URLs into Shopify.</p>
    <div id="pm195BlogResources" class="pm195-resource-list"></div>`;
    heading?.after(panel);
    $('pm195RefreshResources')?.addEventListener('click', loadBlogResources);
    loadBlogResources();
  }

  async function generateBlogClean() {
    const b = $('generateBlogBtn');
    if (!b) return;
    b.disabled = true;
    b.textContent = 'Generating…';
    try {
      let notes = String($('bnotes')?.value || '').trim();
      if (selectedBlogSources.length) {
        const sources = selectedBlogSources.map(x => `${x.headline}: ${x.url}`).join(' | ');
        notes = `${notes}${notes ? ' | ' : ''}Use these verified sources and link them cleanly in the article: ${sources}`;
      }
      const result = await apiCall('/api/control/blog/generate',{
        method:'POST',
        body:JSON.stringify({
          subject:$('bsubject').value,
          content_type:$('btype').value,
          notes:notes || null
        })
      });
      $('btitle').value = result.title || '';
      let body = normalizeBlogHtml(result.body_html || '');
      const links = sourceBlock();
      if (links && !selectedBlogSources.some(x => body.includes(x.url))) body += links;
      $('bbody').value = body;
      showToast?.('Draft ready','Sources are normalized for Shopify.','success');
    } catch (err) {
      if (typeof showToast === 'function') showToast('Blog generation failed',err.message,'error');
    } finally {
      b.disabled = false;
      b.textContent = 'Generate Draft';
    }
  }

  function installBlogActions() {
    document.addEventListener('click', async e => {
      if (e.target.closest('#generateBlogBtn')) {
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        generateBlogClean();
        return;
      }

      if (e.target.closest('#addBlogBtn')) {
        const body = $('bbody');
        if (body) body.value = normalizeBlogHtml(body.value);
        return; // original Save Draft handler still runs
      }

      const publish = e.target.closest('.blog-card [data-blog-action="shopify-publish"]');
      if (publish) {
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        const card = publish.closest('.blog-card');
        publish.disabled = true;
        publish.textContent = 'Preparing…';
        try {
          await apiCall(`/api/control/blog/drafts/${card.dataset.id}/normalize`,{method:'POST'});
          await blogAction(card,'shopify-publish');
        } catch (err) {
          if (typeof showToast === 'function') showToast('Blog publish failed',err.message,'error');
        } finally {
          if (publish.isConnected) {
            publish.disabled = false;
            publish.textContent = 'Publish to Shopify';
          }
        }
      }
    }, true);
  }

  function installImageFallbacks() {
    const root = $('blogOutput');
    if (!root || root.dataset.pm195Images) return;
    root.dataset.pm195Images = '1';
    const wire = () => root.querySelectorAll('.blog-card-image img:not([data-pm195])').forEach(img => {
      img.dataset.pm195 = '1';
      img.addEventListener('error', () => {
        const parent = img.closest('.blog-card-image');
        if (parent) parent.innerHTML = '<div class="pm195-image-missing"><strong>Featured image unavailable</strong><span>Generate or assign a replacement before the next publish.</span></div>';
      }, {once:true});
    });
    new MutationObserver(wire).observe(root,{childList:true,subtree:true});
    wire();
  }

  function installSocialCleaner() {
    document.addEventListener('click', async e => {
      if (e.target.closest('#generateBtn')) {
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        const b = $('generateBtn');
        if (!b) return;
        const platform = String($('platform')?.value || 'facebook').toLowerCase();
        const goal = $('goal')?.value || 'community';
        const topic = String($('topic')?.value || '').trim();
        b.disabled = true;
        b.textContent = 'Generating…';
        try {
          const result = await apiCall('/api/control/autopilot/composer/generate',{
            method:'POST',
            body:JSON.stringify({platform,goal,prompt:topic || 'Generate a useful Pitmark post',topic:topic || null})
          });
          const cleaned = cleanSocialText(result.body || '');
          try { generated = cleaned; } catch {}
          if ($('draftEditor')) $('draftEditor').value = cleaned;
          if ($('composerMessage')) $('composerMessage').textContent = 'Draft ready — formatted for the selected platform.';
          try {
            if (platform === 'instagram' && typeof assetMode === 'function' && assetMode() === 'auto') await suggestInstagramAsset();
          } catch {}
        } catch (err) {
          if ($('composerMessage')) $('composerMessage').textContent = 'ERROR: ' + err.message;
        } finally {
          b.disabled = false;
          b.textContent = 'Generate Copy';
        }
        return;
      }

      if (e.target.closest('#savePostBtn')) {
        const editor = $('draftEditor');
        if (editor) editor.value = cleanSocialText(editor.value);
        try { generated = editor?.value || generated; } catch {}
      }
    }, true);
  }

  function boot() {
    installWorkflowRenderer();
    restructureAutopilot();
    observeRookies();
    installBlogDesk();
    installBlogActions();
    installImageFallbacks();
    installSocialCleaner();

    // Reapply semantic pill colors after Campaign Manager refreshes.
    setTimeout(paintRookiePills,500);
    setTimeout(paintRookiePills,1600);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded',() => setTimeout(boot,220),{once:true});
  else
    setTimeout(boot,220);
})();