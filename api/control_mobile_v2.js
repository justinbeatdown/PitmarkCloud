(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const q = (s, root=document) => root.querySelector(s);
  const qa = (s, root=document) => [...root.querySelectorAll(s)];

  function openView(name) {
    // Pitmark Mail v19 replaces the original mobile email markup and owns the
    // Email navigation button. Calling the legacy view('email') path tries to
    // load removed mMail* elements and makes Mail appear unresponsive.
    if (name === 'email') {
      const mailNav = q('[data-mnav="email"]');
      if (mailNav) {
        mailNav.click();
        window.scrollTo({top:0, behavior:'smooth'});
        return;
      }
    }

    if (typeof window.view === 'function') {
      window.view(name);
      window.scrollTo({top:0, behavior:'smooth'});
      return;
    }
    const nav = q(`[data-mnav="${name}"]`) || q(`[data-mgo="${name}"]`);
    nav?.click();
  }

  function actionButton(icon, title, sub, view) {
    const b = document.createElement('button');
    b.type = 'button';
    b.innerHTML = `<span class="pm-q-icon">${icon}</span><strong>${title}</strong><small>${sub}</small>`;
    b.addEventListener('click', () => openView(view));
    return b;
  }

  function sectionLabel(title, detail='') {
    const el = document.createElement('div');
    el.className = 'pm-mobile-section-label';
    el.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
    return el;
  }

  function buildHome() {
    const home = q('[data-mview="home"]');
    if (!home || home.dataset.mobileV2) return;
    home.dataset.mobileV2 = '1';

    const title = q('.m-title', home);
    if (title) {
      title.querySelector('h1').textContent = 'Command Center';
      title.querySelector('span')?.remove();
    }

    const hero = document.createElement('section');
    hero.className = 'pm-mobile-hero';
    hero.innerHTML = `
      <span class="pm-mobile-kicker">PITMARK OPERATIONS</span>
      <span class="pm-mobile-live" aria-hidden="true"></span>
      <h2>Everything that needs you. Nothing that doesn’t.</h2>
      <p>Approve content, answer mail, check PRT activity and handle follow-ups without digging through the whole system.</p>`;
    title?.after(hero);

    const quick = document.createElement('div');
    quick.className = 'pm-mobile-quick';
    quick.append(
      actionButton('✉', 'Mail', 'Inbox & replies', 'email'),
      actionButton('✓', 'Review', 'Posts waiting', 'autopilot'),
      actionButton('🤝', 'Outreach', 'Relationships', 'outreach'),
      actionButton('⬡', 'Shield', 'Security review', 'shield'),
      actionButton('▤', 'Blog', 'Draft & publish', 'blog')
    );
    hero.after(sectionLabel('Quick actions', 'tap once'), quick);

    const stats = q('.m-stats', home);
    if (stats) {
      stats.before(sectionLabel('Needs your attention', 'live status'));
      const labels = [
        ['mPending','Posts'],
        ['mShield','Shield review'],
        ['mOutreach','Follow-ups'],
        ['mBlog','Draft articles']
      ];
      labels.forEach(([id, text]) => {
        const value = $(id);
        const button = value?.closest('button');
        const label = button?.querySelector('span');
        if (label) label.textContent = text;
      });
    }

    const cards = qa(':scope > .m-card', home);
    const notifications = cards.find(c => /Notifications/i.test(c.textContent));
    if (notifications) notifications.before(sectionLabel('Inbox for Pitmark', 'important events'));

    const more = q('[data-mview="more"]');
    const social = cards.find(c => /Social Publishing/i.test(c.textContent));
    const actions = cards.find(c => /Quick Actions/i.test(c.textContent));
    const drawer = document.createElement('details');
    drawer.className = 'pm-mobile-tools-drawer';
    drawer.innerHTML = '<summary>Cloud utilities & manual tools</summary>';

    [social, actions].filter(Boolean).forEach(card => drawer.appendChild(card));
    if (more && drawer.children.length > 1) {
      const mt = q('.m-title', more);
      mt?.after(drawer);
    }

    syncAttention();
  }

  function buildMore() {
    const more = q('[data-mview="more"]');
    if (!more || more.dataset.mobileV2) return;
    more.dataset.mobileV2 = '1';

    const title = q('.m-title h1', more);
    if (title) title.textContent = 'Workspaces';

    const grid = document.createElement('div');
    grid.className = 'pm-mobile-workspace-grid';

    const items = [
      ['Campaigns','Rookie Year & racers','more'],
      ['Outreach','Tracks & partners','outreach'],
      ['Blog','Articles & publishing','blog'],
      ['Shield','Security & review','shield'],
      ['Autopilot','Content queue','autopilot'],
      ['Mail','Inbox & compose','email']
    ];

    items.forEach(([name, sub, view]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.innerHTML = `<strong>${name}</strong><span>${sub}</span>`;
      if (name === 'Campaigns') {
        b.addEventListener('click', () => {
          q('.pm191-mobile-campaign', more)?.scrollIntoView({behavior:'smooth', block:'start'});
        });
      } else {
        b.addEventListener('click', () => openView(view));
      }
      grid.appendChild(b);
    });

    q('.m-title', more)?.after(grid);
  }

  function modernizeMail() {
    const mail = q('[data-mview="email"]');
    if (!mail || mail.dataset.mobileV2) return;
    mail.dataset.mobileV2 = '1';

    const title = q('.m-title h1', mail);
    if (title) title.textContent = 'Pitmark Mail';

    const compose = $('mMailCompose');
    if (compose) compose.textContent = '+ Compose';
  }

  function syncAttention() {
    ['mPending','mShield','mOutreach','mBlog'].forEach(id => {
      const value = $(id);
      const n = Number(String(value?.textContent || '').replace(/[^0-9.-]/g,''));
      value?.closest('button')?.classList.toggle('pm-needs-attention', Number.isFinite(n) && n > 0);
    });
  }

  function updateBrand() {
    const brand = q('.m-brand span');
    if (brand) brand.textContent = 'CONTROL CENTER · MOBILE · v0.21.28';
  }

  function installAutopilotParity() {
    if (document.documentElement.dataset.pmMobileAutopilotParity) return;
    document.documentElement.dataset.pmMobileAutopilotParity = '1';

    const style = document.createElement('style');
    style.textContent = `
      .pm-mobile-autopilot-note{margin:0 0 12px;padding:12px 13px;border:1px solid #3f4545;border-left:3px solid #ff5500;background:linear-gradient(145deg,#111414,#090b0b);font-size:12px;line-height:1.45;color:#cfd3d3}
      .pm-mobile-autopilot-note strong{display:block;color:#fff;margin-bottom:4px;text-transform:uppercase;font-size:11px;letter-spacing:.05em}
      .pm-mobile-post-media{margin:10px 0;border:1px solid #3c4242;background:#080a0a;border-radius:5px;overflow:hidden}
      .pm-mobile-post-media img{display:block;width:100%;max-height:390px;object-fit:contain;background:#080a0a}
      .pm-mobile-post-media span{display:block;padding:7px 9px;color:#aeb4b4;font-size:10px;text-transform:uppercase;font-weight:800}
      .pm-mobile-source-pill{font-size:9px;color:#ff8b4c;margin-left:6px;text-transform:uppercase;letter-spacing:.04em}
    `;
    document.head.appendChild(style);

    // The original mobile shell predates X publishing support. Bring its live
    // connection state up to desktop parity, including Pitmark's Premium limit.
    try { publishStatus.x = false; } catch {}
    try {
      social = async function(){
        try{
          const s=await api('/api/control/social/status');
          publishStatus.facebook=!!s?.facebook?.configured;
          publishStatus.instagram=!!s?.instagram?.configured;
          publishStatus.x=!!s?.x?.configured;
          const xLabel=publishStatus.x
            ? (s?.x?.premium_long_posts ? 'X Premium ✓' : 'X ✓')
            : 'X —';
          const parts=[
            publishStatus.facebook?'Facebook ✓':'Facebook —',
            publishStatus.instagram?'Instagram ✓':'Instagram —',
            xLabel
          ];
          if($('mSocialStatus'))$('mSocialStatus').textContent=parts.join(' · ');
          const a=await api('/api/control/social/assets');
          if($('mAssetStatus'))$('mAssetStatus').textContent=`${(a.items||[]).length} approved images in Pitmark asset pool.`;
          return s;
        }catch(e){
          if($('mSocialStatus'))$('mSocialStatus').textContent='Check setup';
          return {};
        }
      };
    } catch {}

    // Mobile queue cards now show the actual attached media. For first-party
    // product campaigns, the backend pins Instagram to the real Shopify image;
    // the phone UI makes that visible instead of implying an AI image is needed.
    try {
      postCard = function(p){
        const platform=String(p.platform||'').toLowerCase();
        const source=String(p.source||'');
        const isProduct=platform==='instagram'&&source.startsWith('firstparty:')&&String(p.content_type||'').toLowerCase()==='product';
        const connected=!!publishStatus[platform];
        const canPub=connected&&['approved','scheduled'].includes(p.status)&&!p.stale_for_social;
        const canSched=['pending','approved'].includes(p.status)&&!p.stale_for_social;
        const media=p.media_url?`<div class="pm-mobile-post-media"><img src="${esc(p.media_url)}" alt="${isProduct?'Shopify product image':'Attached post image'}"><span>${isProduct?'Shopify product image':'Attached image'}</span></div>`:'';
        let mediaNote='';
        let assetButton='';
        if(platform==='instagram'){
          mediaNote=isProduct
            ? (p.media_url?'Shopify product image ready ✓':'Waiting for Shopify product image — no AI substitute will be used')
            : (p.media_url?'Image ready ✓':'Image will be auto-selected');
          assetButton=`<button class="m-ghost" data-pa="asset">${isProduct?'Refresh Product Image':'Pick Image'}</button>`;
        }
        const sourcePill=isProduct?'<span class="pm-mobile-source-pill">Shopify product</span>':'';
        return `<article class="m-item" data-id="${p.id}"><div class="top"><b>#${p.id} · ${esc(p.platform)}${sourcePill}</b><span class="pill">${esc(p.status)}</span></div><div class="body">${esc(p.body)}</div>${media}${platform==='instagram'?`<div class="body media-note">${esc(mediaNote)}</div>`:''}<div class="m-actions">${p.status==='pending'?'<button class="m-orange" data-pa="approve">Approve</button>':''}${canSched?'<input class="schedule" type="datetime-local"><button class="m-ghost" data-pa="schedule">Schedule</button>':''}${assetButton}<button class="m-orange" data-pa="publish" ${canPub?'':'disabled'}>Publish</button><button class="m-ghost" data-pa="reject">Reject</button><button class="m-ghost" data-pa="archive">Archive</button></div></article>`;
      };
    } catch {}

    const autopilot = q('[data-mview="autopilot"]');
    const title = q('.m-title', autopilot);
    if (autopilot && title && !q('.pm-mobile-autopilot-note', autopilot)) {
      const note = document.createElement('div');
      note.className = 'pm-mobile-autopilot-note';
      note.innerHTML = '<strong>Autopilot media parity</strong>Product drops use the real Shopify product image on Instagram. Automatic TikTok caption-only drafts are paused until Pitmark has a proper ready-to-post video workflow.';
      title.after(note);
    }
  }

  function boot() {
    document.body.classList.add('pm-mobile-v2');
    updateBrand();
    installAutopilotParity();
    buildHome();
    buildMore();
    modernizeMail();
    syncAttention();

    // Existing Control Center scripts populate data asynchronously. This updates
    // only attention classes/text and never rewrites whole page sections.
    let passes = 0;
    const timer = setInterval(() => {
      syncAttention();
      buildMore();
      if (++passes >= 12) clearInterval(timer);
    }, 1000);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 260), {once:true});
  else
    setTimeout(boot, 260);
})();