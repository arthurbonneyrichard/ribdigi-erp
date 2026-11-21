'use client';

/** Gym floor: personal training, lockers, equipment and guests. Each part loads on its own, so a role that may not see one still sees the rest. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const when = (value?: string) => (value ? new Date(`${value}Z`).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '');
const PARTS = [
  { id: 'training', label: 'Personal training' },
  { id: 'lockers', label: 'Lockers' },
  { id: 'equipment', label: 'Equipment' },
  { id: 'guests', label: 'Guests' },
];

export default function FloorTab({ members }: { members: Row[] }) {
  const [part, setPart] = useState('training');
  const [trainers, setTrainers] = useState<Row[] | null>(null);
  const [sessions, setSessions] = useState<Row[]>([]);
  const [lockers, setLockers] = useState<Row[] | null>(null);
  const [equipment, setEquipment] = useState<Row[] | null>(null);
  const [faults, setFaults] = useState<Row[]>([]);
  const [guests, setGuests] = useState<Row[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [trainerForm, setTrainerForm] = useState({ full_name: '', phone: '', session_price: '' });
  const [sessionForm, setSessionForm] = useState({ trainer_id: '', member_id: '', starts_at: '', minutes: '60' });
  const [lockerNo, setLockerNo] = useState('');
  const [lockerMember, setLockerMember] = useState<Record<string, string>>({});
  const [eqForm, setEqForm] = useState({ name: '', category: '' });
  const [fault, setFault] = useState<Record<string, string>>({});
  const [fix, setFix] = useState<Record<string, string>>({});
  const [guestForm, setGuestForm] = useState({ guest_name: '', phone: '', host_member_id: '', fee: '', method: 'cash' });
  const [rent, setRent] = useState({ days: '', fee: '', method: 'cash' });

  const load = useCallback(async () => {
    const get = async (path: string) => {
      try {
        return (await api(path))?.data ?? [];
      } catch {
        return null; // this role may not see it
      }
    };
    setTrainers(await get('/gym/trainers'));
    setSessions((await get('/gym/training-sessions')) || []);
    setLockers(await get('/gym/lockers'));
    setEquipment(await get('/gym/equipment'));
    setFaults((await get('/gym/maintenance')) || []);
    setGuests(await get('/gym/guests'));
  }, []);
  useEffect(() => { void load(); }, [load]);

  const rentBody = (extra: object) => (rent.days ? { ...extra, rental_days: Number(rent.days), fee: Number(rent.fee || 0), method: Number(rent.fee || 0) > 0 ? rent.method : undefined } : extra);

  async function run(path: string, body: object | null, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
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

  const visible = PARTS.filter((p) => ({ training: trainers, lockers, equipment, guests } as Record<string, Row[] | null>)[p.id] !== null);
  const current = visible.some((p) => p.id === part) ? part : visible[0]?.id;

  return (
    <div className="gm-floor">
      {error ? <p className="gm-error" role="alert">{error}</p> : null}
      {notice ? <p className="gm-ok" role="status">{notice}</p> : null}
      <div className="gm-row" role="tablist" aria-label="Gym floor">
        {visible.map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={current === p.id} className={current === p.id ? 'gm-primary' : ''} onClick={() => setPart(p.id)}>{p.label}</button>
        ))}
      </div>

      {current === 'training' && trainers ? (
        <>
          <section className="gm-box" aria-label="Book a training session">
            <h2>Book a session</h2>
            <div className="gm-form">
              <label><span>Trainer</span>
                <select value={sessionForm.trainer_id} onChange={(e) => setSessionForm({ ...sessionForm, trainer_id: e.target.value })} aria-label="Session trainer">
                  <option value="">Choose</option>
                  {trainers.filter((t) => t.is_active).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
                </select></label>
              <label><span>Member</span>
                <select value={sessionForm.member_id} onChange={(e) => setSessionForm({ ...sessionForm, member_id: e.target.value })} aria-label="Session member">
                  <option value="">Choose</option>
                  {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
                </select></label>
              <label><span>When</span><input type="datetime-local" value={sessionForm.starts_at} onChange={(e) => setSessionForm({ ...sessionForm, starts_at: e.target.value })} aria-label="Session time" /></label>
              <label><span>Minutes</span><input type="number" min="15" max="240" value={sessionForm.minutes} onChange={(e) => setSessionForm({ ...sessionForm, minutes: e.target.value })} aria-label="Session minutes" /></label>
              <button type="button" className="gm-primary" disabled={busy || !sessionForm.trainer_id || !sessionForm.member_id || !sessionForm.starts_at}
                onClick={async () => {
                  const ok = await run('/gym/training-sessions', {
                    trainer_id: sessionForm.trainer_id, member_id: sessionForm.member_id,
                    starts_at: new Date(sessionForm.starts_at).toISOString().slice(0, 19), minutes: Number(sessionForm.minutes),
                  }, 'Session booked');
                  if (ok) setSessionForm({ ...sessionForm, starts_at: '' });
                }}>Book session</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Sessions">
            <h2>Sessions</h2>
            <table>
              <thead><tr><th>When</th><th>Trainer</th><th>Member</th><th>Status</th><th /></tr></thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id}>
                    <td>{when(s.starts_at)}</td><td>{s.trainer_name}</td><td>{s.member_name}</td><td>{String(s.status).replace('_', ' ')}</td>
                    <td className="gm-row">
                      {s.status === 'booked' ? (
                        <>
                          <button type="button" onClick={() => void run(`/gym/training-sessions/${s.id}`, { status: 'completed' }, 'Saved')}>Done</button>
                          <button type="button" onClick={() => void run(`/gym/training-sessions/${s.id}`, { status: 'no_show' }, 'Saved')}>Did not come</button>
                          <button type="button" className="gm-danger" onClick={() => void run(`/gym/training-sessions/${s.id}`, { status: 'cancelled' }, 'Session cancelled')}>Cancel</button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 ? <tr><td colSpan={5} className="gm-muted">No sessions yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="gm-box" aria-label="Trainers">
            <h2>Trainers</h2>
            <p className="gm-muted">{trainers.map((t) => t.full_name).join(', ') || 'No trainers yet.'}</p>
            <div className="gm-form">
              <label><span>Name</span><input value={trainerForm.full_name} onChange={(e) => setTrainerForm({ ...trainerForm, full_name: e.target.value })} aria-label="Trainer name" /></label>
              <label><span>Phone</span><input value={trainerForm.phone} onChange={(e) => setTrainerForm({ ...trainerForm, phone: e.target.value })} aria-label="Trainer phone" placeholder="+233..." /></label>
              <label><span>Session price</span><input type="number" min="0" value={trainerForm.session_price} onChange={(e) => setTrainerForm({ ...trainerForm, session_price: e.target.value })} aria-label="Trainer session price" /></label>
              <button type="button" className="gm-primary" disabled={busy || !trainerForm.full_name.trim()}
                onClick={async () => {
                  const ok = await run('/gym/trainers', {
                    full_name: trainerForm.full_name.trim(), phone: trainerForm.phone.replace(/[\s-]/g, '') || null,
                    session_price: Number(trainerForm.session_price || 0),
                  }, 'Trainer added');
                  if (ok) setTrainerForm({ full_name: '', phone: '', session_price: '' });
                }}>Add trainer</button>
            </div>
          </section>
        </>
      ) : null}

      {current === 'lockers' && lockers ? (
        <section className="gm-box gm-scroll" aria-label="Lockers">
          <h2>Lockers</h2>
          <div className="gm-form">
            <label><span>New locker number</span><input value={lockerNo} onChange={(e) => setLockerNo(e.target.value)} aria-label="Locker number" /></label>
            <button type="button" className="gm-primary" disabled={busy || !lockerNo.trim()}
              onClick={async () => { if (await run('/gym/lockers', { number: lockerNo.trim() }, 'Locker added')) setLockerNo(''); }}>Add locker</button>
          </div>
            <p className="gm-muted">To rent a locker, fill in the days and the fee first (needs an open till). Leave them empty to give a locker with no rental.</p>
            <div className="gm-form">
              <label><span>Rental days</span><input type="number" min="1" max="366" value={rent.days} onChange={(e) => setRent({ ...rent, days: e.target.value })} aria-label="Locker rental days" /></label>
              <label><span>Fee</span><input type="number" min="0" step="0.01" value={rent.fee} onChange={(e) => setRent({ ...rent, fee: e.target.value })} aria-label="Locker rental fee" /></label>
              <label><span>Paid by</span><select value={rent.method} onChange={(e) => setRent({ ...rent, method: e.target.value })} aria-label="Locker rental method"><option value="cash">Cash</option><option value="mobile_money">Mobile Money</option><option value="card">Card</option><option value="bank_transfer">Bank transfer</option></select></label>
            </div>
          <table>
            <thead><tr><th>Locker</th><th>Status</th><th>Member</th><th>Rented until</th><th /></tr></thead>
            <tbody>
              {lockers.map((l) => (
                <tr key={l.id}>
                  <td>{l.number}</td><td>{l.status === 'free' ? 'Free' : 'In use'}</td><td>{l.member_name || '—'}</td><td>{l.rented_until ? `${l.rented_until}${l.overdue ? ' (overdue)' : ''}` : ''}</td>
                  <td className="gm-row">
                    {l.status === 'free' ? (
                      <>
                        <select value={lockerMember[l.id] || ''} onChange={(e) => setLockerMember({ ...lockerMember, [l.id]: e.target.value })} aria-label={`Member for locker ${l.number}`}>
                          <option value="">Member</option>
                          {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
                        </select>
                        <button type="button" disabled={busy || !lockerMember[l.id]} onClick={() => void run(`/gym/lockers/${l.id}/assign`, rentBody({ member_id: lockerMember[l.id] }), 'Locker given')}>Give</button>
                      </>
                    ) : (
                      <>
                        {rent.days ? <button type="button" disabled={busy} onClick={() => void run(`/gym/lockers/${l.id}/renew`, rentBody({}), 'Rental extended')}>Extend rental</button> : null}
                        <button type="button" onClick={() => void run(`/gym/lockers/${l.id}/release`, null, 'Locker free')}>Take back</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {lockers.length === 0 ? <tr><td colSpan={5} className="gm-muted">No lockers yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {current === 'equipment' && equipment ? (
        <section className="gm-box gm-scroll" aria-label="Equipment">
          <h2>Equipment</h2>
          <div className="gm-form">
            <label><span>Name</span><input value={eqForm.name} onChange={(e) => setEqForm({ ...eqForm, name: e.target.value })} aria-label="Equipment name" /></label>
            <label><span>Type</span><input value={eqForm.category} onChange={(e) => setEqForm({ ...eqForm, category: e.target.value })} aria-label="Equipment type" /></label>
            <button type="button" className="gm-primary" disabled={busy || !eqForm.name.trim()}
              onClick={async () => {
                if (await run('/gym/equipment', { name: eqForm.name.trim(), category: eqForm.category.trim() || null }, 'Equipment added')) setEqForm({ name: '', category: '' });
              }}>Add equipment</button>
          </div>
          <table>
            <thead><tr><th>Equipment</th><th>Status</th><th>Report a fault</th></tr></thead>
            <tbody>
              {equipment.map((e) => (
                <tr key={e.id}>
                  <td>{e.name}{e.category ? ` · ${e.category}` : ''}</td>
                  <td>{e.status === 'maintenance' ? `Being fixed (${e.open_faults})` : e.status === 'retired' ? 'Retired' : 'Working'}</td>
                  <td className="gm-row">
                    {e.status !== 'retired' ? (
                      <>
                        <input value={fault[e.id] || ''} onChange={(ev) => setFault({ ...fault, [e.id]: ev.target.value })} aria-label={`Fault on ${e.name}`} placeholder="What is wrong" />
                        <button type="button" disabled={busy || (fault[e.id] || '').trim().length < 3}
                          onClick={async () => { if (await run(`/gym/equipment/${e.id}/faults`, { fault: fault[e.id].trim() }, 'Fault logged')) setFault({ ...fault, [e.id]: '' }); }}>Log fault</button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
              {equipment.length === 0 ? <tr><td colSpan={3} className="gm-muted">No equipment yet.</td></tr> : null}
            </tbody>
          </table>
          <h3>Open faults</h3>
          <table>
            <tbody>
              {faults.map((f) => (
                <tr key={f.id}>
                  <td>{f.equipment_name}: {f.fault}</td>
                  <td className="gm-row">
                    <input value={fix[f.id] || ''} onChange={(ev) => setFix({ ...fix, [f.id]: ev.target.value })} aria-label={`How ${f.equipment_name} was fixed`} placeholder="What was done" />
                    <button type="button" className="gm-primary" disabled={busy || (fix[f.id] || '').trim().length < 3}
                      onClick={() => void run(`/gym/maintenance/${f.id}/close`, { resolution: fix[f.id].trim() }, 'Fixed')}>Fixed</button>
                    <button type="button" className="gm-danger" disabled={busy || (fix[f.id] || '').trim().length < 3}
                      onClick={() => void run(`/gym/maintenance/${f.id}/close`, { resolution: fix[f.id].trim(), retire: true }, 'Machine retired')}>Retire machine</button>
                  </td>
                </tr>
              ))}
              {faults.length === 0 ? <tr><td className="gm-muted">No open faults.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {current === 'guests' && guests ? (
        <section className="gm-box gm-scroll" aria-label="Guests">
          <h2>Guests</h2>
          <div className="gm-form">
            <label><span>Guest name</span><input value={guestForm.guest_name} onChange={(e) => setGuestForm({ ...guestForm, guest_name: e.target.value })} aria-label="Guest name" /></label>
            <label><span>Phone</span><input value={guestForm.phone} onChange={(e) => setGuestForm({ ...guestForm, phone: e.target.value })} aria-label="Guest phone" placeholder="+233..." /></label>
            <label><span>Brought by</span>
              <select value={guestForm.host_member_id} onChange={(e) => setGuestForm({ ...guestForm, host_member_id: e.target.value })} aria-label="Guest host">
                <option value="">Nobody</option>
                {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
              </select></label>
            <label><span>Entry fee (optional)</span><input type="number" min="0" step="0.01" value={guestForm.fee} onChange={(e) => setGuestForm({ ...guestForm, fee: e.target.value })} aria-label="Guest entry fee" /></label>
            {Number(guestForm.fee) > 0 ? <label><span>Paid by</span><select value={guestForm.method} onChange={(e) => setGuestForm({ ...guestForm, method: e.target.value })} aria-label="Guest fee method"><option value="cash">Cash</option><option value="mobile_money">Mobile Money</option><option value="card">Card</option><option value="bank_transfer">Bank transfer</option></select></label> : null}
            <button type="button" className="gm-primary" disabled={busy || !guestForm.guest_name.trim()}
              onClick={async () => {
                const ok = await run('/gym/guests', {
                  guest_name: guestForm.guest_name.trim(), phone: guestForm.phone.replace(/[\s-]/g, '') || null,
                  host_member_id: guestForm.host_member_id || null,
                  ...(Number(guestForm.fee) > 0 ? { fee: Number(guestForm.fee), method: guestForm.method } : {}),
                }, 'Guest in');
                if (ok) setGuestForm({ guest_name: '', phone: '', host_member_id: '', fee: '', method: 'cash' });
              }}>Let guest in</button>
          </div>
          <table>
            <thead><tr><th>Guest</th><th>Brought by</th><th>In</th><th /></tr></thead>
            <tbody>
              {guests.map((g) => (
                <tr key={g.id}>
                  <td>{g.guest_name}</td><td>{g.host_name || '—'}</td><td>{when(g.visited_at)}</td>
                  <td>{g.left_at ? `Left ${when(g.left_at)}` : <button type="button" onClick={() => void run(`/gym/guests/${g.id}/out`, null, 'Guest out')}>Left</button>}</td>
                </tr>
              ))}
              {guests.length === 0 ? <tr><td colSpan={4} className="gm-muted">No guests yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
