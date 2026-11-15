import assert from 'node:assert/strict';
import test from 'node:test';

// A tiny in-memory localStorage and window, enough for lib/consent.
const store = new Map<string, string>();
(globalThis as any).localStorage = {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => void store.set(k, String(v)),
  removeItem: (k: string) => void store.delete(k),
};
const events: string[] = [];
(globalThis as any).window = { dispatchEvent: (e: { type: string }) => void events.push(e.type) };
(globalThis as any).CustomEvent = class {
  type: string;
  detail: unknown;
  constructor(type: string, init?: { detail?: unknown }) {
    this.type = type;
    this.detail = init?.detail;
  }
};

function withAnalytics(on: boolean) {
  process.env.NEXT_PUBLIC_UMAMI_SRC = on ? 'https://stats.example.com/script.js' : '';
  process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID = on ? 'site-1' : '';
}

test('no optional category, no banner, analytics never allowed', async () => {
  const c = await import('./consent');
  withAnalytics(false);
  store.clear();
  assert.deepEqual(c.optionalCategories(), []);
  c.saveConsent({ analytics: true });
  assert.equal(c.analyticsAllowed(), false);
});

test('analytics loads only after a yes, and a no or a withdrawal stops it', async () => {
  const c = await import('./consent');
  withAnalytics(true);
  store.clear();
  assert.deepEqual(c.optionalCategories(), ['analytics']);
  assert.equal(c.readConsent(), null);
  assert.equal(c.analyticsAllowed(), false);

  const yes = c.saveConsent({ analytics: true });
  assert.equal(yes.version, c.CONSENT_VERSION);
  assert.ok(!Number.isNaN(Date.parse(yes.decided_at)));
  assert.equal(c.analyticsAllowed(), true);
  assert.ok(events.includes(c.CONSENT_EVENT));

  c.saveConsent({ analytics: false });
  assert.equal(c.analyticsAllowed(), false);
});

test('a choice saved under an older policy version is asked again', async () => {
  const c = await import('./consent');
  withAnalytics(true);
  store.clear();
  store.set('ribdigi:consent', JSON.stringify({ version: '2020-01-01', analytics: true, decided_at: '2020-01-01T00:00:00Z' }));
  assert.equal(c.readConsent(), null);
  assert.equal(c.analyticsAllowed(), false);
  store.set('ribdigi:consent', 'not json');
  assert.equal(c.readConsent(), null);
});
