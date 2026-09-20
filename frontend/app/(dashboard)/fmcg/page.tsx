'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Scheme = {
  id: string;
  code: string;
  name: string;
  scheme_type: string;
  value: number;
  buy_qty: number;
  get_qty: number;
  starts_on?: string | null;
  ends_on?: string | null;
  is_active: boolean;
};

type Route = {
  id: string;
  code: string;
  name: string;
  driver_name?: string | null;
  vehicle?: string | null;
  stop_count?: number | null;
  is_active: boolean;
};

type Stop = {
  id: string;
  route_id: string;
  customer_id: string;
  customer_name?: string | null;
  sequence: number;
  visit_day?: string | null;
  delivery_status?: string;
  is_active: boolean;
};

type Customer = {
  id: string;
  name: string;
  status?: string;
};

type Summary = {
  schemes_active: number;
  routes_active: number;
  route_stops: number;
  customers_active: number;
  batches_expiring_30d: number;
  deliveries_pending?: number;
  deliveries_completed?: number;
  deliveries_failed?: number;
};

type ExpiringBatch = {
  id?: string;
  batch_number?: string;
  product_name?: string;
  expiry_date?: string;
  quantity?: number;
};

type RoutePerf = {
  route_id: string;
  code: string;
  name: string;
  stops_total: number;
  delivered: number;
  failed: number;
  pending: number;
  delivery_rate: number;
};

const SCHEME_TYPES = ['percent', 'fixed', 'bxgy'];
const VISIT_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

export default function FmcgPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedRouteId, setSelectedRouteId] = useState('');
  const [stops, setStops] = useState<Stop[]>([]);
  const [expiring, setExpiring] = useState<ExpiringBatch[]>([]);
  const [perf, setPerf] = useState<RoutePerf[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [schemeForm, setSchemeForm] = useState({
    code: '',
    name: '',
    scheme_type: 'percent',
    value: '0',
    buy_qty: '0',
    get_qty: '0',
    starts_on: '',
    ends_on: '',
  });
  const [routeForm, setRouteForm] = useState({
    code: '',
    name: '',
    driver_name: '',
    vehicle: '',
  });
  const [stopForm, setStopForm] = useState({
    customer_id: '',
    sequence: '1',
    visit_day: '',
  });

  async function refresh(routeId?: string) {
    const activeRoute = routeId ?? selectedRouteId;
    const [s, sch, rt, cust, exp, pf] = await Promise.all([
      api('/fmcg/summary'),
      api('/fmcg/schemes'),
      api('/fmcg/routes?is_active=true'),
      api('/customers'),
      api('/fmcg/expiring?days=30'),
      api('/fmcg/routes/performance'),
    ]);
    setSummary(s.data || null);
    setSchemes(sch.data || []);
    setRoutes(rt.data || []);
    const custList = Array.isArray(cust.data) ? cust.data : [];
    setCustomers(custList.filter((c: Customer) => (c.status || 'active') === 'active'));
    setExpiring(exp.data?.batches || []);
    setPerf(pf.data || []);
    if (activeRoute) {
      const st = await api(`/fmcg/routes/${activeRoute}/stops`);
      setStops(st.data || []);
    } else {
      setStops([]);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load FMCG'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createScheme(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/fmcg/schemes', {
        method: 'POST',
        body: JSON.stringify({
          code: schemeForm.code.trim(),
          name: schemeForm.name.trim(),
          scheme_type: schemeForm.scheme_type,
          value: Number(schemeForm.value) || 0,
          buy_qty: Number(schemeForm.buy_qty) || 0,
          get_qty: Number(schemeForm.get_qty) || 0,
          starts_on: schemeForm.starts_on.trim() || null,
          ends_on: schemeForm.ends_on.trim() || null,
        }),
      });
      setSchemeForm({
        code: '',
        name: '',
        scheme_type: 'percent',
        value: '0',
        buy_qty: '0',
        get_qty: '0',
        starts_on: '',
        ends_on: '',
      });
      setMessage('Trade scheme created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create scheme');
    } finally {
      setBusy(false);
    }
  }

  async function toggleScheme(scheme: Scheme) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/fmcg/schemes/${scheme.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !scheme.is_active }),
      });
      setMessage(scheme.is_active ? 'Scheme deactivated' : 'Scheme activated');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not update scheme');
    } finally {
      setBusy(false);
    }
  }

  async function createRoute(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const res = await api('/fmcg/routes', {
        method: 'POST',
        body: JSON.stringify({
          code: routeForm.code.trim(),
          name: routeForm.name.trim(),
          driver_name: routeForm.driver_name.trim() || null,
          vehicle: routeForm.vehicle.trim() || null,
        }),
      });
      setRouteForm({ code: '', name: '', driver_name: '', vehicle: '' });
      setMessage('Route created');
      const newId = res.data?.id || '';
      if (newId) setSelectedRouteId(newId);
      await refresh(newId || undefined);
    } catch (err: any) {
      setError(err.message || 'Could not create route');
    } finally {
      setBusy(false);
    }
  }

  async function loadStops(routeId: string) {
    setSelectedRouteId(routeId);
    setError('');
    try {
      if (!routeId) {
        setStops([]);
        return;
      }
      const st = await api(`/fmcg/routes/${routeId}/stops`);
      setStops(st.data || []);
    } catch (err: any) {
      setError(err.message || 'Could not load stops');
    }
  }

  async function addStop(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedRouteId) {
      setError('Select a route first');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/fmcg/routes/${selectedRouteId}/stops`, {
        method: 'POST',
        body: JSON.stringify({
          customer_id: stopForm.customer_id.trim(),
          sequence: Number(stopForm.sequence) || 1,
          visit_day: stopForm.visit_day.trim() || null,
        }),
      });
      setStopForm({ customer_id: '', sequence: '1', visit_day: '' });
      setMessage('Stop added to route');
      await refresh(selectedRouteId);
    } catch (err: any) {
      setError(err.message || 'Could not add stop');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>FMCG</h1>
      <p className="muted">
        Manage trade schemes, distribution routes, and near-expiry awareness for fast-moving goods.
      </p>
      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      {summary && (
        <div className="grid" style={{ marginBottom: 16 }}>
          <div className="card">
            <div className="muted">Active schemes</div>
            <div className="kpi">{summary.schemes_active}</div>
            <div className="muted">{summary.customers_active} customers</div>
          </div>
          <div className="card">
            <div className="muted">Routes</div>
            <div className="kpi">{summary.routes_active}</div>
            <div className="muted">{summary.route_stops} active stops</div>
          </div>
          <div className="card">
            <div className="muted">Near expiry (30d)</div>
            <div className="kpi">{summary.batches_expiring_30d}</div>
            <div className="muted">
              Deliveries {summary.deliveries_completed ?? 0} done · {summary.deliveries_pending ?? 0} pending
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Add trade scheme</h2>
        <form
          onSubmit={createScheme}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
        >
          <label>
            <span>Code</span>
            <input
              value={schemeForm.code}
              onChange={(e) => setSchemeForm((f) => ({ ...f, code: e.target.value }))}
              aria-label="FMCG scheme code"
              required
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={schemeForm.name}
              onChange={(e) => setSchemeForm((f) => ({ ...f, name: e.target.value }))}
              aria-label="FMCG scheme name"
              required
            />
          </label>
          <label>
            <span>Type</span>
            <select
              value={schemeForm.scheme_type}
              onChange={(e) => setSchemeForm((f) => ({ ...f, scheme_type: e.target.value }))}
              aria-label="FMCG scheme type"
            >
              {SCHEME_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Value</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={schemeForm.value}
              onChange={(e) => setSchemeForm((f) => ({ ...f, value: e.target.value }))}
              aria-label="FMCG scheme value"
            />
          </label>
          <label>
            <span>Buy qty</span>
            <input
              type="number"
              min={0}
              value={schemeForm.buy_qty}
              onChange={(e) => setSchemeForm((f) => ({ ...f, buy_qty: e.target.value }))}
              aria-label="FMCG scheme buy qty"
            />
          </label>
          <label>
            <span>Get qty</span>
            <input
              type="number"
              min={0}
              value={schemeForm.get_qty}
              onChange={(e) => setSchemeForm((f) => ({ ...f, get_qty: e.target.value }))}
              aria-label="FMCG scheme get qty"
            />
          </label>
          <label>
            <span>Starts</span>
            <input
              type="date"
              value={schemeForm.starts_on}
              onChange={(e) => setSchemeForm((f) => ({ ...f, starts_on: e.target.value }))}
              aria-label="FMCG scheme starts on"
            />
          </label>
          <label>
            <span>Ends</span>
            <input
              type="date"
              value={schemeForm.ends_on}
              onChange={(e) => setSchemeForm((f) => ({ ...f, ends_on: e.target.value }))}
              aria-label="FMCG scheme ends on"
            />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create FMCG trade scheme">
              {busy ? 'Saving…' : 'Create scheme'}
            </button>
          </div>
        </form>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Trade schemes</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>Value</th>
              <th>BXGY</th>
              <th>Window</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {schemes.map((s) => (
              <tr key={s.id}>
                <td>
                  <code>{s.code}</code>
                </td>
                <td>{s.name}</td>
                <td>{s.scheme_type}</td>
                <td>{Number(s.value || 0).toFixed(2)}</td>
                <td>
                  {s.scheme_type === 'bxgy'
                    ? `${s.buy_qty} + ${s.get_qty}`
                    : '—'}
                </td>
                <td>
                  {s.starts_on || '—'} → {s.ends_on || '—'}
                </td>
                <td>{s.is_active ? 'active' : 'inactive'}</td>
                <td>
                  <button
                    type="button"
                    className={s.is_active ? 'btn-danger' : 'btn-ok'}
                    disabled={busy}
                    onClick={() => toggleScheme(s)}
                    aria-label={`${s.is_active ? 'Deactivate' : 'Activate'} scheme ${s.code}`}
                  >
                    {s.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
            {!schemes.length && (
              <tr>
                <td colSpan={8} className="muted">
                  No trade schemes yet — create one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Add distribution route</h2>
        <form
          onSubmit={createRoute}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label>
            <span>Code</span>
            <input
              value={routeForm.code}
              onChange={(e) => setRouteForm((f) => ({ ...f, code: e.target.value }))}
              aria-label="FMCG route code"
              required
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={routeForm.name}
              onChange={(e) => setRouteForm((f) => ({ ...f, name: e.target.value }))}
              aria-label="FMCG route name"
              required
            />
          </label>
          <label>
            <span>Driver</span>
            <input
              value={routeForm.driver_name}
              onChange={(e) => setRouteForm((f) => ({ ...f, driver_name: e.target.value }))}
              aria-label="FMCG route driver"
            />
          </label>
          <label>
            <span>Vehicle</span>
            <input
              value={routeForm.vehicle}
              onChange={(e) => setRouteForm((f) => ({ ...f, vehicle: e.target.value }))}
              aria-label="FMCG route vehicle"
            />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create FMCG route">
              {busy ? 'Saving…' : 'Create route'}
            </button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Driver</th>
              <th>Vehicle</th>
              <th>Stops</th>
              <th>Select</th>
            </tr>
          </thead>
          <tbody>
            {routes.map((r) => (
              <tr key={r.id}>
                <td>
                  <code>{r.code}</code>
                </td>
                <td>{r.name}</td>
                <td>{r.driver_name || '—'}</td>
                <td>{r.vehicle || '—'}</td>
                <td>{r.stop_count ?? 0}</td>
                <td>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => loadStops(r.id)}
                    aria-label={`Select FMCG route ${r.code}`}
                  >
                    {selectedRouteId === r.id ? 'Selected' : 'Manage stops'}
                  </button>
                </td>
              </tr>
            ))}
            {!routes.length && (
              <tr>
                <td colSpan={6} className="muted">
                  No routes yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Route stops</h2>
        {!selectedRouteId && (
          <p className="muted">Select a route above to add customer stops.</p>
        )}
        {selectedRouteId && (
          <>
            <form
              onSubmit={addStop}
              style={{
                display: 'grid',
                gap: 10,
                gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))',
                marginBottom: 12,
              }}
            >
              <label>
                <span>Customer</span>
                <select
                  value={stopForm.customer_id}
                  onChange={(e) => setStopForm((f) => ({ ...f, customer_id: e.target.value }))}
                  aria-label="FMCG stop customer"
                  required
                >
                  <option value="">Select customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Sequence</span>
                <input
                  type="number"
                  min={1}
                  value={stopForm.sequence}
                  onChange={(e) => setStopForm((f) => ({ ...f, sequence: e.target.value }))}
                  aria-label="FMCG stop sequence"
                />
              </label>
              <label>
                <span>Visit day</span>
                <select
                  value={stopForm.visit_day}
                  onChange={(e) => setStopForm((f) => ({ ...f, visit_day: e.target.value }))}
                  aria-label="FMCG stop visit day"
                >
                  <option value="">Any</option>
                  {VISIT_DAYS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
              <div style={{ alignSelf: 'end' }}>
                <button type="submit" disabled={busy} aria-label="Add FMCG route stop">
                  {busy ? 'Saving…' : 'Add stop'}
                </button>
              </div>
            </form>
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Customer</th>
                  <th>Visit day</th>
                  <th>Delivery</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stops.map((st) => (
                  <tr key={st.id}>
                    <td>{st.sequence}</td>
                    <td>{st.customer_name || st.customer_id}</td>
                    <td>{st.visit_day || 'any'}</td>
                    <td>{st.delivery_status || 'pending'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="btn-ok"
                          disabled={busy || st.delivery_status === 'delivered'}
                          onClick={async () => {
                            setBusy(true);
                            setError('');
                            try {
                              await api(`/fmcg/stops/${st.id}/delivery`, {
                                method: 'PATCH',
                                body: JSON.stringify({ delivery_status: 'delivered' }),
                              });
                              setMessage('Stop marked delivered');
                              await refresh(selectedRouteId);
                            } catch (err: any) {
                              setError(err.message || 'Update failed');
                            } finally {
                              setBusy(false);
                            }
                          }}
                          aria-label={`Mark delivered ${st.customer_name || st.id}`}
                        >
                          Delivered
                        </button>
                        <button
                          type="button"
                          className="btn-danger"
                          disabled={busy || st.delivery_status === 'failed'}
                          onClick={async () => {
                            setBusy(true);
                            setError('');
                            try {
                              await api(`/fmcg/stops/${st.id}/delivery`, {
                                method: 'PATCH',
                                body: JSON.stringify({
                                  delivery_status: 'failed',
                                  fail_reason: 'Customer closed / refused',
                                }),
                              });
                              setMessage('Stop marked failed');
                              await refresh(selectedRouteId);
                            } catch (err: any) {
                              setError(err.message || 'Update failed');
                            } finally {
                              setBusy(false);
                            }
                          }}
                          aria-label={`Mark failed ${st.customer_name || st.id}`}
                        >
                          Failed
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!stops.length && (
                  <tr>
                    <td colSpan={5} className="muted">
                      No stops on this route yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Route performance</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Stops</th>
              <th>Delivered</th>
              <th>Failed</th>
              <th>Pending</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {perf.map((p) => (
              <tr key={p.route_id}>
                <td>
                  <code>{p.code}</code> {p.name}
                </td>
                <td>{p.stops_total}</td>
                <td>{p.delivered}</td>
                <td>{p.failed}</td>
                <td>{p.pending}</td>
                <td>{Number(p.delivery_rate || 0).toFixed(1)}%</td>
              </tr>
            ))}
            {!perf.length && (
              <tr>
                <td colSpan={6} className="muted">
                  No route performance data yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Near-expiry batches (30 days)</h2>
        <p className="muted">
          Uses core inventory FEFO/expiry data. Strict FEFO is configured under Multi-Store inventory settings.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Batch</th>
              <th>Product</th>
              <th>Expiry</th>
              <th>Qty</th>
            </tr>
          </thead>
          <tbody>
            {expiring.map((b, idx) => (
              <tr key={b.id || idx}>
                <td>{b.batch_number || '—'}</td>
                <td>{b.product_name || '—'}</td>
                <td>{b.expiry_date || '—'}</td>
                <td>{b.quantity ?? '—'}</td>
              </tr>
            ))}
            {!expiring.length && (
              <tr>
                <td colSpan={4} className="muted">
                  No batches expiring within 30 days.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
