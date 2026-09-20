import { api, abortScope, clearCache } from './control-center-api.js?v=20260920standings1';
import { DOMAIN_META, renderDomain } from './control-center-views.js?v=20260920standings1';

const VALID_DOMAINS = new Set(Object.keys(DOMAIN_META));
const root = document.getElementById('pitmark-control');
const workspace = document.getElementById('workspace');
const viewRoot = document.getElementById('view-root');
const pageTitle = document.getElementById('page-title');
const pageKicker = document.getElementById('page-kicker');
const pageContext = document.getElementById('page-context');
const mobilePageTitle = document.getElementById('mobile-page-title');
const mobilePageKicker = document.getElementById('mobile-page-kicker');
const commandPalette = document.getElementById('command-palette');
const commandInput = document.getElementById('command-input');
const commandResults = document.getElementById('command-results');
const detailLayer = document.getElementById('detail-sheet');
const sheetKicker = document.getElementById('sheet-kicker');
const sheetTitle = document.getElementById('sheet-title');
const sheetBody = document.getElementById('sheet-body');
const sheetActions = document.getElementById('sheet-actions');
const moreLayer = document.getElementById('more-sheet');
const accountPopover = document.getElementById('account-popover');
const toastRegion = document.getElementById('toast-region');
const refreshButton = document.getElementById('refresh-view');
const accountButton = document.getElementById('account-menu');
const logoutButton = document.getElementById('logout-button');

const state = {
  domain: domainFromLocation(),
  workView: 'now',
  prtTab: 'applications',
  contentTab: 'generated',
};

let renderSequence = 0;
let commandTimer = 0;
let commandSequence = 0;
let sheetActionRunning = false;
let initialized = false;

function domainFromLocation() {
  const raw = (location.hash || '').replace(/^#/, '').split(/[/?]/)[0].toLowerCase();
  return VALID_DOMAINS.has(raw) ? raw : 'hq';
}

function setDocumentState(domain) {
  const meta = DOMAIN_META[domain] || DOMAIN_META.hq;
  root.dataset.activeDomain = domain;
  pageTitle.textContent = meta.title;
  pageKicker.textContent = meta.kicker;
  pageContext.textContent = meta.context;
  if (mobilePageTitle) mobilePageTitle.textContent = meta.title;
  if (mobilePageKicker) mobilePageKicker.textContent = meta.kicker;
  document.title = `${meta.title} · Pitmark Control Center`;

  document.querySelectorAll('[data-domain]').forEach((button) => {
    button.classList.toggle('is-active', button.dataset.domain === domain);
    if (button.matches('.pm-nav-item, #mobile-nav button')) {
      button.setAttribute('aria-current', button.dataset.domain === domain ? 'page' : 'false');
    }
  });
}

function closeTransientNavigation() {
  moreLayer.hidden = true;
  accountPopover.hidden = true;
}

export function navigate(domain, options = {}) {
  if (!VALID_DOMAINS.has(domain)) return;
  if (options.workRow && domain === 'work') state.workView = state.workView || 'now';
  closeTransientNavigation();
  const nextHash = `#${domain}`;
  if (location.hash !== nextHash) {
    history.pushState({ domain }, '', nextHash);
  }
  state.domain = domain;
  setDocumentState(domain);
  renderCurrent(false).then(() => {
    if (options.workRow && domain === 'work') {
      setTimeout(() => document.querySelector(`[data-open-work="${CSS.escape(String(options.workRow))}"]`)?.click(), 0);
    }
  });
}

async function renderCurrent(force = false) {
  const sequence = ++renderSequence;
  const domain = state.domain;
  setDocumentState(domain);
  refreshButton.disabled = true;
  refreshButton.innerHTML = '<span class="pm-spinner"></span><span class="pm-hide-small">Loading</span>';
  try {
    await renderDomain(domain, viewRoot, {
      state,
      force,
      navigate,
      refresh: (hard = false) => renderCurrent(Boolean(hard)),
      openSheet,
      closeSheet,
      toast,
    });
    if (sequence !== renderSequence) return;
    workspace?.focus({ preventScroll: true });
    workspace?.scrollTo({ top: 0, behavior: 'instant' });
  } finally {
    if (sequence === renderSequence) {
      refreshButton.disabled = false;
      refreshButton.innerHTML = '<span>↻</span><span class="pm-hide-small">Refresh</span>';
    }
  }
}

function buttonTone(tone) {
  if (tone === 'primary') return 'pm-button-primary';
  if (tone === 'danger') return 'pm-button-danger';
  return 'pm-button-ghost';
}

export function openSheet({ kicker = 'Details', title = 'Item', body = '', actions = [] } = {}) {
  sheetKicker.textContent = kicker;
  sheetTitle.textContent = title;
  sheetBody.innerHTML = body;
  sheetActions.innerHTML = '';
  for (const action of actions) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `pm-button ${buttonTone(action.tone)}`;
    button.textContent = action.label || 'Action';
    button.addEventListener('click', async () => {
      if (sheetActionRunning) return;
      sheetActionRunning = true;
      const buttons = [...sheetActions.querySelectorAll('button')];
      buttons.forEach((node) => { node.disabled = true; });
      try {
        await action.run?.();
      } catch (error) {
        toast(error?.message || 'That action could not be completed.', 'bad');
      } finally {
        sheetActionRunning = false;
        buttons.forEach((node) => { node.disabled = false; });
      }
    });
    sheetActions.appendChild(button);
  }
  detailLayer.hidden = false;
  document.body.dataset.sheetOpen = 'true';
  setTimeout(() => detailLayer.querySelector('button, input, textarea, select, a')?.focus(), 0);
}

export function closeSheet() {
  detailLayer.hidden = true;
  document.body.removeAttribute('data-sheet-open');
  sheetBody.innerHTML = '';
  sheetActions.innerHTML = '';
}

export function toast(message, tone = '') {
  const node = document.createElement('div');
  node.className = `pm-toast ${tone || ''}`;
  node.textContent = message;
  toastRegion.appendChild(node);
  setTimeout(() => node.remove(), 3800);
}

function openCommand() {
  commandPalette.hidden = false;
  commandInput.value = '';
  commandResults.innerHTML = '<div class="pm-command-empty">Search work, testers, partners, content, and Pitmark systems.</div>';
  setTimeout(() => commandInput.focus(), 0);
}

function closeCommand() {
  commandPalette.hidden = true;
  commandInput.value = '';
  commandResults.innerHTML = '';
  abortScope('search');
}

function resultIcon(kind) {
  return ({ work:'✓', application:'P', tester:'P', founders_race:'🏁', relationship:'↔', social_post:'▤', editorial:'▤' })[kind] || '›';
}

function renderSearchResults(payload) {
  const groups = payload?.groups || {};
  const labels = {
    work: 'Work',
    applications: 'PRT Applications',
    testers: 'PRT Testers',
    founders_race: "Founder’s Race",
    relationships: 'Relationships',
    content: 'Content',
  };
  const chunks = [];
  for (const [key, rows] of Object.entries(groups)) {
    if (!Array.isArray(rows) || !rows.length) continue;
    chunks.push(`<section class="pm-command-group"><span>${escapeHtml(labels[key] || key)}</span>${rows.map((row) => `<button type="button" class="pm-command-result" data-search-view="${escapeHtml(row.target_view || 'hq')}" data-search-id="${escapeHtml(row.target_id ?? '')}" data-search-kind="${escapeHtml(row.kind || '')}"><div><strong>${escapeHtml(row.title || 'Result')}</strong><small>${escapeHtml(row.subtitle || '')}</small></div><span>${escapeHtml(resultIcon(row.kind))}</span></button>`).join('')}</section>`);
  }
  commandResults.innerHTML = chunks.length ? chunks.join('') : '<div class="pm-command-empty">No matching Pitmark records.</div>';
}

function escapeHtml(value = '') {
  return String(value ?? '').replace(/[&<>'"]/g, (ch) => ({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;' })[ch]);
}

async function searchCommand(value) {
  const query = value.trim();
  if (query.length < 2) {
    commandResults.innerHTML = '<div class="pm-command-empty">Type at least two characters to search Pitmark.</div>';
    return;
  }
  const seq = ++commandSequence;
  commandResults.innerHTML = '<div class="pm-command-empty"><span class="pm-inline-loader"><span class="pm-spinner"></span>Searching Pitmark…</span></div>';
  try {
    const payload = await api.search(query);
    if (seq !== commandSequence) return;
    renderSearchResults(payload);
  } catch (error) {
    if (error?.name === 'AbortError') return;
    if (seq !== commandSequence) return;
    commandResults.innerHTML = `<div class="pm-command-empty">${escapeHtml(error?.message || 'Search is unavailable.')}</div>`;
  }
}

function selectSearchResult(button) {
  const domain = VALID_DOMAINS.has(button.dataset.searchView) ? button.dataset.searchView : 'hq';
  const targetId = button.dataset.searchId;
  const kind = button.dataset.searchKind;
  closeCommand();
  if (domain === 'work' && targetId) {
    navigate('work', { workRow: Number(targetId) });
    return;
  }
  if (domain === 'prt') {
    if (kind === 'application') state.prtTab = 'applications';
    if (kind === 'tester') state.prtTab = 'testers';
    if (kind === 'founders_race') state.prtTab = 'founders';
  }
  if (domain === 'content') {
    if (kind === 'editorial') state.contentTab = 'editorial';
    if (kind === 'social_post') state.contentTab = 'generated';
  }
  navigate(domain);
}

function openMore() {
  accountPopover.hidden = true;
  moreLayer.hidden = false;
}

function closeMore() {
  moreLayer.hidden = true;
}

async function logout() {
  logoutButton.disabled = true;
  try {
    await api.logout();
  } catch (error) {
    if (error?.status && error.status !== 401) toast(error.message, 'bad');
  } finally {
    location.assign('/control');
  }
}

async function bootstrapStatus() {
  const dot = document.getElementById('rail-status-dot');
  const version = document.getElementById('rail-version');
  try {
    const payload = await api.hq();
    version.textContent = `v${payload?.version || 'connected'}`;
    dot.classList.add('is-good');
    const work = payload?.modules?.work?.data;
    const prt = payload?.modules?.prt?.data;
    const content = payload?.modules?.content?.data;
    const workCount = Number(work?.summary?.blocked || 0) + Number(work?.summary?.p1 || 0);
    const prtCount = Number(prt?.applications?.new || 0) + Number(prt?.feedback?.blocker || prt?.feedback?.blockers || 0);
    const contentCount = Number(content?.autopilot?.pending || 0);
    updateNavBadge('nav-work-count', workCount);
    updateNavBadge('nav-prt-count', prtCount);
    updateNavBadge('nav-content-count', contentCount);
  } catch {
    version.textContent = 'Connection issue';
    dot.classList.add('is-bad');
  }
}

function updateNavBadge(id, value) {
  const badge = document.getElementById(id);
  if (!badge) return;
  badge.textContent = String(value);
  badge.hidden = !value;
}

function onGlobalClick(event) {
  const domainButton = event.target.closest('[data-domain]');
  if (domainButton) {
    const domain = domainButton.dataset.domain;
    if (VALID_DOMAINS.has(domain)) navigate(domain);
    return;
  }
  if (event.target.closest('[data-command-open]') || event.target.closest('#global-command')) { openCommand(); return; }
  if (event.target.closest('[data-overlay-close]')) { closeCommand(); return; }
  if (event.target === commandPalette) { closeCommand(); return; }
  if (event.target.closest('[data-sheet-close]')) { closeSheet(); return; }
  if (event.target.closest('[data-more-open]')) { openMore(); return; }
  if (event.target.closest('[data-more-close]')) { closeMore(); return; }
  const result = event.target.closest('[data-search-view]');
  if (result) { selectSearchResult(result); return; }
}

function bindOnce() {
  if (initialized) return;
  initialized = true;

  document.addEventListener('click', onGlobalClick);
  refreshButton.addEventListener('click', () => {
    clearCache();
    renderCurrent(true);
    bootstrapStatus();
  });
  accountButton.addEventListener('click', (event) => {
    event.stopPropagation();
    moreLayer.hidden = true;
    accountPopover.hidden = !accountPopover.hidden;
  });
  document.addEventListener('click', (event) => {
    if (!accountPopover.hidden && !accountPopover.contains(event.target) && !accountButton.contains(event.target)) accountPopover.hidden = true;
  });
  logoutButton.addEventListener('click', logout);
  commandInput.addEventListener('input', () => {
    clearTimeout(commandTimer);
    commandTimer = setTimeout(() => searchCommand(commandInput.value), 180);
  });
  commandResults.addEventListener('click', (event) => {
    const result = event.target.closest('[data-search-view]');
    if (result) selectSearchResult(result);
  });
  window.addEventListener('popstate', () => {
    const next = domainFromLocation();
    if (next !== state.domain) {
      state.domain = next;
      setDocumentState(next);
      renderCurrent(false);
    }
  });
  window.addEventListener('hashchange', () => {
    const next = domainFromLocation();
    if (next !== state.domain) {
      state.domain = next;
      setDocumentState(next);
      renderCurrent(false);
    }
  });
  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault(); openCommand(); return;
    }
    if (!typing && event.key === '/') { event.preventDefault(); openCommand(); return; }
    if (event.key === 'Escape') {
      if (!detailLayer.hidden) { closeSheet(); return; }
      if (!commandPalette.hidden) { closeCommand(); return; }
      if (!moreLayer.hidden) { closeMore(); return; }
      accountPopover.hidden = true;
    }
  });
}

function start() {
  if (!root || !viewRoot) return;
  bindOnce();
  state.domain = domainFromLocation();
  if (!location.hash) history.replaceState({ domain: state.domain }, '', `#${state.domain}`);
  setDocumentState(state.domain);
  renderCurrent(false);
  bootstrapStatus();
}

start();
