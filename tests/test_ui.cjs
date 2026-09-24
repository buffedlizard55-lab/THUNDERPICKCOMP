/* Headless static-JS smoke test without browser dependencies. All data local. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const app = fs.readFileSync(path.join(root, 'assets', 'app.js'), 'utf8');
const pages = fs.readdirSync(root).filter((name) => name.endsWith('.html'));
const currentObs = JSON.parse(fs.readFileSync(path.join(root, 'data', 'observations.json'), 'utf8'));
const masterCount = JSON.parse(fs.readFileSync(path.join(root, 'data', 'master_list.json'), 'utf8')).length;
const currentLedger = JSON.parse(fs.readFileSync(path.join(root, 'data', 'ledger.json'), 'utf8'));

function element(type, props = {}) {
  return {
    innerHTML: '<p>Loading verified data…</p>',
    textContent: '',
    getAttribute(name) { return name === 'data-render' ? type : props[name] || null; },
  };
}
async function render(page, broken = null, transform = (name, value) => value) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  const targets = [...html.matchAll(/data-render="([^"]+)"(?:\s+data-limit="([^"]+)")?/g)]
    .map(([, type, limit]) => element(type, { 'data-limit': limit }));
  const footer = [element('today')];
  const counts = [element('mastercount')];
  const doc = {
    body: { innerHTML: 'THE SITE MUST NOT BE REPLACED BY AN ERROR' },
    addEventListener(name, callback) { assert.equal(name, 'DOMContentLoaded'); callback(); },
    querySelectorAll(query) {
      if (query === '[data-render]') return targets;
      if (query === '[data-today]') return footer;
      if (query === '[data-master-count]') return counts;
      if (query === '[data-ledger-meta]') return [];
      return [];
    },
    getElementById() { return null; },
  };
  const fetcher = async (url) => {
    const name = url.replace('data/', '');
    if (broken === name) throw new Error('simulated network failure for ' + name);
    const value = JSON.parse(fs.readFileSync(path.join(root, 'data', name), 'utf8'));
    return { ok: true, json: async () => transform(name, value) };
  };
  vm.runInNewContext(app, { document: doc, fetch: fetcher, Date, location: { hash: '' }, console });
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(doc.body.innerHTML, 'THE SITE MUST NOT BE REPLACED BY AN ERROR');
  return { targets, footer: footer[0], counts: counts[0] };
}

(async () => {
  for (const page of pages) {
    const view = await render(page);
    for (const node of view.targets) {
      assert.doesNotMatch(node.innerHTML, /Loading verified data|Loading source-check|Data unavailable/,
        page + ': ' + node.getAttribute('data-render'));
    }
    assert.equal(view.footer.textContent, currentObs.last_completed_utc +
      (currentObs.mode === 'offline-replay' ? ' (offline research replay)' : ''));
    assert.equal(view.counts.textContent, String(masterCount));
    console.log('Rendered', page, 'targets:', view.targets.length);
  }
  const lb = await render('leaderboard.html');
  const standings = lb.targets.find((e) => e.getAttribute('data-render') === 'leaderboard').innerHTML;
  if (!currentLedger.entries.some((e) => e.settlement.result !== 'pending')) {
    assert.equal((standings.match(/<td>T1<\/td>/g) || []).length, 8, 'no realized P/L means all users tie');
    assert.match(standings, /—/); // ROI undefined before settlement
  }
  const market = await render('markets.html', null, (name, x) => {
    if (name === 'observations.json') {
      x.events[0].title = '<img src=x onerror=alert(1)>';
      x.events[0].source_url = 'javascript:alert(1)';
    }
    return x;
  });
  const ev = market.targets.find((e) => e.getAttribute('data-render') === 'market-events').innerHTML;
  assert.match(ev, /&lt;img/);
  assert.doesNotMatch(ev, /<img|href="javascript:/);
  const failed = await render('index.html', 'observations.json');
  assert.match(failed.targets.find((e) => e.getAttribute('data-render') === 'pulse').innerHTML,
    /Data unavailable/);
  assert.equal(failed.footer.textContent, 'unavailable');
  console.log('UI smoke tests passed (all pages, ranks, date, XSS, failed feed).');
})().catch((error) => { console.error(error); process.exitCode = 1; });
