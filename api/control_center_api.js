const ENDPOINTS = Object.freeze({
  hq: '/api/control/hq/overview',
  work: '/api/control/work',
  search: '/api/control/search',
  prtOverview: '/api/control/ops/overview',
  prtTesters: '/api/control/ops/testers',
  foundersRace: '/api/control/ops/founders-race',
  feedback: '/api/control/ops/feedback',
  posts: '/api/control/autopilot/posts',
  socialPublish: '/api/control/social/posts',
  socialAssetsGenerate: '/api/control/social/assets/generate',
  compose: '/api/control/autopilot/composer/generate',
  blogDrafts: '/api/control/blog/drafts',
  outreach: '/api/control/outreach',
  status: '/api/control/status',
  brief: '/api/control/brief',
  opportunities: '/api/control/autopilot/opportunities',
  intelligenceRun: '/api/control/autopilot/intelligence/run',
  researchPrepare: '/api/control/community/research/prepare',
  notifications: '/api/control/notifications',
  workspaceStatus: '/api/control/workspace/status',
  workspaceOAuthStart: '/api/control/workspace/oauth/start',
  workspaceOAuthComplete: '/api/control/workspace/oauth/complete',
  storeOverview: '/api/control/store/overview',
  standings: '/api/control/standings',
  standingsRefresh: '/api/control/standings/refresh',
  logout: '/api/control/auth/logout',
});

const activeScopes = new Map();
const memoryCache = new Map();

export class ControlApiError extends Error {
  constructor(message, status = 0, payload = null) {
    super(message);
    this.name = 'ControlApiError';
    this.status = status;
    this.payload = payload;
  }
}

function cacheKey(url, method) {
  return `${method}:${url}`;
}

function beginScope(scope) {
  if (!scope) return null;
  activeScopes.get(scope)?.abort();
  const controller = new AbortController();
  activeScopes.set(scope, controller);
  return controller;
}

export function abortScope(scope) {
  const controller = activeScopes.get(scope);
  if (controller) controller.abort();
  activeScopes.delete(scope);
}

export function clearCache(prefix = '') {
  for (const key of memoryCache.keys()) {
    if (!prefix || key.includes(prefix)) memoryCache.delete(key);
  }
}

export async function request(url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const scope = options.scope || '';
  const maxAge = Number(options.maxAge || 0);
  const key = cacheKey(url, method);
  if (method === 'GET' && maxAge > 0) {
    const cached = memoryCache.get(key);
    if (cached && Date.now() - cached.at < maxAge) return structuredClone(cached.value);
  }

  const controller = beginScope(scope);
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  let response;
  try {
    response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller?.signal,
    });
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new ControlApiError('Pitmark Cloud could not be reached.', 0, null);
  } finally {
    if (scope && activeScopes.get(scope) === controller) activeScopes.delete(scope);
  }

  if (response.status === 401 || response.status === 403) {
    location.assign('/control');
    throw new ControlApiError('Your Control Center session expired.', response.status, null);
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = text; }
  }
  if (!response.ok) {
    const detail = payload?.detail || payload?.error || (typeof payload === 'string' ? payload : '') || `Request failed (${response.status})`;
    throw new ControlApiError(String(detail), response.status, payload);
  }

  if (method === 'GET' && maxAge > 0) memoryCache.set(key, { at: Date.now(), value: payload });
  return payload;
}

const query = (base, params = {}) => {
  const url = new URL(base, location.origin);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  }
  return `${url.pathname}${url.search}`;
};

export const api = Object.freeze({
  endpoints: ENDPOINTS,
  // HQ is read in parallel by the initial view and the rail status. Do not give
  // those identical reads a shared abort scope or the second call cancels the
  // first render before anything reaches the screen.
  hq: (options = {}) => request(ENDPOINTS.hq, { maxAge: 15000, ...options }),
  work: (view = 'now', options = {}) => request(query(ENDPOINTS.work, { view }), { scope: 'work', maxAge: 12000, ...options }),
  updateWork: (rowNumber, body) => request(`${ENDPOINTS.work}/${encodeURIComponent(rowNumber)}`, { method: 'PATCH', body }),
  search: (q) => request(query(ENDPOINTS.search, { q }), { scope: 'search' }),
  prtOverview: (options = {}) => request(ENDPOINTS.prtOverview, { scope: 'prt-overview', maxAge: 12000, ...options }),
  prtTesters: (options = {}) => request(ENDPOINTS.prtTesters, { scope: 'prt-testers', maxAge: 12000, ...options }),
  foundersRace: (options = {}) => request(ENDPOINTS.foundersRace, { scope: 'prt-race', maxAge: 12000, ...options }),
  feedback: (status = '', options = {}) => request(query(ENDPOINTS.feedback, { status }), { scope: 'prt-feedback', maxAge: 12000, ...options }),
  setApplicationStatus: (id, status) => request(`/api/control/ops/testers/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status } }),
  setFeedbackStatus: (id, status) => request(`/api/control/ops/feedback/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status } }),
  posts: (status = '', options = {}) => request(query(ENDPOINTS.posts, { status }), { scope: 'content-posts', maxAge: 8000, ...options }),
  savePost: (body) => request(ENDPOINTS.posts, { method: 'POST', body }),
  updatePost: (id, body) => request(`${ENDPOINTS.posts}/${encodeURIComponent(id)}`, { method: 'PATCH', body }),
  deletePost: (id) => request(`${ENDPOINTS.posts}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  decidePost: (id, action, scheduledFor = null) => request(`${ENDPOINTS.posts}/${encodeURIComponent(id)}/decision`, { method: 'POST', body: { action, scheduled_for: scheduledFor } }),
  publishPost: (id) => request(`${ENDPOINTS.socialPublish}/${encodeURIComponent(id)}/publish`, { method: 'POST' }),
  compose: (body) => request(ENDPOINTS.compose, { method: 'POST', body }),
  generateSocialImage: (body) => request(ENDPOINTS.socialAssetsGenerate, { method: 'POST', body }),
  blogDrafts: (status = '', options = {}) => request(query(ENDPOINTS.blogDrafts, { status }), { scope: 'editorial', maxAge: 10000, ...options }),
  decideBlog: (id, action, scheduledFor = null) => request(`${ENDPOINTS.blogDrafts}/${encodeURIComponent(id)}/decision`, { method: 'POST', body: { action, scheduled_for: scheduledFor } }),
  outreach: (stage = '', options = {}) => request(query(ENDPOINTS.outreach, { stage }), { scope: 'outreach', maxAge: 12000, ...options }),
  updateOutreach: (id, body) => request(`${ENDPOINTS.outreach}/${encodeURIComponent(id)}`, { method: 'PATCH', body }),
  status: (options = {}) => request(ENDPOINTS.status, { scope: 'systems-status', maxAge: 15000, ...options }),
  brief: (options = {}) => request(ENDPOINTS.brief, { scope: 'hq-brief', maxAge: 15000, ...options }),
  opportunities: (options = {}) => request(ENDPOINTS.opportunities, { scope: 'hq-opportunities', maxAge: 60000, ...options }),
  runIntelligence: () => request(ENDPOINTS.intelligenceRun, { method: 'POST' }),
  prepareOpportunityResearch: (opportunityId, hint = '') => request(ENDPOINTS.researchPrepare, { method: 'POST', body: { opportunity_id: Number(opportunityId), research_type: 'opportunity_deep_dive', hint } }),
  notifications: (options = {}) => request(ENDPOINTS.notifications, { scope: 'notifications', maxAge: 10000, ...options }),
  workspaceStatus: (options = {}) => request(ENDPOINTS.workspaceStatus, { scope: 'workspace-status', maxAge: 5000, ...options }),
  workspaceOAuthStart: () => request(ENDPOINTS.workspaceOAuthStart, { method: 'POST' }),
  workspaceOAuthComplete: (callbackUrl) => request(ENDPOINTS.workspaceOAuthComplete, { method: 'POST', body: { callback_url: callbackUrl } }),
  storeOverview: (options = {}) => request(ENDPOINTS.storeOverview, { scope: 'store-overview', maxAge: 12000, ...options }),
  standings: (season = '', options = {}) => request(query(ENDPOINTS.standings, { season }), { scope: 'standings', maxAge: 300000, ...options }),
  refreshStandings: (season = '') => request(query(ENDPOINTS.standingsRefresh, { season }), { method: 'POST' }),
  logout: () => request(ENDPOINTS.logout, { method: 'POST' }),
});
