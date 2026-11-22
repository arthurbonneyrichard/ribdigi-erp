'use client';

/** FMCG field workforce: field job and sales target per person, and the month's visits and sales against target. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const ROLES: [string, string][] = [
  ['rep', 'Sales rep'], ['van_sales', 'Van sales'], ['merchandiser', 'Merchandiser'], ['delivery', 'Delivery'], ['warehouse', 'Warehouse'], ['supervisor', 'Supervisor'],
];
const roleWord = (r: string) => ROLES.find(([k]) => k === r)?.[1] || r;

export const FIELD_SCREEN = { title: 'Field workforce', sub: 'Reps, van sales, merchandisers and delivery: visits and sales against target.', icon: 'users' };

export default function FieldWorkforce({ seesPay }: { seesPay: boolean }) {
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState<Row | null>(null);
  const [people, setPeople] = useState<Row[]>([]);
  const [f, setF] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      setData((await api(`/hrm/field-workforce?period=${period}`))?.data || null);
      setPeople((await api('/hrm/employees'))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, [period]);
  useEffect(() => { void load(); }, [load]);

  async function save() {
    setError(''); setNotice('');
    try {
      await api(`/hrm/employees/${f.person}/field-profile`, {
        method: 'PUT',
        body: JSON.stringify({ field_role: f.role || 'rep', monthly_sales_target: f.target ? Number(f.target) : null }),
      });
      setNotice('Saved');
      setF({});
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  async function remove(id: string) {
    setError(''); setNotice('');
    try {
      await api(`/hrm/employees/${id}/field-profile`, { method: 'DELETE' });
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  const staff: Row[] = data?.staff || [];
  return (
    <>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
      <section className="hr-box hr-scroll" aria-label="Field staff this month">
        <div className="hr-cardhead"><h2>Field staff</h2></div>
        <div className="hr-row">
          <input type="month" aria-label="Field month" value={period} onChange={(e) => e.target.value && setPeriod(e.target.value)} />
          {data ? <span className="hr-muted">{Object.entries(data.by_role || {}).map(([k, n]) => `${roleWord(k)}: ${n}`).join(' · ') || 'No field staff yet'}</span> : null}
        </div>
        {data?.no_territory?.length ? <p className="hr-bad" role="alert">No territory yet: {data.no_territory.join(', ')}. Add them to a territory in FMCG so visits count.</p> : null}
        <table>
          <thead>
            <tr><th>Name</th><th>Job</th><th>Territory</th><th>Days in</th><th>Visits today</th><th>Visits (target)</th><th>Net sales</th><th>Target</th><th>Reached</th>{seesPay ? <th>Commission</th> : null}<th /></tr>
          </thead>
          <tbody>
            {staff.map((r) => (
              <tr key={r.employee_id}>
                <td>{r.name}{r.linked_login ? '' : <small className="hr-muted"> · no sign-in matches their email</small>}</td>
                <td>{roleWord(r.field_role)}</td>
                <td>{r.territories.join(', ') || '—'}</td>
                <td className="hr-num">{r.days_present}</td>
                <td className="hr-num">{r.visits_today}</td>
                <td className="hr-num">{r.visits_month}{r.visit_target != null ? ` / ${r.visit_target}` : ''}</td>
                <td className="hr-num">{formatMoney(r.net_sales)}</td>
                <td className="hr-num">{r.sales_target != null ? formatMoney(r.sales_target) : '—'}</td>
                <td className="hr-num">{r.achievement_pct != null ? `${r.achievement_pct}%` : '—'}</td>
                {seesPay ? <td className="hr-num">{formatMoney(r.commission)}</td> : null}
                <td><button type="button" className="btn-danger" aria-label={`Remove field job for ${r.name}`} onClick={() => void remove(r.employee_id)}>Remove</button></td>
              </tr>
            ))}
            {staff.length === 0 ? <tr><td colSpan={seesPay ? 11 : 10} className="hr-muted">No one has a field job yet.</td></tr> : null}
          </tbody>
        </table>
        <p className="hr-muted">Visits come from FMCG check-ins and sales from delivered orders, matched by the sign-in email on the staff record. Target visits = the territory&apos;s daily target × days in.</p>
      </section>
      <section className="hr-box" aria-label="Give someone a field job">
        <div className="hr-cardhead"><h2>Give someone a field job</h2></div>
        <div className="hr-row">
          <select aria-label="Field staff member" value={f.person || ''} onChange={(e) => setF({ ...f, person: e.target.value })}>
            <option value="">Choose a person…</option>
            {people.filter((p) => p.status === 'active').map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
          <select aria-label="Field job" value={f.role || 'rep'} onChange={(e) => setF({ ...f, role: e.target.value })}>
            {ROLES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input type="number" min="0" placeholder="Monthly sales target" aria-label="Monthly sales target" value={f.target || ''} onChange={(e) => setF({ ...f, target: e.target.value })} />
          <button type="button" disabled={!f.person} onClick={() => void save()}>Save field job</button>
        </div>
      </section>
    </>
  );
}
