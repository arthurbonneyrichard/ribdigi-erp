'use client';

/**
 * FMCG fleet: the vehicle register with document expiry and service due, fuel and repair records,
 * putting a vehicle on a dispatch, and running costs per vehicle. The server refuses a vehicle with
 * an expired document or one already out; this screen asks and shows.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const FLEET_TABS = ['fleet'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin', 'fmcg_fleet'];
const KINDS = ['van', 'truck', 'pickup', 'motorbike', 'other'];
const LOG_KINDS = [
  { id: 'fuel', label: 'Fuel' }, { id: 'service', label: 'Service' }, { id: 'repair', label: 'Repair' },
  { id: 'tyre', label: 'Tyres' }, { id: 'accident', label: 'Accident' }, { id: 'other', label: 'Other' },
];
const METHODS = [
  { id: 'cash', label: 'Cash' }, { id: 'bank_transfer', label: 'Bank transfer' }, { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'card', label: 'Card' }, { id: 'cheque', label: 'Cheque' },
];
const DOC_WORDS: Record<string, string> = { ok: 'OK', expiring: 'Expiring soon', expired: 'Expired', not_recorded: 'Not recorded' };

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function FmcgFleet({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [vehicles, setVehicles] = useState<Row[]>([]);
  const [attention, setAttention] = useState<Row[]>([]);
  const [drivers, setDrivers] = useState<Row[]>([]);
  const [dispatches, setDispatches] = useState<Row[]>([]);
  const blank = { plate: '', name: '', kind: 'van', make_model: '', driver_user_id: '', odometer_km: '', insurance_expiry: '', roadworthy_expiry: '', licence_expiry: '', service_every_km: '' };
  const [form, setForm] = useState(blank);
  const [openId, setOpenId] = useState('');
  const [logs, setLogs] = useState<Row[]>([]);
  const [log, setLog] = useState({ kind: 'fuel', odometer_km: '', litres: '', amount: '', vendor: '', note: '', pay_method: 'cash' });
  const [assign, setAssign] = useState({ dispatch_id: '', vehicle_id: '' });
  const [period, setPeriod] = useState({ start: iso(new Date(Date.now() - 30 * 86400000)), end: iso(new Date()) });
  const [report, setReport] = useState<Row[]>([]);
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      const [v, a, d, u] = await Promise.all([
        api('/fmcg/fleet/vehicles'), api('/fmcg/fleet/attention'), api('/fmcg/dispatches'), api('/users').catch(() => null),
      ]);
      setVehicles(v?.data || []);
      setAttention(a?.data || []);
      setDispatches((d?.data || []).filter((x: Row) => x.status === 'open'));
      setDrivers((Array.isArray(u?.data) ? u.data : []).filter((x: Row) => x.role === 'fmcg_driver' || x.role === 'fmcg_rep'));
      setReport((await api(`/fmcg/fleet/report?start=${period.start}&end=${period.end}`))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, [period.start, period.end]);

  useEffect(() => {
    if (manager) load();
  }, [manager, load]);

  async function showLogs(id: string) {
    setOpenId(id);
    try {
      setLogs((await api(`/fmcg/fleet/vehicles/${id}/logs`))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      setNotice(done);
      await load();
      if (openId) await showLogs(openId);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const send = (path: string, body: unknown, method = 'POST') => api(path, { method, body: JSON.stringify(body) });
  const n = (v: string) => (v.trim() === '' ? undefined : Number(v));

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">The fleet is managed by a manager.</div>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {attention.length ? (
        <section className="fs-box" aria-label="Needs attention">
          <div className="fs-cardhead"><h2>Needs attention</h2></div>
          {attention.map((a, i) => <p key={i}><span className="fs-flag">{a.level === 'service' ? 'Service' : a.level === 'expired' ? 'Expired' : 'Soon'}</span> {a.text}</p>)}
        </section>
      ) : null}

      <section className="fs-box" aria-label="Add a vehicle">
        <div className="fs-cardhead"><h2>Add a vehicle</h2></div>
        <div className="fs-form">
          <label><span>Number plate</span><input value={form.plate} onChange={(e) => setForm({ ...form, plate: e.target.value })} aria-label="Vehicle plate" /></label>
          <label><span>Name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Vehicle name" /></label>
          <label><span>Type</span>
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label="Vehicle type">{KINDS.map((k) => <option key={k} value={k}>{k}</option>)}</select>
          </label>
          <label><span>Make and model</span><input value={form.make_model} onChange={(e) => setForm({ ...form, make_model: e.target.value })} aria-label="Vehicle make and model" /></label>
          <label><span>Driver</span>
            <select value={form.driver_user_id} onChange={(e) => setForm({ ...form, driver_user_id: e.target.value })} aria-label="Vehicle driver">
              <option value="">No driver</option>{drivers.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
            </select>
          </label>
          <label><span>Odometer (km)</span><input type="number" min="0" value={form.odometer_km} onChange={(e) => setForm({ ...form, odometer_km: e.target.value })} aria-label="Vehicle odometer" /></label>
          <label><span>Service every (km)</span><input type="number" min="0" value={form.service_every_km} onChange={(e) => setForm({ ...form, service_every_km: e.target.value })} aria-label="Service interval" /></label>
          <label><span>Insurance expires</span><input type="date" value={form.insurance_expiry} onChange={(e) => setForm({ ...form, insurance_expiry: e.target.value })} aria-label="Insurance expiry" /></label>
          <label><span>Roadworthy expires</span><input type="date" value={form.roadworthy_expiry} onChange={(e) => setForm({ ...form, roadworthy_expiry: e.target.value })} aria-label="Roadworthy expiry" /></label>
          <label><span>Licence expires</span><input type="date" value={form.licence_expiry} onChange={(e) => setForm({ ...form, licence_expiry: e.target.value })} aria-label="Licence expiry" /></label>
          <button type="button" className="fs-primary" disabled={busy || form.plate.trim().length < 2 || form.name.trim().length < 2}
            onClick={() => run(async () => {
              await send('/fmcg/fleet/vehicles', {
                plate: form.plate.trim(), name: form.name.trim(), kind: form.kind,
                ...(form.make_model.trim().length >= 2 ? { make_model: form.make_model.trim() } : {}),
                ...(form.driver_user_id ? { driver_user_id: form.driver_user_id } : {}),
                odometer_km: n(form.odometer_km) ?? 0,
                ...(form.service_every_km ? { service_every_km: Number(form.service_every_km) } : {}),
                ...(form.insurance_expiry ? { insurance_expiry: form.insurance_expiry } : {}),
                ...(form.roadworthy_expiry ? { roadworthy_expiry: form.roadworthy_expiry } : {}),
                ...(form.licence_expiry ? { licence_expiry: form.licence_expiry } : {}),
              });
              setForm(blank);
            }, 'Vehicle added.')}>Add vehicle</button>
        </div>
      </section>

      <section className="fs-box fs-scroll" aria-label="Vehicles">
        <table>
          <thead><tr><th>Plate</th><th>Name</th><th>Driver</th><th>Status</th><th>Km</th><th>Insurance</th><th>Roadworthy</th><th>Licence</th><th>Service</th><th /></tr></thead>
          <tbody>
            {vehicles.map((v) => (
              <tr key={v.id}>
                <td>{v.plate}</td><td>{v.name}</td><td>{v.driver || '-'}</td>
                <td>{v.on_dispatch ? `Out (${v.on_dispatch})` : v.status}</td><td className="fs-num">{v.odometer_km}</td>
                {['insurance', 'roadworthy', 'licence'].map((d) => {
                  const doc = v.compliance.documents[d];
                  return <td key={d}>{doc.state === 'ok' ? doc.expiry : <span className="fs-flag">{DOC_WORDS[doc.state]}{doc.expiry ? ` ${doc.expiry}` : ''}</span>}</td>;
                })}
                <td>{v.service.km_to_service == null ? '-' : v.service.due ? <span className="fs-flag">Due</span> : `${v.service.km_to_service} km`}</td>
                <td>
                  <button type="button" aria-label={`Records for ${v.plate}`} onClick={() => showLogs(v.id)}>Records</button>{' '}
                  {v.status === 'active' ? <button type="button" disabled={busy} aria-label={`Send ${v.plate} to workshop`} onClick={() => run(() => send(`/fmcg/fleet/vehicles/${v.id}`, { status: 'workshop' }, 'PATCH'), 'In the workshop.')}>Workshop</button> : <button type="button" disabled={busy || v.status === 'retired'} aria-label={`Make ${v.plate} active`} onClick={() => run(() => send(`/fmcg/fleet/vehicles/${v.id}`, { status: 'active' }, 'PATCH'), 'Active again.')}>Make active</button>}
                </td>
              </tr>
            ))}
            {vehicles.length === 0 ? <tr><td colSpan={10} className="fs-muted">No vehicles yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      <section className="fs-box" aria-label="Put a vehicle on a dispatch">
        <div className="fs-cardhead"><h2>Put a vehicle on a dispatch</h2></div>
        <div className="fs-form">
          <label><span>Dispatch</span>
            <select value={assign.dispatch_id} onChange={(e) => setAssign({ ...assign, dispatch_id: e.target.value })} aria-label="Assign dispatch">
              <option value="">Pick an open dispatch</option>{dispatches.map((d) => <option key={d.id} value={d.id}>{d.dispatch_number} · {d.vehicle || 'no vehicle'}</option>)}
            </select>
          </label>
          <label><span>Vehicle</span>
            <select value={assign.vehicle_id} onChange={(e) => setAssign({ ...assign, vehicle_id: e.target.value })} aria-label="Assign vehicle">
              <option value="">Pick a vehicle</option>{vehicles.filter((v) => v.status === 'active').map((v) => <option key={v.id} value={v.id}>{v.plate}</option>)}
            </select>
          </label>
          <button type="button" className="fs-primary" disabled={busy || !assign.dispatch_id || !assign.vehicle_id}
            onClick={() => run(() => send(`/fmcg/dispatches/${assign.dispatch_id}/vehicle`, { vehicle_id: assign.vehicle_id }), 'Vehicle assigned.')}>Assign</button>
        </div>
        <p className="fs-muted">A vehicle with an expired document, in the workshop, or already on another open dispatch is refused.</p>
      </section>

      {openId ? (
        <section className="fs-box" aria-label="Vehicle records">
          <div className="fs-cardhead"><h2>Records: {vehicles.find((v) => v.id === openId)?.plate}</h2></div>
          <div className="fs-form">
            <label><span>Kind</span>
              <select value={log.kind} onChange={(e) => setLog({ ...log, kind: e.target.value })} aria-label="Record kind">{LOG_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
            </label>
            <label><span>Odometer (km)</span><input type="number" min="0" value={log.odometer_km} onChange={(e) => setLog({ ...log, odometer_km: e.target.value })} aria-label="Record odometer" /></label>
            {log.kind === 'fuel' ? <label><span>Litres</span><input type="number" min="0" value={log.litres} onChange={(e) => setLog({ ...log, litres: e.target.value })} aria-label="Record litres" /></label> : null}
            <label><span>Amount paid</span><input type="number" min="0" value={log.amount} onChange={(e) => setLog({ ...log, amount: e.target.value })} aria-label="Record amount" /></label>
            <label><span>How paid</span>
              <select value={log.pay_method} onChange={(e) => setLog({ ...log, pay_method: e.target.value })} aria-label="Record payment method">{METHODS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
            </label>
            <label><span>Vendor</span><input value={log.vendor} onChange={(e) => setLog({ ...log, vendor: e.target.value })} aria-label="Record vendor" /></label>
            <label><span>Note</span><input value={log.note} onChange={(e) => setLog({ ...log, note: e.target.value })} aria-label="Record note" /></label>
            <button type="button" className="fs-primary" disabled={busy || (log.kind === 'fuel' && !(Number(log.litres) > 0 && Number(log.amount) > 0))}
              onClick={() => run(async () => {
                await send(`/fmcg/fleet/vehicles/${openId}/logs`, {
                  kind: log.kind, ...(n(log.odometer_km) !== undefined ? { odometer_km: n(log.odometer_km) } : {}),
                  ...(log.kind === 'fuel' ? { litres: Number(log.litres) } : {}), amount: n(log.amount) ?? 0,
                  ...(Number(log.amount) > 0 ? { pay_method: log.pay_method } : {}),
                  ...(log.vendor.trim().length >= 2 ? { vendor: log.vendor.trim() } : {}), ...(log.note.trim().length >= 3 ? { note: log.note.trim() } : {}),
                });
                setLog({ ...log, odometer_km: '', litres: '', amount: '', vendor: '', note: '' });
              }, 'Recorded.')}>Save record</button>
          </div>
          <table>
            <thead><tr><th>Date</th><th>Kind</th><th>Km</th><th>Litres</th><th>Amount</th><th>Vendor</th><th>Note</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}><td>{l.date}</td><td>{l.kind}</td><td className="fs-num">{l.odometer_km ?? '-'}</td><td className="fs-num">{l.litres ?? '-'}</td><td className="fs-num">{formatMoney(l.amount)}</td><td>{l.vendor || '-'}</td><td>{l.note || '-'}</td></tr>
              ))}
              {logs.length === 0 ? <tr><td colSpan={7} className="fs-muted">No records yet.</td></tr> : null}
            </tbody>
          </table>
          <p className="fs-muted">The odometer can only go up. Costs you pay here are booked as vehicle expenses; fuel paid from a van&apos;s takings is already booked there and only appears here.</p>
        </section>
      ) : null}

      <section className="fs-box fs-scroll" aria-label="Running costs">
        <div className="fs-cardhead"><h2>Running costs</h2></div>
        <div className="fs-form">
          <label><span>From</span><input type="date" value={period.start} onChange={(e) => setPeriod({ ...period, start: e.target.value })} aria-label="Costs from" /></label>
          <label><span>To</span><input type="date" value={period.end} onChange={(e) => setPeriod({ ...period, end: e.target.value })} aria-label="Costs to" /></label>
        </div>
        <table>
          <thead><tr><th>Vehicle</th><th>Trips</th><th>Sales</th><th>Fuel</th><th>Service</th><th>Repairs</th><th>Total</th><th>Km</th><th>Cost per km</th><th>Km per litre</th><th>Cost % of sales</th></tr></thead>
          <tbody>
            {report.map((r) => (
              <tr key={r.vehicle_id}>
                <td>{r.plate}</td><td className="fs-num">{r.trips}</td><td className="fs-num">{formatMoney(r.sales_delivered)}</td>
                <td className="fs-num">{formatMoney(r.fuel_cost)}</td><td className="fs-num">{formatMoney(r.service_cost)}</td><td className="fs-num">{formatMoney(r.repair_cost)}</td>
                <td className="fs-num"><strong>{formatMoney(r.total_cost)}</strong></td><td className="fs-num">{r.km_driven ?? '-'}</td>
                <td className="fs-num">{r.cost_per_km ?? '-'}</td><td className="fs-num">{r.km_per_litre ?? '-'}</td><td className="fs-num">{r.cost_pct_of_sales != null ? `${r.cost_pct_of_sales}%` : '-'}</td>
              </tr>
            ))}
            {report.length === 0 ? <tr><td colSpan={11} className="fs-muted">No vehicles yet.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </div>
  );
}
