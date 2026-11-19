'use client';

/** Case file for HR managers (notes, evidence, suspension, appeal decision) and a person's own appeal. */

import React, { useCallback, useEffect, useState } from 'react';
import { api, apiFetch } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const KIND_WORDS: Record<string, string> = {
  investigation: 'Investigation note', evidence: 'Evidence', suspension: 'Suspension', appeal: 'Appeal by the employee', appeal_decision: 'Appeal decision',
};

export function CaseFile({ cases }: { cases: Row[] }) {
  const [cid, setCid] = useState('');
  const [data, setData] = useState<Row | null>(null);
  const [f, setF] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    if (!cid) { setData(null); return; }
    try {
      setData((await api(`/hrm/cases/${cid}/events`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, [cid]);
  useEffect(() => { void load(); }, [load]);

  async function run(path: string, body: object | FormData, done: string) {
    setError(''); setNotice('');
    try {
      if (body instanceof FormData) {
        const res = await apiFetch(path, { method: 'POST', body });
        if (!res.ok) {
          const j = await res.json().catch(() => null);
          throw new Error(typeof j?.detail === 'string' ? j.detail : j?.detail?.message || 'The file was not saved.');
        }
      } else {
        await api(path, { method: 'POST', body: JSON.stringify(body) });
      }
      setNotice(done);
      setF({});
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  async function open(id: string, name: string) {
    const res = await apiFetch(`/hrm/cases/evidence/${id}/file`);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url; a.download = name || 'evidence'; a.click();
    URL.revokeObjectURL(url);
  }

  const chosen = cases.find((c) => c.id === cid);
  const set = (k: string, v: string) => setF({ ...f, [k]: v });

  return (
    <section className="hr-box hr-scroll" aria-label="Case file">
      <div className="hr-cardhead"><h2>Case file</h2></div>
      <div className="hr-row">
        <select aria-label="Choose a case file" value={cid} onChange={(e) => setCid(e.target.value)}>
          <option value="">Choose a case…</option>
          {cases.map((c) => <option key={c.id} value={c.id}>{c.case_number} · {c.employee_name} · {c.subject}</option>)}
        </select>
      </div>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
      {data && chosen ? (
        <>
          <table>
            <thead><tr><th>When</th><th>What</th><th>Detail</th></tr></thead>
            <tbody>
              {data.events.map((e: Row) => (
                <tr key={e.id}>
                  <td>{String(e.at || '').slice(0, 10)}</td>
                  <td>{KIND_WORDS[e.kind] || e.kind}{e.outcome ? `: ${e.outcome}` : ''}</td>
                  <td>
                    {e.note}{e.kind === 'suspension' ? ` (${e.starts_on}${e.ends_on ? ` to ${e.ends_on}` : ' onwards'})` : ''}
                    {e.has_file ? <> <button type="button" aria-label={`Open evidence ${e.filename}`} onClick={() => void open(e.id, e.filename)}>{e.filename}</button></> : null}
                  </td>
                </tr>
              ))}
              {data.events.length === 0 ? <tr><td colSpan={3} className="hr-muted">Nothing on file yet.</td></tr> : null}
            </tbody>
          </table>

          {chosen.status !== 'closed' ? (
            <>
              <div className="hr-row">
                <input placeholder="Investigation note" aria-label="Investigation note" value={f.note || ''} onChange={(e) => set('note', e.target.value)} />
                <button type="button" disabled={(f.note || '').trim().length < 2} onClick={() => run(`/hrm/cases/${cid}/notes`, { note: f.note.trim() }, 'Note added')}>Add note</button>
              </div>
              {chosen.kind === 'disciplinary' ? (
                <div className="hr-row">
                  <input type="date" aria-label="Suspension starts" value={f.s_from || ''} onChange={(e) => set('s_from', e.target.value)} />
                  <input type="date" aria-label="Suspension ends" value={f.s_to || ''} onChange={(e) => set('s_to', e.target.value)} />
                  <input placeholder="Why suspended" aria-label="Suspension reason" value={f.s_why || ''} onChange={(e) => set('s_why', e.target.value)} />
                  <button type="button" disabled={!f.s_from || (f.s_why || '').trim().length < 2}
                    onClick={() => run(`/hrm/cases/${cid}/suspension`, { starts_on: f.s_from, ends_on: f.s_to || null, note: f.s_why.trim() }, 'Suspension recorded')}>Record suspension</button>
                </div>
              ) : null}
            </>
          ) : null}

          {chosen.status !== 'closed' || data.appeal?.appeal ? (
            <div className="hr-row">
              <input type="file" aria-label="Evidence file" onChange={(e) => setF({ ...f, __file: e.target.files?.[0] ? '1' : '' })} id="case-evidence-file" />
              <input placeholder="What this file shows" aria-label="Evidence description" value={f.ev || ''} onChange={(e) => set('ev', e.target.value)} />
              <button type="button" disabled={(f.ev || '').trim().length < 2 || !f.__file}
                onClick={() => {
                  const file = (document.getElementById('case-evidence-file') as HTMLInputElement | null)?.files?.[0];
                  if (!file) return;
                  const fd = new FormData(); fd.append('file', file); fd.append('note', f.ev.trim());
                  void run(`/hrm/cases/${cid}/evidence`, fd, 'Evidence filed');
                }}>File evidence</button>
            </div>
          ) : null}

          {chosen.status === 'closed' ? (
            <div>
              <h3>Appeal</h3>
              {data.appeal?.decision ? <p>Decided: <strong>{data.appeal.decision.outcome}</strong>. {data.appeal.decision.note}</p>
                : data.appeal?.appeal ? (
                  <div className="hr-row">
                    <select aria-label="Appeal outcome" value={f.ao || ''} onChange={(e) => set('ao', e.target.value)}>
                      <option value="">Decide…</option><option value="upheld">Uphold the appeal</option><option value="rejected">Reject the appeal</option>
                    </select>
                    <input placeholder="Reasons" aria-label="Appeal decision note" value={f.an || ''} onChange={(e) => set('an', e.target.value)} />
                    <button type="button" disabled={!f.ao || (f.an || '').trim().length < 2}
                      onClick={() => run(`/hrm/cases/${cid}/appeal/decision`, { outcome: f.ao, note: f.an.trim() }, 'Appeal decided')}>Record decision</button>
                    <small className="hr-muted">Someone other than the person who closed the case must decide.</small>
                  </div>
                ) : <p className="hr-muted">No appeal lodged.{data.appeal?.can_appeal ? ` Open until ${data.appeal.deadline}.` : ''}</p>}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

/** A person's own appeal against a closed case about them. */
export function MyAppeal({ caseId }: { caseId: string }) {
  const [st, setSt] = useState<Row | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setSt((await api(`/hrm/me/cases/${caseId}/appeal`))?.data || null); } catch (err) { setError(problem(err)); }
  }, [caseId]);
  useEffect(() => { void load(); }, [load]);
  if (!st) return null;
  if (st.decision) return <small>Appeal {st.decision.outcome}.</small>;
  if (st.appeal) return <small>Appeal sent to HR.</small>;
  if (!st.can_appeal) return null;
  return (
    <span>
      <input placeholder="Why you disagree" aria-label="Appeal reason" value={reason} onChange={(e) => setReason(e.target.value)} />{' '}
      <button type="button" disabled={reason.trim().length < 2} aria-label="Appeal this outcome"
        onClick={async () => {
          try { await api(`/hrm/me/cases/${caseId}/appeal`, { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) }); setReason(''); await load(); } catch (err) { setError(problem(err)); }
        }}>Appeal (by {st.deadline})</button>
      {error ? <small className="hr-bad"> {error}</small> : null}
    </span>
  );
}
