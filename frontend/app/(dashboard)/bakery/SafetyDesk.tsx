'use client';

/**
 * Bakery food safety: write down fridge, freezer and oven temperatures, sign the opening,
 * closing, cleaning and delivery checklists, and print the record for an inspector.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { bakeryApi, openPrintable } from '../../../lib/bakeryTill';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const KINDS = ['fridge', 'freezer', 'display', 'oven', 'proofer', 'other'];
const LABEL: Record<string, string> = { opening: 'Opening', closing: 'Closing', cleaning: 'Deep clean', delivery: 'Delivery received' };

export default function SafetyDesk({ isManager }: { isManager: boolean }) {
  const [data, setData] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [temps, setTemps] = useState<Record<string, string>>({});
  const [actions, setActions] = useState<Record<string, string>>({});
  const [ticks, setTicks] = useState<Record<string, number[]>>({});
  const [note, setNote] = useState<Record<string, string>>({});
  const [point, setPoint] = useState({ name: '', kind: 'fridge', min_c: '', max_c: '' });

  const load = useCallback(async () => {
    try {
      const res = await bakeryApi('/bakery/safety');
      setData(res?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function run(path: string, body: object, done: string, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await bakeryApi(path, { method, body: JSON.stringify(body) });
      setNotice(res?.message || done);
      await load();
      return true;
    } catch (err) {
      setError(problem(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const points: Row[] = data?.points || [];
  const bad = Number(data?.bad_readings_today || 0);
  const due = Number(data?.readings_still_due || 0);

  return (
    <div className="bk-trade">
      {error ? <div className="bk-banner bad" role="alert">{error}</div> : null}
      {notice ? <div className="bk-banner ok" role="status">{notice}</div> : null}

      <section className="bk-box" aria-label="Food safety today">
        <div className="bk-row bk-spread">
          <b>Today</b>
          <span className="bk-muted">
            {bad > 0 ? <span className="bk-pill bad">{bad} outside the safe range</span> : null} {due > 0 ? `${due} readings still to take` : 'All readings taken'}
          </span>
        </div>
        <div className="bk-row">
          <button type="button" className="bk-secondary" aria-label="Print food safety record for the last 30 days" onClick={() => void openPrintable('/bakery/safety/print')}>
            Print inspector record (30 days)
          </button>
        </div>
      </section>

      <section className="bk-box bk-scroll" aria-label="Temperature checks">
        <h3>Temperature checks</h3>
        <table>
          <thead><tr><th>Point</th><th>Safe range</th><th>Last reading</th><th>Take a reading</th></tr></thead>
          <tbody>
            {points.map((p) => {
              const last = p.last_reading;
              const typed = temps[p.id] ?? '';
              const outside = typed !== '' && (Number(typed) < Number(p.min_c) || Number(typed) > Number(p.max_c));
              return (
                <tr key={p.id}>
                  <td>{p.name}<div className="bk-muted">{p.taken_today}/{p.checks_per_day} today</div></td>
                  <td>{p.min_c}° to {p.max_c}°C</td>
                  <td>{last ? <span className={`bk-pill ${last.in_range ? 'ok' : 'bad'}`}>{last.reading_c}°C</span> : '—'}</td>
                  <td>
                    <div className="bk-row">
                      <input type="number" step="0.1" inputMode="decimal" aria-label={`Temperature for ${p.name}`} value={typed} onChange={(e) => setTemps({ ...temps, [p.id]: e.target.value })} style={{ width: 90 }} />
                      {outside ? (
                        <input aria-label={`What was done about ${p.name}`} placeholder="What did you do about it?" value={actions[p.id] ?? ''} onChange={(e) => setActions({ ...actions, [p.id]: e.target.value })} />
                      ) : null}
                      <button
                        type="button" className="bk-primary" disabled={busy || typed === ''} aria-label={`Record temperature for ${p.name}`}
                        onClick={async () => {
                          const ok = await run('/bakery/safety/readings', { point_id: p.id, reading_c: Number(typed), action_taken: (actions[p.id] || '').trim() || null }, 'Reading recorded');
                          if (ok) { setTemps({ ...temps, [p.id]: '' }); setActions({ ...actions, [p.id]: '' }); }
                        }}
                      >Record</button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {points.length === 0 ? <tr><td colSpan={4} className="bk-muted">No fridges or ovens set up yet.{isManager ? ' Add one below.' : ' Ask a manager to add them.'}</td></tr> : null}
          </tbody>
        </table>
      </section>

      {isManager ? (
        <section className="bk-box" aria-label="Add a temperature point">
          <h3>Add a fridge, freezer or oven</h3>
          <div className="bk-row">
            <input aria-label="Point name" placeholder="Walk-in fridge" value={point.name} onChange={(e) => setPoint({ ...point, name: e.target.value })} />
            <select aria-label="Point kind" value={point.kind} onChange={(e) => setPoint({ ...point, kind: e.target.value })}>
              {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <input type="number" step="0.1" aria-label="Lowest safe temperature" placeholder="Lowest °C (optional)" value={point.min_c} onChange={(e) => setPoint({ ...point, min_c: e.target.value })} />
            <input type="number" step="0.1" aria-label="Highest safe temperature" placeholder="Highest °C (optional)" value={point.max_c} onChange={(e) => setPoint({ ...point, max_c: e.target.value })} />
            <button
              type="button" className="bk-primary" disabled={busy || !point.name.trim()} aria-label="Add temperature point"
              onClick={async () => {
                const ok = await run('/bakery/safety/points', { name: point.name.trim(), kind: point.kind, min_c: point.min_c === '' ? null : Number(point.min_c), max_c: point.max_c === '' ? null : Number(point.max_c) }, 'Point added');
                if (ok) setPoint({ name: '', kind: 'fridge', min_c: '', max_c: '' });
              }}
            >Add</button>
          </div>
          <p className="bk-muted">Leave the range empty to use the usual one for that kind (fridge 0 to 5°C, freezer −25 to −18°C).</p>
        </section>
      ) : null}

      <section className="bk-box" aria-label="Checklists">
        <h3>Checklists</h3>
        <div className="bk-grid">
          {(data?.checklists || []).map((c: Row) => {
            const chosen = ticks[c.kind] || [];
            return (
              <article key={c.kind} className="bk-box">
                <div className="bk-row bk-spread"><b>{LABEL[c.kind] || c.kind}</b>{c.done_today ? <span className="bk-pill ok">Done today</span> : <span className="bk-pill">Not done</span>}</div>
                {c.items.map((text: string, i: number) => (
                  <label key={i} className="bk-row">
                    <input type="checkbox" checked={chosen.includes(i)} aria-label={`${LABEL[c.kind]}: ${text}`} onChange={(e) => setTicks({ ...ticks, [c.kind]: e.target.checked ? [...chosen, i] : chosen.filter((x) => x !== i) })} />
                    <span>{text}</span>
                  </label>
                ))}
                <input aria-label={`${LABEL[c.kind]} notes`} placeholder="Notes (optional)" value={note[c.kind] || ''} onChange={(e) => setNote({ ...note, [c.kind]: e.target.value })} />
                <button
                  type="button" className="bk-primary" disabled={busy} aria-label={`Sign ${LABEL[c.kind]} checklist`}
                  onClick={async () => {
                    const ok = await run('/bakery/safety/checks', { kind: c.kind, done: chosen, notes: (note[c.kind] || '').trim() || null }, 'Checklist signed');
                    if (ok) { setTicks({ ...ticks, [c.kind]: [] }); setNote({ ...note, [c.kind]: '' }); }
                  }}
                >Sign checklist</button>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
