'use client';

/**
 * Member portal. A member opens the private link the gym gave them (/gym-member?t=...). The link is
 * the only credential: it expires and the gym can cancel it. No sign-in, no password.
 * Renewing is done at the gym: Ribdigi records payments, it does not take them.
 */

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

type Row = Record<string, any>;
const KEY = 'ribdigi.gymMember.token';

async function call(token: string, path: string, body?: object) {
  const res = await fetch(`/api/v1/public/gym-member${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'X-Portal-Token': token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = json?.detail;
    const err = new Error(typeof detail === 'string' ? detail : detail?.message || 'Something went wrong. Try again.') as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return json?.data;
}
const when = (v?: string) => (v ? new Date(`${v}Z`).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '');

function Portal() {
  const params = useSearchParams();
  const [token, setToken] = useState('');
  const [tab, setTab] = useState('home');
  const [me, setMe] = useState<Row | null>(null);
  const [classes, setClasses] = useState<Row[]>([]);
  const [programmes, setProgrammes] = useState<Row[]>([]);
  const [measures, setMeasures] = useState<Row | null>(null);
  const [plans, setPlans] = useState<Row[]>([]);
  const [payments, setPayments] = useState<Row[]>([]);
  const [code, setCode] = useState('');
  const [codeImg, setCodeImg] = useState('');
  const [fb, setFb] = useState({ kind: 'feedback', message: '', rating: '5' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [bad, setBad] = useState(false);

  useEffect(() => {
    const fromUrl = params.get('t');
    let t = fromUrl || '';
    try {
      if (fromUrl) sessionStorage.setItem(KEY, fromUrl);
      else t = sessionStorage.getItem(KEY) || '';
    } catch { /* storage can be blocked */ }
    setToken(t);
    if (!t) setBad(true);
  }, [params]);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setMe(await call(token, '/me'));
      setClasses((await call(token, '/classes')) || []);
      setProgrammes((await call(token, '/programmes')) || []);
      setMeasures(await call(token, '/measurements'));
      setPlans((await call(token, '/nutrition')) || []);
      setPayments((await call(token, '/payments')) || []);
    } catch (err) {
      if ((err as { status?: number }).status === 401) setBad(true);
      else setError((err as Error).message);
    }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  async function act(path: string, body: object, done: string) {
    setError('');
    setNotice('');
    try {
      const data = await call(token, path, body);
      setNotice(done);
      await load();
      return data;
    } catch (err) {
      setError((err as Error).message);
      return null;
    }
  }

  if (bad) {
    return (
      <main style={{ maxWidth: 520, margin: '4rem auto', padding: '0 1rem' }}>
        <h1>This link is not valid</h1>
        <p>It may have expired or been replaced. Ask the gym for a new link.</p>
      </main>
    );
  }
  if (!me) return <main style={{ maxWidth: 520, margin: '4rem auto', padding: '0 1rem' }}><p>Loading…</p></main>;

  const tabs = [['home', 'My plan'], ['classes', 'Classes'], ['workouts', 'Workouts'], ['body', 'Progress'], ['food', 'Nutrition'], ['pay', 'Payments'], ['talk', 'Tell the gym']];
  return (
    <main style={{ maxWidth: 760, margin: '1.5rem auto', padding: '0 1rem', fontFamily: 'inherit' }}>
      <h1>Hello, {String(me.full_name).split(' ')[0]}</h1>
      {error ? <p role="alert" style={{ color: '#a11' }}>{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <nav style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '1rem 0' }} role="tablist" aria-label="Member portal">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)} style={{ fontWeight: tab === id ? 700 : 400 }}>{label}</button>
        ))}
      </nav>

      {tab === 'home' ? (
        <section aria-label="My plan">
          <p><strong>{me.plan_name || 'No plan yet'}</strong> · {me.state}</p>
          {me.ends_on ? <p>Ends {me.ends_on}{me.days_left != null ? ` (${me.days_left} days left)` : ''}</p> : null}
          {me.visits_left != null ? <p>{me.visits_left} visits left</p> : null}
          <p>To renew, please see the front desk.</p>
          <h2>Door code</h2>
          {code ? (
            <>
              <p>Show this code at the door. A new code replaces the old one.</p>
              {codeImg ? <p><img src={codeImg} alt="Your door QR code" width={200} height={200} /></p> : null}
              <code style={{ wordBreak: 'break-all' }} aria-label="Door code">{code}</code>
            </>
          ) : null}
          <p><button type="button" onClick={async () => { const d = await act('/door-code', {}, 'New door code ready'); if (d?.token) { setCode(d.token); setCodeImg(d.qr_png || ''); } }}>Get a door code</button></p>
          <label><input type="checkbox" checked={!!me.marketing_consent} onChange={(e) => void act('/consent', { consent: e.target.checked }, 'Saved')} aria-label="Allow offers from the gym" /> The gym may send me offers</label>
        </section>
      ) : null}

      {tab === 'classes' ? (
        <section aria-label="Classes">
          {classes.map((c) => (
            <p key={c.id}>
              <strong>{c.name}</strong> · {when(c.starts_at)}{c.trainer_name ? ` · ${c.trainer_name}` : ''} · {c.places_left} places left{' '}
              {c.my_booking_id ? (
                <button type="button" onClick={() => void act(`/bookings/${c.my_booking_id}/cancel`, {}, 'Cancelled')}>Cancel ({c.my_status})</button>
              ) : (
                <button type="button" onClick={() => void act(`/classes/${c.id}/book`, { waitlist: c.places_left === 0 }, c.places_left === 0 ? 'You are on the waiting list' : 'Booked')}>{c.places_left === 0 ? 'Join waiting list' : 'Book'}</button>
              )}
            </p>
          ))}
          {classes.length === 0 ? <p>No classes coming up.</p> : null}
        </section>
      ) : null}

      {tab === 'workouts' ? (
        <section aria-label="Workouts">
          {programmes.map((p) => (
            <div key={p.id}>
              <h2>{p.name} <small>({p.status})</small></h2>
              <ul>
                {p.lines.map((l: Row) => (
                  <li key={l.id}>
                    {['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][l.day_of_week]} · {l.exercise}: {l.sets} × {l.reps}{l.weight_kg ? ` @ ${l.weight_kg} kg` : ''} (done {l.times_done}×){' '}
                    {p.status === 'active' ? <button type="button" onClick={() => void act(`/programmes/${p.id}/workouts`, { line_id: l.id, sets_done: l.sets, reps_done: l.sets * l.reps, weight_kg: l.weight_kg ?? undefined }, 'Workout logged')}>I did this today</button> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {programmes.length === 0 ? <p>Your trainer has not set a programme yet.</p> : null}
        </section>
      ) : null}

      {tab === 'body' ? (
        <section aria-label="Progress">
          <p>Tracking only, not medical advice.</p>
          {measures?.change_since_first && Object.keys(measures.change_since_first).length ? <p>Since your first record: {Object.entries(measures.change_since_first).map(([k, v]) => `${k.replace('_', ' ')} ${Number(v) > 0 ? '+' : ''}${v}`).join(', ')}</p> : null}
          <table>
            <thead><tr><th>Date</th><th>Weight</th><th>BMI</th><th>Waist</th></tr></thead>
            <tbody>{(measures?.items || []).map((r: Row) => <tr key={r.id}><td>{r.measured_on}</td><td>{r.weight_kg ?? ''}</td><td>{r.bmi ?? ''}</td><td>{r.waist_cm ?? ''}</td></tr>)}</tbody>
          </table>
        </section>
      ) : null}

      {tab === 'food' ? (
        <section aria-label="Nutrition">
          <p>Guidance from your gym, not medical advice.</p>
          {plans.map((p) => (
            <div key={p.id}>
              <h2>{p.name} <small>({p.status})</small></h2>
              <p>{Object.entries(p.targets).filter(([, v]) => v != null).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ')}</p>
              {p.allergies ? <p>Allergies on file: {p.allergies}</p> : null}
              {p.meals ? <pre style={{ whiteSpace: 'pre-wrap' }}>{p.meals}</pre> : null}
            </div>
          ))}
          {plans.length === 0 ? <p>No nutrition plan yet.</p> : null}
        </section>
      ) : null}

      {tab === 'pay' ? (
        <section aria-label="Payments">
          <table>
            <thead><tr><th>Date</th><th>What</th><th>How</th><th>Amount</th></tr></thead>
            <tbody>{payments.map((p) => <tr key={p.id}><td>{when(p.date)}</td><td>{p.kind}</td><td>{String(p.method).replace('_', ' ')}</td><td>{p.amount}</td></tr>)}</tbody>
          </table>
        </section>
      ) : null}

      {tab === 'talk' ? (
        <section aria-label="Tell the gym">
          <label>What is it?{' '}
            <select value={fb.kind} onChange={(e) => setFb({ ...fb, kind: e.target.value })} aria-label="Feedback type">
              <option value="feedback">A comment</option><option value="complaint">A complaint</option><option value="rating">A rating</option>
            </select>
          </label>
          {fb.kind === 'rating' ? <label> Stars <input type="number" min="1" max="5" value={fb.rating} onChange={(e) => setFb({ ...fb, rating: e.target.value })} aria-label="Rating" /></label> : null}
          <p><textarea value={fb.message} onChange={(e) => setFb({ ...fb, message: e.target.value })} rows={4} style={{ width: '100%' }} aria-label="Your message" /></p>
          <button type="button" disabled={fb.kind !== 'rating' && !fb.message.trim()} onClick={async () => {
            const body: Record<string, unknown> = { kind: fb.kind };
            if (fb.message.trim()) body.message = fb.message.trim();
            if (fb.kind === 'rating') body.rating = Number(fb.rating);
            if (await act('/feedback', body, 'Thank you. The gym has your message.')) setFb({ ...fb, message: '' });
          }}>Send</button>
        </section>
      ) : null}
    </main>
  );
}

export default function GymMemberPage() {
  return <Suspense fallback={null}><Portal /></Suspense>;
}
