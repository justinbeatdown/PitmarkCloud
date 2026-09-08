import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const script = readFileSync(new URL('../api/prt-downloads.js', import.meta.url), 'utf8');
function page(fetchImpl = () => Promise.resolve({ok: true})) {
  const handlers = {};
  const calls = [];
  const document = {
    addEventListener: (name, fn) => { handlers[name] = fn; },
    getElementById: () => ({textContent: 'v0.16.79'})
  };
  runInNewContext(script, {
    document, URL,
    location: {href: 'https://prt.pitmarkracing.com/prt', origin: 'https://prt.pitmarkracing.com'},
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
