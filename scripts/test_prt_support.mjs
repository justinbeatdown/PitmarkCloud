import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const html = readFileSync(new URL('../api/prt-support.html', import.meta.url), 'utf8');
const script = readFileSync(new URL('../api/prt-support.js', import.meta.url), 'utf8');
function supportPage() {
  const items = [...html.matchAll(/<details data-tags="([^"]+)">([\s\S]*?)<\/details>/g)]
    .map(x => ({dataset: {tags: x[1]}, textContent: x[2].replace(/<[^>]*>/g, ''), hidden: false}));
  const buttons = [...html.matchAll(/<button data-filter="([^"]+)"/g)].map(x => {
    const classes = new Set();
    return {
      dataset: {filter: x[1]}, attrs: {},
      classList: {add: v => classes.add(v), remove: v => classes.delete(v), contains: v => classes.has(v)},
      setAttribute(name, value) { this.attrs[name] = value; },
      addEventListener(name, handler) { this[name] = handler; }
    };
  });
  const q = {value: '', addEventListener(name, handler) { this[name] = handler; }};
  const noResults = {hidden: true};
  runInNewContext(script, {document: {
    getElementById: id => id === 'faqSearch' ? q : noResults,
    querySelectorAll: selector => selector === '#faqList details' ? items : buttons
  }});
  return {items, buttons, noResults, search(value) { q.value = value; q.input({target: q}); }};
}
test('search finds text inside a closed answer', () => {
  const p = supportPage();
  assert.equal(p.items.length, 8);
  p.search('entitlement');
  assert.equal(p.items.filter(x => !x.hidden).length, 1);
  assert.equal(p.noResults.hidden, true);
});
test('an empty result explains the next step and another search recovers', () => {
  const p = supportPage();
  p.search('no-such-support-answer');
  assert.equal(p.items.filter(x => !x.hidden).length, 0);
  assert.equal(p.noResults.hidden, false);
  p.search('  ACTIVATION  ');
  assert.equal(p.items.filter(x => !x.hidden).length, 3);
  assert.equal(p.noResults.hidden, true);
  p.search('');
  assert.equal(p.items.filter(x => !x.hidden).length, 8);
});
test('topic filters expose their selected state and toggle back to all answers', () => {
  const p = supportPage();
  const account = p.buttons.find(x => x.dataset.filter === 'account');
  account.click();
  assert.equal(p.items.filter(x => !x.hidden).length, 2);
  assert.equal(account.attrs['aria-pressed'], 'true');
  account.click();
  assert.equal(p.items.filter(x => !x.hidden).length, 8);
  assert.equal(account.attrs['aria-pressed'], 'false');
});
