import { api, clearCache } from './control-center-api.js';

export const DOMAIN_META = Object.freeze({
  hq: { title: 'HQ', kicker: 'Corporate Operations', context: 'What matters, what moved, and what needs you.' },
  work: { title: 'Work', kicker: 'Master Checklist', context: 'The live source of truth for Pitmark work.' },
  prt: { title: 'PRT', kicker: 'Product Operations', context: 'Testers, feedback, Founder’s Race, and product work.' },
  partnerships: { title: 'Partnerships', kicker: 'Relationships', context: 'Tracks, leagues, broadcasters, partners, and follow-ups.' },
  content: { title: 'Content', kicker: 'Social Manager', context: 'Generated posts, approvals, publishing, and editorial.' },
  store: { title: 'Store & Brand', kicker: 'Commerce Operations', context: 'Store, web, brand, launches, and related work.' },
  people: { title: 'People', kicker: 'Pitmark Network', context: 'The people and organizations moving Pitmark forward.' },
  systems: { title: 'Systems', kicker: 'Platform Operations', context: 'Pitmark Cloud, automation, services, and signals.' },
  insights: { title: 'Insights', kicker: 'Operating Intelligence', context: 'Useful momentum from real Pitmark activity.' },
});

const esc = (value = '') => String(value ?? '').replace(/[&<>'"]/g, ch => ({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;' }[ch]));
const n = (value) => Number(value || 0).toLocaleString();
const low = (value) => String(value || '').trim().toLowerCase();
const compact = (value, max = 120) => { const s = String(value || '').replace(/\s+/g, ' ').trim(); return s.length > max ? `${s.slice(0, max - 1)}…` : s; };
const dateText = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString([], { month:'short', day:'numeric', hour:'numeric', minute:'2-digit' });
};
const age = (value) => {
  if (!value) return 'unknown age';
  const d = new Date(value); if (Number.isNaN(d.getTime())) return String(value);
  const seconds = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (seconds < 90) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds/60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds/3600)}h ago`;
  return `${Math.floor(seconds/86400)}d ago`;
};
const titleOf = (row, fallback = 'Untitled') => row?.name || row?.full_name || row?.tester_name || row?.display_name || row?.organization || row?.title || row?.email || fallback;
const statusBadge = (status = 'unknown') => {
  const s = low(status); const tone = ['done','complete','completed','published','redeemed','active','accepted','resolved'].includes(s) ? 'good' : ['blocked','declined','rejected','expired','revoked','error','failed'].includes(s) ? 'bad' : ['waiting','monitoring','hold','scheduled','issued','reviewing','pending'].includes(s) ? 'warn' : '';
  return `<span class="pm-badge ${tone}">${esc(status || 'unknown')}</span>`;
};
const priority = (value = '') => `<span class="pm-priority ${esc(low(value))}">${esc(value || '—')}</span>`;
const moduleError = (name, error, retry = '') => `<div class="pm-callout is-error"><span class="icon">!</span><div><strong>${esc(name)} could not load</strong><p>${esc(error || 'Pitmark Cloud returned an unavailable state.')}</p>${retry ? `<div class="pm-error-actions"><button class="pm-button pm-button-ghost" data-retry="${esc(retry)}">Retry</button></div>` : ''}</div></div>`;
const empty = (text) => `<div class="pm-empty">${esc(text)}</div>`;
const viewHeader = (eyebrow, title, copy, actions = '') => `<header class="pm-view-header"><div><span class="eyebrow">${esc(eyebrow)}</span><h2>${esc(title)}</h2><p>${esc(copy)}</p></div><div class="pm-view-actions">${actions}</div></header>`;
const panel = (title, eyebrow, body, tools = '') => `<section class="pm-surface pm-panel"><header class="pm-panel-header"><div><span class="eyebrow">${esc(eyebrow)}</span><h3>${esc(title)}</h3></div><div class="pm-panel-tools">${tools}</div></header>${body}</section>`;
const details = (pairs) => `<div class="pm-detail-list">${pairs.filter(([,v]) => v !== undefined && v !== null && v !== '').map(([k,v]) => `<div class="pm-detail-pair"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join('')}</div>`;
const workRow = (item) => `<button class="pm-row" type="button" data-open-work="${Number(item.row_number)}"><div class="pm-row-main"><div class="pm-row-meta">${priority(item.priority)}<span class="pm-status ${esc(item.bucket)}">${esc(item.status || item.bucket)}</span><span class="pm-badge">${esc(item.area || 'General')}</span></div><strong>${esc(item.task || 'Untitled work')}</strong><p>${esc(compact(item.next_action || item.notes || 'No next action recorded.', 150))}</p></div><div class="pm-row-side"><span class="pm-muted">${esc(item.last_updated || 'No date')}</span><span>›</span></div></button>`;

function unwrap(module) { return module?.ok ? module.data : null; }
function failure(module, fallback) { return module?.ok === false ? module.error : fallback; }

async function renderHQ(root, ctx) {
  const payload = await api.hq({ maxAge: ctx.force ? 0 : 15000 });
  const modules = payload?.modules || {};
  const workConnected = modules.work?.ok === true;
  const work = unwrap(modules.work); const prt = unwrap(modules.prt); const content = unwrap(modules.content); const relationships = unwrap(modules.relationships); const systems = unwrap(modules.systems); const notifications = unwrap(modules.notifications);
  const attention = work?.attention || [];
  const wait = work?.waiting || [];
  const summary = work?.summary || {};
  const p = prt || {}; const c = content || {};
  const signalItems = notifications?.items || [];
  const feedbackOpen = Number(p.feedback?.open ?? p.feedback?.total ?? 0);
  const appCount = Number(p.applications?.new || 0);
  const approvalCount = Number(c.autopilot?.pending || 0);
  const followUpCount = Number(relationships?.waiting_follow_up || 0);
  const unreadCount = Number(notifications?.unread || 0);
  const headline = workConnected ? (attention.length ? `${attention.length} thing${attention.length === 1 ? '' : 's'} deserve your attention.` : 'Pitmark is clear for the moment.') : 'Pitmark HQ is online.';
  const sub = workConnected ? (work?.stale ? 'Master Checklist is showing cached data while the live source reconnects.' : 'Live operations across work, PRT, content, relationships, and systems.') : 'PRT, content, relationships, and systems are live. Work sync is temporarily unavailable.';
  const checklistBadge = workConnected ? (work?.stale ? '<span class="pm-badge warn">Checklist cached</span>' : '<span class="pm-badge good">Checklist live</span>') : '<span class="pm-badge warn">Checklist unavailable</span>';

  const operatingQueue = [
    workConnected && attention.length ? { domain:'work', kicker:'Work · Attention', title:`${attention.length} checklist item${attention.length === 1 ? '' : 's'} need you`, copy:'P0/P1, blockers, or active work that needs an owner decision.' } : null,
    appCount ? { domain:'prt', kicker:'PRT · Intake', title:`${appCount} new tester application${appCount === 1 ? '' : 's'}`, copy:'Review applicants and keep Early Access moving.' } : null,
    feedbackOpen ? { domain:'prt', kicker:'PRT · Feedback', title:`${feedbackOpen} tester feedback item${feedbackOpen === 1 ? '' : 's'} open`, copy:'Review product feedback and release-impacting reports.' } : null,
    approvalCount ? { domain:'content', kicker:'Content · Approval', title:`${approvalCount} generated post${approvalCount === 1 ? '' : 's'} waiting`, copy:'Review, edit, approve, schedule, or archive social copy.' } : null,
    followUpCount ? { domain:'partnerships', kicker:'Relationships', title:`${followUpCount} follow-up${followUpCount === 1 ? '' : 's'} tracked`, copy:'Open the partnership pipeline and move conversations forward.' } : null,
    unreadCount ? { domain:'systems', kicker:'Systems · Signals', title:`${unreadCount} unread operational signal${unreadCount === 1 ? '' : 's'}`, copy:'Review current platform and automation notifications.' } : null,
  ].filter(Boolean);

  const queueBody = operatingQueue.length ? `<div class="pm-row-list">${operatingQueue.map(item => `<button class="pm-row" type="button" data-go="${item.domain}"><div class="pm-row-main"><div class="pm-row-meta"><span class="pm-badge orange">${esc(item.kicker)}</span></div><strong>${esc(item.title)}</strong><p>${esc(item.copy)}</p></div><div class="pm-row-side"><span>Open</span><span>›</span></div></button>`).join('')}</div>` : empty('No cross-company actions are waiting right now.');

  const signalsBody = signalItems.length ? `<div class="pm-row-list">${signalItems.slice(0,7).map(item => `<div class="pm-row"><div class="pm-row-main"><div class="pm-row-meta">${statusBadge(item.priority || item.status || 'info')}<span class="pm-badge">${esc(item.module || 'Pitmark')}</span></div><strong>${esc(item.title || 'Operational signal')}</strong><p>${esc(compact(item.detail || item.reason || 'No additional detail.', 150))}</p></div><div class="pm-row-side"><span class="pm-muted">${esc(age(item.created_at))}</span></div></div>`).join('')}</div>` : empty('No current operational signals.');

  const quickAccess = `<div class="pm-quick-grid">
    <button type="button" data-go="prt"><span>P</span><strong>PRT</strong><small>Testers, feedback, Founder’s Race</small></button>
    <button type="button" data-go="content"><span>▤</span><strong>Content</strong><small>Generated, approvals, editorial</small></button>
    <button type="button" data-go="partnerships"><span>↔</span><strong>Partnerships</strong><small>Tracks, leagues, follow-ups</small></button>
    <button type="button" data-go="store"><span>◇</span><strong>Store & Brand</strong><small>Commerce and brand work</small></button>
    <button type="button" data-go="systems"><span>⌁</span><strong>Systems</strong><small>Cloud, automation, signals</small></button>
    <button type="button" data-go="insights"><span>↗</span><strong>Insights</strong><small>Operating momentum</small></button>
  </div>`;

  root.innerHTML = `
    <section class="pm-brief"><div><span class="eyebrow">TODAY AT PITMARK</span><h2>${esc(headline)}</h2><p>${esc(sub)}</p></div><div class="pm-brief-meta">${checklistBadge}<span class="pm-badge">v${esc(payload?.version || systems?.app_version || '—')}</span></div></section>
    <div class="pm-metric-strip">
      ${workConnected ? `<button type="button" class="pm-metric pm-metric-action" data-hq-action="attention" aria-label="Open work needing attention"><span>Needs attention</span><strong>${n(attention.length)}</strong><small>P0/P1, blockers, active work</small><i aria-hidden="true">›</i></button><button type="button" class="pm-metric pm-metric-action" data-hq-action="waiting" aria-label="Open waiting work"><span>Waiting</span><strong>${n(summary.waiting)}</strong><small>External or pending items</small><i aria-hidden="true">›</i></button>` : ''}
      <button type="button" class="pm-metric pm-metric-action" data-hq-action="applications" aria-label="Open PRT applications"><span>PRT applications</span><strong>${n(appCount)}</strong><small>New applications</small><i aria-hidden="true">›</i></button>
      <button type="button" class="pm-metric pm-metric-action" data-hq-action="approvals" aria-label="Open content approvals"><span>Content approvals</span><strong>${n(approvalCount)}</strong><small>Generated posts waiting</small><i aria-hidden="true">›</i></button>
      <button type="button" class="pm-metric pm-metric-action" data-hq-action="relationships" aria-label="Open relationships"><span>Relationships</span><strong>${n(relationships?.total)}</strong><small>${n(followUpCount)} follow-ups tracked</small><i aria-hidden="true">›</i></button>
      ${workConnected ? '' : `<button type="button" class="pm-metric pm-metric-action" data-hq-action="feedback"><span>PRT feedback</span><strong>${n(feedbackOpen)}</strong><small>Open tester feedback</small><i aria-hidden="true">›</i></button><button type="button" class="pm-metric pm-metric-action" data-hq-action="signals"><span>Signals</span><strong>${n(unreadCount)}</strong><small>Unread operational signals</small><i aria-hidden="true">›</i></button>`}
    </div>
    <div class="pm-grid pm-grid-hq">
      ${panel('Operator Queue','What Needs You',queueBody,'')}
      ${panel('Pitmark Pulse','Company State', `
        <div class="pm-pulse-grid">
          ${workConnected ? `<div class="pm-pulse"><header><span>Work</span>${summary.blocked ? '<b class="pm-danger-text">Blocked</b>' : '<b class="pm-good-text">Moving</b>'}</header><strong>${n(summary.open)}</strong><p>open items · ${n(summary.completed)} completed</p><div class="pm-progress"><span style="width:${Math.min(100, (Number(summary.completed||0) / Math.max(1, Number(summary.total||1))) * 100)}%"></span></div></div>` : ''}
          <div class="pm-pulse"><header><span>PRT</span><b>${n(p.testers?.redeemed)} testers</b></header><strong>${n(feedbackOpen)}</strong><p>feedback items open · ${n(p.founders_race?.pending)} race referrals pending</p></div>
          <div class="pm-pulse"><header><span>Content</span><b>${n(c.autopilot?.scheduled)} scheduled</b></header><strong>${n(approvalCount)}</strong><p>social approvals · ${n(c.editorial?.drafts)} editorial drafts</p></div>
          <div class="pm-pulse"><header><span>Partners</span><b>${n(relationships?.total)}</b></header><strong>${n(followUpCount)}</strong><p>records with a follow-up</p></div>
          <div class="pm-pulse"><header><span>Systems</span><b>${systems?.database?.durable_for_render ? 'Durable' : 'Check DB'}</b></header><strong>${modules.systems?.ok ? 'OK' : '!'}</strong><p>${esc(systems?.environment || 'system state unavailable')}</p></div>
          <div class="pm-pulse"><header><span>Signals</span><b>Unread</b></header><strong>${n(unreadCount)}</strong><p>operational notifications</p></div>
        </div>`, '')}
    </div>
    ${workConnected ? `<div class="pm-grid pm-grid-2 pm-hq-lower">${panel('Waiting','External Dependencies', wait.length ? `<div class="pm-row-list">${wait.slice(0,6).map(workRow).join('')}</div>` : empty('Nothing is waiting right now.'), '')}${panel('Recent Progress','Momentum', (work?.recently_completed || []).length ? `<div class="pm-row-list">${work.recently_completed.slice(0,6).map(workRow).join('')}</div>` : empty('Completed work will show here.'), '')}</div>` : ''}
    <div class="pm-grid pm-grid-2 pm-hq-lower">
      ${panel('Recent Signals','Operations Feed',signalsBody,`<button class="pm-button pm-button-ghost" data-go="systems">Open Systems</button>`)}
      ${panel('Quick Access','Company Areas',quickAccess,'')}
    </div>`;
  bindWorkOpeners(root, ctx);
}

const WORK_VIEWS = ['now','today','active','waiting','monitoring','blocked','desktop','phone','completed','roadmap'];
async function renderWork(root, ctx) {
  const view = ctx.state.workView || 'now';
  const payload = await api.work(view, { maxAge: ctx.force ? 0 : 12000 });
  const items = payload?.items || []; const summary = payload?.summary || {};
  root.innerHTML = `${viewHeader('Master Checklist','Run the work, not another dashboard.','Every row comes from the live Pitmark Master Checklist.', `<span class="pm-badge ${payload.stale ? 'warn':'good'}">${payload.stale ? 'Cached':'Live source'}</span>`)}
    <div class="pm-filter-bar"><div class="pm-tabs">${WORK_VIEWS.map(v => `<button class="pm-tab ${v===view?'is-active':''}" type="button" data-work-view="${v}">${esc(v[0].toUpperCase()+v.slice(1))}${['waiting','monitoring','blocked','completed','roadmap'].includes(v) ? `<b>${n(summary[v])}</b>`:''}</button>`).join('')}</div></div>
    <div class="pm-metric-strip"><div class="pm-metric"><span>Open</span><strong>${n(summary.open)}</strong><small>all unfinished work</small></div><div class="pm-metric"><span>P1</span><strong>${n(summary.p1)}</strong><small>high-priority open work</small></div><div class="pm-metric"><span>Blocked</span><strong>${n(summary.blocked)}</strong><small>cannot move yet</small></div><div class="pm-metric"><span>Waiting</span><strong>${n(summary.waiting)}</strong><small>pending elsewhere</small></div><div class="pm-metric"><span>Done</span><strong>${n(summary.completed)}</strong><small>recorded completions</small></div></div>
    ${panel(`${view[0].toUpperCase()+view.slice(1)} Work`,'Source of Truth', items.length ? `<div class="pm-row-list">${items.map(workRow).join('')}</div>` : empty(`No ${view} items are recorded.`), `<span class="pm-badge">${n(items.length)} items</span>`)}
    ${payload.error ? `<div style="margin-top:10px">${moduleError('Live checklist refresh',payload.error)}</div>`:''}`;
  root.onclick = (event) => {
    const tab = event.target.closest('[data-work-view]'); if (tab) { ctx.state.workView = tab.dataset.workView; ctx.refresh(); return; }
    const row = event.target.closest('[data-open-work]'); if (row) openWorkItem(items.find(i => String(i.row_number) === row.dataset.openWork), ctx);
  };
}

function bindWorkOpeners(root, ctx) {
  root.onclick = (event) => {
    const metric = event.target.closest('[data-hq-action]');
    if (metric) {
      const action = metric.dataset.hqAction;
      if (action === 'attention') { ctx.state.workView = 'now'; ctx.navigate('work'); return; }
      if (action === 'waiting') { ctx.state.workView = 'waiting'; ctx.navigate('work'); return; }
      if (action === 'applications') { ctx.state.prtTab = 'applications'; ctx.navigate('prt'); return; }
      if (action === 'approvals') { ctx.state.contentTab = 'generated'; ctx.navigate('content'); return; }
      if (action === 'relationships') { ctx.navigate('partnerships'); return; }
      if (action === 'feedback') { ctx.state.prtTab = 'feedback'; ctx.navigate('prt'); return; }
      if (action === 'signals') { ctx.navigate('systems'); return; }
    }
    const go = event.target.closest('[data-go]'); if (go) { ctx.navigate(go.dataset.go); return; }
    const row = event.target.closest('[data-open-work]');
    if (row) { ctx.navigate('work', { workRow: Number(row.dataset.openWork) }); }
  };
}

function openWorkItem(item, ctx) {
  if (!item) return;
  const id = `work-notes-${item.row_number}`;
  ctx.openSheet({ kicker:`${item.area || 'Work'} · ${item.priority || 'No priority'}`, title:item.task || 'Checklist item', body:`${details([['Status',item.status],['Priority',item.priority],['Area',item.area],['Next action',item.next_action],['Last updated',item.last_updated]])}<div class="pm-detail-block"><h4>Notes</h4><textarea class="pm-textarea" id="${id}" placeholder="Add context to the Master Checklist…">${esc(item.notes || '')}</textarea></div>`, actions:[
    { label:'Save notes', tone:'ghost', run:async()=>{ await api.updateWork(item.row_number,{notes:document.getElementById(id)?.value || ''}); clearCache('/api/control/work'); ctx.toast('Master Checklist notes updated.','good'); ctx.closeSheet(); ctx.refresh(); } },
    { label:'Waiting', tone:'ghost', run:async()=>{ await api.updateWork(item.row_number,{status:'Waiting'}); clearCache('/api/control/work'); ctx.toast('Moved to Waiting.','good'); ctx.closeSheet(); ctx.refresh(); } },
    { label:'Monitoring', tone:'ghost', run:async()=>{ await api.updateWork(item.row_number,{status:'Monitoring'}); clearCache('/api/control/work'); ctx.toast('Moved to Monitoring.','good'); ctx.closeSheet();ctx.refresh(); } },
    { label:'Mark done', tone:'primary', run:async()=>{ await api.updateWork(item.row_number,{status:'Done'}); clearCache('/api/control/work'); ctx.toast('Completed and synced to Master Checklist.','good'); ctx.closeSheet(); ctx.refresh(); } },
  ]});
}

const PRT_TABS = ['applications','testers','founders','feedback'];
async function renderPRT(root, ctx) {
  const [overview, testers, race, feedback] = await Promise.allSettled([api.prtOverview(), api.prtTesters(), api.foundersRace(), api.feedback()]);
  const o = overview.status==='fulfilled'?overview.value:null; const t = testers.status==='fulfilled'?testers.value:null; const r = race.status==='fulfilled'?race.value:null; const f = feedback.status==='fulfilled'?feedback.value:null;
  const tab = ctx.state.prtTab || 'applications';
  const tabs = `<div class="pm-tabs">${[['applications','Applications',o?.applications?.new],['testers','Active Testers',t?.tester_summary?.active],['founders',"Founder’s Race",r?.summary?.pending],['feedback','Feedback',f?.summary?.open ?? f?.items?.length]].map(([key,label,count])=>`<button class="pm-tab ${tab===key?'is-active':''}" type="button" data-prt-tab="${key}">${label}<b>${n(count)}</b></button>`).join('')}</div>`;
  let body='';
  if(tab==='applications') body = t ? renderApplications(t.applications || []) : moduleError('PRT applications',testers.reason?.message,'prt');
  if(tab==='testers') body = t ? renderTesters(t.invites || []) : moduleError('PRT testers',testers.reason?.message,'prt');
  if(tab==='founders') body = r ? renderRace(r.leaderboard || []) : moduleError("Founder’s Race",race.reason?.message,'prt');
  if(tab==='feedback') body = f ? renderFeedback(f.items || []) : moduleError('PRT feedback',feedback.reason?.message,'prt');
  root.innerHTML = `${viewHeader('Product Operations','Pitmark Racing Tools','Operate the tester program, feedback loop, and Founder’s Race from one place.', `<a class="pm-button pm-button-ghost" href="/control/early-access">Applicant Center ↗</a><a class="pm-button pm-button-ghost" href="/control/founders-race">Race Admin ↗</a>`)}${tabs}${body}`;
  root.onclick = async (event) => {
    const tabButton=event.target.closest('[data-prt-tab]'); if(tabButton){ctx.state.prtTab=tabButton.dataset.prtTab;ctx.refresh();return;}
    const appAction=event.target.closest('[data-app-status]'); if(appAction){event.stopPropagation();await mutateApplication(appAction,ctx);return;}
    const fbAction=event.target.closest('[data-feedback-status]'); if(fbAction){event.stopPropagation();await mutateFeedback(fbAction,ctx);return;}
    const row=event.target.closest('[data-prt-detail]'); if(row) openPrtDetail(row.dataset.prtDetail,row.dataset.prtId,{testers:t,race:r,feedback:f},ctx);
  };
}
function renderApplications(rows){return panel('Tester Applications','PRT Intake',rows.length?`<div class="pm-table-wrap"><table class="pm-table"><thead><tr><th>Applicant</th><th>Role</th><th>Status</th><th>Submitted</th><th class="right">Action</th></tr></thead><tbody>${rows.map(row=>`<tr data-prt-detail="application" data-prt-id="${row.id}"><td data-label="Applicant"><strong>${esc(titleOf(row,'Applicant'))}</strong><small>${esc(row.email || row.discord || row.iracing_name || '—')}</small></td><td data-label="Role">${esc(row.role || 'Driver')}</td><td data-label="Status">${statusBadge(row.status || 'new')}</td><td data-label="Submitted">${esc(age(row.created_at || row.submitted_at))}</td><td data-label="Action" class="right"><div class="pm-row-actions"><button class="pm-button pm-button-ghost" data-app-status="hold" data-id="${row.id}">Hold</button><button class="pm-button pm-button-ghost" data-app-status="declined" data-id="${row.id}">Decline</button><button class="pm-button pm-button-primary" data-app-status="accepted" data-id="${row.id}">Accept</button></div></td></tr>`).join('')}</tbody></table></div>`:empty('No applications found.'))}
function renderTesters(rows){return panel('Tester Program','Early Access',rows.length?`<div class="pm-table-wrap"><table class="pm-table"><thead><tr><th>Tester</th><th>Invite</th><th>Tester state</th><th>Device</th><th>Last activity</th></tr></thead><tbody>${rows.map(row=>`<tr data-prt-detail="tester" data-prt-id="${row.id}"><td data-label="Tester"><strong>${esc(titleOf(row,'Tester'))}</strong><small>${esc(row.email || row.hub_email || '—')}</small></td><td data-label="Invite">${statusBadge(row.status)}</td><td data-label="Tester state">${statusBadge(row.tester_status)}</td><td data-label="Device">${esc(row.device_id || row.bound_device_id || 'Not bound')}</td><td data-label="Last activity">${esc(age(row.last_seen_at || row.redeemed_at || row.updated_at))}</td></tr>`).join('')}</tbody></table></div>`:empty('No tester invites found.'))}
function renderRace(rows){return panel("Founder’s Race","Competition",rows.length?`<div class="pm-table-wrap"><table class="pm-table"><thead><tr><th>Pos</th><th>Participant</th><th>Qualified</th><th>Pending</th><th>Flagged</th><th>Milestone</th></tr></thead><tbody>${rows.map(row=>`<tr data-prt-detail="founders" data-prt-id="${row.tester_id || row.id || ''}"><td data-label="Position"><strong>#${esc(row.position || '—')}</strong></td><td data-label="Participant"><strong>${esc(titleOf(row,'Participant'))}</strong><small>${esc(row.referral_code || '')}</small></td><td data-label="Qualified">${n(row.qualified)}</td><td data-label="Pending">${n(row.pending)}</td><td data-label="Flagged">${n(row.flagged)}</td><td data-label="Milestone">${statusBadge(row.milestone_status || row.milestone || 'racing')}</td></tr>`).join('')}</tbody></table></div>`:empty('No Founder’s Race participants yet.'),`<a class="pm-button pm-button-ghost" href="/control/founders-race">Full admin ↗</a>`)}
function renderFeedback(rows){return panel('Tester Feedback','Quality Loop',rows.length?`<div class="pm-table-wrap"><table class="pm-table"><thead><tr><th>Report</th><th>Kind</th><th>Severity</th><th>Status</th><th>Age</th><th class="right">Action</th></tr></thead><tbody>${rows.map(row=>`<tr data-prt-detail="feedback" data-prt-id="${row.id}"><td data-label="Report"><strong>${esc(row.title || row.summary || 'Feedback')}</strong><small>${esc(row.tester_name || row.reporter || row.email || '')}</small></td><td data-label="Kind">${esc(row.kind || row.type || 'feedback')}</td><td data-label="Severity">${statusBadge(row.severity || 'normal')}</td><td data-label="Status">${statusBadge(row.status || 'open')}</td><td data-label="Age">${esc(age(row.created_at))}</td><td data-label="Action" class="right"><div class="pm-row-actions"><button class="pm-button pm-button-ghost" data-feedback-status="reviewing" data-id="${row.id}">Reviewing</button><button class="pm-button pm-button-primary" data-feedback-status="resolved" data-id="${row.id}">Resolve</button></div></td></tr>`).join('')}</tbody></table></div>`:empty('No feedback reports found.'))}
async function mutateApplication(button,ctx){button.disabled=true;try{await api.setApplicationStatus(button.dataset.id,button.dataset.appStatus);clearCache('/api/control/ops');ctx.toast(`Application moved to ${button.dataset.appStatus}.`,'good');ctx.refresh();}catch(e){ctx.toast(e.message,'bad');button.disabled=false;}}
async function mutateFeedback(button,ctx){button.disabled=true;try{await api.setFeedbackStatus(button.dataset.id,button.dataset.feedbackStatus);clearCache('/api/control/ops');ctx.toast(`Feedback marked ${button.dataset.feedbackStatus}.`,'good');ctx.refresh();}catch(e){ctx.toast(e.message,'bad');button.disabled=false;}}
function openPrtDetail(kind,id,data,ctx){let row;if(kind==='application')row=(data.testers?.applications||[]).find(x=>String(x.id)===String(id));if(kind==='tester')row=(data.testers?.invites||[]).find(x=>String(x.id)===String(id));if(kind==='founders')row=(data.race?.leaderboard||[]).find(x=>String(x.tester_id||x.id)===String(id));if(kind==='feedback')row=(data.feedback?.items||[]).find(x=>String(x.id)===String(id));if(!row)return;ctx.openSheet({kicker:kind,title:titleOf(row,kind),body:`${details(Object.entries(row).filter(([k])=>!['notes','body','description'].includes(k)).slice(0,14))}${row.notes||row.body||row.description?`<div class="pm-detail-block"><h4>Details</h4><p>${esc(row.notes||row.body||row.description)}</p></div>`:''}`,actions:[{label:'Close',tone:'ghost',run:ctx.closeSheet}]});}

const CONTENT_TABS = ['generated','approval','approved','scheduled','published','archived','editorial'];

function selectedContentIds(ctx){
  return new Set((ctx.state.contentSelection || []).map(String));
}

function storeContentSelection(ctx, selected){
  ctx.state.contentSelection = [...selected];
}

function syncContentSelection(root, rows, ctx){
  const selected = selectedContentIds(ctx);
  root.querySelectorAll('[data-post-select]').forEach(input => {
    input.checked = selected.has(String(input.value));
    input.closest('.pm-content-select-row')?.classList.toggle('is-selected', input.checked);
  });
  const visible = rows.map(row => String(row.id));
  const selectedVisible = visible.filter(id => selected.has(id)).length;
  const selectAll = root.querySelector('[data-select-all]');
  if(selectAll){
    selectAll.checked = visible.length > 0 && selectedVisible === visible.length;
    selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
  }
  const count = root.querySelector('[data-selected-count]');
  if(count) count.textContent = String(selectedVisible);
  root.querySelectorAll('[data-bulk-action]').forEach(button => { button.disabled = selectedVisible === 0; });
}

function contentBulkBar(rows, selected){
  if(!rows.length) return '';
  const allSelected = rows.every(row => selected.has(String(row.id)));
  return `<div class="pm-bulk-bar">
    <label class="pm-bulk-select-all">
      <input type="checkbox" data-select-all ${allSelected ? 'checked' : ''}>
      <span>Select all</span>
    </label>
    <strong><span data-selected-count>${rows.filter(row => selected.has(String(row.id))).length}</span> selected</strong>
    <div class="pm-bulk-actions">
      <button class="pm-button pm-button-ghost" type="button" data-bulk-action="edit">Edit</button>
      <button class="pm-button pm-button-ghost" type="button" data-bulk-action="approve">Approve</button>
      <button class="pm-button pm-button-primary" type="button" data-bulk-action="publish">Publish</button>
      <button class="pm-button pm-button-danger" type="button" data-bulk-action="delete">Delete</button>
    </div>
  </div>`;
}

async function renderContent(root,ctx){
  const tab=ctx.state.contentTab||'generated';
  let rows=[];let editorial=[];
  try{
    if(tab==='editorial'){editorial=await api.blogDrafts();}
    else if(tab==='generated'){rows=await api.posts();}
    else if(tab==='approval'){rows=await api.posts('pending');}
    else if(tab==='archived'){const [a,b]=await Promise.all([api.posts('archived'),api.posts('rejected')]);rows=[...a,...b];}
    else{rows=await api.posts(tab);}
  }catch(e){root.innerHTML=moduleError('Content',e.message,'content');return;}

  const visibleIds=new Set(rows.map(row=>String(row.id)));
  const selected=selectedContentIds(ctx);
  for(const id of [...selected]) if(!visibleIds.has(id)) selected.delete(id);
  storeContentSelection(ctx,selected);

  const counts=rows.reduce((acc,row)=>{const s=low(row.status||'pending');acc[s]=(acc[s]||0)+1;return acc;},{});
  const labels={generated:'Pipeline',approval:'Needs Approval',approved:'Approved',scheduled:'Scheduled',published:'Published',archived:'Archived',editorial:'Editorial'};
  const countFor=(key)=>key==='generated'?rows.length:key==='approval'?(counts.pending||0):(counts[key]||0);
  const tabs=`<div class="pm-tabs pm-content-tabs">${CONTENT_TABS.map(key=>`<button class="pm-tab ${tab===key?'is-active':''}" type="button" data-content-tab="${key}"><span>${labels[key]||key}</span>${key!=='editorial'? `<b>${n(countFor(key))}</b>` : ''}</button>`).join('')}</div>`;
  root.innerHTML=`${viewHeader('Social Manager','Content Pipeline','See exactly what needs approval, what is ready, what Astra scheduled, and what already published.',`<button class="pm-button pm-button-primary" type="button" data-compose>New post</button>`)}${tabs}${tab==='editorial'?renderEditorial(editorial):(tab==='generated'?renderContentPipeline(rows,selected):renderPosts(rows,tab,selected))}`;

  root.onclick=(event)=>{
    const t=event.target.closest('[data-content-tab]');
    if(t){
      ctx.state.contentTab=t.dataset.contentTab;
      ctx.state.contentSelection=[];
      ctx.refresh();
      return;
    }
    if(event.target.closest('[data-compose]')){openComposer(ctx);return;}
    const action=event.target.closest('[data-bulk-action]');
    if(action){bulkContentAction(action.dataset.bulkAction,rows,ctx);return;}
    const p=event.target.closest('[data-post-id]');
    if(p)openPost(rows.find(x=>String(x.id)===p.dataset.postId),ctx);
    const b=event.target.closest('[data-blog-id]');
    if(b)openBlog(editorial.find(x=>String(x.id)===b.dataset.blogId),ctx);
  };
  root.onchange=(event)=>{
    const one=event.target.closest('[data-post-select]');
    if(one){
      const next=selectedContentIds(ctx);
      if(one.checked) next.add(String(one.value)); else next.delete(String(one.value));
      storeContentSelection(ctx,next);
      syncContentSelection(root,rows,ctx);
      return;
    }
    const all=event.target.closest('[data-select-all]');
    if(all){
      const next=selectedContentIds(ctx);
      for(const row of rows){
        const id=String(row.id);
        if(all.checked) next.add(id); else next.delete(id);
      }
      storeContentSelection(ctx,next);
      syncContentSelection(root,rows,ctx);
    }
  };
  syncContentSelection(root,rows,ctx);
}

function contentSourceLabel(row){
  const source=low(row?.source||'');
  if(source.startsWith('astra:')) return 'Astra';
  if(source.startsWith('firstparty:')) return 'First-party';
  if(source.startsWith('intelligence:')) return 'News';
  if(source.startsWith('dailycampaign:')) return 'Daily campaign';
  if(source==='control_center'||source==='manual') return 'Manual';
  return row?.source ? compact(row.source,24) : 'Unknown';
}

function contentStatusText(row){
  const status=low(row?.status||'pending');
  if(status==='scheduled') return row.scheduled_for ? `Scheduled ${dateText(row.scheduled_for)}` : 'Scheduled';
  if(status==='published') return `Published ${age(row.updated_at||row.created_at)}`;
  if(status==='approved') return 'Approved · ready';
  if(status==='rejected') return 'Rejected';
  if(status==='archived') return 'Archived';
  return 'Needs approval';
}

function pipelineSection(title,eyebrow,items,selected,emptyText){
  if(!items.length) return panel(title,eyebrow,empty(emptyText));
  return panel(title,eyebrow,`<div class="pm-row-list pm-content-row-list">${items.map(row=>`<div class="pm-content-select-row pm-content-status-${esc(low(row.status||'pending'))} ${selected.has(String(row.id))?'is-selected':''}">
    <label class="pm-content-check" title="Select post"><input type="checkbox" data-post-select value="${row.id}" ${selected.has(String(row.id))?'checked':''}><span aria-hidden="true"></span></label>
    <button class="pm-row" type="button" data-post-id="${row.id}">
      <div class="pm-row-main">
        <div class="pm-row-meta"><span class="pm-badge orange">${esc(row.platform||'social')}</span>${statusBadge(row.status)}<span class="pm-badge">${esc(contentSourceLabel(row))}</span>${row.media_url?'<span class="pm-badge">Media</span>':''}</div>
        <strong>${esc(row.title||compact(row.body,80)||'Generated post')}</strong>
        <p>${esc(compact(row.body,170))}</p>
      </div>
      <div class="pm-row-side"><strong class="pm-content-state-text">${esc(contentStatusText(row))}</strong><span>›</span></div>
    </button>
  </div>`).join('')}</div>`,`<span class="pm-badge">${n(items.length)}</span>`);
}

function renderContentPipeline(rows,selected=new Set()){
  const pending=rows.filter(r=>low(r.status)==='pending');
  const approved=rows.filter(r=>low(r.status)==='approved');
  const scheduled=rows.filter(r=>low(r.status)==='scheduled');
  const published=rows.filter(r=>low(r.status)==='published');
  const tools=contentBulkBar(rows,selected);
  return `<div class="pm-content-overview">
    <div class="pm-metric-strip">
      <button class="pm-metric pm-metric-action" type="button" data-content-tab="approval"><span>Needs approval</span><strong>${n(pending.length)}</strong><small>decision required</small><i>›</i></button>
      <button class="pm-metric pm-metric-action" type="button" data-content-tab="approved"><span>Approved</span><strong>${n(approved.length)}</strong><small>ready to schedule/publish</small><i>›</i></button>
      <button class="pm-metric pm-metric-action" type="button" data-content-tab="scheduled"><span>Scheduled</span><strong>${n(scheduled.length)}</strong><small>queued for publishing</small><i>›</i></button>
      <button class="pm-metric pm-metric-action" type="button" data-content-tab="published"><span>Published</span><strong>${n(published.length)}</strong><small>recent live posts</small><i>›</i></button>
    </div>
    <div class="pm-content-autonomy-note"><span class="pm-badge good">Low-risk auto scheduling active</span><p>Astra and Social Operations can schedule verified racing current-events, community engagement, and safe first-party Facebook, Instagram, and X content. Sensitive claims, offers, partner commitments, support/legal issues, and uncertain facts still stop for review.</p></div>
    ${tools}
    <div class="pm-grid pm-grid-2 pm-content-pipeline-grid">
      ${pipelineSection('Needs Approval','Decision Queue',pending.slice(0,8),selected,'Nothing is waiting for approval.')}
      ${pipelineSection('Scheduled','Publishing Queue',scheduled.slice(0,8),selected,'Nothing is scheduled right now.')}
      ${pipelineSection('Approved & Ready','Ready Queue',approved.slice(0,8),selected,'No approved posts are waiting.')}
      ${pipelineSection('Recently Published','Live History',published.slice(0,8),selected,'No recent published posts are in the working window.')}
    </div>
  </div>`;
}

function renderPosts(rows,tab,selected=new Set()){
  const tools=contentBulkBar(rows,selected);
  const title=tab==='approval'?'Needs Approval':tab==='approved'?'Approved & Ready':'Autopilot Posts';
  return panel(title,'Generated Social',
    `${tools}${rows.length?`<div class="pm-row-list pm-content-row-list">${rows.map(row=>`<div class="pm-content-select-row pm-content-status-${esc(low(row.status||'pending'))} ${selected.has(String(row.id))?'is-selected':''}">
      <label class="pm-content-check" title="Select post">
        <input type="checkbox" data-post-select value="${row.id}" ${selected.has(String(row.id))?'checked':''}>
        <span aria-hidden="true"></span>
      </label>
      <button class="pm-row" type="button" data-post-id="${row.id}">
        <div class="pm-row-main">
          <div class="pm-row-meta"><span class="pm-badge orange">${esc(row.platform||'social')}</span>${statusBadge(row.status)}<span class="pm-badge">${esc(contentSourceLabel(row))}</span>${row.media_url?'<span class="pm-badge">Media</span>':''}</div>
          <strong>${esc(row.title||compact(row.body,80)||'Generated post')}</strong>
          <p>${esc(compact(row.body,170))}</p>
        </div>
        <div class="pm-row-side"><strong class="pm-content-state-text">${esc(contentStatusText(row))}</strong><span>›</span></div>
      </button>
    </div>`).join('')}</div>`:empty('No posts in this view.')}`);
}

function renderEditorial(rows){return panel('Editorial','Blog & News',rows.length?`<div class="pm-row-list">${rows.map(row=>`<button class="pm-row" type="button" data-blog-id="${row.id}"><div class="pm-row-main"><div class="pm-row-meta"><span class="pm-badge">${esc(row.content_type||'article')}</span>${statusBadge(row.status)}</div><strong>${esc(row.title)}</strong><p>${esc(compact(String(row.body_html||'').replace(/<[^>]+>/g,' '),150))}</p></div><div class="pm-row-side"><span class="pm-muted">${esc(age(row.updated_at||row.created_at))}</span><span>›</span></div></button>`).join('')}</div>`:empty('No editorial drafts found.'))}

function openPost(row,ctx){
  if(!row)return;
  const titleId=`post-title-${row.id}`,bodyId=`post-body-${row.id}`;
  const status=low(row.status||'pending');
  const platform=low(row.platform||'social');
  const canLivePublish=['facebook','instagram','x'].includes(platform);
  const canGenerateMedia=['facebook','instagram','x','tiktok','tiktok_reels'].includes(platform);
  const actions=[
    {label:'Copy',tone:'ghost',run:async()=>{await navigator.clipboard.writeText(document.getElementById(bodyId)?.value||'');ctx.toast('Post copied.','good');}},
    {label:'Archive',tone:'ghost',run:()=>postDecision(row.id,'archive',ctx)},
  ];
  if(canGenerateMedia && status!=='published'&&status!=='archived'&&status!=='rejected'){
    actions.push({label:row.media_url?'Regenerate image':'Generate image',tone:'ghost',run:async()=>{
      const title=document.getElementById(titleId)?.value||row.title||'Pitmark Racing';
      const body=document.getElementById(bodyId)?.value||row.body||'';
      const result=await api.generateSocialImage({
        prompt:`Create a finished Pitmark Racing Co. social image for this post. Topic: ${title}. Post context: ${body}`,
        platform,
        content_type:row.content_type||'community',
        quality:'medium',
        add_to_library:true
      });
      await api.updatePost(row.id,{media_url:result.url});
      clearCache('/api/control/autopilot/posts');
      ctx.toast('Social image generated and attached.','good');
      ctx.closeSheet();
      ctx.refresh(true);
    }});
  }
  if(status!=='published'&&status!=='archived'&&status!=='rejected'){
    actions.push({label:'Save',tone:'ghost',run:async()=>{await api.updatePost(row.id,{title:document.getElementById(titleId)?.value||'',body:document.getElementById(bodyId)?.value||''});clearCache('/api/control/autopilot/posts');ctx.toast('Post updated.','good');ctx.closeSheet();ctx.refresh();}});
  }
  if(status==='pending'){
    actions.push({label:'Reject',tone:'danger',run:()=>postDecision(row.id,'reject',ctx)});
    actions.push({label:'Approve',tone:'primary',run:()=>postDecision(row.id,'approve',ctx)});
  }else if(['approved','scheduled'].includes(status)&&canLivePublish){
    actions.push({label:'Publish Now',tone:'primary',run:()=>publishPost(row,ctx)});
  }
  const publishNote=['approved','scheduled'].includes(status)&&!canLivePublish
    ? `<div class="pm-callout is-warn"><div><strong>Manual publishing required</strong><p>Live publishing is currently wired for Facebook, Instagram, and X. Copy this post for ${esc(row.platform||'this platform')}.</p></div></div>`
    : '';
  const mediaPreview=row.media_url
    ? `<div class="pm-detail-block"><h4>Attached media</h4><img src="${esc(row.media_url)}" alt="Attached social media" style="width:100%;max-height:420px;object-fit:contain;border-radius:12px;background:#080808"></div>`
    : (canGenerateMedia?'<div class="pm-callout"><div><strong>No image attached</strong><p>Generate one here and Control Center will attach a publish-safe JPEG to this post.</p></div></div>':'');
  ctx.openSheet({
    kicker:`${row.platform||'Social'} · ${row.status||'unknown'}`,
    title:row.title||'Generated post',
    body:`<div class="pm-form"><div class="pm-field"><label>Title</label><input class="pm-input" id="${titleId}" value="${esc(row.title||'')}"></div><div class="pm-field"><label>Post copy</label><textarea class="pm-textarea" id="${bodyId}" style="min-height:220px">${esc(row.body||'')}</textarea></div>${mediaPreview}${publishNote}${details([['Source',row.source],['Created',dateText(row.created_at)],['Scheduled',dateText(row.scheduled_for)],['Media',row.media_url||'None']])}</div>`,
    actions
  });
}

async function postDecision(id,action,ctx){try{await api.decidePost(id,action);clearCache('/api/control/autopilot/posts');if(action==='approve')ctx.state.contentTab='approved';ctx.toast(action==='approve'?'Post approved — ready to publish.':`Post ${action}d.`,'good');ctx.closeSheet();ctx.refresh();}catch(e){ctx.toast(e.message,'bad');}}
async function publishPost(row,ctx){try{const result=await api.publishPost(row.id);clearCache('/api/control/autopilot/posts');ctx.state.contentTab='published';ctx.toast(result?.warning?`Published live. ${result.warning}`:`Published live to ${row.platform||'social'}.`,'good');ctx.closeSheet();ctx.refresh();}catch(e){ctx.toast(e.message,'bad');}}

function selectedRows(rows,ctx){
  const selected=selectedContentIds(ctx);
  return rows.filter(row=>selected.has(String(row.id)));
}

async function runBulk(items,runner){
  let ok=0;const errors=[];
  for(const item of items){
    try{await runner(item);ok+=1;}catch(error){errors.push(error?.message||'Unknown error');}
  }
  return {ok,failed:errors.length,errors};
}

async function bulkContentAction(action,rows,ctx){
  const selected=selectedRows(rows,ctx);
  if(!selected.length){ctx.toast('Select at least one post first.','bad');return;}
  if(action==='edit'){openBulkEdit(selected,ctx);return;}

  if(action==='approve'){
    const eligible=selected.filter(row=>low(row.status)==='pending');
    if(!eligible.length){ctx.toast('None of the selected posts are waiting for approval.','bad');return;}
    const result=await runBulk(eligible,row=>api.decidePost(row.id,'approve'));
    clearCache('/api/control/autopilot/posts');
    ctx.state.contentSelection=[];
    ctx.state.contentTab='approved';
    ctx.toast(result.failed?`${result.ok} approved; ${result.failed} failed.`:`${result.ok} post${result.ok===1?'':'s'} approved.`,result.failed?'bad':'good');
    ctx.refresh();
    return;
  }

  if(action==='publish'){
    const eligible=selected.filter(row=>['approved','scheduled'].includes(low(row.status))&&['facebook','instagram','x'].includes(low(row.platform)));
    if(!eligible.length){ctx.toast('Select approved or scheduled Facebook, Instagram, or X posts to publish.','bad');return;}
    if(!window.confirm(`Publish ${eligible.length} selected post${eligible.length===1?'':'s'} live now?`))return;
    const result=await runBulk(eligible,row=>api.publishPost(row.id));
    clearCache('/api/control/autopilot/posts');
    ctx.state.contentSelection=[];
    ctx.state.contentTab='published';
    ctx.toast(result.failed?`${result.ok} published; ${result.failed} failed. ${result.errors[0]||''}`:`${result.ok} post${result.ok===1?'':'s'} published live.`,result.failed?'bad':'good');
    ctx.refresh();
    return;
  }

  if(action==='delete'){
    if(!window.confirm(`Permanently delete ${selected.length} selected post${selected.length===1?'':'s'}? This cannot be undone.`))return;
    const result=await runBulk(selected,row=>api.deletePost(row.id));
    clearCache('/api/control/autopilot/posts');
    ctx.state.contentSelection=[];
    ctx.toast(result.failed?`${result.ok} deleted; ${result.failed} failed.`:`${result.ok} post${result.ok===1?'':'s'} deleted.`,result.failed?'bad':'good');
    ctx.refresh();
  }
}

function openBulkEdit(rows,ctx){
  const findId='bulk-find',replaceId='bulk-replace',prependId='bulk-prepend',appendId='bulk-append',platformId='bulk-platform',titlesId='bulk-titles';
  ctx.openSheet({
    kicker:'Bulk Content Edit',
    title:`Edit ${rows.length} selected post${rows.length===1?'':'s'}`,
    body:`<div class="pm-form">
      <div class="pm-field"><label>Change platform</label><select class="pm-select" id="${platformId}"><option value="">Keep each post's platform</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="x">X</option><option value="tiktok">TikTok</option><option value="discord">Discord</option></select></div>
      <div class="pm-form-grid">
        <div class="pm-field"><label>Find text</label><input class="pm-input" id="${findId}" placeholder="Optional text to replace"></div>
        <div class="pm-field"><label>Replace with</label><input class="pm-input" id="${replaceId}" placeholder="Replacement text"></div>
      </div>
      <div class="pm-field"><label>Prepend to every post</label><textarea class="pm-textarea" id="${prependId}" style="min-height:80px" placeholder="Optional text added before each post"></textarea></div>
      <div class="pm-field"><label>Append to every post</label><textarea class="pm-textarea" id="${appendId}" style="min-height:80px" placeholder="Optional text added after each post"></textarea></div>
      <label class="pm-check-line"><input type="checkbox" id="${titlesId}"><span>Also apply find/replace to post titles</span></label>
      <div class="pm-callout"><div><strong>Safe bulk edit</strong><p>Blank fields leave that part unchanged. Prepend/append affects post copy only.</p></div></div>
    </div>`,
    actions:[
      {label:'Cancel',tone:'ghost',run:ctx.closeSheet},
      {label:'Apply to selected',tone:'primary',run:async()=>{
        const platform=document.getElementById(platformId)?.value||'';
        const find=document.getElementById(findId)?.value||'';
        const replace=document.getElementById(replaceId)?.value||'';
        const prepend=document.getElementById(prependId)?.value||'';
        const append=document.getElementById(appendId)?.value||'';
        const titles=Boolean(document.getElementById(titlesId)?.checked);
        if(!platform&&!find&&!prepend&&!append){ctx.toast('Choose at least one bulk edit.','bad');return;}
        const transform=(value)=>{
          let out=String(value||'');
          if(find) out=out.split(find).join(replace);
          return out;
        };
        const result=await runBulk(rows,row=>{
          const patch={};
          let body=transform(row.body||'');
          if(prepend) body=`${prepend}${body}`;
          if(append) body=`${body}${append}`;
          if(find||prepend||append) patch.body=body;
          if(platform) patch.platform=platform;
          if(titles&&find) patch.title=transform(row.title||'');
          return api.updatePost(row.id,patch);
        });
        clearCache('/api/control/autopilot/posts');
        ctx.state.contentSelection=[];
        ctx.toast(result.failed?`${result.ok} updated; ${result.failed} failed.`:`${result.ok} post${result.ok===1?'':'s'} updated.`,result.failed?'bad':'good');
        ctx.closeSheet();
        ctx.refresh();
      }}
    ]
  });
}

function openComposer(ctx){
  const topic='composer-topic',platform='composer-platform',body='composer-body',media='composer-media',preview='composer-media-preview';
  ctx.openSheet({
    kicker:'Autopilot Composer',
    title:'Create social content',
    body:`<div class="pm-form">
      <div class="pm-form-grid">
        <div class="pm-field"><label>Platform</label><select class="pm-select" id="${platform}"><option>facebook</option><option>instagram</option><option>x</option><option>tiktok</option><option>discord</option></select></div>
        <div class="pm-field"><label>Goal</label><select class="pm-select" id="composer-goal"><option value="community">Community / engagement</option><option value="authority">Current event / authority</option><option value="education">Education</option><option value="product">Product</option></select></div>
      </div>
      <div class="pm-field"><label>Topic / prompt</label><textarea class="pm-textarea" id="${topic}" placeholder="What should Pitmark talk about?"></textarea></div>
      <div class="pm-field"><label>Generated copy</label><textarea class="pm-textarea" id="${body}" placeholder="Generate first, then edit here."></textarea></div>
      <input type="hidden" id="${media}" value="">
      <div id="${preview}" class="pm-detail-block" hidden><h4>Generated social image</h4><img alt="Generated social image" style="width:100%;max-height:420px;object-fit:contain;border-radius:12px;background:#080808"></div>
    </div>`,
    actions:[
      {label:'Generate copy',tone:'ghost',run:async()=>{
        try{
          const result=await api.compose({platform:document.getElementById(platform).value,goal:document.getElementById('composer-goal').value,topic:document.getElementById(topic).value,prompt:document.getElementById(topic).value,tone:'pitmark',use_context:true});
          document.getElementById(body).value=result.body||'';
          ctx.toast('Copy generated.','good');
        }catch(e){ctx.toast(e.message,'bad');}
      }},
      {label:'Generate image',tone:'ghost',run:async()=>{
        try{
          const p=document.getElementById(platform).value;
          if(p==='discord'){ctx.toast('Discord does not need a generated social image.','bad');return;}
          const promptText=document.getElementById(topic).value||document.getElementById(body).value;
          if(!promptText.trim()){ctx.toast('Add a topic or generate copy first.','bad');return;}
          const result=await api.generateSocialImage({prompt:`Create a finished Pitmark Racing Co. social image for: ${promptText}. Use the supplied topic as the source of truth and do not invent identities, results, car numbers, sponsors, or track details.`,platform:p,content_type:document.getElementById('composer-goal').value,quality:'medium',add_to_library:true});
          document.getElementById(media).value=result.url||'';
          const box=document.getElementById(preview);const img=box?.querySelector('img');
          if(box&&img){img.src=result.url;box.hidden=false;}
          ctx.toast('Publish-safe social image generated.','good');
        }catch(e){ctx.toast(e.message,'bad');}
      }},
      {label:'Save to queue',tone:'primary',run:async()=>{
        try{
          const goal=document.getElementById('composer-goal').value;
          await api.savePost({platform:document.getElementById(platform).value,title:compact(document.getElementById(topic).value,160),body:document.getElementById(body).value,content_type:goal,source:'control_center',risk:'low',media_url:document.getElementById(media).value||null});
          clearCache('/api/control/autopilot/posts');
          ctx.toast(goal==='community'||goal==='authority'?'Post saved. Low-risk automation may schedule it automatically.':'Post saved to the content queue.','good');
          ctx.closeSheet();
          ctx.refresh();
        }catch(e){ctx.toast(e.message,'bad');}
      }}
    ]
  });
}
function openBlog(row,ctx){if(!row)return;ctx.openSheet({kicker:`Editorial · ${row.status||'draft'}`,title:row.title,body:`${details([['Type',row.content_type],['Status',row.status],['Updated',dateText(row.updated_at)],['Scheduled',dateText(row.scheduled_for)]])}<div class="pm-detail-block"><h4>Draft</h4><p>${esc(String(row.body_html||'').replace(/<[^>]+>/g,' '))}</p></div>`,actions:[{label:'Archive',tone:'ghost',run:async()=>{await api.decideBlog(row.id,'archive');clearCache('/api/control/blog/drafts');ctx.toast('Draft archived.','good');ctx.closeSheet();ctx.refresh();}},{label:'Approve',tone:'primary',run:async()=>{await api.decideBlog(row.id,'approve');clearCache('/api/control/blog/drafts');ctx.toast('Draft approved.','good');ctx.closeSheet();ctx.refresh();}}]});}

async function renderPartnerships(root,ctx){let rows;try{rows=await api.outreach();}catch(e){root.innerHTML=moduleError('Relationships',e.message,'partnerships');return;}const stages=rows.reduce((a,r)=>(a[low(r.stage)||'unknown']=(a[low(r.stage)||'unknown']||0)+1,a),{});root.innerHTML=`${viewHeader('Relationship Operations','Partnerships','A lightweight operating CRM for tracks, leagues, partners, broadcasters, and opportunities.')}<div class="pm-metric-strip"><div class="pm-metric"><span>Total relationships</span><strong>${n(rows.length)}</strong><small>tracked records</small></div><div class="pm-metric"><span>Prospects</span><strong>${n(stages.prospect||stages.new)}</strong><small>early-stage relationships</small></div><div class="pm-metric"><span>Active</span><strong>${n(stages.active||stages.partner)}</strong><small>active relationships</small></div><div class="pm-metric"><span>Waiting</span><strong>${n(stages.waiting)}</strong><small>pending next move</small></div><div class="pm-metric"><span>Follow-ups</span><strong>${n(rows.filter(r=>r.next_follow_up).length)}</strong><small>next action recorded</small></div></div>${panel('Relationship Pipeline','Real-world + sim network',rows.length?`<div class="pm-table-wrap"><table class="pm-table"><thead><tr><th>Organization / person</th><th>Type</th><th>Stage</th><th>Support</th><th>Next follow-up</th></tr></thead><tbody>${rows.map(r=>`<tr data-outreach-id="${r.id}"><td data-label="Organization / person"><strong>${esc(r.organization||r.name)}</strong><small>${esc(r.organization?r.name:'')}</small></td><td data-label="Type">${esc(r.contact_type||'Other')}</td><td data-label="Stage">${statusBadge(r.stage)}</td><td data-label="Support">${esc(r.supporter_status||'—')}</td><td data-label="Next follow-up">${esc(r.next_follow_up||'—')}</td></tr>`).join('')}</tbody></table></div>`:empty('No relationship records found.'))}`;root.onclick=(e)=>{const tr=e.target.closest('[data-outreach-id]');if(tr)openRelationship(rows.find(r=>String(r.id)===tr.dataset.outreachId),ctx);};}
function openRelationship(row,ctx){if(!row)return;const stage=`rel-stage-${row.id}`,follow=`rel-follow-${row.id}`,notes=`rel-notes-${row.id}`;ctx.openSheet({kicker:row.contact_type||'Relationship',title:row.organization||row.name,body:`${details([['Contact',row.name],['Stage',row.stage],['Supporter state',row.supporter_status],['Contact channel',row.email||'Not recorded']])}<div class="pm-form"><div class="pm-form-grid"><div class="pm-field"><label>Stage</label><input class="pm-input" id="${stage}" value="${esc(row.stage||'')}"></div><div class="pm-field"><label>Next follow-up</label><input class="pm-input" id="${follow}" value="${esc(row.next_follow_up||'')}"></div></div><div class="pm-field"><label>Notes</label><textarea class="pm-textarea" id="${notes}">${esc(row.notes||'')}</textarea></div></div>`,actions:[{label:'Save relationship',tone:'primary',run:async()=>{await api.updateOutreach(row.id,{stage:document.getElementById(stage).value,next_follow_up:document.getElementById(follow).value,notes:document.getElementById(notes).value});clearCache('/api/control/outreach');ctx.toast('Relationship updated.','good');ctx.closeSheet();ctx.refresh();}}]});}

async function renderStore(root,ctx){
  const [overviewResult,...workResults]=await Promise.allSettled([
    api.storeOverview({maxAge:ctx.force?0:12000}),
    ...['active','waiting','monitoring','roadmap'].map(v=>api.work(v))
  ]);
  const overview=overviewResult.status==='fulfilled'?overviewResult.value:null;
  const all=workResults.filter(x=>x.status==='fulfilled').flatMap(x=>x.value.items||[]);
  const unique=[...new Map(all.map(i=>[i.row_number,i])).values()];
  const rows=unique.filter(i=>/(store|brand|web|commerce|shopify|merchant|tiktok shop|product|collection|pricing|sale|gmc)/i.test(`${i.area} ${i.task} ${i.next_action||''} ${i.notes||''}`));
  const commerce=overview?.commerce||{};
  const connection=commerce.connection||{};
  const products=commerce.products||{};
  const collections=commerce.collections||{};
  const orders=commerce.orders||{};
  const content=overview?.content||{};
  const latest=orders.latest||null;
  const productItems=(products.items||[]).slice(0,6);
  const collectionItems=(collections.items||[]).slice(0,8);
  const firstSaleState=orders.has_sale===true?'Sale recorded':orders.has_sale===false?'First sale still open':'Order visibility unavailable';
  const productBody=productItems.length?`<div class="pm-row-list">${productItems.map(p=>`<a class="pm-row" href="https://pitmarkracing.com/products/${encodeURIComponent(p.handle||'')}" target="_blank" rel="noopener"><div class="pm-row-main"><div class="pm-row-meta">${statusBadge(p.status||'active')}<span class="pm-badge">${p.price?'$'+esc(p.price):'Store product'}</span></div><strong>${esc(p.title||'Untitled product')}</strong><p>Updated ${esc(dateText(p.updated_at))}</p></div><div class="pm-row-side"><span>Open ↗</span></div></a>`).join('')}</div>`:empty(products.error?'Products could not be loaded from Shopify.':'No recent products returned.');
  const collectionBody=collectionItems.length?`<div class="pm-row-list">${collectionItems.map(x=>`<a class="pm-row" href="https://pitmarkracing.com/collections/${encodeURIComponent(x.handle||'')}" target="_blank" rel="noopener"><div class="pm-row-main"><div class="pm-row-meta"><span class="pm-badge orange">Collection</span><span class="pm-badge">${n(x.product_count)} products</span></div><strong>${esc(x.title||'Collection')}</strong><p>Updated ${esc(dateText(x.updated_at))}</p></div><div class="pm-row-side"><span>Open ↗</span></div></a>`).join('')}</div>`:empty(collections.error?'Collections could not be loaded from Shopify.':'No collections returned.');
  const blockerRows=rows.filter(i=>/(merchant|tiktok shop|pricing|sale|conversion|checkout|product|store|shopify|website|homepage|collection)/i.test(`${i.area} ${i.task} ${i.next_action||''}`)).slice(0,8);
  root.innerHTML=`
    ${viewHeader('Commerce Operations','Store & Brand','Operate the storefront, product catalog, conversion work, and brand launches from one place.',`<a class="pm-button pm-button-ghost" href="https://pitmarkracing.com" target="_blank" rel="noopener">Open Store ↗</a>`)}
    <section class="pm-brief"><div><span class="eyebrow">REVENUE PULSE</span><h2>${esc(firstSaleState)}</h2><p>${latest?esc(`Latest Shopify order ${latest.name||''} · ${latest.financial_status||'status unknown'}`):'Keep the page focused on trust, traffic, and conversion until the first customer order lands.'}</p></div><div class="pm-brief-meta"><span class="pm-badge ${connection.authenticated?'good':'warn'}">Shopify ${connection.authenticated?'live':'check connection'}</span></div></section>
    <div class="pm-metric-strip">
      <div class="pm-metric"><span>Recent products</span><strong>${n(products.count)}</strong><small>${products.has_more?'12 newest shown':'catalog snapshot'}</small></div>
      <div class="pm-metric"><span>Collections</span><strong>${n(collections.count)}</strong><small>${collections.has_more?'20 newest shown':'live Shopify'}</small></div>
      <div class="pm-metric"><span>Product content</span><strong>${n(content.product_posts)}</strong><small>pending / approved / scheduled</small></div>
      <div class="pm-metric"><span>Content approvals</span><strong>${n(content.pending_posts)}</strong><small>all pending social posts</small></div>
      <div class="pm-metric"><span>Commerce work</span><strong>${n(rows.length)}</strong><small>Master Checklist matches</small></div>
    </div>
    <div class="pm-grid pm-grid-2">
      ${panel('Conversion & First-Sale Work','Revenue Operations',blockerRows.length?`<div class="pm-row-list">${blockerRows.map(workRow).join('')}</div>`:empty('No current commerce blocker is recorded. Use this page to keep first-sale work visible.'),'<button class="pm-button pm-button-ghost" type="button" data-store-go-content>Open Content</button>')}
      ${panel('Store Health','Shopify',details([
        ['Authentication',connection.authenticated?'Connected':'Needs attention'],
        ['Shop',connection.shop_name||'Pitmark Racing Co.'],
        ['API',connection.api_version||'—'],
        ['First sale',firstSaleState],
        ['Editorial drafts',n(content.blog_drafts)]
      ])+(connection.error?`<div class="pm-callout is-warn"><div><strong>Shopify needs attention</strong><p>${esc(connection.error)}</p></div></div>`:''))}
    </div>
    <div class="pm-grid pm-grid-2 pm-hq-lower">
      ${panel('Recent Products','Merchandising',productBody,`<a class="pm-button pm-button-ghost" href="https://pitmarkracing.com/collections/all" target="_blank" rel="noopener">Shop All ↗</a>`)}
      ${panel('Collections','Campaign Surfaces',collectionBody,'')}
    </div>
    ${panel('Store & Brand Work','Master Checklist',rows.length?`<div class="pm-row-list">${rows.map(workRow).join('')}</div>`:empty('No other Store & Brand work is open right now.'),`<span class="pm-badge">${n(rows.length)} tracked</span>`)}
  `;
  root.onclick=(e)=>{
    if(e.target.closest('[data-store-go-content]')){ctx.state.contentTab='generated';ctx.navigate('content');return;}
    const row=e.target.closest('[data-open-work]');if(row)openWorkItem(rows.find(i=>String(i.row_number)===row.dataset.openWork),ctx);
  };
}

async function renderPeople(root,ctx){const [testersResult,outreachResult,raceResult]=await Promise.allSettled([api.prtTesters(),api.outreach(),api.foundersRace()]);const testers=testersResult.status==='fulfilled'?(testersResult.value.invites||[]):[];const outreach=outreachResult.status==='fulfilled'?outreachResult.value:[];const race=raceResult.status==='fulfilled'?(raceResult.value.leaderboard||[]):[];root.innerHTML=`${viewHeader('Pitmark Network','People','Testers and relationship contacts without duplicating their source systems.')}<div class="pm-grid pm-grid-2">${panel('PRT Testers','Product Community',testers.length?`<div class="pm-row-list">${testers.slice(0,30).map(r=>`<div class="pm-row"><div class="pm-row-main"><strong>${esc(titleOf(r,'Tester'))}</strong><p>${esc(r.email||r.hub_email||'')} · ${esc(r.tester_status||r.status||'unknown')}</p></div><div class="pm-row-side">${statusBadge(r.status)}</div></div>`).join('')}</div>`:empty('No testers loaded.'))}${panel('Relationships','Business Network',outreach.length?`<div class="pm-row-list">${outreach.slice(0,30).map(r=>`<div class="pm-row"><div class="pm-row-main"><strong>${esc(r.organization||r.name)}</strong><p>${esc(r.contact_type||'Other')} · ${esc(r.stage||'unknown')}</p></div><div class="pm-row-side">${statusBadge(r.stage)}</div></div>`).join('')}</div>`:empty('No relationships loaded.'))}</div>${panel("Founder’s Race",'Community Competition',race.length?`<div class="pm-row-list">${race.slice(0,12).map(r=>`<div class="pm-row"><div class="pm-row-main"><strong>#${esc(r.position||'—')} ${esc(titleOf(r,'Participant'))}</strong><p>${n(r.qualified)} qualified · ${n(r.pending)} pending referrals</p></div><div class="pm-row-side"><span class="pm-badge orange">${esc(r.referral_code||'Racing')}</span></div></div>`).join('')}</div>`:empty('No race participants loaded.'))}`;}

function renderCommandBrief(brief){
  const sections=brief?.sections||{};
  const important=[...(sections.critical||[]),...(sections.action||[]),...(sections.opportunities||[])].slice(0,6);
  const counts=brief?.counts||{};
  const countLine=[
    Number(counts.critical||0)?`${counts.critical} critical`:'',
    Number(counts.action||0)?`${counts.action} action`:'',
    Number(counts.opportunities||0)?`${counts.opportunities} opportunities`:'',
  ].filter(Boolean).join(' · ');
  return `<div class="pm-command-summary">
    <div class="pm-command-head"><strong>${esc(brief?.headline||'Pitmark operating brief')}</strong>${countLine?`<span>${esc(countLine)}</span>`:''}</div>
    ${important.length?`<div class="pm-row-list">${important.map(item=>`<div class="pm-row"><div class="pm-row-main"><div class="pm-row-meta">${statusBadge(item.priority||'info')}<span class="pm-badge">${esc(item.module||'Pitmark')}</span></div><strong>${esc(item.title||'Operational item')}</strong><p>${esc(compact(item.detail||'',150))}</p></div></div>`).join('')}</div>`:'<div class="pm-empty">Nothing needs attention right now.</div>'}
  </div>`;
}

async function renderSystems(root,ctx){
  const [statusResult,briefResult,notifyResult,hqResult,workspaceResult]=await Promise.allSettled([
    api.status(),api.brief(),api.notifications(),api.hq(),api.workspaceStatus()
  ]);
  const status=statusResult.status==='fulfilled'?statusResult.value:null;
  const brief=briefResult.status==='fulfilled'?briefResult.value:null;
  const notificationPayload=notifyResult.status==='fulfilled'?notifyResult.value:null;
  const notifications=Array.isArray(notificationPayload)?notificationPayload:(notificationPayload?.items||[]);
  const systemModule=hqResult.status==='fulfilled'?unwrap(hqResult.value?.modules?.systems):null;
  const workspace=workspaceResult.status==='fulfilled'?workspaceResult.value:null;
  const workspaceBody=workspace
    ? `<div class="pm-detail-list">
        <div class="pm-detail-pair"><span>Status</span><strong>${workspace.connected?'Connected':'Needs authorization'}</strong></div>
        <div class="pm-detail-pair"><span>Source</span><strong>Pitmark Master Checklist</strong></div>
        <div class="pm-detail-pair"><span>Credential</span><strong>${esc(workspace.credential_source||'none')}</strong></div>
      </div>
      ${workspace.error?`<div class="pm-callout is-warn"><div><strong>Google Sheets is not available to Pitmark Cloud</strong><p>${esc(workspace.error)}</p></div></div>`:''}
      ${workspace.connected
        ? '<div class="pm-callout"><div><strong>Master Checklist live</strong><p>Work, HQ priorities, waiting items, recent progress, and Work Momentum can read and update the Google Sheet.</p></div></div>'
        : '<button class="pm-button pm-button-primary" type="button" data-workspace-connect>Connect Google Sheets</button>'}`
    : moduleError('Google Sheets',workspaceResult.reason?.message||'Connection status unavailable.');
  root.innerHTML=`${viewHeader('Platform Operations','Systems','Human-readable Pitmark Cloud health and current operating signals.')}
    <div class="pm-grid pm-grid-2">
      ${panel('Pitmark Cloud','Runtime',status?`${details([['Version',systemModule?.app_version||'—'],['Environment',systemModule?.environment||'—'],['Autopilot service',status.autopilot?'Available':'Unavailable'],['Outreach records',status.outreach_contacts],['Blog drafts',status.blog_drafts]])}`:moduleError('Status',statusResult.reason?.message))}
      ${panel('Google Sheets','Workspace',workspaceBody)}
    </div>
    <div class="pm-grid pm-grid-2 pm-hq-lower">
      ${panel('Command Brief','Operations',brief?renderCommandBrief(brief):moduleError('Command brief',briefResult.reason?.message))}
      ${panel('Signals','Notifications',notifications.length?`<div class="pm-row-list">${notifications.slice(0,8).map(r=>`<div class="pm-row"><div class="pm-row-main"><strong>${esc(r.title||r.module||'Signal')}</strong><p>${esc(compact(r.detail||r.reason||'',120))}</p></div><div class="pm-row-side">${statusBadge(r.priority||r.status||'info')}</div></div>`).join('')}</div>`:empty('No current operational signals.'))}
    </div>`;
  root.onclick=(event)=>{
    if(event.target.closest('[data-workspace-connect]')) openWorkspaceConnect(ctx);
  };
}

async function openWorkspaceConnect(ctx){
  let popup=null;
  try{
    popup=window.open('about:blank','pitmark-google-sheets');
    const start=await api.workspaceOAuthStart();
    if(popup) popup.location.href=start.authorization_url;
    else window.open(start.authorization_url,'_blank','noopener');
    const inputId='workspace-oauth-callback';
    ctx.openSheet({
      kicker:'Google Workspace',
      title:'Connect Pitmark Master Checklist',
      body:`<div class="pm-form">
        <div class="pm-callout"><div><strong>One-time Google authorization</strong><p>Sign in as justin@pitmarkracing.com and approve Google Sheets access. Google will then try to open ${esc(start.redirect_uri)}. That localhost page may say it cannot connect — that is expected.</p></div></div>
        <div class="pm-detail-block"><h4>Finish the connection</h4><p>On the localhost error page, copy the full URL from the browser address bar. Return here and paste it below. Pitmark Cloud will exchange the one-time code securely; the Google refresh token is encrypted in the Pitmark database and is never shown in Control Center.</p></div>
        <div class="pm-field"><label>Google localhost callback URL</label><textarea class="pm-textarea" id="${inputId}" style="min-height:110px" placeholder="http://127.0.0.1:8765/?state=...&code=..."></textarea></div>
      </div>`,
      actions:[
        {label:'Cancel',tone:'ghost',run:ctx.closeSheet},
        {label:'Complete connection',tone:'primary',run:async()=>{
          const callbackUrl=document.getElementById(inputId)?.value?.trim()||'';
          if(!callbackUrl){ctx.toast('Paste the full Google localhost callback URL first.','bad');return;}
          const result=await api.workspaceOAuthComplete(callbackUrl);
          clearCache('/api/control/hq/overview');
          clearCache('/api/control/work');
          ctx.toast(result?.connected?'Google Sheets connected. Master Checklist is live.':'Google Sheets connection needs attention.',result?.connected?'good':'bad');
          ctx.closeSheet();
          ctx.refresh(true);
        }}
      ]
    });
  }catch(e){
    try{popup?.close();}catch{}
    ctx.toast(e.message||'Google Sheets connection could not start.','bad');
  }
}

async function renderInsights(root,ctx){const payload=await api.hq();const m=payload.modules||{};const work=unwrap(m.work)||{};const prt=unwrap(m.prt)||{};const content=unwrap(m.content)||{};const rel=unwrap(m.relationships)||{};const s=work.summary||{};root.innerHTML=`${viewHeader('Operating Intelligence','Insights','Current operational momentum from real Pitmark sources—not vanity metrics.')}<div class="pm-metric-strip"><div class="pm-metric"><span>Open work</span><strong>${n(s.open)}</strong><small>${n(s.p1)} P1 · ${n(s.blocked)} blocked</small></div><div class="pm-metric"><span>Completed</span><strong>${n(s.completed)}</strong><small>Master Checklist history</small></div><div class="pm-metric"><span>PRT testers</span><strong>${n(prt.testers?.redeemed)}</strong><small>${n(prt.applications?.new)} new applications</small></div><div class="pm-metric"><span>Content queue</span><strong>${n(content.autopilot?.pending)}</strong><small>${n(content.autopilot?.scheduled)} scheduled</small></div><div class="pm-metric"><span>Relationships</span><strong>${n(rel.total)}</strong><small>${n(rel.waiting_follow_up)} follow-ups</small></div></div><div class="pm-grid pm-grid-2">${panel('Work Momentum','Source of Truth',`<div class="pm-pulse-grid"><div class="pm-pulse"><header><span>Active</span></header><strong>${n(s.active)}</strong><p>currently moving</p></div><div class="pm-pulse"><header><span>Monitoring</span></header><strong>${n(s.monitoring)}</strong><p>being watched</p></div><div class="pm-pulse"><header><span>Waiting</span></header><strong>${n(s.waiting)}</strong><p>external dependencies</p></div><div class="pm-pulse"><header><span>Roadmap</span></header><strong>${n(s.roadmap)}</strong><p>future work</p></div></div>`)}${panel('Growth Activity','Operational Snapshot',`<div class="pm-detail-list"><div class="pm-detail-pair"><span>Founder’s Race pending</span><strong>${n(prt.founders_race?.pending)}</strong></div><div class="pm-detail-pair"><span>PRT feedback</span><strong>${n(prt.feedback?.open??prt.feedback?.total)}</strong></div><div class="pm-detail-pair"><span>Editorial drafts</span><strong>${n(content.editorial?.drafts)}</strong></div><div class="pm-detail-pair"><span>Published social</span><strong>${n(content.autopilot?.published)}</strong></div></div>`)}</div>`;}

export async function renderDomain(domain, root, ctx) {
  root.onclick = null;
  root.innerHTML = `<div class="pm-view-skeleton"><div class="pm-skeleton pm-skeleton-line wide"></div><div class="pm-skeleton-grid"><div class="pm-skeleton block"></div><div class="pm-skeleton block"></div><div class="pm-skeleton block"></div></div></div>`;
  try {
    if (domain === 'hq') return await renderHQ(root,ctx);
    if (domain === 'work') return await renderWork(root,ctx);
    if (domain === 'prt') return await renderPRT(root,ctx);
    if (domain === 'partnerships') return await renderPartnerships(root,ctx);
    if (domain === 'content') return await renderContent(root,ctx);
    if (domain === 'store') return await renderStore(root,ctx);
    if (domain === 'people') return await renderPeople(root,ctx);
    if (domain === 'systems') return await renderSystems(root,ctx);
    if (domain === 'insights') return await renderInsights(root,ctx);
    throw new Error(`Unknown Pitmark operating area: ${domain}`);
  } catch (error) {
    if (error?.name === 'AbortError') return;
    root.innerHTML = `${viewHeader('Control Center','This workspace hit a problem.','Other Pitmark areas are still available.')} ${moduleError(DOMAIN_META[domain]?.title || domain,error?.message || String(error),domain)}`;
    root.onclick = (event) => { if (event.target.closest('[data-retry]')) ctx.refresh(true); };
  }
}
