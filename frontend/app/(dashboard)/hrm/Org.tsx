'use client';

/** Org chart (from each person's "Reports to") and headcount by department. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

function Branch({ node }: { node: Row }) {
  return (
    <li>
      <div className="hr-org-card">
        <strong>{node.name}</strong>
        <small className="hr-muted">{[node.job_title, node.department].filter(Boolean).join(' · ') || 'No job title'}</small>
        {node.team_size ? <small className="hr-muted">{node.team_size} report{node.team_size === 1 ? 's' : ''} to them</small> : null}
      </div>
      {node.reports?.length ? <ul>{node.reports.map((k: Row) => <Branch key={k.id} node={k} />)}</ul> : null}
    </li>
  );
}

export default function Org({ canPlan }: { canPlan: boolean }) {
  const [chart, setChart] = useState<Row | null>(null);
  const [heads, setHeads] = useState<Row[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [newDept, setNewDept] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [c, h] = await Promise.all([api('/hrm/org-chart'), api('/hrm/headcount')]);
      setChart(c?.data || null);
      setHeads(h?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function save(department: string, value: string) {
    setError('');
    try {
      const res = await api('/hrm/headcount', {
        method: 'PUT',
        body: JSON.stringify({ department, planned: value.trim() === '' ? null : Number(value) }),
      });
      setHeads(res?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <>
      <section className="hr-box hr-scroll" aria-label="Headcount">
        <div className="hr-cardhead"><h2>Headcount by department</h2></div>
        {error ? <p className="hr-bad" role="alert">{error}</p> : null}
        <table>
          <thead><tr><th>Department</th><th>Planned</th><th>Filled</th><th>Being hired</th><th>Still to find</th></tr></thead>
          <tbody>
            {heads.map((r) => (
              <tr key={r.department}>
                <td>{r.department}</td>
                <td>
                  {canPlan ? (
                    <input
                      type="number" min="0" style={{ maxWidth: 90 }} aria-label={`Planned headcount for ${r.department}`}
                      value={draft[r.department] ?? (r.planned ?? '')}
                      onChange={(e) => setDraft({ ...draft, [r.department]: e.target.value })}
                      onBlur={(e) => { if (String(r.planned ?? '') !== e.target.value) void save(r.department, e.target.value); }}
                    />
                  ) : (r.planned ?? '—')}
                </td>
                <td className="hr-num">{r.filled}</td><td className="hr-num">{r.hiring}</td>
                <td className={r.gap > 0 ? 'hr-num hr-bad' : 'hr-num'}>{r.gap == null ? '—' : r.gap < 0 ? `${-r.gap} over plan` : r.gap}</td>
              </tr>
            ))}
            {heads.length === 0 ? <tr><td colSpan={5} className="hr-muted">No staff yet.</td></tr> : null}
          </tbody>
        </table>
        {canPlan ? (
          <div className="hr-row">
            <input placeholder="Another department" value={newDept} onChange={(e) => setNewDept(e.target.value)} aria-label="New department to plan" />
            <button type="button" disabled={!newDept.trim()} onClick={() => { void save(newDept.trim(), '0'); setNewDept(''); }}>Add department</button>
          </div>
        ) : null}
        <p className="hr-muted">Still to find = planned less filled less open vacancies. Departments come from each staff record.</p>
      </section>
      <section className="hr-box hr-scroll" aria-label="Org chart">
        <div className="hr-cardhead"><h2>Who reports to whom</h2></div>
        {chart?.loops?.length ? (
          <p className="hr-bad" role="alert">
            These people report to each other in a circle. Change someone&apos;s &quot;Reports to&quot;: {chart.loops.map((n: Row) => n.name).join(', ')}.
          </p>
        ) : null}
        {chart?.roots?.length ? <ul className="hr-org">{chart.roots.map((n: Row) => <Branch key={n.id} node={n} />)}</ul> : <p className="hr-muted">No staff yet.</p>}
      </section>
    </>
  );
}
