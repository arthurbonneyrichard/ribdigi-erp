'use client';

/**
 * Happy hours: a percentage off chosen dishes (or the whole menu) on chosen days between two
 * times. The till applies it when a dish goes on a bill; the price on the bill then stays fixed.
 */

import { useEffect, useState } from 'react';
import { api } from '../lib/api';

type Rule = {
  name: string;
  percent: number;
  days: string[];
  start: string;
  end: string;
  product_ids: string[];
  active: boolean;
};

const DAYS: [string, string][] = [
  ['mon', 'Mon'],
  ['tue', 'Tue'],
  ['wed', 'Wed'],
  ['thu', 'Thu'],
  ['fri', 'Fri'],
  ['sat', 'Sat'],
  ['sun', 'Sun'],
];

export default function RestaurantHappyHours({ dishes }: { dishes: { id: string; name: string }[] }) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [running, setRunning] = useState<string[]>([]);
  const [clock, setClock] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/restaurant/happy-hours')
      .then((res) => {
        setRules((res?.data?.rules || []) as Rule[]);
        setRunning(res?.data?.running_now || []);
        setClock(res?.data?.local_time || '');
      })
      .catch((err) => setError(err?.message || 'Could not load happy hours'));
  }, []);

  function change(i: number, patch: Partial<Rule>) {
    setRules(rules.map((r, j) => (j === i ? { ...r, ...patch } : r)));
    setSaved('');
  }

  async function save() {
    setBusy(true);
    setError('');
    try {
      const res = await api('/restaurant/happy-hours', { method: 'PUT', body: JSON.stringify({ rules }) });
      setRules((res?.data?.rules || []) as Rule[]);
      setRunning(res?.data?.running_now || []);
      setSaved('Happy hours saved');
    } catch (err: any) {
      setError(err?.message || 'Could not save happy hours');
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="rd-panel rd-domain">
      <summary>
        <strong>Happy hours</strong>
        <span>{running.length ? `On now: ${running.join(', ')}` : rules.length ? `${rules.length} set` : 'None'}</span>
      </summary>
      <div className="rest-order-form" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="rd-hint-line">
          A happy hour takes a percentage off while it runs (restaurant time now: {clock || '…'}). Leave the dishes empty for the whole menu.
          A rule from 22:00 to 02:00 runs into the next morning.
        </p>
        {rules.map((r, i) => (
          <fieldset key={i} style={{ border: '1px solid var(--line, #D4E5C4)', borderRadius: 12, padding: 12 }}>
            <legend>{r.name || `Happy hour ${i + 1}`}</legend>
            <label>
              <span>Name</span>
              <input aria-label={`Happy hour ${i + 1} name`} value={r.name} onChange={(e) => change(i, { name: e.target.value })} />
            </label>
            <label>
              <span>Percent off</span>
              <input aria-label={`Happy hour ${i + 1} percent off`} inputMode="decimal" value={String(r.percent ?? '')} onChange={(e) => change(i, { percent: Number(e.target.value.replace(/[^0-9.]/g, '')) || 0 })} />
            </label>
            <label>
              <span>From</span>
              <input type="time" aria-label={`Happy hour ${i + 1} start`} value={r.start} onChange={(e) => change(i, { start: e.target.value })} />
            </label>
            <label>
              <span>Until</span>
              <input type="time" aria-label={`Happy hour ${i + 1} end`} value={r.end} onChange={(e) => change(i, { end: e.target.value })} />
            </label>
            <div role="group" aria-label={`Happy hour ${i + 1} days`} style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {DAYS.map(([k, label]) => (
                <label key={k} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={r.days.includes(k)}
                    onChange={(e) => change(i, { days: e.target.checked ? [...r.days, k] : r.days.filter((d) => d !== k) })}
                  />
                  {label}
                </label>
              ))}
            </div>
            <label>
              <span>Dishes (none ticked = whole menu)</span>
              <select
                multiple
                aria-label={`Happy hour ${i + 1} dishes`}
                value={r.product_ids}
                onChange={(e) => change(i, { product_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}
                style={{ minHeight: 120 }}
              >
                {dishes.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={r.active} onChange={(e) => change(i, { active: e.target.checked })} />
              On
            </label>
            <button type="button" aria-label={`Remove happy hour ${i + 1}`} onClick={() => setRules(rules.filter((_, j) => j !== i))}>
              Remove
            </button>
          </fieldset>
        ))}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() =>
              setRules([...rules, { name: 'Happy hour', percent: 20, days: ['mon', 'tue', 'wed', 'thu', 'fri'], start: '17:00', end: '19:00', product_ids: [], active: true }])
            }
          >
            Add a happy hour
          </button>
          <button type="button" disabled={busy} aria-label="Save happy hours" onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save happy hours'}
          </button>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {saved ? <p role="status">{saved}</p> : null}
      </div>
    </details>
  );
}
