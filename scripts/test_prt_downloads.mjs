import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const script = readFileSync(new URL('../api/prt-downloads.js', import.meta.url), 'utf8');
function page(fetchImpl = () => Promise.resolve({ok: true}), query = '', links = []) {
  const handlers = {};
  const calls = [];
  const document = {
    addEventListener: (name, fn) => { handlers[name] = fn; },
    getElementById: () => ({textContent: 'v0.16.79'}),
    querySelectorAll: () => links
  };
  runInNewContext(script, {
    document, URL,
    location: {href: 'https://prt.pitmarkracing.com/prt' + query, origin: 'https://prt.pitmarkracing.com'},
    fetch: (...args) => { calls.push(args); return fetchImpl(...args); }
  });
  function activate({type = 'click', button = 0, cancelled = false, href = '/downloads/PRT-Setup-Latest.exe', source = 'prt-home-hero', tracked = true} = {}) {
    const event = {
      type, button, defaultPrevented: cancelled,
      target: {closest: () => tracked ? {href, dataset: {prtDownload: source}} : null},
      preventDefault() { throw new Error('Download navigation must not be cancelled'); }
    };
    handlers[type](event);
  }
  return {activate, calls};
}

test('a download click sends only source and version and survives navigation', () => {
  const p = page();
  p.activate();
  assert.equal(p.calls.length, 1);
  const [url, options] = p.calls[0];
  assert.equal(url, '/api/prt/analytics/download');
  assert.equal(options.keepalive, true);
  assert.equal(options.method, 'POST');
  assert.deepEqual(JSON.parse(options.body), {source: 'prt-home-hero', version: '0.16.79'});
});

test('known campaign clicks retain placement and public campaign labels', () => {
  const p = page(undefined, '?utm_campaign=prt_raceproof_202609&utm_source=facebook&utm_content=race&email=private@example.com');
  p.activate();
  const body = JSON.parse(p.calls[0][1].body);
  assert.equal(body.source, 'prt-home-hero|facebook|race|prt_raceproof_202609');
  assert.ok(body.source.length <= 80);
  assert.deepEqual(Object.keys(body).sort(), ['source', 'version']);
  assert.ok(!p.calls[0][1].body.includes('private'));
});
test('unrecognized and incomplete campaign labels leave ordinary attribution intact', () => {
  for (const query of [
    '?utm_campaign=other&utm_source=facebook&utm_content=race',
    '?utm_campaign=prt_raceproof_202609&utm_source=private@example.com&utm_content=race',
    '?utm_campaign=prt_raceproof_202609&utm_source=facebook&utm_content=unknown',
    '?utm_campaign=prt_raceproof_202609&utm_source=facebook'
  ]) {
    const p = page(undefined, query);
    p.activate();
    assert.equal(JSON.parse(p.calls[0][1].body).source, 'prt-home-hero');
  }
});
test('campaign labels follow setup links without changing installers or external destinations', () => {
  const urls = ['/prt/support#faqList', '/prt/apply', '/downloads/PRT-Setup-Latest.exe', '/api/discord/install/launch', 'https://example.com/prt', 'mailto:prt@pitmarkracing.com'];
  const links = urls.map(href => ({href}));
  page(undefined, '?utm_campaign=prt_raceproof_202609&utm_source=tiktok&utm_content=invite&secret=ignore', links);
  for (const link of links.slice(0, 2)) {
    const url = new URL(link.href);
    assert.equal(url.searchParams.get('utm_source'), 'tiktok');
    assert.equal(url.searchParams.get('utm_content'), 'invite');
    assert.equal(url.searchParams.has('secret'), false);
  }
  assert.equal(new URL(links[0].href).hash, '#faqList');
  assert.deepEqual(links.slice(2).map(x => x.href), urls.slice(2));
});
test('each homepage and support download location keeps its attribution', () => {
  const p = page();
  for (const source of ['prt-home-hero', 'prt-home-early-access', 'prt-support', 'prt-support-install']) p.activate({source});
  assert.deepEqual(p.calls.map(x => JSON.parse(x[1].body).source), ['prt-home-hero', 'prt-home-early-access', 'prt-support', 'prt-support-install']);
});
test('a stalled analytics request never holds up a download click', () => {
  const p = page(() => new Promise(() => {}));
  assert.doesNotThrow(() => p.activate());
  assert.equal(p.calls.length, 1);
});
test('network failures and blocked fetch leave download navigation alone', async () => {
  const rejected = page(() => Promise.reject(new Error('offline')));
  const thrown = page(() => { throw new Error('blocked'); });
  assert.doesNotThrow(() => rejected.activate());
  assert.doesNotThrow(() => thrown.activate());
  await new Promise(resolve => setImmediate(resolve));
});
test('middle-click is counted but right-click and cancelled clicks are not', () => {
  const p = page();
  p.activate({type: 'auxclick', button: 1});
  p.activate({type: 'auxclick', button: 2});
  p.activate({cancelled: true});
  assert.equal(p.calls.length, 1);
});
test('other navigation and external links do not generate download events', () => {
  const p = page();
  p.activate({tracked: false});
  p.activate({href: '/prt/apply'});
  p.activate({href: 'https://example.com/downloads/PRT-Setup-Latest.exe'});
  assert.equal(p.calls.length, 0);
});
