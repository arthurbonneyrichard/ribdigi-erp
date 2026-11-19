'use client';

/**
 * Staff journey: onboarding and offboarding checklists, exit interview, career history, benefits,
 * custom fields, OKRs and succession. No pay figures appear here. Sections for HR managers only
 * (exit interview, career changes, OKRs, succession, field set-up) are hidden from officers; the
 * server refuses them too.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => new Date().toISOString().slice(0, 10);
const REASONS = ['better_pay', 'career_growth', 'relocation', 'personal', 'management', 'contract_end', 'dismissal', 'retirement', 'other'];
const words = (s: string) => s.replace(/_/g, ' ');

export const JOURNEY_SCREEN = { title: 'Staff journey', sub: 'Starting, moving, benefits, goals and leaving, one person at a time.', icon: 'users' };

export default function Journey({ isManager }: { isManager: boolean }) {
  const [people, setPeople] = useState<Row[]>([]);
  const [pid, setPid] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [open, setOpen] = useState<Row[]>([]);
  const [lists, setLists] = useState<Record<string, Row | null>>({});
  const [career, setCareer] = useState<Row[]>([]);
  const [benefits, setBenefits] = useState<Row[]>([]);
  const [fields, setFields] = useState<Row[]>([]);
  const [objs, setObjs] = useState<Row[]>([]);
  const [succ, setSucc] = useState<Row[]>([]);
  const [f, setF] = useState<Row>({});
  const [period, setPeriod] = useState(`${new Date().getFullYear()}`);

  const get = async (path: string) => (await api(path))?.data;

  const loadGeneral = useCallback(async () => {
    try {
      setPeople((await get('/hrm/employees')) || []);
      setOpen((await get('/hrm/checklists')) || []);
      if (isManager) {
        setObjs((await get(`/hrm/objectives?period=${encodeURIComponent(period)}`)) || []);
        setSucc((await get('/hrm/succession')) || []);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [isManager, period]);

  const loadPerson = useCallback(async () => {
    if (!pid) return;
    try {
      const [on, off, cr, be, cf] = await Promise.all([
        get(`/hrm/employees/${pid}/checklist/onboarding`),
        get(`/hrm/employees/${pid}/checklist/offboarding`),
        get(`/hrm/employees/${pid}/career`),
        get(`/hrm/employees/${pid}/benefits`),
        get(`/hrm/employees/${pid}/custom`),
      ]);
      setLists({ onboarding: on?.total ? on : null, offboarding: off?.total ? off : null });
      setCareer(cr || []);
      setBenefits(be || []);
      setFields(cf || []);
    } catch (err) {
      setError(problem(err));
    }
  }, [pid]);

  useEffect(() => { void loadGeneral(); }, [loadGeneral]);
  useEffect(() => { void loadPerson(); }, [loadPerson]);

  async function run(path: string, body: object | null, done: string, method = 'POST') {
    setError('');
    setNotice('');
    try {
      await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
      setNotice(done);
      await Promise.all([loadGeneral(), loadPerson()]);
    } catch (err) {
      setError(problem(err));
    }
  }

  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const nn = (v: string | undefined) => (v && v.trim() ? v.trim() : null);

  function Checklist({ kind }: { kind: 'onboarding' | 'offboarding' }) {
    const l = lists[kind];
    return (
      <section className="hr-box" aria-label={`${kind} checklist`}>
        <div className="hr-cardhead"><h2>{kind === 'onboarding' ? 'Onboarding' : 'Offboarding and clearance'}</h2></div>
        {!l ? (
          <button type="button" aria-label={`Start ${kind} checklist`} onClick={() => run(`/hrm/employees/${pid}/checklist`, { kind }, 'Checklist started')}>
            Start {kind} checklist
          </button>
        ) : (
          <>
            <p className="hr-muted">{l.done} of {l.total} done{l.complete ? ' — all clear' : ''}</p>
            <ul className="hr-list">
              {l.tasks.map((t: Row) => (
                <li key={t.id}>
                  <label>
                    <input type="checkbox" checked={t.done} aria-label={t.title}
                      onChange={() => run(`/hrm/checklist/tasks/${t.id}/${t.done ? 'undo' : 'done'}`, null, t.done ? 'Reopened' : 'Done')} />
                    {' '}{t.title}{t.done_on ? <small className="hr-muted"> · {t.done_on}</small> : null}
                  </label>
                </li>
              ))}
            </ul>
            <div className="hr-row">
              <input placeholder="Another step" aria-label={`New ${kind} step`} value={f[`task_${kind}`] || ''} onChange={(e) => set(`task_${kind}`, e.target.value)} />
              <button type="button" disabled={!(f[`task_${kind}`] || '').trim()}
                onClick={() => run(`/hrm/employees/${pid}/checklist/tasks`, { kind, title: f[`task_${kind}`].trim() }, 'Step added').then(() => set(`task_${kind}`, ''))}>Add step</button>
            </div>
            {kind === 'offboarding' && isManager ? (
              <div className="hr-row" aria-label="Exit interview">
                <strong>Exit interview{l.exit_interview ? ' (saved)' : ''}</strong>
                <select aria-label="Main reason for leaving" value={f.reason || l.exit_interview?.reason_category || ''} onChange={(e) => set('reason', e.target.value)}>
                  <option value="">Main reason…</option>
                  {REASONS.map((r) => <option key={r} value={r}>{words(r)}</option>)}
                </select>
                <input placeholder="What they told us" aria-label="Exit interview feedback" value={f.exit_fb ?? l.exit_interview?.feedback ?? ''} onChange={(e) => set('exit_fb', e.target.value)} />
                <button type="button" disabled={!(f.reason || l.exit_interview)}
                  onClick={() => run(`/hrm/employees/${pid}/exit-interview`, { held_on: today(), reason_category: f.reason || l.exit_interview.reason_category, feedback: nn(f.exit_fb ?? l.exit_interview?.feedback) }, 'Exit interview saved', 'PUT')}>
                  Save exit interview
                </button>
              </div>
            ) : null}
            {kind === 'offboarding' ? <p className="hr-muted">Clearing does not end employment. Record the leaving date on the Employees screen.</p> : null}
          </>
        )}
      </section>
    );
  }

  return (
    <>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      {notice ? <p className="hr-ok" role="status">{notice}</p> : null}

      <section className="hr-box" aria-label="Checklists still open">
        <div className="hr-cardhead"><h2>Checklists still open</h2></div>
        {open.length === 0 ? <p className="hr-muted">Nothing outstanding.</p> : (
          <ul className="hr-list">
            {open.map((o) => (
              <li key={`${o.employee_id}${o.kind}`}>
                <button type="button" aria-label={`Open ${o.kind} for ${o.name}`} onClick={() => setPid(o.employee_id)}>{o.name}</button>{' '}
                <span className="hr-muted">{o.kind} · {o.done}/{o.total}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="hr-row">
          <select aria-label="Choose a member of staff" value={pid} onChange={(e) => setPid(e.target.value)}>
            <option value="">Choose a person…</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}{p.status !== 'active' ? ' (left)' : ''}</option>)}
          </select>
        </div>
      </section>

      {pid ? (
        <>
          <Checklist kind="onboarding" />
          <Checklist kind="offboarding" />

          <section className="hr-box hr-scroll" aria-label="Career history">
            <div className="hr-cardhead"><h2>Career history</h2></div>
            <table>
              <thead><tr><th>Date</th><th>What</th><th>Job</th><th>Department</th><th>Note</th></tr></thead>
              <tbody>
                {career.map((c) => (
                  <tr key={c.id}>
                    <td>{c.effective_on}</td><td>{c.kind}</td>
                    <td>{c.to_job_title ? `${c.from_job_title || '—'} → ${c.to_job_title}` : '—'}</td>
                    <td>{c.to_department ? `${c.from_department || '—'} → ${c.to_department}` : '—'}</td>
                    <td>{c.note || ''}</td>
                  </tr>
                ))}
                {career.length === 0 ? <tr><td colSpan={5} className="hr-muted">Nothing recorded yet.</td></tr> : null}
              </tbody>
            </table>
            {isManager ? (
              <div className="hr-row">
                <select aria-label="Kind of change" value={f.ckind || 'promotion'} onChange={(e) => set('ckind', e.target.value)}>
                  {['promotion', 'transfer', 'confirmation', 'other'].map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
                <input placeholder="New job title" aria-label="New job title" value={f.cjob || ''} onChange={(e) => set('cjob', e.target.value)} />
                <input placeholder="New department" aria-label="New department" value={f.cdept || ''} onChange={(e) => set('cdept', e.target.value)} />
                <button type="button" onClick={() => run(`/hrm/employees/${pid}/career`, { kind: f.ckind || 'promotion', effective_on: today(), to_job_title: nn(f.cjob), to_department: nn(f.cdept), note: null }, 'Recorded')}>
                  Record change (today)
                </button>
              </div>
            ) : null}
            <p className="hr-muted">A change takes effect on the day you record it. Pay changes are made under pay, not here.</p>
          </section>

          <section className="hr-box hr-scroll" aria-label="Benefits">
            <div className="hr-cardhead"><h2>Benefits and insurance</h2></div>
            <table>
              <thead><tr><th>Benefit</th><th>Kind</th><th>Provider</th><th>Policy</th><th>From</th><th>Until</th><th /></tr></thead>
              <tbody>
                {benefits.map((b) => (
                  <tr key={b.id}>
                    <td>{b.name}</td><td>{b.kind}</td><td>{b.provider || ''}</td><td>{b.policy_number || ''}</td><td>{b.starts_on}</td><td>{b.ends_on || '—'}</td>
                    <td>{b.active ? <button type="button" className="btn-danger" aria-label={`End ${b.name}`} onClick={() => run(`/hrm/benefits/${b.id}/end`, { ends_on: today() }, 'Benefit ended')}>End</button> : null}</td>
                  </tr>
                ))}
                {benefits.length === 0 ? <tr><td colSpan={7} className="hr-muted">No benefits recorded.</td></tr> : null}
              </tbody>
            </table>
            <div className="hr-row">
              <select aria-label="Kind of benefit" value={f.bkind || 'insurance'} onChange={(e) => set('bkind', e.target.value)}>
                {['insurance', 'pension', 'welfare', 'other'].map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
              <input placeholder="Name, e.g. Group health" aria-label="Benefit name" value={f.bname || ''} onChange={(e) => set('bname', e.target.value)} />
              <input placeholder="Provider" aria-label="Benefit provider" value={f.bprov || ''} onChange={(e) => set('bprov', e.target.value)} />
              <input placeholder="Policy number" aria-label="Benefit policy number" value={f.bpol || ''} onChange={(e) => set('bpol', e.target.value)} />
              <input type="date" aria-label="Benefit starts on" value={f.bstart || today()} onChange={(e) => set('bstart', e.target.value)} />
              <button type="button" disabled={!(f.bname || '').trim()}
                onClick={() => run(`/hrm/employees/${pid}/benefits`, { kind: f.bkind || 'insurance', name: f.bname.trim(), provider: nn(f.bprov), policy_number: nn(f.bpol), starts_on: f.bstart || today() }, 'Benefit recorded')}>
                Add benefit
              </button>
            </div>
          </section>

          <section className="hr-box" aria-label="Custom fields">
            <div className="hr-cardhead"><h2>Extra details</h2></div>
            {fields.length === 0 ? <p className="hr-muted">No extra fields set up.</p> : (
              <div className="hr-grid">
                {fields.map((fl) => (
                  <label key={fl.field_id}>{fl.label}
                    <input type={fl.kind === 'number' ? 'number' : fl.kind === 'date' ? 'date' : 'text'} defaultValue={fl.value || ''} key={`${pid}${fl.field_id}${fl.value}`}
                      aria-label={fl.label}
                      onBlur={(e) => { if ((fl.value || '') !== e.target.value) void run(`/hrm/employees/${pid}/custom/${fl.field_id}`, { value: e.target.value }, 'Saved', 'PUT'); }} />
                  </label>
                ))}
              </div>
            )}
          </section>
        </>
      ) : <p className="hr-muted">Choose a person to see their checklists, career, benefits and details.</p>}

      {isManager ? (
        <>
          <section className="hr-box" aria-label="New extra field">
            <div className="hr-cardhead"><h2>Set up an extra staff field</h2></div>
            <div className="hr-row">
              <input placeholder="e.g. Shoe size" aria-label="Extra field name" value={f.flabel || ''} onChange={(e) => set('flabel', e.target.value)} />
              <select aria-label="Extra field type" value={f.fkind || 'text'} onChange={(e) => set('fkind', e.target.value)}>
                <option value="text">Text</option><option value="number">Number</option><option value="date">Date</option>
              </select>
              <button type="button" disabled={!(f.flabel || '').trim()} onClick={() => run('/hrm/custom-fields', { label: f.flabel.trim(), kind: f.fkind || 'text' }, 'Field added')}>Add field</button>
            </div>
          </section>

          <section className="hr-box hr-scroll" aria-label="Goals (OKRs)">
            <div className="hr-cardhead"><h2>Goals (OKRs)</h2></div>
            <div className="hr-row">
              <input aria-label="Goals period" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="2026 or 2026-Q4" />
            </div>
            {objs.map((o) => (
              <div key={o.id} className="hr-okr">
                <strong>{o.title}</strong> <small className="hr-muted">{o.level}{o.department ? ` · ${o.department}` : ''}{o.employee_id ? ` · ${people.find((p) => p.id === o.employee_id)?.full_name || ''}` : ''}</small>
                <span className="hr-meta"> {o.progress == null ? 'no key results yet' : `${o.progress}%`}</span>
                <ul>
                  {o.key_results.map((k: Row) => (
                    <li key={k.id}>
                      {k.title}: {k.current} / {k.target} {k.unit || ''} ({k.progress}%){' '}
                      <input type="number" min="0" style={{ maxWidth: 110 }} aria-label={`Progress for ${k.title}`} defaultValue={k.current}
                        onBlur={(e) => { if (Number(e.target.value) !== Number(k.current)) void run(`/hrm/objectives/${k.id}`, { current: Number(e.target.value) }, 'Progress saved', 'PATCH'); }} />
                    </li>
                  ))}
                </ul>
                <div className="hr-row">
                  <input placeholder="Key result" aria-label={`New key result for ${o.title}`} value={f[`kr_${o.id}`] || ''} onChange={(e) => set(`kr_${o.id}`, e.target.value)} />
                  <input type="number" min="1" placeholder="Target" aria-label={`Target for ${o.title}`} style={{ maxWidth: 110 }} value={f[`kt_${o.id}`] || ''} onChange={(e) => set(`kt_${o.id}`, e.target.value)} />
                  <button type="button" disabled={!(f[`kr_${o.id}`] || '').trim() || !Number(f[`kt_${o.id}`])}
                    onClick={() => run('/hrm/objectives', { kind: 'key_result', parent_id: o.id, title: f[`kr_${o.id}`].trim(), target: Number(f[`kt_${o.id}`]) }, 'Key result added')}>Add key result</button>
                </div>
              </div>
            ))}
            {objs.length === 0 ? <p className="hr-muted">No goals for {period}.</p> : null}
            <div className="hr-row">
              <select aria-label="Goal level" value={f.olevel || 'employee'} onChange={(e) => set('olevel', e.target.value)}>
                <option value="employee">Person</option><option value="department">Department</option><option value="company">Company</option>
              </select>
              {(f.olevel || 'employee') === 'employee' ? (
                <select aria-label="Goal for" value={f.operson || pid} onChange={(e) => set('operson', e.target.value)}>
                  <option value="">Choose…</option>
                  {people.filter((p) => p.status === 'active').map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              ) : null}
              {f.olevel === 'department' ? <input placeholder="Department" aria-label="Goal department" value={f.odept || ''} onChange={(e) => set('odept', e.target.value)} /> : null}
              <input placeholder="Objective" aria-label="New objective" value={f.otitle || ''} onChange={(e) => set('otitle', e.target.value)} />
              <button type="button" disabled={!(f.otitle || '').trim()}
                onClick={() => run('/hrm/objectives', { kind: 'objective', level: f.olevel || 'employee', period, title: f.otitle.trim(), employee_id: (f.olevel || 'employee') === 'employee' ? (f.operson || pid || null) : null, department: nn(f.odept) }, 'Objective added')}>Add objective</button>
            </div>
          </section>

          <section className="hr-box hr-scroll" aria-label="Succession">
            <div className="hr-cardhead"><h2>Succession</h2></div>
            <table>
              <thead><tr><th>Position</th><th>Now held by</th><th>Could be taken over by</th><th>Ready</th><th /></tr></thead>
              <tbody>
                {succ.map((s) => (
                  <tr key={s.id}>
                    <td>{s.position}</td><td>{s.incumbent || '—'}</td><td>{s.successor}</td><td>{words(s.readiness)}</td>
                    <td><button type="button" className="btn-danger" aria-label={`Remove succession plan for ${s.position}`} onClick={() => run(`/hrm/succession/${s.id}`, null, 'Removed', 'DELETE')}>Remove</button></td>
                  </tr>
                ))}
                {succ.length === 0 ? <tr><td colSpan={5} className="hr-muted">No succession plans.</td></tr> : null}
              </tbody>
            </table>
            <div className="hr-row">
              <input placeholder="Position" aria-label="Succession position" value={f.spos || ''} onChange={(e) => set('spos', e.target.value)} />
              <select aria-label="Successor" value={f.ssucc || ''} onChange={(e) => set('ssucc', e.target.value)}>
                <option value="">Successor…</option>
                {people.filter((p) => p.status === 'active').map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
              </select>
              <select aria-label="How soon" value={f.sready || 'one_two_years'} onChange={(e) => set('sready', e.target.value)}>
                <option value="ready_now">Ready now</option><option value="one_two_years">1–2 years</option><option value="three_plus">3+ years</option>
              </select>
              <button type="button" disabled={!(f.spos || '').trim() || !f.ssucc}
                onClick={() => run('/hrm/succession', { position: f.spos.trim(), successor_id: f.ssucc, readiness: f.sready || 'one_two_years', incumbent_id: pid || null }, 'Plan saved')}>
                Add plan{pid ? ' (current holder: selected person)' : ''}
              </button>
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}
