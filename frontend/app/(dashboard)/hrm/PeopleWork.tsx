'use client';

/**
 * HRM people work: hiring, reviews, training, contracts, cases, staff kit, claims and
 * notices, plus the staff side of each under My pay and leave. Same look as the rest of
 * the HRM desk (hrm.css); the server decides who may do what (hrm.job).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => new Date().toISOString().slice(0, 10);
const PAY_METHODS = [
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'cash', label: 'Cash' },
  { id: 'cheque', label: 'Cheque' },
];
const STAGE_WORDS: Record<string, string> = {
  applied: 'Applied', screening: 'Screening', interview: 'Interview', offer: 'Offer made',
  hired: 'Hired', rejected: 'Not taken', withdrawn: 'Withdrew',
};
const NEXT: Record<string, string> = { applied: 'screening', screening: 'interview', interview: 'offer' };
const OUTCOMES: Record<string, { id: string; label: string }[]> = {
  disciplinary: [
    { id: 'none', label: 'No action' },
    { id: 'verbal_warning', label: 'Verbal warning' },
    { id: 'written_warning', label: 'Written warning' },
    { id: 'final_warning', label: 'Final written warning' },
    { id: 'suspension', label: 'Suspension' },
    { id: 'dismissal', label: 'Dismissal' },
  ],
  grievance: [
    { id: 'upheld', label: 'Upheld' },
    { id: 'not_upheld', label: 'Not upheld' },
    { id: 'none', label: 'Withdrawn, no finding' },
  ],
};

export const PEOPLE_WORK_SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  hiring: { title: 'Hiring', sub: 'Open jobs, candidates stage by stage, offers and new starters.', icon: 'users' },
  reviews: { title: 'Reviews', sub: 'Weighted goals, the person’s own view, then the reviewer’s score.', icon: 'chart' },
  training: { title: 'Training', sub: 'Courses, who has done them, what is due again.', icon: 'calendarCheck' },
  contracts: { title: 'Contracts', sub: 'Terms, end dates and probation to confirm.', icon: 'receipt' },
  cases: { title: 'Cases', sub: 'Disciplinary cases and grievances. Confidential.', icon: 'alert' },
  kit: { title: 'Staff kit', sub: 'Laptops, phones, uniforms and vehicles held by staff.', icon: 'tag' },
  claims: { title: 'Expense claims', sub: 'Money staff spent for the company, paid back once approved.', icon: 'wallet' },
  notices: { title: 'Notices', sub: 'Announcements and HR policies staff can read.', icon: 'calendar' },
};

function useRunner(reload: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function run(path: string, body: object | null, done: string, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      setNotice(done);
      await reload();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, notice, run, setError };
}

function Banner({ error, notice }: { error: string; notice: string }) {
  return (
    <>
      {notice ? <div className="hr-banner" role="status">{notice}</div> : null}
      {error ? <div className="hr-banner bad" role="alert">{error}</div> : null}
    </>
  );
}

function PersonPick({ people, value, onChange, label }: { people: Row[]; value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label><span>Employee</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        <option value="">Choose</option>
        {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
      </select>
    </label>
  );
}

export function PeopleWork({ tab, seesPay }: { tab: string; seesPay: boolean }) {
  const [people, setPeople] = useState<Row[]>([]);
  const [data, setData] = useState<Row | null>(null);
  const [extra, setExtra] = useState<Row[]>([]);
  const [openVac, setOpenVac] = useState('');
  const [f, setF] = useState<Row>({});
  // Which screen is showing now. Data is tagged with the screen it was loaded for, so a
  // sidebar click from one screen to another never renders the old screen's data in the new
  // one (that crashed Training after Hiring), and a late answer for a screen left behind is dropped.
  const tabRef = useRef(tab);
  tabRef.current = tab;

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    const keep = (value: Row) => {
      if (tabRef.current === tab) setData({ ...value, __tab: tab });
    };
    const staff = (await get('/hrm/employees').catch(() => [])) || [];
    if (tabRef.current === tab) setPeople(staff);
    if (tab === 'hiring') keep({ vacancies: (await get('/hrm/vacancies')) || [] });
    if (tab === 'reviews') keep({ reviews: (await get('/hrm/reviews')) || [] });
    if (tab === 'training') keep({ courses: [], records: [], gaps: [], ...((await get('/hrm/trainings')) || {}) });
    if (tab === 'contracts') keep({ contracts: [], alerts: { contracts_ending: [], probation_due: [] }, ...((await get('/hrm/contracts')) || {}) });
    if (tab === 'cases') keep({ cases: (await get('/hrm/cases')) || [] });
    if (tab === 'kit') keep({ assets: (await get('/hrm/assets')) || [] });
    if (tab === 'claims') keep({ claims: (await get('/hrm/claims')) || [] });
    if (tab === 'notices') keep({ notices: (await get('/hrm/notices')) || [] });
  }, [tab]);
  const { busy, error, notice, run, setError } = useRunner(load);

  useEffect(() => {
    setF({});
    setData(null);
    load().catch((err) => setError(problem(err)));
  }, [load, setError]);

  useEffect(() => {
    if (!openVac) return;
    api(`/hrm/vacancies/${openVac}/candidates`).then((r) => setExtra(r?.data || [])).catch((err) => setError(problem(err)));
  }, [openVac, data, setError]);

  const set = (key: string, value: unknown) => setF((old) => ({ ...old, [key]: value }));
  const txt = (key: string) => String(f[key] ?? '');

  if (!data || data.__tab !== tab) return <Banner error={error} notice={notice} />;

  return (
    <>
      <Banner error={error} notice={notice} />

      {tab === 'hiring' ? (
        <>
          <section className="hr-box" aria-label="Open a vacancy">
            <h2>Open a job</h2>
            <div className="hr-form">
              <label><span>Job title</span><input value={txt('title')} onChange={(e) => set('title', e.target.value)} aria-label="Vacancy title" /></label>
              <label><span>Department</span><input value={txt('department')} onChange={(e) => set('department', e.target.value)} aria-label="Vacancy department" /></label>
              <label><span>People needed</span><input type="number" min="1" value={txt('openings') || '1'} onChange={(e) => set('openings', e.target.value)} aria-label="Vacancy openings" /></label>
              <label><span>Closes on</span><input type="date" value={txt('closes_on')} onChange={(e) => set('closes_on', e.target.value)} aria-label="Vacancy closes on" /></label>
              <label className="hr-wide"><span>What the job is</span><textarea value={txt('description')} onChange={(e) => set('description', e.target.value)} aria-label="Vacancy description" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || txt('title').trim().length < 2}
                onClick={async () => {
                  if (await run('/hrm/vacancies', { title: txt('title').trim(), department: txt('department').trim() || null, openings: Number(f.openings || 1), closes_on: f.closes_on || null, description: txt('description').trim() || null }, 'Vacancy opened')) setF({});
                }}
              >Open job</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Vacancies">
            <h2>Jobs</h2>
            <table>
              <thead><tr><th>Job</th><th>Status</th><th>Candidates</th><th /></tr></thead>
              <tbody>
                {data.vacancies.map((v: Row) => (
                  <tr key={v.id}>
                    <td>{v.title}{v.department ? <><br /><small className="hr-muted">{v.department}</small></> : null}</td>
                    <td>{v.status === 'open' ? 'Open' : v.status === 'filled' ? 'Filled' : 'Closed'}</td>
                    <td>{Object.entries(v.candidates || {}).map(([k, n]) => `${STAGE_WORDS[k] || k}: ${n}`).join(', ') || 'None yet'}</td>
                    <td>
                      <div className="hr-row">
                        <button type="button" onClick={() => setOpenVac(openVac === v.id ? '' : v.id)}>{openVac === v.id ? 'Hide' : 'Candidates'}</button>
                        {v.status === 'open' ? <button type="button" className="hr-danger" onClick={() => void run(`/hrm/vacancies/${v.id}/close`, null, 'Vacancy closed')}>Close</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {data.vacancies.length === 0 ? <tr><td colSpan={4} className="hr-muted">No jobs yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          {openVac ? (
            <section className="hr-box hr-scroll" aria-label="Candidates">
              <h2>Candidates</h2>
              <div className="hr-form">
                <label><span>Name</span><input value={txt('c_name')} onChange={(e) => set('c_name', e.target.value)} aria-label="Candidate name" /></label>
                <label><span>Email</span><input value={txt('c_email')} onChange={(e) => set('c_email', e.target.value)} aria-label="Candidate email" /></label>
                <label><span>Phone</span><input value={txt('c_phone')} placeholder="+233…" onChange={(e) => set('c_phone', e.target.value)} aria-label="Candidate phone" /></label>
                <button
                  type="button" className="hr-primary" disabled={busy || txt('c_name').trim().length < 2}
                  onClick={async () => {
                    if (await run(`/hrm/vacancies/${openVac}/candidates`, { full_name: txt('c_name').trim(), email: txt('c_email').trim() || null, phone: txt('c_phone').replace(/[\s-]/g, '') || null }, 'Candidate added')) setF({});
                  }}
                >Add candidate</button>
              </div>
              <table>
                <thead><tr><th>Name</th><th>Stage</th><th>Score</th><th /></tr></thead>
                <tbody>
                  {extra.map((c) => (
                    <tr key={c.id}>
                      <td>{c.full_name}<br /><small className="hr-muted">{c.email || c.phone || ''}</small></td>
                      <td>{STAGE_WORDS[c.stage] || c.stage}{c.offered_basic != null ? <><br /><small className="hr-muted">Offer {money(c.offered_basic)}</small></> : null}</td>
                      <td>{c.score ?? '—'}</td>
                      <td>
                        <div className="hr-row">
                          {NEXT[c.stage] === 'offer' && seesPay ? (
                            <input type="number" min="0" placeholder="Basic a month" style={{ maxWidth: 140 }} value={f[`pay_${c.id}`] || ''} onChange={(e) => set(`pay_${c.id}`, e.target.value)} aria-label={`Basic salary offered to ${c.full_name}`} />
                          ) : null}
                          {NEXT[c.stage] && (NEXT[c.stage] !== 'offer' || seesPay) ? (
                            <button
                              type="button" className="hr-primary" disabled={busy || (NEXT[c.stage] === 'offer' && !(Number(f[`pay_${c.id}`]) > 0))}
                              onClick={() => {
                                if (NEXT[c.stage] === 'offer') {
                                  void run(`/hrm/candidates/${c.id}/move`, { stage: 'offer', offered_basic: Number(f[`pay_${c.id}`]) }, 'Offer recorded');
                                } else {
                                  void run(`/hrm/candidates/${c.id}/move`, { stage: NEXT[c.stage] }, 'Moved on');
                                }
                              }}
                            >{NEXT[c.stage] === 'offer' ? 'Make offer' : `Move to ${STAGE_WORDS[NEXT[c.stage]].toLowerCase()}`}</button>
                          ) : null}
                          {c.stage === 'offer' && seesPay ? (
                            <>
                              <input type="date" value={f[`start_${c.id}`] || today()} onChange={(e) => set(`start_${c.id}`, e.target.value)} aria-label={`First day for ${c.full_name}`} />
                              <input type="number" min="0" max="12" style={{ maxWidth: 90 }} value={f[`prob_${c.id}`] ?? '3'} onChange={(e) => set(`prob_${c.id}`, e.target.value)} aria-label={`Probation months for ${c.full_name}`} title="Probation months (0 for none)" />
                              <button
                                type="button" className="hr-primary" disabled={busy}
                                onClick={() => void run(`/hrm/candidates/${c.id}/hire`, { starts_on: f[`start_${c.id}`] || today(), probation_months: Number(f[`prob_${c.id}`] ?? 3) }, 'Hired: their staff record is ready')}
                              >Hire</button>
                            </>
                          ) : null}
                          {!['hired', 'rejected', 'withdrawn'].includes(c.stage) ? (
                            <button type="button" className="hr-danger" disabled={busy} onClick={() => void run(`/hrm/candidates/${c.id}/move`, { stage: 'rejected' }, 'Marked as not taken')}>Not taken</button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {extra.length === 0 ? <tr><td colSpan={4} className="hr-muted">No candidates yet.</td></tr> : null}
                </tbody>
              </table>
            </section>
          ) : null}
        </>
      ) : null}

      {tab === 'reviews' ? (
        <>
          <section className="hr-box" aria-label="Start a review">
            <h2>Start a review</h2>
            <p className="hr-muted">Write up to six goals with weights that add up to 100. The person scores themselves first, then the reviewer scores 1 to 5.</p>
            <div className="hr-form">
              <PersonPick people={people} value={txt('employee_id')} onChange={(v) => set('employee_id', v)} label="Review employee" />
              <label><span>Period</span><input value={txt('cycle')} placeholder="2026 year end" onChange={(e) => set('cycle', e.target.value)} aria-label="Review period" /></label>
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <React.Fragment key={i}>
                  <label><span>Goal {i + 1}</span><input value={txt(`g${i}`)} onChange={(e) => set(`g${i}`, e.target.value)} aria-label={`Goal ${i + 1}`} /></label>
                  <label><span>Weight %</span><input type="number" min="0" max="100" value={txt(`w${i}`)} onChange={(e) => set(`w${i}`, e.target.value)} aria-label={`Goal ${i + 1} weight`} /></label>
                  <label><span>Target (optional)</span><input type="number" value={txt(`t${i}`)} onChange={(e) => set(`t${i}`, e.target.value)} aria-label={`Goal ${i + 1} target`} /></label>
                  <label><span>Counted in</span><input value={txt(`u${i}`)} placeholder="GHS, sales, %" maxLength={30} onChange={(e) => set(`u${i}`, e.target.value)} aria-label={`Goal ${i + 1} unit`} /></label>
                </React.Fragment>
              ))}
              <button
                type="button" className="hr-primary" disabled={busy || !f.employee_id || txt('cycle').trim().length < 2}
                onClick={async () => {
                  const goals = [0, 1, 2, 3, 4, 5].filter((i) => txt(`g${i}`).trim()).map((i) => ({
                    title: txt(`g${i}`).trim(),
                    weight: Number(f[`w${i}`] || 0),
                    target: txt(`t${i}`).trim() ? Number(f[`t${i}`]) : null,
                    unit: txt(`u${i}`).trim() || null,
                  }));
                  if (await run('/hrm/reviews', { employee_id: f.employee_id, cycle: txt('cycle').trim(), goals }, 'Review started')) setF({});
                }}
              >Start review</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Reviews">
            <h2>Reviews</h2>
            <table>
              <thead><tr><th>Who</th><th>Period</th><th>Goals</th><th>Status</th><th>Score</th><th /></tr></thead>
              <tbody>
                {data.reviews.map((r: Row) => (
                  <tr key={r.id}>
                    <td>{r.employee_name}</td><td>{r.cycle}</td>
                    <td>
                      {(r.goals || []).map((g: Row) => `${g.title} (${g.weight}%)${g.target != null ? ` target ${g.target}${g.unit ? ` ${g.unit}` : ''}${g.actual != null ? `, so far ${g.actual} (${g.progress ?? '—'}%)` : ''}` : ''}${g.self_score ? ` self ${g.self_score}` : ''}${g.score ? ` · ${g.score}` : ''}`).join('; ')}
                      {r.feedback?.asked ? (
                        <><br /><small className="hr-muted">
                          360: {r.feedback.given} of {r.feedback.asked} answered{r.feedback.average != null ? `, average ${r.feedback.average}` : ''}
                          {r.feedback.waiting_on?.length ? ` · waiting on ${r.feedback.waiting_on.join(', ')}` : ''}
                        </small></>
                      ) : null}
                    </td>
                    <td>{({ open: 'Waiting for their view', self_done: 'Ready to score', done: 'Finished' } as Row)[r.status] || r.status}</td>
                    <td>{r.overall ?? '—'}</td>
                    <td>
                      {r.status !== 'done' ? (
                        <button type="button" className="hr-primary" disabled={busy} aria-label={`Open review for ${r.employee_name}`} onClick={() => set('open_review', f.open_review === r.id ? '' : r.id)}>
                          {f.open_review === r.id ? 'Close' : 'Score, track, ask'}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {data.reviews.length === 0 ? <tr><td colSpan={6} className="hr-muted">No reviews yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          {data.reviews.filter((r: Row) => r.id === f.open_review).map((r: Row) => (
            <section className="hr-box" aria-label={`Review of ${r.employee_name}`} key={r.id}>
              <h2>{r.employee_name}: {r.cycle}</h2>
              {r.self_comment ? <p className="hr-muted">Their view: {r.self_comment}</p> : null}
              <div className="hr-form">
                {(r.goals || []).map((g: Row, i: number) => (
                  <React.Fragment key={i}>
                    <label><span>{g.title} ({g.weight}%){g.self_score ? `, they said ${g.self_score}` : ''}</span>
                      <select value={f[`s_${r.id}_${i}`] || ''} onChange={(e) => set(`s_${r.id}_${i}`, e.target.value)} aria-label={`Score for ${g.title}`}>
                        <option value="">Score</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </label>
                    {g.target != null ? (
                      <label><span>So far (target {g.target}{g.unit ? ` ${g.unit}` : ''})</span>
                        <input type="number" value={txt(`a_${r.id}_${i}`) || (g.actual ?? '')} onChange={(e) => set(`a_${r.id}_${i}`, e.target.value)}
                          onBlur={(e) => { if (e.target.value !== '' && e.target.value !== String(g.actual ?? '')) void run(`/hrm/reviews/${r.id}/progress`, { goal: i, actual: Number(e.target.value) }, 'Progress saved'); }}
                          aria-label={`Progress on ${g.title}`} />
                      </label>
                    ) : null}
                  </React.Fragment>
                ))}
                <label className="hr-wide"><span>Your comments</span><textarea value={txt(`c_${r.id}`)} onChange={(e) => set(`c_${r.id}`, e.target.value)} aria-label="Reviewer comments" /></label>
                <button
                  type="button" className="hr-primary"
                  disabled={busy || (r.goals || []).some((_g: Row, i: number) => !f[`s_${r.id}_${i}`])}
                  onClick={async () => {
                    const scores = (r.goals || []).map((_g: Row, i: number) => Number(f[`s_${r.id}_${i}`]));
                    if (await run(`/hrm/reviews/${r.id}/complete`, { scores, comment: txt(`c_${r.id}`).trim() || null }, 'Review finished')) set('open_review', '');
                  }}
                >Finish review</button>
              </div>
              <h3>360 feedback</h3>
              <p className="hr-muted">Colleagues give a 1 to 5 rating and comments. Answers are shown without names, and only once two have answered.</p>
              {r.feedback?.comments?.length ? (
                <ul>{r.feedback.comments.map((c: Row, i: number) => <li key={i}>{c.rating}/5 · {[c.strengths && `Does well: ${c.strengths}`, c.improve && `Could be better: ${c.improve}`].filter(Boolean).join(' · ')}</li>)}</ul>
              ) : null}
              <div className="hr-row">
                <select multiple value={(f[`ask_${r.id}`] as string[]) || []} onChange={(e) => set(`ask_${r.id}`, Array.from(e.target.selectedOptions).map((o) => o.value))} aria-label="Colleagues to ask" style={{ minHeight: 90 }}>
                  {people.filter((p: Row) => p.id !== r.employee_id).map((p: Row) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
                <button
                  type="button" disabled={busy || !((f[`ask_${r.id}`] as string[]) || []).length}
                  onClick={async () => { if (await run(`/hrm/reviews/${r.id}/feedback`, { employee_ids: f[`ask_${r.id}`] }, 'Colleagues asked')) set(`ask_${r.id}`, []); }}
                >Ask for feedback</button>
              </div>
            </section>
          ))}
        </>
      ) : null}

      {tab === 'training' ? (
        <>
          {data.gaps?.length ? (
            <section className="hr-box hr-scroll" aria-label="Training due">
              <h2>Mandatory training due</h2>
              <table><tbody>{data.gaps.map((g: Row, i: number) => <tr key={i}><td>{g.employee_name}</td><td>{g.training}</td><td>{g.why}</td></tr>)}</tbody></table>
            </section>
          ) : null}
          <section className="hr-box" aria-label="Add a course">
            <h2>Courses</h2>
            <div className="hr-form">
              <label><span>Course</span><input value={txt('title')} onChange={(e) => set('title', e.target.value)} aria-label="Course title" /></label>
              <label><span>Provider</span><input value={txt('provider')} onChange={(e) => set('provider', e.target.value)} aria-label="Course provider" /></label>
              <label><span>Valid for months (blank = always)</span><input type="number" min="1" value={txt('valid_months')} onChange={(e) => set('valid_months', e.target.value)} aria-label="Course valid months" /></label>
              <label className="hr-check"><input type="checkbox" checked={Boolean(f.mandatory)} onChange={(e) => set('mandatory', e.target.checked)} aria-label="Course is mandatory" /><span>Everyone must have it</span></label>
              <button
                type="button" className="hr-primary" disabled={busy || txt('title').trim().length < 2}
                onClick={async () => {
                  if (await run('/hrm/trainings', { title: txt('title').trim(), provider: txt('provider').trim() || null, mandatory: Boolean(f.mandatory), valid_months: f.valid_months ? Number(f.valid_months) : null }, 'Course added')) setF({});
                }}
              >Add course</button>
            </div>
            <table><tbody>{data.courses.map((c: Row) => <tr key={c.id}><td>{c.title}</td><td>{c.provider || '—'}</td><td>{c.mandatory ? 'Mandatory' : 'Optional'}</td><td>{c.valid_months ? `${c.valid_months} months` : 'Does not expire'}</td></tr>)}</tbody></table>
          </section>
          <section className="hr-box hr-scroll" aria-label="Record training">
            <h2>Who has done what</h2>
            <div className="hr-form">
              <PersonPick people={people} value={txt('employee_id')} onChange={(v) => set('employee_id', v)} label="Training employee" />
              <label><span>Course</span>
                <select value={txt('training_id')} onChange={(e) => set('training_id', e.target.value)} aria-label="Training course">
                  <option value="">Choose</option>
                  {data.courses.map((c: Row) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </label>
              <label><span>Done on</span><input type="date" value={txt('completed_on')} onChange={(e) => set('completed_on', e.target.value)} aria-label="Training done on" /></label>
              <label><span>Certificate</span><input value={txt('certificate_ref')} onChange={(e) => set('certificate_ref', e.target.value)} aria-label="Certificate reference" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !f.employee_id || !f.training_id || !f.completed_on}
                onClick={async () => {
                  if (await run('/hrm/training-records', { employee_id: f.employee_id, training_id: f.training_id, completed_on: f.completed_on, certificate_ref: txt('certificate_ref').trim() || null }, 'Training recorded')) setF({});
                }}
              >Record</button>
            </div>
            <table>
              <thead><tr><th>Who</th><th>Course</th><th>Done</th><th>Due again</th></tr></thead>
              <tbody>{data.records.map((r: Row) => <tr key={r.id}><td>{r.employee_name}</td><td>{r.training}</td><td>{r.completed_on}</td><td>{r.expires_on ? `${r.expires_on}${r.state !== 'valid' ? ` (${r.state})` : ''}` : '—'}</td></tr>)}</tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'contracts' ? (
        <>
          {(data.alerts?.contracts_ending?.length || data.alerts?.probation_due?.length) ? (
            <section className="hr-box" aria-label="Coming up">
              <h2>In the next 30 days</h2>
              {data.alerts.contracts_ending.map((c: Row) => <div className="hr-line" key={`e${c.id}`}><span>{c.employee_name}: contract ends</span><span>{c.ends_on}</span></div>)}
              {data.alerts.probation_due.map((c: Row) => (
                <div className="hr-line" key={`p${c.id}`}>
                  <span>{c.employee_name}: probation ends {c.probation_ends_on}</span>
                  <button type="button" className="hr-primary" disabled={busy} onClick={() => void run(`/hrm/contracts/${c.id}/confirm`, null, 'Probation confirmed')}>Confirm</button>
                </div>
              ))}
            </section>
          ) : null}
          <section className="hr-box" aria-label="Add a contract">
            <h2>Record a contract</h2>
            <div className="hr-form">
              <PersonPick people={people} value={txt('employee_id')} onChange={(v) => set('employee_id', v)} label="Contract employee" />
              <label><span>Kind</span>
                <select value={txt('kind') || 'permanent'} onChange={(e) => set('kind', e.target.value)} aria-label="Contract kind">
                  <option value="permanent">Permanent</option><option value="fixed_term">Fixed term</option><option value="casual">Casual</option><option value="probation">Probation</option>
                </select>
              </label>
              <label><span>Starts</span><input type="date" value={txt('starts_on')} onChange={(e) => set('starts_on', e.target.value)} aria-label="Contract starts" /></label>
              <label><span>Ends</span><input type="date" value={txt('ends_on')} onChange={(e) => set('ends_on', e.target.value)} aria-label="Contract ends" /></label>
              <label><span>Probation ends</span><input type="date" value={txt('probation_ends_on')} onChange={(e) => set('probation_ends_on', e.target.value)} aria-label="Probation ends" /></label>
              <label><span>Reference</span><input value={txt('reference')} onChange={(e) => set('reference', e.target.value)} aria-label="Contract reference" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !f.employee_id || !f.starts_on}
                onClick={async () => {
                  if (await run('/hrm/contracts', { employee_id: f.employee_id, kind: f.kind || 'permanent', starts_on: f.starts_on, ends_on: f.ends_on || null, probation_ends_on: f.probation_ends_on || null, reference: txt('reference').trim() || null }, 'Contract saved')) setF({});
                }}
              >Save contract</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Contracts">
            <h2>Contracts</h2>
            <table>
              <thead><tr><th>Who</th><th>Kind</th><th>From</th><th>To</th><th>Probation</th></tr></thead>
              <tbody>{data.contracts.map((c: Row) => <tr key={c.id}><td>{c.employee_name}</td><td>{c.kind.replace('_', ' ')}</td><td>{c.starts_on}</td><td>{c.ends_on || 'Open-ended'}</td><td>{c.probation_ends_on ? (c.confirmed_on ? `Confirmed ${c.confirmed_on}` : `Ends ${c.probation_ends_on}`) : '—'}</td></tr>)}</tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'cases' ? (
        <>
          <section className="hr-box" aria-label="Open a case">
            <h2>Open a case</h2>
            <p className="hr-muted">Only HR managers see cases. Staff see that a case exists and how it ended, not these notes.</p>
            <div className="hr-form">
              <PersonPick people={people} value={txt('employee_id')} onChange={(v) => set('employee_id', v)} label="Case employee" />
              <label><span>Kind</span>
                <select value={txt('kind') || 'disciplinary'} onChange={(e) => set('kind', e.target.value)} aria-label="Case kind">
                  <option value="disciplinary">Disciplinary</option><option value="grievance">Grievance</option>
                </select>
              </label>
              <label><span>Subject</span><input value={txt('subject')} onChange={(e) => set('subject', e.target.value)} aria-label="Case subject" /></label>
              <label className="hr-wide"><span>What happened</span><textarea value={txt('details')} onChange={(e) => set('details', e.target.value)} aria-label="Case details" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !f.employee_id || txt('subject').trim().length < 2 || txt('details').trim().length < 2}
                onClick={async () => {
                  if (await run('/hrm/cases', { employee_id: f.employee_id, kind: f.kind || 'disciplinary', subject: txt('subject').trim(), details: txt('details').trim() }, 'Case opened')) setF({});
                }}
              >Open case</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Cases">
            <h2>Cases</h2>
            <table>
              <thead><tr><th>Case</th><th>Who</th><th>About</th><th>Status</th><th /></tr></thead>
              <tbody>
                {data.cases.map((c: Row) => (
                  <tr key={c.id}>
                    <td>{c.case_number}<br /><small className="hr-muted">{c.kind}</small></td>
                    <td>{c.employee_name}</td>
                    <td>{c.subject}<br /><small className="hr-muted">{c.details}</small>{c.outcome_note ? <><br /><small>Outcome: {c.outcome_note}</small></> : null}</td>
                    <td>{c.status === 'closed' ? (OUTCOMES[c.kind]?.find((o) => o.id === c.outcome)?.label || c.outcome) : 'Open'}</td>
                    <td>
                      {c.status !== 'closed' ? (
                        <div className="hr-row">
                          <select aria-label={`Outcome for ${c.case_number}`} value={f[`o_${c.id}`] || ''} onChange={(e) => set(`o_${c.id}`, e.target.value)}>
                            <option value="">Outcome…</option>
                            {OUTCOMES[c.kind].map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                          </select>
                          <input placeholder="What was decided, and why" value={f[`on_${c.id}`] || ''} onChange={(e) => set(`on_${c.id}`, e.target.value)} aria-label={`Decision note for ${c.case_number}`} />
                          <button
                            type="button" className="hr-primary" disabled={busy || !f[`o_${c.id}`] || String(f[`on_${c.id}`] || '').trim().length < 2}
                            onClick={() => void run(`/hrm/cases/${c.id}`, { close: true, outcome: f[`o_${c.id}`], outcome_note: String(f[`on_${c.id}`]).trim() }, 'Case closed', 'PATCH')}
                          >Close case</button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {data.cases.length === 0 ? <tr><td colSpan={5} className="hr-muted">No cases.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'kit' ? (
        <>
          <section className="hr-box" aria-label="Issue an item">
            <h2>Issue an item</h2>
            <div className="hr-form">
              <PersonPick people={people} value={txt('employee_id')} onChange={(v) => set('employee_id', v)} label="Kit employee" />
              <label><span>Item</span><input value={txt('item')} onChange={(e) => set('item', e.target.value)} aria-label="Kit item" /></label>
              <label><span>Kind</span>
                <select value={txt('kind') || 'other'} onChange={(e) => set('kind', e.target.value)} aria-label="Kit kind">
                  {['laptop', 'phone', 'uniform', 'vehicle', 'tool', 'other'].map((k) => <option key={k} value={k}>{k[0].toUpperCase() + k.slice(1)}</option>)}
                </select>
              </label>
              <label><span>Serial</span><input value={txt('serial')} onChange={(e) => set('serial', e.target.value)} aria-label="Kit serial" /></label>
              <label><span>Issued on</span><input type="date" value={txt('issued_on')} onChange={(e) => set('issued_on', e.target.value)} aria-label="Kit issued on" /></label>
              <label><span>Condition</span><input value={txt('condition')} onChange={(e) => set('condition', e.target.value)} aria-label="Kit condition" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !f.employee_id || txt('item').trim().length < 2 || !f.issued_on}
                onClick={async () => {
                  if (await run('/hrm/assets', { employee_id: f.employee_id, item: txt('item').trim(), kind: f.kind || 'other', serial: txt('serial').trim() || null, issued_on: f.issued_on, condition: txt('condition').trim() || null }, 'Item issued')) setF({});
                }}
              >Issue</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Staff kit">
            <h2>Held by staff</h2>
            <table>
              <thead><tr><th>Item</th><th>Who</th><th>Issued</th><th>Back</th><th /></tr></thead>
              <tbody>
                {data.assets.map((a: Row) => (
                  <tr key={a.id}>
                    <td>{a.item}{a.serial ? <><br /><small className="hr-muted">{a.serial}</small></> : null}</td>
                    <td>{a.employee_name}</td><td>{a.issued_on}</td>
                    <td>{a.returned_on ? `${a.returned_on} (${a.condition_back})` : 'Still out'}</td>
                    <td>
                      {!a.returned_on ? (
                        <div className="hr-row">
                          <input placeholder="Condition" style={{ maxWidth: 140 }} value={f[`cond_${a.id}`] ?? 'Good'} onChange={(e) => set(`cond_${a.id}`, e.target.value)} aria-label={`Condition of returned item ${a.id}`} />
                          <button
                            type="button" disabled={busy || String(f[`cond_${a.id}`] ?? 'Good').trim().length < 2}
                            onClick={() => void run(`/hrm/assets/${a.id}/return`, { returned_on: today(), condition: String(f[`cond_${a.id}`] ?? 'Good').trim() }, 'Item handed back')}
                          >Handed back</button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {data.assets.length === 0 ? <tr><td colSpan={5} className="hr-muted">Nothing issued.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'claims' ? (
        <section className="hr-box hr-scroll" aria-label="Expense claims">
          <h2>Claims</h2>
          <p className="hr-muted">Staff claim under My pay and leave. Someone other than the claimant approves it; approving pays it back and books it to Operating Expenses.</p>
          <table>
            <thead><tr><th>Claim</th><th>Who</th><th>For</th><th>Amount</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.claims.map((c: Row) => (
                <tr key={c.id}>
                  <td>{c.claim_number}<br /><small className="hr-muted">{c.spent_on}</small></td>
                  <td>{c.employee_name}</td>
                  <td>{c.description}{c.receipt_ref ? <><br /><small className="hr-muted">Receipt {c.receipt_ref}</small></> : null}</td>
                  <td className="hr-num">{money(c.amount)}</td>
                  <td>{({ pending: 'Waiting', paid: `Paid (${c.paid_method?.replace('_', ' ')})`, rejected: 'Turned down' } as Row)[c.status] || c.status}{c.decision_note ? <><br /><small className="hr-muted">{c.decision_note}</small></> : null}</td>
                  <td>
                    {c.status === 'pending' ? (
                      <div className="hr-row">
                        <select aria-label={`Pay back ${c.claim_number} by`} value={f[`m_${c.id}`] || 'bank_transfer'} onChange={(e) => set(`m_${c.id}`, e.target.value)}>
                          {PAY_METHODS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                        </select>
                        <button type="button" className="hr-primary" disabled={busy} onClick={() => void run(`/hrm/claims/${c.id}/decide`, { approve: true, method: f[`m_${c.id}`] || 'bank_transfer' }, 'Paid back')}>Approve and pay</button>
                        <input placeholder="Reason to turn down" value={f[`why_${c.id}`] || ''} onChange={(e) => set(`why_${c.id}`, e.target.value)} aria-label={`Reason to turn down ${c.claim_number}`} />
                        <button
                          type="button" className="hr-danger" disabled={busy || !String(f[`why_${c.id}`] || '').trim()}
                          onClick={() => void run(`/hrm/claims/${c.id}/decide`, { approve: false, note: String(f[`why_${c.id}`]).trim() }, 'Turned down')}
                        >Turn down</button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
              {data.claims.length === 0 ? <tr><td colSpan={6} className="hr-muted">No claims.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {tab === 'notices' ? (
        <>
          <section className="hr-box" aria-label="Post a notice">
            <h2>Post</h2>
            <div className="hr-form">
              <label><span>Kind</span>
                <select value={txt('kind') || 'announcement'} onChange={(e) => set('kind', e.target.value)} aria-label="Notice kind">
                  <option value="announcement">Announcement</option><option value="policy">HR policy</option>
                </select>
              </label>
              <label><span>Title</span><input value={txt('title')} onChange={(e) => set('title', e.target.value)} aria-label="Notice title" /></label>
              <label className="hr-wide"><span>Text</span><textarea value={txt('body')} onChange={(e) => set('body', e.target.value)} aria-label="Notice text" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || txt('title').trim().length < 2 || txt('body').trim().length < 2}
                onClick={async () => {
                  if (await run('/hrm/notices', { kind: f.kind || 'announcement', title: txt('title').trim(), body: txt('body').trim() }, 'Posted')) setF({});
                }}
              >Post</button>
            </div>
          </section>
          <section className="hr-box" aria-label="Notices">
            <h2>Posted</h2>
            {data.notices.map((n: Row) => (
              <div className="hr-line" key={n.id}>
                <span><b>{n.title}</b> <small className="hr-muted">{n.kind === 'policy' ? 'Policy' : 'Announcement'}{n.is_active ? '' : ', taken down'}</small></span>
                {n.is_active ? <button type="button" className="hr-danger" disabled={busy} onClick={() => void run(`/hrm/notices/${n.id}/retire`, null, 'Taken down')}>Take down</button> : null}
              </div>
            ))}
            {data.notices.length === 0 ? <p className="hr-muted">Nothing posted.</p> : null}
          </section>
        </>
      ) : null}
    </>
  );
}

/** The staff side, shown under My pay and leave. */
export function MyMore() {
  const [more, setMore] = useState<Row | null>(null);
  const [f, setF] = useState<Row>({});
  const load = useCallback(async () => setMore((await api('/hrm/me/more'))?.data || null), []);
  const { busy, error, notice, run, setError } = useRunner(load);
  useEffect(() => {
    load().catch((err) => setError(problem(err)));
  }, [load, setError]);
  const set = (key: string, value: unknown) => setF((old) => ({ ...old, [key]: value }));
  const txt = (key: string) => String(f[key] ?? '');
  if (!more) return <Banner error={error} notice={notice} />;
  return (
    <>
      <Banner error={error} notice={notice} />
      {more.notices.length ? (
        <section className="hr-box" aria-label="Notices from HR">
          <h2>From HR</h2>
          {more.notices.map((n: Row) => (
            <details key={n.id} className="hr-line"><summary><b>{n.title}</b> <small className="hr-muted">{n.kind === 'policy' ? 'Policy' : 'Announcement'}</small></summary><p style={{ whiteSpace: 'pre-wrap' }}>{n.body}</p></details>
          ))}
        </section>
      ) : null}
      {more.reviews.filter((r: Row) => r.status === 'open').map((r: Row) => (
        <section className="hr-box" aria-label={`My review ${r.cycle}`} key={r.id}>
          <h2>Your review: {r.cycle}</h2>
          <p className="hr-muted">Score yourself 1 to 5 on each goal. Your reviewer sees your view before scoring.</p>
          {(r.goals || []).some((g: Row) => g.target != null) ? (
            <div className="hr-form">
              {(r.goals || []).map((g: Row, i: number) => (g.target != null ? (
                <label key={`k${i}`}><span>{g.title}: so far (target {g.target}{g.unit ? ` ${g.unit}` : ''}){g.progress != null ? `, ${g.progress}%` : ''}</span>
                  <input type="number" value={txt(`${r.id}_a${i}`) || (g.actual ?? '')} onChange={(e) => set(`${r.id}_a${i}`, e.target.value)}
                    onBlur={(e) => { if (e.target.value !== '' && e.target.value !== String(g.actual ?? '')) void run(`/hrm/me/reviews/${r.id}/progress`, { goal: i, actual: Number(e.target.value) }, 'Progress saved'); }}
                    aria-label={`My progress on ${g.title}`} />
                </label>
              ) : null))}
            </div>
          ) : null}
          <div className="hr-form">
            {(r.goals || []).map((g: Row, i: number) => (
              <label key={i}><span>{g.title} ({g.weight}%)</span>
                <select value={f[`${r.id}_${i}`] || ''} onChange={(e) => set(`${r.id}_${i}`, e.target.value)} aria-label={`My score for ${g.title}`}>
                  <option value="">Score</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            ))}
            <label className="hr-wide"><span>Your comments</span><textarea value={txt(`${r.id}_c`)} onChange={(e) => set(`${r.id}_c`, e.target.value)} aria-label="My review comments" /></label>
            <button
              type="button" className="hr-primary"
              disabled={busy || (r.goals || []).some((_g: Row, i: number) => !f[`${r.id}_${i}`])}
              onClick={() => void run(`/hrm/me/reviews/${r.id}/self`, { scores: (r.goals || []).map((_g: Row, i: number) => Number(f[`${r.id}_${i}`])), comment: txt(`${r.id}_c`).trim() || null }, 'Your view is sent')}
            >Send my view</button>
          </div>
        </section>
      ))}
      <MyFeedbackAsks />
      <section className="hr-box" aria-label="Claim back money spent">
        <h2>Claim back money you spent</h2>
        <div className="hr-form">
          <label><span>Spent on</span><input type="date" value={txt('spent_on')} onChange={(e) => set('spent_on', e.target.value)} aria-label="Claim spent on" /></label>
          <label><span>For</span><input value={txt('description')} onChange={(e) => set('description', e.target.value)} aria-label="Claim for" /></label>
          <label><span>Amount</span><input type="number" min="0" step="0.01" value={txt('amount')} onChange={(e) => set('amount', e.target.value)} aria-label="Claim amount" /></label>
          <label><span>Receipt number</span><input value={txt('receipt_ref')} onChange={(e) => set('receipt_ref', e.target.value)} aria-label="Claim receipt" /></label>
          <button
            type="button" className="hr-primary" disabled={busy || !f.spent_on || txt('description').trim().length < 2 || !(Number(f.amount) > 0)}
            onClick={async () => {
              if (await run('/hrm/me/claims', { spent_on: f.spent_on, description: txt('description').trim(), amount: Number(f.amount), receipt_ref: txt('receipt_ref').trim() || null }, 'Claim sent')) setF({});
            }}
          >Send claim</button>
        </div>
        {more.claims.length ? (
          <table aria-label="My claims"><tbody>{more.claims.map((c: Row) => <tr key={c.id}><td>{c.claim_number}</td><td>{c.description}</td><td className="hr-num">{money(c.amount)}</td><td>{c.status}</td></tr>)}</tbody></table>
        ) : null}
      </section>
      <section className="hr-box" aria-label="Raise a grievance">
        <h2>Raise a concern with HR</h2>
        <p className="hr-muted">Goes to HR managers only.</p>
        <div className="hr-form">
          <label><span>About</span><input value={txt('g_subject')} onChange={(e) => set('g_subject', e.target.value)} aria-label="Grievance subject" /></label>
          <label className="hr-wide"><span>What happened</span><textarea value={txt('g_details')} onChange={(e) => set('g_details', e.target.value)} aria-label="Grievance details" /></label>
          <button
            type="button" className="hr-primary" disabled={busy || txt('g_subject').trim().length < 2 || txt('g_details').trim().length < 2}
            onClick={async () => {
              if (await run('/hrm/me/grievances', { subject: txt('g_subject').trim(), details: txt('g_details').trim() }, 'Sent to HR in confidence')) setF({});
            }}
          >Send to HR</button>
        </div>
        {more.cases.length ? <table aria-label="My cases"><tbody>{more.cases.map((c: Row) => <tr key={c.id}><td>{c.case_number}</td><td>{c.kind}</td><td>{c.subject}</td><td>{c.status === 'closed' ? `Closed${c.outcome ? `: ${String(c.outcome).replace(/_/g, ' ')}` : ''}` : 'Open'}</td></tr>)}</tbody></table> : null}
      </section>
      {more.training.length || more.assets.length || more.contracts.length ? (
        <section className="hr-box" aria-label="My training, kit and contract">
          <h2>My training, kit and contract</h2>
          {more.training.map((t: Row) => <div className="hr-line" key={t.id}><span>{t.training}</span><span>{t.completed_on}{t.expires_on ? `, due again ${t.expires_on}` : ''}</span></div>)}
          {more.assets.map((a: Row) => <div className="hr-line" key={a.id}><span>{a.item}</span><span>since {a.issued_on}</span></div>)}
          {more.contracts.map((c: Row) => <div className="hr-line" key={c.id}><span>{c.kind.replace('_', ' ')} contract</span><span>{c.starts_on} to {c.ends_on || 'open-ended'}</span></div>)}
        </section>
      ) : null}
    </>
  );
}


/** Colleagues' reviews this person has been asked to give feedback on. */
function MyFeedbackAsks() {
  const [rows, setRows] = useState<Row[]>([]);
  const [f, setF] = useState<Row>({});
  const load = useCallback(async () => setRows((await api('/hrm/me/feedback'))?.data || []), []);
  const { busy, error, notice, run, setError } = useRunner(load);
  useEffect(() => {
    load().catch((err) => setError(problem(err)));
  }, [load, setError]);
  const open = rows.filter((r) => r.open);
  if (!open.length) return notice ? <Banner error={error} notice={notice} /> : null;
  return (
    <>
      <Banner error={error} notice={notice} />
      {open.map((r) => (
        <section className="hr-box" aria-label={`Feedback on ${r.about}`} key={r.id}>
          <h2>Feedback on {r.about} ({r.cycle})</h2>
          <p className="hr-muted">Your answer is shown without your name, and only once a second colleague has answered. Their goals: {(r.goals || []).join(', ')}.</p>
          <div className="hr-form">
            <label><span>Overall, 1 to 5</span>
              <select value={f[`${r.id}_r`] || ''} onChange={(e) => setF({ ...f, [`${r.id}_r`]: e.target.value })} aria-label={`Rating for ${r.about}`}>
                <option value="">Choose</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label className="hr-wide"><span>What they do well</span><textarea value={f[`${r.id}_s`] || ''} onChange={(e) => setF({ ...f, [`${r.id}_s`]: e.target.value })} aria-label={`What ${r.about} does well`} /></label>
            <label className="hr-wide"><span>What could be better</span><textarea value={f[`${r.id}_i`] || ''} onChange={(e) => setF({ ...f, [`${r.id}_i`]: e.target.value })} aria-label={`What ${r.about} could do better`} /></label>
            <button
              type="button" className="hr-primary"
              disabled={busy || !f[`${r.id}_r`] || !(String(f[`${r.id}_s`] || '').trim() || String(f[`${r.id}_i`] || '').trim())}
              onClick={() => void run(`/hrm/me/feedback/${r.id}`, { rating: Number(f[`${r.id}_r`]), strengths: String(f[`${r.id}_s`] || '').trim() || null, improve: String(f[`${r.id}_i`] || '').trim() || null }, 'Thank you. Your feedback is shown without your name.')}
            >Send feedback</button>
          </div>
        </section>
      ))}
    </>
  );
}
