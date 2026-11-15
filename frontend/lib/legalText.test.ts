import assert from 'node:assert/strict';
import test from 'node:test';
import { parseLegalText, safeHref } from './legalText';
import { LEGAL_DEFAULTS, LEGAL_SLUGS } from './legalDefaults';

test('headings, lists, bold and links parse into blocks', () => {
  const b = parseLegalText('## Who\n\nWe are **Ribdigi** [terms](/legal/terms).\n\n- one\n- two\n  more');
  assert.equal(b.length, 3);
  assert.equal(b[0].kind, 'h2');
  assert.deepEqual((b[1] as any).parts.map((p: any) => p.kind), ['text', 'bold', 'text', 'link', 'text']);
  assert.deepEqual((b[2] as any).items.length, 2);
  assert.equal((b[2] as any).items[1][0].text, 'two more');
});

test('only safe links survive; anything else shows as text', () => {
  assert.equal(safeHref('/legal/privacy'), '/legal/privacy');
  assert.equal(safeHref('https://example.com/x'), 'https://example.com/x');
  assert.equal(safeHref('mailto:a@b.com'), 'mailto:a@b.com');
  for (const bad of ['javascript:alert(1)', '//evil.com', 'http://plain.com', 'data:text/html,x']) assert.equal(safeHref(bad), null, bad);
  const [p] = parseLegalText('[click](javascript:alert(1))') as any;
  assert.ok(p.parts.every((x: any) => x.kind === 'text'));
});

test('placeholders and the built-in texts parse', () => {
  const b = parseLegalText('{{cookie_settings}}\n\nIt is {{analytics_status}}');
  assert.equal(b[0].kind, 'cookie_settings');
  assert.equal((b[1] as any).parts[1].kind, 'analytics_status');
  for (const slug of LEGAL_SLUGS) assert.ok(parseLegalText(LEGAL_DEFAULTS[slug].body).length > 8, slug);
});
