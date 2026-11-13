'use client';

/**
 * HRM time: shifts and roster, the clock board (today, corrections, the month and overtime),
 * work sites with QR codes and ZKTeco terminal / BioTime links, and the staff clock under
 * My pay and leave. The server checks who may do what and where a clock-in may come from.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const isoDay = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const hours = (min: number) => (min ? `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, '0')}m` : '—');
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const STATUS: Record<string, string> = {
  present: 'In on time', late: 'Late', absent: 'Not in', on_leave: 'On leave', off: 'Not rostered', still_in: 'Still in', due: 'Not started yet',
};

export const TIME_SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  shifts: { title: 'Shifts and roster', sub: 'Working patterns and who works when.', icon: 'calendar' },
  clock: { title: 'Clock board', sub: 'Who is in, late or missing; corrections; the month and overtime.', icon: 'clock' },
  devices: { title: 'Sites and terminals', sub: 'Where staff clock in: GPS areas, QR codes, ZKTeco terminals and BioTime.', icon: 'door' },
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
      setNotice(typeof done === 'string' ? done : 'Saved');
      await reload();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, notice, run, setError, setNotice };
}

function Banner({ error, notice }: { error: string; notice: string }) {
  return (
    <>
      {notice ? <div className="hr-banner" role="status">{notice}</div> : null}
      {error ? <div className="hr-banner bad" role="alert">{error}</div> : null}
    </>
  );
}

export function TimeWork({ tab, seesPay }: { tab: string; seesPay: boolean }) {
  const [people, setPeople] = useState<Row[]>([]);
  const [data, setData] = useState<Row | null>(null);
  const [day, setDay] = useState(isoDay());
  const [period, setPeriod] = useState(isoDay().slice(0, 7));
  const [f, setF] = useState<Row>({ weekdays: [0, 1, 2, 3, 4] });
  const [qr, setQr] = useState<Row | null>(null);
  const [why, setWhy] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    setPeople((await get('/hrm/employees').catch(() => [])) || []);
    if (tab === 'shifts') {
      const start = isoDay();
      const end = isoDay(new Date(Date.now() + 13 * 86400000));
      const [shifts, roster] = await Promise.all([get('/hrm/shifts'), get(`/hrm/roster?start=${start}&end=${end}`)]);
      setData({ shifts: shifts || [], roster: roster || [] });
    }
    if (tab === 'clock') {
      const [board, corrections, month] = await Promise.all([get(`/hrm/time/day?day=${day}`), get('/hrm/time/corrections'), get(`/hrm/time/month?period=${period}`)]);
      setData({ board: board || [], corrections: corrections || [], month: month || [] });
    }
    if (tab === 'devices') {
      const [sites, links] = await Promise.all([get('/hrm/sites'), get('/hrm/biometric')]);
      setData({ sites: sites || [], links: links || [] });
    }
  }, [tab, day, period]);
  const { busy, error, notice, run, setError } = useRunner(load);

  useEffect(() => {
    setData(null);
    load().catch((err) => setError(problem(err)));
  }, [load, setError]);

  useEffect(() => {
    if (!qr) return undefined;
    const timer = window.setInterval(async () => {
      try {
        setQr((await api(`/hrm/sites/${qr.site_id}/qr`))?.data || null);
      } catch {
        /* keep showing the last code */
      }
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [qr]);

  const set = (key: string, value: unknown) => setF((old) => ({ ...old, [key]: value }));
  const txt = (key: string) => String(f[key] ?? '');
  if (!data) return <Banner error={error} notice={notice} />;

  return (
    <>
      <Banner error={error} notice={notice} />

      {tab === 'shifts' ? (
        <>
          <section className="hr-box" aria-label="Add a shift">
            <h2>Shifts</h2>
            <div className="hr-form">
              <label><span>Name</span><input value={txt('name')} placeholder="Morning" onChange={(e) => set('name', e.target.value)} aria-label="Shift name" /></label>
              <label><span>Starts</span><input type="time" value={txt('starts_at')} onChange={(e) => set('starts_at', e.target.value)} aria-label="Shift starts" /></label>
              <label><span>Ends (earlier = next day)</span><input type="time" value={txt('ends_at')} onChange={(e) => set('ends_at', e.target.value)} aria-label="Shift ends" /></label>
              <label><span>Unpaid break (minutes)</span><input type="number" min="0" value={txt('break_minutes') || '0'} onChange={(e) => set('break_minutes', e.target.value)} aria-label="Shift break minutes" /></label>
              <label><span>Late after (minutes)</span><input type="number" min="0" value={txt('grace_minutes') || '10'} onChange={(e) => set('grace_minutes', e.target.value)} aria-label="Shift grace minutes" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || txt('name').trim().length < 2 || !f.starts_at || !f.ends_at}
                onClick={async () => {
                  if (await run('/hrm/shifts', { name: txt('name').trim(), starts_at: f.starts_at, ends_at: f.ends_at, break_minutes: Number(f.break_minutes || 0), grace_minutes: Number(f.grace_minutes ?? 10) }, 'Shift saved')) setF({ weekdays: [0, 1, 2, 3, 4] });
                }}
              >Save shift</button>
            </div>
            <table><tbody>{data.shifts.map((s: Row) => (
              <tr key={s.id}>
                <td>{s.name}</td><td>{s.starts_at}–{s.ends_at}</td><td>{s.break_minutes} min break</td><td>late after {s.grace_minutes} min</td>
                <td>{s.is_active ? <button type="button" className="hr-danger" disabled={busy} onClick={() => void run(`/hrm/shifts/${s.id}/retire`, null, 'Shift switched off')}>Switch off</button> : 'Off'}</td>
              </tr>
            ))}</tbody></table>
          </section>
          <section className="hr-box" aria-label="Put people on the roster">
            <h2>Roster</h2>
            <div className="hr-form">
              <label><span>Shift</span>
                <select value={txt('shift_id')} onChange={(e) => set('shift_id', e.target.value)} aria-label="Roster shift">
                  <option value="">Day off (take off the roster)</option>
                  {data.shifts.filter((s: Row) => s.is_active).map((s: Row) => <option key={s.id} value={s.id}>{s.name} {s.starts_at}–{s.ends_at}</option>)}
                </select>
              </label>
              <label><span>From</span><input type="date" value={txt('start')} onChange={(e) => set('start', e.target.value)} aria-label="Roster from" /></label>
              <label><span>To</span><input type="date" value={txt('end')} onChange={(e) => set('end', e.target.value)} aria-label="Roster to" /></label>
              <fieldset className="hr-wide" aria-label="Roster days">
                {WEEKDAYS.map((w, i) => (
                  <label key={w} className="hr-check">
                    <input type="checkbox" checked={(f.weekdays || []).includes(i)} onChange={(e) => set('weekdays', e.target.checked ? [...(f.weekdays || []), i] : (f.weekdays || []).filter((x: number) => x !== i))} aria-label={`Roster ${w}`} />
                    <span>{w}</span>
                  </label>
                ))}
              </fieldset>
              <fieldset className="hr-wide" aria-label="Roster people">
                {people.map((p) => (
                  <label key={p.id} className="hr-check">
                    <input type="checkbox" checked={(f.people || []).includes(p.id)} onChange={(e) => set('people', e.target.checked ? [...(f.people || []), p.id] : (f.people || []).filter((x: string) => x !== p.id))} aria-label={`Roster ${p.full_name}`} />
                    <span>{p.full_name}</span>
                  </label>
                ))}
              </fieldset>
              <button
                type="button" className="hr-primary" disabled={busy || !(f.people || []).length || !f.start || !f.end || !(f.weekdays || []).length}
                onClick={() => void run('/hrm/roster', { employee_ids: f.people, start: f.start, end: f.end, weekdays: f.weekdays, shift_id: f.shift_id || null }, 'Roster saved')}
              >Save roster</button>
            </div>
          </section>
          <section className="hr-box hr-scroll" aria-label="Next two weeks">
            <h2>Next two weeks</h2>
            <table>
              <thead><tr><th>Day</th><th>Who</th><th>Shift</th></tr></thead>
              <tbody>
                {data.roster.map((r: Row) => <tr key={`${r.day}${r.employee_id}`}><td>{r.day}</td><td>{r.employee_name}</td><td>{r.shift} {r.starts_at}–{r.ends_at}</td></tr>)}
                {data.roster.length === 0 ? <tr><td colSpan={3} className="hr-muted">Nobody rostered yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'clock' ? (
        <>
          <section className="hr-box hr-scroll" aria-label="Clock board">
            <h2>
              Clock board{' '}
              <input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Clock board day" style={{ maxWidth: 170 }} />
            </h2>
            <table>
              <thead><tr><th>Who</th><th>Shift</th><th>In</th><th>Out</th><th>Worked</th><th>Late</th><th>Early</th><th>Overtime</th><th>Status</th></tr></thead>
              <tbody>
                {data.board.map((r: Row) => (
                  <tr key={r.employee_id}>
                    <td>{r.employee_name}</td><td>{r.shift ? `${r.shift} ${r.shift_time}` : '—'}</td>
                    <td>{r.first_in || '—'}</td><td>{r.last_out || '—'}</td><td>{hours(r.worked_minutes)}</td>
                    <td>{r.late_minutes ? `${r.late_minutes} min` : '—'}</td><td>{r.early_minutes ? `${r.early_minutes} min` : '—'}</td>
                    <td>{hours(r.overtime_minutes)}</td><td>{STATUS[r.status] || r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="hr-box" aria-label="Enter times for someone">
            <h2>Enter times for someone</h2>
            <p className="hr-muted">Replaces that day&apos;s clock times. The old ones stay in the record, marked replaced.</p>
            <div className="hr-form">
              <label><span>Employee</span>
                <select value={txt('rec_emp')} onChange={(e) => set('rec_emp', e.target.value)} aria-label="Times employee">
                  <option value="">Choose</option>{people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
              </label>
              <label><span>Day</span><input type="date" value={txt('rec_day')} onChange={(e) => set('rec_day', e.target.value)} aria-label="Times day" /></label>
              <label><span>In</span><input type="time" value={txt('rec_in')} onChange={(e) => set('rec_in', e.target.value)} aria-label="Time in" /></label>
              <label><span>Out</span><input type="time" value={txt('rec_out')} onChange={(e) => set('rec_out', e.target.value)} aria-label="Time out" /></label>
              <label><span>Why</span><input value={txt('rec_note')} onChange={(e) => set('rec_note', e.target.value)} aria-label="Times reason" /></label>
              <button
                type="button" className="hr-primary" disabled={busy || !f.rec_emp || !f.rec_day || (!f.rec_in && !f.rec_out) || txt('rec_note').trim().length < 3}
                onClick={async () => {
                  const ok = await run('/hrm/time/record', {
                    employee_id: f.rec_emp, day: f.rec_day,
                    in_at: f.rec_in ? `${f.rec_day}T${f.rec_in}:00` : null,
                    out_at: f.rec_out ? `${f.rec_day}T${f.rec_out}:00` : null,
                    note: txt('rec_note').trim(),
                  }, 'Times saved');
                  if (ok) setF({ weekdays: [0, 1, 2, 3, 4] });
                }}
              >Save times</button>
            </div>
          </section>
          {data.corrections.some((c: Row) => c.status === 'pending') ? (
            <section className="hr-box hr-scroll" aria-label="Clock corrections">
              <h2>Asked to put right</h2>
              <table><tbody>
                {data.corrections.filter((c: Row) => c.status === 'pending').map((c: Row) => (
                  <tr key={c.id}>
                    <td>{c.employee_name}</td><td>{c.day}</td>
                    <td>{c.in_at ? `in ${c.in_at.slice(11, 16)}` : ''} {c.out_at ? `out ${c.out_at.slice(11, 16)}` : ''}</td><td>{c.reason}</td>
                    <td>
                      <div className="hr-row">
                        <button type="button" className="hr-primary" disabled={busy} onClick={() => void run(`/hrm/time/corrections/${c.id}/decide`, { approve: true }, 'Put right')}>Approve</button>
                        <input placeholder="Reason to turn down" value={why[c.id] || ''} onChange={(e) => setWhy({ ...why, [c.id]: e.target.value })} aria-label={`Reason to turn down correction ${c.id}`} />
                        <button
                          type="button" className="hr-danger" disabled={busy || !(why[c.id] || '').trim()}
                          onClick={() => void run(`/hrm/time/corrections/${c.id}/decide`, { approve: false, note: (why[c.id] || '').trim() }, 'Turned down')}
                        >Turn down</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody></table>
            </section>
          ) : null}
          <section className="hr-box hr-scroll" aria-label="The month">
            <h2>
              The month{' '}
              <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Time month" style={{ maxWidth: 170 }} />
            </h2>
            <p className="hr-muted">Overtime is paid only once approved here, on that month&apos;s payroll. You cannot approve more than the clock shows.</p>
            <table>
              <thead><tr><th>Who</th><th>Worked</th><th>Late days</th><th>Not in</th><th>Overtime on the clock</th><th>Approved</th><th /></tr></thead>
              <tbody>
                {data.month.map((r: Row) => (
                  <tr key={r.employee_id}>
                    <td>{r.employee_name}</td><td>{hours(r.worked_minutes)}</td><td>{r.late_days}</td><td>{r.absent_days}</td>
                    <td>{hours(r.overtime_minutes)}</td>
                    <td>{r.overtime_approved ? `${hours(r.overtime_approved.minutes)}${r.overtime_approved.amount != null ? ` · ${money(r.overtime_approved.amount)}` : ''}${r.overtime_approved.status === 'paid' ? ' (paid)' : ''}` : '—'}</td>
                    <td>
                      {seesPay && r.overtime_minutes > 0 && r.overtime_approved?.status !== 'paid' ? (
                        <button type="button" className="hr-primary" disabled={busy} onClick={() => void run('/hrm/time/overtime', { employee_id: r.employee_id, period, minutes: r.overtime_minutes }, 'Overtime approved')}>
                          Approve {hours(r.overtime_minutes)}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'devices' ? (
        <>
          <section className="hr-box" aria-label="Work sites">
            <h2>Work sites</h2>
            <p className="hr-muted">
              A site is a GPS point and radius, and a QR code to show on a screen there (it changes every five minutes). Turn on
              &quot;clock-ins must be at a site&quot; under Pay rates to refuse phone clock-ins from anywhere else.
            </p>
            <div className="hr-form">
              <label><span>Name</span><input value={txt('s_name')} onChange={(e) => set('s_name', e.target.value)} aria-label="Site name" /></label>
              <label><span>Latitude</span><input type="number" step="0.000001" value={txt('s_lat')} onChange={(e) => set('s_lat', e.target.value)} aria-label="Site latitude" /></label>
              <label><span>Longitude</span><input type="number" step="0.000001" value={txt('s_lon')} onChange={(e) => set('s_lon', e.target.value)} aria-label="Site longitude" /></label>
              <label><span>Radius (metres)</span><input type="number" min="20" value={txt('s_radius') || '150'} onChange={(e) => set('s_radius', e.target.value)} aria-label="Site radius" /></label>
              <button
                type="button" disabled={busy}
                onClick={() => navigator.geolocation?.getCurrentPosition(
                  (pos) => setF((old) => ({ ...old, s_lat: pos.coords.latitude.toFixed(6), s_lon: pos.coords.longitude.toFixed(6) })),
                  () => setError('This browser would not share its location.'),
                  { enableHighAccuracy: true, timeout: 15000 },
                )}
              >Use where I am</button>
              <button
                type="button" className="hr-primary" disabled={busy || txt('s_name').trim().length < 2}
                onClick={async () => {
                  const ok = await run('/hrm/sites', {
                    name: txt('s_name').trim(),
                    latitude: f.s_lat ? Number(f.s_lat) : null,
                    longitude: f.s_lon ? Number(f.s_lon) : null,
                    radius_m: Number(f.s_radius || 150),
                  }, 'Site saved');
                  if (ok) setF({ weekdays: [0, 1, 2, 3, 4] });
                }}
              >Save site</button>
            </div>
            <table><tbody>{data.sites.map((s: Row) => (
              <tr key={s.id}>
                <td>{s.name}</td><td>{s.latitude != null ? `${s.latitude}, ${s.longitude} (${s.radius_m} m)` : 'QR code only'}</td>
                <td><button type="button" onClick={async () => { try { setQr((await api(`/hrm/sites/${s.id}/qr`))?.data || null); } catch (err) { setError(problem(err)); } }}>Show QR code</button></td>
              </tr>
            ))}</tbody></table>
            {qr ? (
              <div className="hr-qr" role="region" aria-label="Site clock-in code">
                <p>Clock-in code for {qr.site}</p>
                <img
                  alt={`QR code ${qr.code}`}
                  width={220}
                  height={220}
                  src={qr.image}
                />
                <p className="hr-qr-code">{qr.code}</p>
                <small className="hr-muted">Staff scan it or type the eight letters under My pay and leave. It changes every five minutes; this screen refreshes itself.</small>
                <button type="button" onClick={() => setQr(null)}>Close</button>
              </div>
            ) : null}
          </section>
          <section className="hr-box" aria-label="ZKTeco terminals and BioTime">
            <h2>ZKTeco terminals and BioTime</h2>
            <p className="hr-muted">
              Give each person their terminal ID (the PIN on the fingerprint or face terminal) on their staff record. Then either
              link your BioTime server, and press Sync to read its punches, or point the terminal&apos;s cloud server setting at this
              ERP&apos;s address and register its serial number here. Check the first day&apos;s punches against the terminal before
              paying from them.
            </p>
            <div className="hr-form">
              <label><span>Kind</span>
                <select value={txt('l_kind') || 'device'} onChange={(e) => set('l_kind', e.target.value)} aria-label="Link kind">
                  <option value="device">Terminal sends punches here (push)</option>
                  <option value="biotime">BioTime server (ERP reads it)</option>
                </select>
              </label>
              <label><span>Name</span><input value={txt('l_name')} placeholder="Front door" onChange={(e) => set('l_name', e.target.value)} aria-label="Link name" /></label>
              {(f.l_kind || 'device') === 'device' ? (
                <label><span>Serial number</span><input value={txt('l_serial')} onChange={(e) => set('l_serial', e.target.value)} aria-label="Terminal serial number" /></label>
              ) : (
                <>
                  <label><span>BioTime address</span><input value={txt('l_url')} placeholder="https://biotime.example.com" onChange={(e) => set('l_url', e.target.value)} aria-label="BioTime address" /></label>
                  <label><span>API user</span><input value={txt('l_user')} onChange={(e) => set('l_user', e.target.value)} aria-label="BioTime user" /></label>
                  <label><span>Password</span><input type="password" autoComplete="off" value={txt('l_pass')} onChange={(e) => set('l_pass', e.target.value)} aria-label="BioTime password" /></label>
                </>
              )}
              <label><span>Site (optional)</span>
                <select value={txt('l_site')} onChange={(e) => set('l_site', e.target.value)} aria-label="Link site">
                  <option value="">None</option>{data.sites.map((s: Row) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
              <button
                type="button" className="hr-primary" disabled={busy || !seesPay || txt('l_name').trim().length < 2}
                title={seesPay ? undefined : 'An HR manager links terminals'}
                onClick={async () => {
                  const kind = f.l_kind || 'device';
                  const body = kind === 'device'
                    ? { kind, name: txt('l_name').trim(), device_serial: txt('l_serial').trim(), site_id: f.l_site || null }
                    : { kind, name: txt('l_name').trim(), base_url: txt('l_url').trim(), username: txt('l_user').trim(), password: txt('l_pass'), site_id: f.l_site || null };
                  if (await run('/hrm/biometric', body, 'Linked')) setF({ weekdays: [0, 1, 2, 3, 4] });
                }}
              >Link</button>
            </div>
            <table>
              <thead><tr><th>Name</th><th>Kind</th><th>Last heard</th><th>Last result</th><th /></tr></thead>
              <tbody>
                {data.links.map((l: Row) => (
                  <tr key={l.id}>
                    <td>{l.name}{l.device_serial ? <><br /><small className="hr-muted">{l.device_serial}</small></> : null}{l.base_url ? <><br /><small className="hr-muted">{l.base_url}</small></> : null}</td>
                    <td>{l.kind === 'biotime' ? 'BioTime' : 'Terminal push'}{l.is_active ? '' : ' (off)'}</td>
                    <td>{(l.last_seen_at || l.last_synced_at || '—').toString().slice(0, 16).replace('T', ' ')}</td>
                    <td>{l.last_result || '—'}</td>
                    <td>
                      <div className="hr-row">
                        {l.kind === 'biotime' && l.is_active ? <button type="button" className="hr-primary" disabled={busy} onClick={() => void run(`/hrm/biometric/${l.id}/sync`, null, 'Synced')}>Sync now</button> : null}
                        {l.is_active && seesPay ? <button type="button" className="hr-danger" disabled={busy} onClick={() => void run(`/hrm/biometric/${l.id}/off`, null, 'Switched off')}>Switch off</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {data.links.length === 0 ? <tr><td colSpan={5} className="hr-muted">No terminals linked.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </>
  );
}

/** Clock in and out from the person's own phone, their roster, and asking to put a time right. */
export function MyClock() {
  const [me, setMe] = useState<Row | null>(null);
  const [code, setCode] = useState('');
  const [f, setF] = useState<Row>({});
  const load = useCallback(async () => setMe((await api('/hrm/me/time'))?.data || null), []);
  const { busy, error, notice, run, setError } = useRunner(load);
  useEffect(() => {
    load().catch(() => setMe(null));
  }, [load]);
  if (!me) return null;

  async function punch(kind: 'in' | 'out') {
    const send = (extra: Row) => run('/hrm/me/clock', { kind, ...(code.trim() ? { qr_code: code.trim().toUpperCase() } : {}), ...extra }, kind === 'in' ? 'Clocked in' : 'Clocked out');
    if (!navigator.geolocation) {
      await send({});
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => void send({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy_m: Math.round(pos.coords.accuracy) }),
      () => void send({}),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
    setCode('');
  }

  const t = me.today || {};
  return (
    <>
      <Banner error={error} notice={notice} />
      <section className="hr-box" aria-label="Clock in and out">
        <h2>{me.clocked_in ? 'You are clocked in' : 'Clock in'}</h2>
        <p className="hr-muted">
          Today: {t.shift ? `${t.shift} ${t.shift_time}` : 'not rostered'}
          {t.first_in ? ` · in ${t.first_in}` : ''}{t.last_out ? ` · out ${t.last_out}` : ''}
          {t.worked_minutes ? ` · ${hours(t.worked_minutes)}` : ''}
        </p>
        <div className="hr-form">
          <label><span>Site code (if asked)</span><input value={code} maxLength={8} onChange={(e) => setCode(e.target.value)} aria-label="Site clock-in code" /></label>
          <button type="button" className="hr-primary" disabled={busy} onClick={() => void punch(me.clocked_in ? 'out' : 'in')}>
            {me.clocked_in ? 'Clock out' : 'Clock in'}
          </button>
        </div>
        <small className="hr-muted">Your phone&apos;s location is sent with each clock so HR can see where it came from.</small>
      </section>
      {me.roster.length ? (
        <section className="hr-box" aria-label="My shifts">
          <h2>My next shifts</h2>
          {me.roster.map((r: Row) => <div className="hr-line" key={r.day}><span>{r.day}</span><span>{r.shift} {r.starts_at}–{r.ends_at}</span></div>)}
        </section>
      ) : null}
      <section className="hr-box" aria-label="Put a clock time right">
        <h2>Forgot to clock?</h2>
        <div className="hr-form">
          <label><span>Day</span><input type="date" value={f.day || ''} onChange={(e) => setF({ ...f, day: e.target.value })} aria-label="Correction day" /></label>
          <label><span>In</span><input type="time" value={f.in || ''} onChange={(e) => setF({ ...f, in: e.target.value })} aria-label="Correction in" /></label>
          <label><span>Out</span><input type="time" value={f.out || ''} onChange={(e) => setF({ ...f, out: e.target.value })} aria-label="Correction out" /></label>
          <label><span>Why</span><input value={f.reason || ''} onChange={(e) => setF({ ...f, reason: e.target.value })} aria-label="Correction reason" /></label>
          <button
            type="button" className="hr-primary" disabled={busy || !f.day || (!f.in && !f.out) || String(f.reason || '').trim().length < 3}
            onClick={async () => {
              const ok = await run('/hrm/me/clock-corrections', {
                day: f.day, in_at: f.in ? `${f.day}T${f.in}:00` : null, out_at: f.out ? `${f.day}T${f.out}:00` : null, reason: String(f.reason).trim(),
              }, 'Sent to HR');
              if (ok) setF({});
            }}
          >Ask HR</button>
        </div>
        {me.corrections.length ? <table><tbody>{me.corrections.map((c: Row) => <tr key={c.id}><td>{c.day}</td><td>{c.reason}</td><td>{c.status}</td></tr>)}</tbody></table> : null}
      </section>
    </>
  );
}

export default TimeWork;
