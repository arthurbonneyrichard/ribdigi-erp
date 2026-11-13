'use client';

/** Cover for leave approvals while a manager is away. Staff set their own; HR sees all. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => new Date().toISOString().slice(0, 10);

export default function Cover({ asHr = false }: { asHr?: boolean }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [people, setPeople] = useState<Row[]>([]);
  const [form, setForm] = useState({ from_employee_id: '', to_employee_id: '', starts_on: today(), ends_on: today(), reason: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const [c, p] = await Promise.all([api('/hrm/cover'), api('/hrm/cover/people')]);
      setRows(c?.data || []);
      setPeople(p?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function send(path: string, body: object, done: string) {
    setBusy(true);
    setError('');
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
      setNotice(done);
      await load();
      return true;
    } catch (err) {
      setError(problem(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const current = rows.filter((r) => !r.ended);
  return (
    <section className="hr-box hr-scroll" aria-label="Approval cover">
      <div className="hr-cardhead"><h2>{asHr ? 'Approval cover' : 'Cover while I am away'}</h2></div>
      <p className="hr-muted">
        The person covering decides leave for the manager&apos;s team at the manager step, gets the notices, and sees those requests under My team.
        End it early when the manager is back.
      </p>
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      <div className="hr-row">
        {asHr ? (
          <select value={form.from_employee_id} onChange={(e) => setForm({ ...form, from_employee_id: e.target.value })} aria-label="Manager who is away">
            <option value="">Manager who is away</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        ) : null}
        <select value={form.to_employee_id} onChange={(e) => setForm({ ...form, to_employee_id: e.target.value })} aria-label="Who covers">
          <option value="">Who covers</option>
          {people.filter((p) => p.id !== form.from_employee_id).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input type="date" value={form.starts_on} onChange={(e) => setForm({ ...form, starts_on: e.target.value })} aria-label="Cover from" />
        <input type="date" value={form.ends_on} min={form.starts_on} onChange={(e) => setForm({ ...form, ends_on: e.target.value })} aria-label="Cover to" />
        <input placeholder="Reason (optional)" maxLength={255} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} aria-label="Cover reason" />
        <button
          type="button" className="hr-primary" disabled={busy || !form.to_employee_id || (asHr && !form.from_employee_id)}
          onClick={async () => {
            const ok = await send('/hrm/cover', { ...form, from_employee_id: asHr ? form.from_employee_id : null, reason: form.reason.trim() || null }, 'Cover set.');
            if (ok) setForm({ ...form, to_employee_id: '', reason: '' });
          }}
        >
          Set cover
        </button>
      </div>
      {current.length ? (
        <table>
          <thead><tr><th>Away</th><th>Covers</th><th>From</th><th>To</th><th /></tr></thead>
          <tbody>
            {current.map((r) => (
              <tr key={r.id}>
                <td>{r.from_name}</td><td>{r.to_name}</td><td>{r.starts_on}</td><td>{r.ends_on}{r.running ? ' (now)' : ''}</td>
                <td><button type="button" disabled={busy} aria-label={`End cover for ${r.from_name}`} onClick={() => void send(`/hrm/cover/${r.id}/end`, {}, 'Cover ended.')}>End now</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
