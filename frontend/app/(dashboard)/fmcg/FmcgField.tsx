'use client';

/**
 * FMCG field work: a rep checks in and out at an outlet with the phone's location, and
 * managers see coverage and set up territories (routes + reps). Location comes from the
 * browser (navigator.geolocation); a visit still saves without it and is flagged.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;
type Fix = { latitude: number; longitude: number; accuracy_m: number } | null;

export const FIELD_TABS = ['visits', 'territories'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];

const OUTCOMES = [
  { id: 'order', label: 'Took an order' },
  { id: 'no_order', label: 'No order' },
  { id: 'closed', label: 'Shop closed' },
  { id: 'not_found', label: 'Could not find it' },
];
const NO_ORDER = [
  { id: 'has_stock', label: 'Still has stock' },
  { id: 'no_money', label: 'No money today' },
  { id: 'owner_away', label: 'Owner away' },
  { id: 'price', label: 'Price' },
  { id: 'competitor', label: 'Buying from someone else' },
  { id: 'other', label: 'Other' },
];
const FLAG_WORDS: Record<string, string> = {
  far: 'Far from the outlet',
  rough_gps: 'Weak location',
  no_gps: 'No location',
  outlet_unmapped: 'Outlet not on the map yet',
  order_not_booked: 'Said order, none booked',
};

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Ask the phone where it is. Resolves to null when the person says no or there is no fix. */
function whereAmI(): Promise<Fix> {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy_m: Math.round(pos.coords.accuracy) }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  });
}

function Flags({ flags }: { flags: string[] }) {
  if (!flags?.length) return <span className="fs-muted">None</span>;
  return <>{flags.map((f) => <span key={f} className="fs-flag">{FLAG_WORDS[f] || f}</span>)}</>;
}

export default function FmcgField({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [meId, setMeId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [visits, setVisits] = useState<Row[]>([]);
  const [day, setDay] = useState(today());
  const [coverage, setCoverage] = useState<Row | null>(null);
  const [territories, setTerritories] = useState<Row[]>([]);
  const [routes, setRoutes] = useState<Row[]>([]);
  const [people, setPeople] = useState<Row[]>([]);
  const [report, setReport] = useState<Row[]>([]);
  const [period, setPeriod] = useState(today().slice(0, 7));
  const [outletId, setOutletId] = useState('');
  const [finish, setFinish] = useState({ outcome: 'order', no_order_reason: '', notes: '' });
  const blank = { id: '', code: '', name: '', daily_visit_target: '0', notes: '', route_ids: [] as string[], rep_user_ids: [] as string[] };
  const [form, setForm] = useState(blank);
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe()
      .then((me: Row | null) => {
        setRole(String(me?.data?.role || ''));
        setMeId(String(me?.data?.id || ''));
      })
      .catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      if (tab === 'visits') {
        const [o, v] = await Promise.all([api('/fmcg/my-outlets'), api(`/fmcg/visits?day=${day}`)]);
        setOutlets(o?.data || []);
        setVisits(v?.data || []);
        if (manager) setCoverage((await api(`/fmcg/coverage?day=${day}`))?.data || null);
      } else if (tab === 'territories' && manager) {
        const [t, r, p, rep] = await Promise.all([
          api('/fmcg/territories'), api('/fmcg/routes'), api('/fmcg/field-people'), api(`/fmcg/territories/report?period=${period}`),
        ]);
        setTerritories(t?.data || []);
        setRoutes(r?.data || []);
        setPeople(p?.data || []);
        setReport(rep?.data || []);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, day, period, manager]);

  useEffect(() => {
    if (role) load();
  }, [role, load]);

  async function checkIn() {
    setBusy(true);
    setError('');
    setNotice('Finding where you are…');
    const fix = await whereAmI();
    try {
      const res = await api('/fmcg/visits/check-in', { method: 'POST', body: JSON.stringify({ outlet_id: outletId, ...(fix || {}) }) });
      const v = res?.data || {};
      setNotice(
        !fix ? 'Checked in without your location. Turn on location for this site next time.'
          : v.set_outlet_location ? 'Checked in. This outlet is now on the map.'
            : v.flags?.includes('far') ? `Checked in, but you are ${Math.round(v.distance_m)} m from the outlet.`
              : 'Checked in.',
      );
      setOutletId('');
      await load();
    } catch (err) {
      setNotice('');
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function checkOut(visit: Row) {
    setBusy(true);
    setError('');
    const fix = await whereAmI();
    try {
      await api(`/fmcg/visits/${visit.id}/check-out`, {
        method: 'POST',
        body: JSON.stringify({
          outcome: finish.outcome,
          no_order_reason: finish.outcome === 'no_order' ? finish.no_order_reason || null : null,
          notes: finish.notes.trim() || null,
          ...(fix || {}),
        }),
      });
      setNotice('Visit finished.');
      setFinish({ outcome: 'order', no_order_reason: '', notes: '' });
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveTerritory() {
    setBusy(true);
    setError('');
    try {
      const body = {
        code: form.code.trim(), name: form.name.trim(), notes: form.notes.trim() || null,
        daily_visit_target: Number(form.daily_visit_target || 0), is_active: true,
        route_ids: form.route_ids, rep_user_ids: form.rep_user_ids,
      };
      await api(form.id ? `/fmcg/territories/${form.id}` : '/fmcg/territories', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify(body) });
      setNotice('Territory saved.');
      setForm(blank);
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const mineOpen = visits.find((v) => !v.checked_out && (!manager || v.user_id === meId));

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {tab === 'visits' ? (
        <>
          {mineOpen ? (
            <section className="fs-box" aria-label="Current visit">
              <div className="fs-cardhead"><h2>At {mineOpen.outlet_name} since {mineOpen.checked_in}</h2></div>
              {mineOpen.flags?.length ? <p><Flags flags={mineOpen.flags} /></p> : null}
              <div className="fs-form">
                <label><span>How did it go</span>
                  <select value={finish.outcome} onChange={(e) => setFinish({ ...finish, outcome: e.target.value })} aria-label="Visit outcome">
                    {OUTCOMES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                </label>
                {finish.outcome === 'no_order' ? (
                  <label><span>Why no order</span>
                    <select value={finish.no_order_reason} onChange={(e) => setFinish({ ...finish, no_order_reason: e.target.value })} aria-label="Why no order">
                      <option value="">Choose</option>
                      {NO_ORDER.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                    </select>
                  </label>
                ) : null}
                <label><span>Notes</span><input value={finish.notes} maxLength={500} onChange={(e) => setFinish({ ...finish, notes: e.target.value })} aria-label="Visit notes" /></label>
                <button
                  type="button" className="fs-primary"
                  disabled={busy || (finish.outcome === 'no_order' && !finish.no_order_reason)}
                  onClick={() => checkOut(mineOpen)}
                >
                  Finish visit
                </button>
              </div>
              {finish.outcome === 'order' ? <p className="fs-muted">Book the order on Orders before you finish, so it is linked to this visit.</p> : null}
            </section>
          ) : (
            <section className="fs-box" aria-label="Check in">
              <div className="fs-cardhead"><h2>Check in at an outlet</h2></div>
              <div className="fs-form">
                <label><span>Outlet</span>
                  <select value={outletId} onChange={(e) => setOutletId(e.target.value)} aria-label="Visit outlet">
                    <option value="">Choose</option>
                    {outlets.map((o) => (
                      <option key={o.id} value={o.id}>{o.name}{o.visited_today ? ' · visited today' : ''}{o.latitude == null ? ' · not on map' : ''}</option>
                    ))}
                  </select>
                </label>
                <button type="button" className="fs-primary" disabled={busy || !outletId} onClick={checkIn}>Check in here</button>
              </div>
              <p className="fs-muted">Uses your phone&apos;s location. Allow location for this site when asked.</p>
              {outlets.length === 0 ? <p className="fs-muted">No outlets yet. Ask a manager to put you on a territory.</p> : null}
            </section>
          )}

          <section className="fs-box" aria-label="Visit day">
            <div className="fs-form">
              <label><span>Day</span><input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Visits day" /></label>
            </div>
          </section>

          {manager && coverage ? (
            <>
              <section className="fs-box fs-scroll" aria-label="Reps today">
                <div className="fs-cardhead"><h2>Reps</h2></div>
                <table>
                  <thead><tr><th>Rep</th><th>Visits</th><th>Orders</th><th>Strike rate</th><th>First in</th><th>Last out</th><th>Flagged</th></tr></thead>
                  <tbody>
                    {coverage.reps.map((r: Row) => (
                      <tr key={r.user_id}><td>{r.rep_name}</td><td className="fs-num">{r.visits}</td><td className="fs-num">{r.orders}</td><td className="fs-num">{r.strike_rate}%</td><td>{r.first_in || '-'}</td><td>{r.last_out || '-'}</td><td className="fs-num">{r.flagged}</td></tr>
                    ))}
                    {coverage.reps.length === 0 ? <tr><td colSpan={7} className="fs-muted">No visits on this day.</td></tr> : null}
                  </tbody>
                </table>
              </section>
              <section className="fs-box fs-scroll" aria-label="Route coverage">
                <div className="fs-cardhead"><h2>Planned stops</h2></div>
                <table>
                  <thead><tr><th>Route</th><th>Planned</th><th>Visited</th><th>Missed</th></tr></thead>
                  <tbody>
                    {coverage.routes.map((r: Row) => (
                      <tr key={r.route_id}><td>{r.route}</td><td className="fs-num">{r.planned}</td><td className="fs-num">{r.visited}</td><td>{r.missed.join(', ') || <span className="fs-muted">None</span>}</td></tr>
                    ))}
                    {coverage.routes.length === 0 ? <tr><td colSpan={4} className="fs-muted">No route stops planned for this day.</td></tr> : null}
                  </tbody>
                </table>
              </section>
            </>
          ) : null}

          <section className="fs-box fs-scroll" aria-label="Visits">
            <div className="fs-cardhead"><h2>{manager ? 'All visits' : 'My visits'}</h2></div>
            <table>
              <thead><tr>{manager ? <th>Rep</th> : null}<th>Outlet</th><th>In</th><th>Out</th><th>Minutes</th><th>Outcome</th><th>Distance</th><th>Check</th></tr></thead>
              <tbody>
                {visits.map((v) => (
                  <tr key={v.id}>
                    {manager ? <td>{v.rep_name}</td> : null}
                    <td>{v.outlet_name}</td><td>{v.checked_in}</td><td>{v.checked_out || 'Still there'}</td>
                    <td className="fs-num">{v.minutes ?? '-'}</td>
                    <td>{OUTCOMES.find((o) => o.id === v.outcome)?.label || '-'}{v.no_order_reason ? ` (${NO_ORDER.find((o) => o.id === v.no_order_reason)?.label})` : ''}</td>
                    <td className="fs-num">{v.distance_m == null ? '-' : `${Math.round(v.distance_m)} m`}</td>
                    <td><Flags flags={v.flags} /></td>
                  </tr>
                ))}
                {visits.length === 0 ? <tr><td colSpan={manager ? 8 : 7} className="fs-muted">No visits on this day.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'territories' && !manager ? <div className="fs-banner">Territories are set by a manager.</div> : null}

      {tab === 'territories' && manager ? (
        <>
          <section className="fs-box" aria-label="Territory">
            <div className="fs-cardhead"><h2>{form.id ? `Change ${form.name}` : 'Add a territory'}</h2></div>
            <div className="fs-form">
              <label><span>Code</span><input value={form.code} disabled={!!form.id} maxLength={40} onChange={(e) => setForm({ ...form, code: e.target.value })} aria-label="Territory code" /></label>
              <label><span>Name</span><input value={form.name} maxLength={150} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Territory name" /></label>
              <label><span>Visits a day per rep</span><input type="number" min="0" max="500" value={form.daily_visit_target} onChange={(e) => setForm({ ...form, daily_visit_target: e.target.value })} aria-label="Territory daily visit target" /></label>
            </div>
            <fieldset className="fs-pick">
              <legend>Routes in this territory</legend>
              {routes.map((r) => (
                <label key={r.id}><input type="checkbox" checked={form.route_ids.includes(r.id)} onChange={() => setForm({ ...form, route_ids: toggle(form.route_ids, r.id) })} aria-label={`Territory route ${r.name}`} /> {r.code} · {r.name}</label>
              ))}
              {routes.length === 0 ? <p className="fs-muted">Add routes first.</p> : null}
            </fieldset>
            <fieldset className="fs-pick">
              <legend>Reps who work it</legend>
              {people.map((p) => (
                <label key={p.id}><input type="checkbox" checked={form.rep_user_ids.includes(p.id)} onChange={() => setForm({ ...form, rep_user_ids: toggle(form.rep_user_ids, p.id) })} aria-label={`Territory rep ${p.name}`} /> {p.name}</label>
              ))}
            </fieldset>
            <p className="fs-muted">A route sits in one territory. Putting it here takes it out of any other.</p>
            <div className="fs-form">
              <button type="button" className="fs-primary" disabled={busy || !form.code.trim() || !form.name.trim()} onClick={saveTerritory}>Save territory</button>
              {form.id ? <button type="button" onClick={() => setForm(blank)}>Cancel</button> : null}
            </div>
          </section>

          <section className="fs-box fs-scroll" aria-label="Territories">
            <div className="fs-cardhead"><h2>Territories</h2></div>
            <div className="fs-form">
              <label><span>Month</span><input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Territory report month" /></label>
            </div>
            <table>
              <thead><tr><th>Code</th><th>Name</th><th>Reps</th><th>Outlets</th><th>Reached this month</th><th>Visits</th><th>Delivered sales</th><th /></tr></thead>
              <tbody>
                {territories.map((t) => {
                  const r = report.find((x) => x.territory_id === t.id) || {};
                  return (
                    <tr key={t.id}>
                      <td>{t.code}</td><td>{t.name}</td><td>{t.reps.map((x: Row) => x.name).join(', ') || <span className="fs-muted">None</span>}</td>
                      <td className="fs-num">{r.outlets ?? 0}</td><td className="fs-num">{r.outlets_visited ?? 0} ({r.coverage_pct ?? 0}%)</td>
                      <td className="fs-num">{r.visits ?? 0}</td><td className="fs-num">{formatMoney(Number(r.sales || 0))}</td>
                      <td>
                        <button
                          type="button" aria-label={`Change territory ${t.name}`}
                          onClick={() => setForm({ id: t.id, code: t.code, name: t.name, notes: t.notes || '', daily_visit_target: String(t.daily_visit_target), route_ids: t.routes.map((x: Row) => x.id), rep_user_ids: t.reps.map((x: Row) => x.id) })}
                        >
                          Change
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {territories.length === 0 ? <tr><td colSpan={8} className="fs-muted">No territories yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}
