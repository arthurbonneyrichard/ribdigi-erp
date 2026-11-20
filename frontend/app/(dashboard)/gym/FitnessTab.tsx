'use client';

/** Fitness: exercise library, workout programmes and body measurements. Trainers and managers only. Tracking, not medical advice. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const DAYS = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const today = () => new Date().toISOString().slice(0, 10);
const num = (v: string) => (v.trim() === '' ? undefined : Number(v));
const TARGETS: [string, string][] = [['calories', 'Calories'], ['protein_g', 'Protein (g)'], ['carbs_g', 'Carbs (g)'], ['fat_g', 'Fat (g)'], ['water_ml', 'Water (ml)']];
const MEASURES: [string, string][] = [
  ['weight_kg', 'Weight (kg)'], ['height_cm', 'Height (cm)'], ['body_fat_pct', 'Body fat (%)'], ['waist_cm', 'Waist (cm)'],
  ['chest_cm', 'Chest (cm)'], ['hips_cm', 'Hips (cm)'], ['arms_cm', 'Arms (cm)'], ['thighs_cm', 'Thighs (cm)'], ['resting_hr', 'Resting heart rate'],
];

export default function FitnessTab({ members }: { members: Row[] }) {
  const [part, setPart] = useState('programmes');
  const [memberId, setMemberId] = useState('');
  const [exercises, setExercises] = useState<Row[]>([]);
  const [trainers, setTrainers] = useState<Row[]>([]);
  const [programmes, setProgrammes] = useState<Row[]>([]);
  const [measures, setMeasures] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [exForm, setExForm] = useState({ name: '', muscle_group: '' });
  const [prog, setProg] = useState({ name: '', goal: '', trainer_id: '', starts_on: today() });
  const [lines, setLines] = useState<Row[]>([{ exercise_id: '', day_of_week: 1, sets: 3, reps: 10, weight_kg: '' }]);
  const [logs, setLogs] = useState<Record<string, { sets: string; reps: string; weight: string }>>({});
  const [plans, setPlans] = useState<Row[]>([]);
  const [nForm, setNForm] = useState<Record<string, string>>({ starts_on: today() });
  const [intake, setIntake] = useState<Record<string, Record<string, string>>>({});
  const [mForm, setMForm] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setExercises((await api('/gym/exercises'))?.data ?? []);
      try { setTrainers((await api('/gym/trainers'))?.data ?? []); } catch { setTrainers([]); }
      if (memberId) {
        setProgrammes((await api(`/gym/programmes?member_id=${memberId}`))?.data ?? []);
        setMeasures((await api(`/gym/members/${memberId}/measurements`))?.data ?? null);
        setPlans((await api(`/gym/nutrition-plans?member_id=${memberId}`))?.data ?? []);
      } else {
        setProgrammes([]);
        setMeasures(null);
        setPlans([]);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [memberId]);
  useEffect(() => { void load(); }, [load]);

  async function send(path: string, body: object, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
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

  return (
    <div className="gm-floor">
      {error ? <p className="gm-error" role="alert">{error}</p> : null}
      {notice ? <p className="gm-ok" role="status">{notice}</p> : null}
      <p className="gm-muted">Fitness tracking only. These numbers are not medical advice or a diagnosis.</p>
      <div className="gm-row" role="tablist" aria-label="Fitness">
        {[['programmes', 'Workout programmes'], ['measures', 'Body measurements'], ['nutrition', 'Nutrition'], ['library', 'Exercise library']].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={part === id} className={part === id ? 'gm-primary' : ''} onClick={() => setPart(id)}>{label}</button>
        ))}
      </div>

      {part === 'library' ? (
        <section className="gm-box" aria-label="Exercise library">
          <h2>Exercise library</h2>
          <p className="gm-muted">{exercises.map((e) => e.name).join(', ') || 'No exercises yet.'}</p>
          <div className="gm-form">
            <label><span>Exercise</span><input value={exForm.name} onChange={(e) => setExForm({ ...exForm, name: e.target.value })} aria-label="Exercise name" /></label>
            <label><span>Muscle group</span><input value={exForm.muscle_group} onChange={(e) => setExForm({ ...exForm, muscle_group: e.target.value })} aria-label="Exercise muscle group" /></label>
            <button type="button" className="gm-primary" disabled={busy || !exForm.name.trim()}
              onClick={async () => {
                const ok = await send('/gym/exercises', { name: exForm.name.trim(), muscle_group: exForm.muscle_group.trim() || undefined }, 'Exercise added');
                if (ok) setExForm({ name: '', muscle_group: '' });
              }}>Add exercise</button>
          </div>
        </section>
      ) : (
        <section className="gm-box" aria-label="Choose member">
          <label><span>Member</span>
            <select value={memberId} onChange={(e) => setMemberId(e.target.value)} aria-label="Fitness member">
              <option value="">Choose a member</option>
              {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
            </select></label>
        </section>
      )}

      {part === 'programmes' && memberId ? (
        <>
          <section className="gm-box" aria-label="New programme">
            <h2>New programme</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={prog.name} onChange={(e) => setProg({ ...prog, name: e.target.value })} aria-label="Programme name" /></label>
              <label><span>Goal</span><input value={prog.goal} onChange={(e) => setProg({ ...prog, goal: e.target.value })} aria-label="Programme goal" /></label>
              <label><span>Trainer</span>
                <select value={prog.trainer_id} onChange={(e) => setProg({ ...prog, trainer_id: e.target.value })} aria-label="Programme trainer">
                  <option value="">None</option>
                  {trainers.filter((t) => t.is_active).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
                </select></label>
              <label><span>Starts</span><input type="date" value={prog.starts_on} onChange={(e) => setProg({ ...prog, starts_on: e.target.value })} aria-label="Programme start date" /></label>
            </div>
            {lines.map((ln, i) => (
              <div className="gm-form" key={i}>
                <label><span>Exercise</span>
                  <select value={ln.exercise_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, exercise_id: e.target.value } : x)))} aria-label={`Exercise ${i + 1}`}>
                    <option value="">Choose</option>
                    {exercises.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                  </select></label>
                <label><span>Day</span>
                  <select value={ln.day_of_week} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, day_of_week: Number(e.target.value) } : x)))} aria-label={`Day ${i + 1}`}>
                    {DAYS.slice(1).map((d, k) => <option key={d} value={k + 1}>{d}</option>)}
                  </select></label>
                <label><span>Sets</span><input type="number" min="1" value={ln.sets} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, sets: Number(e.target.value) } : x)))} aria-label={`Sets ${i + 1}`} /></label>
                <label><span>Reps</span><input type="number" min="1" value={ln.reps} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, reps: Number(e.target.value) } : x)))} aria-label={`Reps ${i + 1}`} /></label>
                <label><span>Weight (kg)</span><input type="number" min="0" value={ln.weight_kg} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, weight_kg: e.target.value } : x)))} aria-label={`Weight ${i + 1}`} /></label>
                {lines.length > 1 ? <button type="button" className="gm-danger" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</button> : null}
              </div>
            ))}
            <div className="gm-row">
              <button type="button" onClick={() => setLines([...lines, { exercise_id: '', day_of_week: 1, sets: 3, reps: 10, weight_kg: '' }])}>Add exercise line</button>
              <button type="button" className="gm-primary" disabled={busy || !prog.name.trim() || lines.some((l) => !l.exercise_id)}
                onClick={async () => {
                  const ok = await send('/gym/programmes', {
                    member_id: memberId, name: prog.name.trim(), goal: prog.goal.trim() || undefined, trainer_id: prog.trainer_id || undefined,
                    starts_on: prog.starts_on,
                    lines: lines.map((l) => ({ exercise_id: l.exercise_id, day_of_week: l.day_of_week, sets: l.sets, reps: l.reps, weight_kg: num(String(l.weight_kg)) })),
                  }, 'Programme saved');
                  if (ok) { setProg({ ...prog, name: '', goal: '' }); setLines([{ exercise_id: '', day_of_week: 1, sets: 3, reps: 10, weight_kg: '' }]); }
                }}>Save programme</button>
            </div>
          </section>
          {programmes.map((p) => (
            <section className="gm-box gm-scroll" key={p.id} aria-label={`Programme ${p.name}`}>
              <h2>{p.name} <span className="gm-muted">({p.status})</span></h2>
              <p className="gm-muted">{p.goal || 'No goal set'}{p.trainer_name ? ` · ${p.trainer_name}` : ''}</p>
              <table>
                <thead><tr><th>Day</th><th>Exercise</th><th>Plan</th><th>Done</th><th>Log today</th></tr></thead>
                <tbody>
                  {p.lines.map((l: Row) => {
                    const v = logs[l.id] || { sets: String(l.sets), reps: String(l.sets * l.reps), weight: l.weight_kg ?? '' };
                    return (
                      <tr key={l.id}>
                        <td>{DAYS[l.day_of_week]}</td><td>{l.exercise}</td>
                        <td>{l.sets} × {l.reps}{l.weight_kg ? ` @ ${l.weight_kg} kg` : ''}</td><td>{l.times_done}</td>
                        <td className="gm-row">
                          {p.status === 'active' ? (
                            <>
                              <input type="number" min="0" value={v.sets} aria-label={`Sets done ${l.exercise}`} style={{ width: 64 }} onChange={(e) => setLogs({ ...logs, [l.id]: { ...v, sets: e.target.value } })} />
                              <input type="number" min="0" value={v.reps} aria-label={`Reps done ${l.exercise}`} style={{ width: 72 }} onChange={(e) => setLogs({ ...logs, [l.id]: { ...v, reps: e.target.value } })} />
                              <button type="button" disabled={busy} onClick={() => void send(`/gym/programmes/${p.id}/workouts`, { line_id: l.id, sets_done: Number(v.sets), reps_done: Number(v.reps), weight_kg: num(String(v.weight)) }, 'Workout logged')}>Log</button>
                            </>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {p.status === 'active' ? (
                <div className="gm-row">
                  <button type="button" className="gm-primary" onClick={() => void send(`/gym/programmes/${p.id}/status`, { status: 'completed' }, 'Programme completed')}>Mark completed</button>
                  <button type="button" className="gm-danger" onClick={() => void send(`/gym/programmes/${p.id}/status`, { status: 'cancelled' }, 'Programme cancelled')}>Cancel programme</button>
                </div>
              ) : null}
            </section>
          ))}
          {programmes.length === 0 ? <p className="gm-muted">No programmes for this member yet.</p> : null}
        </>
      ) : null}

      {part === 'nutrition' && memberId ? (
        <>
          <section className="gm-box" aria-label="New nutrition plan">
            <h2>New nutrition plan</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={nForm.name || ''} onChange={(e) => setNForm({ ...nForm, name: e.target.value })} aria-label="Nutrition plan name" /></label>
              {TARGETS.map(([k, label]) => (
                <label key={k}><span>{label}</span><input type="number" min="0" value={nForm[k] || ''} onChange={(e) => setNForm({ ...nForm, [k]: e.target.value })} aria-label={`Target ${label}`} /></label>
              ))}
              <label><span>Allergies</span><input value={nForm.allergies || ''} onChange={(e) => setNForm({ ...nForm, allergies: e.target.value })} aria-label="Nutrition allergies" /></label>
              <label><span>Preferences</span><input value={nForm.preferences || ''} onChange={(e) => setNForm({ ...nForm, preferences: e.target.value })} aria-label="Nutrition preferences" /></label>
              <label><span>Meals</span><textarea value={nForm.meals || ''} onChange={(e) => setNForm({ ...nForm, meals: e.target.value })} aria-label="Nutrition meals" /></label>
              <label><span>Starts</span><input type="date" value={nForm.starts_on || ''} onChange={(e) => setNForm({ ...nForm, starts_on: e.target.value })} aria-label="Nutrition start date" /></label>
              <button type="button" className="gm-primary" disabled={busy || !(nForm.name || '').trim()}
                onClick={async () => {
                  const body: Record<string, unknown> = { member_id: memberId, name: nForm.name.trim(), starts_on: nForm.starts_on };
                  TARGETS.forEach(([k]) => { const n = num(nForm[k] || ''); if (n !== undefined) body[k] = Math.round(n); });
                  ['allergies', 'preferences', 'meals'].forEach((k) => { if ((nForm[k] || '').trim()) body[k] = nForm[k].trim(); });
                  if (await send('/gym/nutrition-plans', body, 'Nutrition plan saved')) setNForm({ starts_on: today() });
                }}>Save plan</button>
            </div>
          </section>
          {plans.map((p) => (
            <section className="gm-box gm-scroll" key={p.id} aria-label={`Nutrition plan ${p.name}`}>
              <h2>{p.name} <span className="gm-muted">({p.status})</span></h2>
              <p className="gm-muted">{TARGETS.map(([k, label]) => (p.targets[k] != null ? `${label} ${p.targets[k]}` : '')).filter(Boolean).join(' · ')}</p>
              {p.allergies ? <p>Allergies: {p.allergies}</p> : null}
              {p.meals ? <pre style={{ whiteSpace: 'pre-wrap' }}>{p.meals}</pre> : null}
              {p.status === 'active' ? (
                <div className="gm-form">
                  {TARGETS.map(([k, label]) => (
                    <label key={k}><span>{label} today</span><input type="number" min="0" value={intake[p.id]?.[k] || ''} onChange={(e) => setIntake({ ...intake, [p.id]: { ...intake[p.id], [k]: e.target.value } })} aria-label={`Intake ${label}`} /></label>
                  ))}
                  <button type="button" disabled={busy || !TARGETS.some(([k]) => (intake[p.id]?.[k] || '').trim())}
                    onClick={async () => {
                      const body: Record<string, number> = {};
                      TARGETS.forEach(([k]) => { const n = num(intake[p.id]?.[k] || ''); if (n !== undefined) body[k] = Math.round(n); });
                      if (await send(`/gym/nutrition-plans/${p.id}/intake`, body, 'Intake logged')) setIntake({ ...intake, [p.id]: {} });
                    }}>Log today</button>
                  <button type="button" className="gm-primary" onClick={() => void send(`/gym/nutrition-plans/${p.id}/status`, { status: 'completed' }, 'Plan completed')}>Mark completed</button>
                  <button type="button" className="gm-danger" onClick={() => void send(`/gym/nutrition-plans/${p.id}/status`, { status: 'cancelled' }, 'Plan cancelled')}>Cancel plan</button>
                </div>
              ) : null}
              <table>
                <thead><tr><th>Date</th>{TARGETS.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
                <tbody>
                  {p.logs.map((l: Row) => <tr key={l.id}><td>{l.logged_on}</td>{TARGETS.map(([k]) => <td key={k}>{l[k] ?? ''}</td>)}</tr>)}
                  {p.logs.length === 0 ? <tr><td colSpan={6} className="gm-muted">Nothing logged yet.</td></tr> : null}
                </tbody>
              </table>
            </section>
          ))}
          {plans.length === 0 ? <p className="gm-muted">No nutrition plan for this member yet.</p> : null}
        </>
      ) : null}

      {part === 'measures' && memberId ? (
        <>
          <section className="gm-box" aria-label="Record measurements">
            <h2>Record measurements</h2>
            <div className="gm-form">
              {MEASURES.map(([key, label]) => (
                <label key={key}><span>{label}</span><input type="number" min="0" step="0.1" value={mForm[key] || ''} onChange={(e) => setMForm({ ...mForm, [key]: e.target.value })} aria-label={`Measure ${label}`} /></label>
              ))}
              <label><span>Note</span><input value={mForm.notes || ''} onChange={(e) => setMForm({ ...mForm, notes: e.target.value })} aria-label="Measurement note" /></label>
              <button type="button" className="gm-primary" disabled={busy || !MEASURES.some(([k]) => (mForm[k] || '').trim())}
                onClick={async () => {
                  const body: Record<string, unknown> = {};
                  MEASURES.forEach(([k]) => { const n = num(mForm[k] || ''); if (n !== undefined) body[k] = k === 'resting_hr' ? Math.round(n) : n; });
                  if ((mForm.notes || '').trim()) body.notes = mForm.notes.trim();
                  if (await send(`/gym/members/${memberId}/measurements`, body, 'Measurements saved')) setMForm({});
                }}>Save measurements</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Measurement history">
            <h2>History</h2>
            {measures && Object.keys(measures.change_since_first || {}).length ? (
              <p className="gm-muted">Since the first record: {Object.entries(measures.change_since_first).map(([k, v]) => `${k.replace('_', ' ')} ${Number(v) > 0 ? '+' : ''}${v}`).join(', ')}</p>
            ) : null}
            <table>
              <thead><tr><th>Date</th><th>Weight</th><th>BMI</th><th>Body fat</th><th>Waist</th><th>Chest</th><th>Hips</th><th>Arms</th><th>Thighs</th></tr></thead>
              <tbody>
                {(measures?.items || []).map((r: Row) => (
                  <tr key={r.id}>
                    <td>{r.measured_on}</td><td>{r.weight_kg ?? ''}</td><td>{r.bmi ?? ''}</td><td>{r.body_fat_pct ?? ''}</td><td>{r.waist_cm ?? ''}</td>
                    <td>{r.chest_cm ?? ''}</td><td>{r.hips_cm ?? ''}</td><td>{r.arms_cm ?? ''}</td><td>{r.thighs_cm ?? ''}</td>
                  </tr>
                ))}
                {!measures?.items?.length ? <tr><td colSpan={9} className="gm-muted">No measurements yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}
