'use client';

/**
 * FMCG selling on its own tables (fmcg_*): outlets, orders, loading, delivery, collections,
 * returns and reports. Schemes, routes and pack conversion stay on the main FMCG page.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import DeskDashboard from '../../../components/DeskDashboard';
import DeskIcon from '../../../components/DeskIcon';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const FMCG_SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  outlets: { title: 'Outlets', sub: 'The shops you sell to, their credit and what they owe.', icon: 'map' },
  orders: { title: 'Orders', sub: 'Book orders, load the truck and deliver.', icon: 'receipt' },
  collections: { title: 'Collections', sub: 'Money in from outlets, and goods coming back.', icon: 'cash' },
  reports: { title: 'Reports', sub: 'Sales, returns, discounts and profit by outlet, product and route.', icon: 'chart' },
  schemes: { title: 'Trade schemes', sub: 'Deals for outlets: buy so many, get a discount or free goods.', icon: 'tag' },
  routes: { title: 'Routes', sub: 'Which outlets each van visits, and on which day.', icon: 'map' },
  deliveries: { title: 'Deliveries', sub: 'Trucks out, what they carried and the cash they brought back.', icon: 'truck' },
  visits: { title: 'Outlet visits', sub: 'Check in at outlets with your phone, and see who was where.', icon: 'map' },
  territories: { title: 'Territories', sub: 'Groups of routes, the reps who work them, and how much of each was reached.', icon: 'map' },
  packs: { title: 'Pack convert', sub: 'Break cartons into packs, or pack singles into cartons.', icon: 'box' },
};

/** The screen header shared by every FMCG screen. Sits inside .fmcg-sell. */
export function FmcgHead({ tab }: { tab: string }) {
  const screen = FMCG_SCREENS[tab];
  if (!screen) return null;
  return (
    <header className="fs-head">
      <span className="fs-head-ico" aria-hidden="true"><DeskIcon name={screen.icon} size={26} /></span>
      <div className="fs-head-text">
        <h1>{screen.title}</h1>
        <p>{screen.sub}</p>
      </div>
    </header>
  );
}

const ICON_WORDS: [string, string][] = [
  ['outlet', 'map'], ['order', 'receipt'], ['deliver', 'truck'], ['truck', 'truck'], ['payment', 'cash'],
  ['return', 'arrow'], ['add', 'plus'], ['book', 'plus'], ['product', 'box'], ['route', 'map'],
];
function Head({ title, meta }: { title: string; meta?: React.ReactNode }) {
  const lower = title.toLowerCase();
  const pick = ICON_WORDS.find(([word]) => lower.includes(word))?.[1] || 'chart';
  return (
    <div className="fs-cardhead">
      <span className="fs-ico" aria-hidden="true"><DeskIcon name={pick} size={18} /></span>
      <h2>{title}</h2>
      {meta ? <span className="fs-meta">{meta}</span> : null}
    </div>
  );
}

export const SELLING_TABS = ['outlets', 'orders', 'collections', 'reports'];

const METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'card', label: 'Card' },
  { id: 'cheque', label: 'Cheque' },
];
const RETURN_REASONS = [
  { id: 'damaged', label: 'Damaged' },
  { id: 'expired', label: 'Past its date' },
  { id: 'unsold', label: 'Unsold stock' },
  { id: 'wrong_item', label: 'Wrong item' },
  { id: 'other', label: 'Other' },
];

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (offset = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export function FmcgToday() {
  const [data, setData] = useState<Row | null>(null);
  const [role, setRole] = useState('');
  useEffect(() => {
    api('/fmcg/today').then((r) => setData(r?.data ?? null)).catch(() => setData(null));
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);
  if (!data) return null;
  const rep = role === 'fmcg_rep';
  const driver = role === 'fmcg_driver';
  return (
    <DeskDashboard
      desk="Distribution dashboard"
      actions={[
        ...(driver ? [] : [{ label: 'Book an order', href: '/fmcg?tab=orders', primary: true, icon: 'plus', hint: 'For an outlet' }]),
        ...(rep ? [] : [{ label: 'Deliveries', href: '/fmcg?tab=orders', primary: driver, icon: 'truck', hint: 'Load and deliver' }]),
        { label: 'Record a payment', href: '/fmcg?tab=collections', icon: 'cash', hint: 'Money from outlets' },
        ...(rep || driver ? [] : [{ label: 'Add an outlet', href: '/fmcg?tab=outlets', icon: 'map', hint: 'Shops you supply' }]),
      ]}
      tiles={[
        ...('sales_today' in data
          ? [{ label: 'Delivered sales today', icon: 'cash', spark: (data.trend?.points || []).map((p: Row) => Number(p.value)), value: money(data.sales_today), before: { now: Number(data.sales_today), value: Number(data.sales_yesterday || 0), word: 'yesterday' } }]
          : []),
        { label: 'Collected today', icon: 'wallet', value: money(data.collected_today), href: '/fmcg?tab=collections' },
        { label: 'To load', icon: 'box', value: data.orders_to_load, sub: `${data.orders_on_trucks} on trucks now`, href: '/fmcg?tab=orders' },
        { label: 'Delivered today', icon: 'truck', value: data.delivered_today, href: '/fmcg?tab=orders' },
        ...('owed_total' in data
          ? [{ label: 'Outlets owe', icon: 'receipt', value: money(data.owed_total), sub: Number(data.owed_late) > 0 ? `${money(data.owed_late)} of it late` : 'Nothing late', warn: Number(data.owed_late) > 0, href: '/fmcg?tab=reports' }]
          : []),
      ]}
      trend={data.trend}
      attention={data.attention}
    />
  );
}

export default function FmcgSelling({ tab }: { tab: string }) {
  const [outlets, setOutlets] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [delivered, setDelivered] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [routes, setRoutes] = useState<Row[]>([]);
  const [dispatches, setDispatches] = useState<Row[]>([]);
  const [payments, setPayments] = useState<Row[]>([]);
  const [returns, setReturns] = useState<Row[]>([]);
  const [report, setReport] = useState<Row | null>(null);
  const [range, setRange] = useState({ start: iso(-6), end: iso() });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [outletForm, setOutletForm] = useState({ name: '', phone: '', address: '', credit_limit: '0', payment_terms_days: '30', route_id: '', salesperson_name: '' });
  const [order, setOrder] = useState({ customer_id: '', terms: 'credit', notes: '', override_reason: '' });
  const [basket, setBasket] = useState<{ product_id: string; quantity: string }[]>([{ product_id: '', quantity: '1' }]);
  const [needsOverride, setNeedsOverride] = useState(false);
  const [pay, setPay] = useState({ customer_id: '', amount: '', method: 'cash', dispatch_id: '' });
  const [dialog, setDialog] = useState<Row | null>(null);
  const [role, setRole] = useState('');
  const rep = role === 'fmcg_rep';
  const driver = role === 'fmcg_driver';

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    const get = async (path: string) => (await api(path))?.data;
    try {
      if (tab === 'outlets') {
        const [o, r] = await Promise.all([get('/fmcg/outlets'), get('/fmcg/routes')]);
        setOutlets(o || []);
        setRoutes(r || []);
      } else if (tab === 'orders') {
        const [o, all, p, c, d] = await Promise.all([
          get('/fmcg/orders'),
          get('/fmcg/orders?show=delivered'),
          get('/fmcg/products-for-sale'),
          get('/fmcg/outlets'),
          get('/fmcg/dispatches').catch(() => []),
        ]);
        setOrders(o || []);
        setDelivered(all || []);
        setProducts(p || []);
        setOutlets(c || []);
        setDispatches((d || []).filter((x: Row) => x.status === 'open'));
      } else if (tab === 'collections') {
        const [o, p, d, r] = await Promise.all([
          get('/fmcg/outlets'),
          get('/fmcg/collections'),
          get('/fmcg/dispatches').catch(() => []),
          get('/fmcg/returns'),
        ]);
        setOutlets(o || []);
        setPayments(p || []);
        setDispatches((d || []).filter((x: Row) => x.status === 'open'));
        setReturns(r || []);
      } else if (tab === 'reports') {
        setReport(await get(`/fmcg/reports?start_date=${range.start}&end_date=${range.end}`));
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, range.start, range.end]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(path: string, body: object, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api(path, { method: 'POST', body: JSON.stringify(body) });
      setNotice(done);
      await load();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function addOutlet() {
    const ok = await run(
      '/fmcg/outlets',
      {
        name: outletForm.name.trim(),
        phone: outletForm.phone.replace(/[\s-]/g, '') || null,
        address: outletForm.address.trim() || null,
        credit_limit: Number(outletForm.credit_limit || 0),
        payment_terms_days: Number(outletForm.payment_terms_days || 0),
        route_id: outletForm.route_id || null,
        salesperson_name: outletForm.salesperson_name.trim() || null,
      },
      'Outlet added',
    );
    if (ok) setOutletForm({ name: '', phone: '', address: '', credit_limit: '0', payment_terms_days: '30', route_id: '', salesperson_name: '' });
  }

  async function bookOrder() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api('/fmcg/orders', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: order.customer_id,
          terms: order.terms,
          lines: basket.filter((l) => l.product_id).map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity) })),
          notes: order.notes.trim() || null,
          override_reason: order.override_reason.trim() || null,
        }),
      });
      setNotice('Order booked');
      setOrder({ customer_id: '', terms: 'credit', notes: '', override_reason: '' });
      setBasket([{ product_id: '', quantity: '1' }]);
      setNeedsOverride(false);
      await load();
    } catch (err) {
      const text = problem(err);
      if (/credit limit/i.test(text)) setNeedsOverride(true);
      setError(text);
    } finally {
      setBusy(false);
    }
  }

  async function confirmDialog() {
    if (!dialog) return;
    const row = dialog.row;
    let ok: unknown = null;
    if (dialog.kind === 'load') ok = await run(`/fmcg/orders/${row.id}/load`, { dispatch_id: dialog.dispatch_id }, 'Order loaded');
    if (dialog.kind === 'deliver') {
      ok = await run(`/fmcg/orders/${row.id}/deliver`, { payment_method: row.terms === 'cash' ? dialog.method : null }, 'Delivered');
    }
    if (dialog.kind === 'failed') ok = await run(`/fmcg/orders/${row.id}/failed`, { reason: dialog.reason.trim() }, 'Sent back to be loaded again');
    if (dialog.kind === 'cancel') ok = await run(`/fmcg/orders/${row.id}/cancel`, { reason: dialog.reason.trim() }, 'Order cancelled');
    if (dialog.kind === 'return') {
      const lines = Object.entries(dialog.quantities as Record<string, string>)
        .filter(([, q]) => Number(q) > 0)
        .map(([line_id, q]) => ({ line_id, quantity: Number(q) }));
      ok = await run(`/fmcg/orders/${row.id}/returns`, { lines, reason: dialog.reason, resaleable: dialog.resaleable }, 'Return recorded');
    }
    if (dialog.kind === 'settle') {
      const res = (await run(`/fmcg/dispatches/${row.id}/settle`, { counted_cash: Number(dialog.counted || 0) }, 'Dispatch settled')) as Row | null;
      if (res) {
        const gap = Number(res.over_short);
        setNotice(gap === 0 ? 'Dispatch settled. The cash matches.' : `Dispatch settled. ${gap < 0 ? 'Short' : 'Over'} by ${money(Math.abs(gap))}.`);
      }
      ok = res;
    }
    if (ok) setDialog(null);
  }

  async function openSettle(row: Row) {
    const res = await api(`/fmcg/dispatches/${row.id}/cash`).catch(() => null);
    setDialog({ kind: 'settle', row, expected: res?.data?.expected_cash ?? 0, counted: '' });
  }

  const dialogReady = dialog
    ? dialog.kind === 'load'
      ? Boolean(dialog.dispatch_id)
      : dialog.kind === 'failed' || dialog.kind === 'cancel'
        ? dialog.reason.trim().length >= 3
        : dialog.kind === 'return'
          ? Object.values(dialog.quantities as Record<string, string>).some((q) => Number(q) > 0)
          : dialog.kind === 'settle'
            ? dialog.counted !== ''
            : true
    : false;
  const titles: Record<string, string> = { load: 'Load', deliver: 'Deliver', failed: 'Could not deliver', cancel: 'Cancel', return: 'Return from', settle: 'Settle' };
  const owing = outlets.filter((o) => Number(o.balance) > 0);

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {dialog ? (
        <div className="fs-veil">
          <div className="fs-dialog" role="dialog" aria-modal="true" aria-label={titles[dialog.kind]}>
            <h2>{titles[dialog.kind]} {dialog.row.order_number || dialog.row.dispatch_number}</h2>
            {dialog.kind === 'load' ? (
              <label><span>Dispatch</span>
                <select value={dialog.dispatch_id} onChange={(e) => setDialog({ ...dialog, dispatch_id: e.target.value })} aria-label="Dispatch">
                  <option value="">Choose</option>
                  {dispatches.map((d) => <option key={d.id} value={d.id}>{d.dispatch_number} · {d.route_code || 'route'} · {d.dispatch_date}</option>)}
                </select>
              </label>
            ) : null}
            {dialog.kind === 'deliver' ? (
              <>
                <p>{dialog.row.customer_name} · {money(dialog.row.total)}</p>
                {dialog.row.terms === 'cash' ? (
                  <label><span>How they paid</span>
                    <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="How they paid">
                      {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                    </select>
                  </label>
                ) : <p className="fs-muted">On credit. It goes on the outlet&apos;s account.</p>}
              </>
            ) : null}
            {dialog.kind === 'failed' || dialog.kind === 'cancel' ? (
              <label><span>Reason</span>
                <input autoFocus value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Reason" />
              </label>
            ) : null}
            {dialog.kind === 'return' ? (
              <>
                {dialog.row.lines.map((line: Row) => (
                  <label key={line.id}>
                    <span>{line.name} (up to {Number(line.quantity) - Number(line.returned_qty)})</span>
                    <input
                      type="number" min="0" value={dialog.quantities[line.id] ?? ''} aria-label={`Return quantity ${line.name}`}
                      onChange={(e) => setDialog({ ...dialog, quantities: { ...dialog.quantities, [line.id]: e.target.value } })}
                    />
                  </label>
                ))}
                <label><span>Reason</span>
                  <select value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Return reason">
                    {RETURN_REASONS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                  </select>
                </label>
                <label><span>The goods</span>
                  <select value={dialog.resaleable ? 'yes' : 'no'} onChange={(e) => setDialog({ ...dialog, resaleable: e.target.value === 'yes' })} aria-label="Can be resold">
                    <option value="no">Cannot be sold again</option>
                    <option value="yes">Back into stock</option>
                  </select>
                </label>
              </>
            ) : null}
            {dialog.kind === 'settle' ? (
              <>
                <p>Cash collected on this dispatch: <b>{money(dialog.expected)}</b></p>
                <label><span>Cash handed in</span>
                  <input autoFocus type="number" min="0" value={dialog.counted} onChange={(e) => setDialog({ ...dialog, counted: e.target.value })} aria-label="Cash handed in" />
                </label>
                <p className="fs-muted">Orders still on the truck go back to be loaded again.</p>
              </>
            ) : null}
            {error ? <div className="fs-banner bad">{error}</div> : null}
            <div className="fs-row">
              <button type="button" className="fs-primary" disabled={busy || !dialogReady} onClick={() => void confirmDialog()}>Confirm</button>
              <button type="button" onClick={() => setDialog(null)}>Go back</button>
            </div>
          </div>
        </div>
      ) : null}

      {tab === 'outlets' ? (
        <>
          <section className="fs-box" aria-label="Add outlet">
            <Head title="Add an outlet" />
            <div className="fs-form">
              <label><span>Outlet name</span><input value={outletForm.name} onChange={(e) => setOutletForm({ ...outletForm, name: e.target.value })} aria-label="Outlet name" /></label>
              <label><span>Phone</span><input value={outletForm.phone} placeholder="+233…" onChange={(e) => setOutletForm({ ...outletForm, phone: e.target.value })} aria-label="Outlet phone" /></label>
              <label><span>Address</span><input value={outletForm.address} onChange={(e) => setOutletForm({ ...outletForm, address: e.target.value })} aria-label="Outlet address" /></label>
              <label><span>Credit limit (0 = none set)</span><input type="number" min="0" value={outletForm.credit_limit} onChange={(e) => setOutletForm({ ...outletForm, credit_limit: e.target.value })} aria-label="Outlet credit limit" /></label>
              <label><span>Days to pay</span><input type="number" min="0" value={outletForm.payment_terms_days} onChange={(e) => setOutletForm({ ...outletForm, payment_terms_days: e.target.value })} aria-label="Outlet days to pay" /></label>
              <label><span>Route</span>
                <select value={outletForm.route_id} onChange={(e) => setOutletForm({ ...outletForm, route_id: e.target.value })} aria-label="Outlet route">
                  <option value="">None yet</option>
                  {routes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </label>
              <label><span>Sales rep</span><input value={outletForm.salesperson_name} onChange={(e) => setOutletForm({ ...outletForm, salesperson_name: e.target.value })} aria-label="Outlet sales rep" /></label>
              <button type="button" className="fs-primary" disabled={busy || !outletForm.name.trim()} onClick={() => void addOutlet()}>Add outlet</button>
            </div>
          </section>
          <section className="fs-box fs-scroll" aria-label="Outlets">
            <Head title="Outlets" />
            <table>
              <thead><tr><th>Outlet</th><th>Route</th><th>Rep</th><th>Credit limit</th><th>Days to pay</th><th>Owes</th></tr></thead>
              <tbody>
                {outlets.map((o) => (
                  <tr key={o.id}>
                    <td>{o.name}<br /><small className="fs-muted">{o.phone}</small></td>
                    <td>{o.route_name || '—'}</td><td>{o.salesperson_name || '—'}</td>
                    <td>{Number(o.credit_limit) > 0 ? money(o.credit_limit) : 'None set'}</td>
                    <td>{o.payment_terms_days}</td><td className="fs-num">{money(o.balance)}</td>
                  </tr>
                ))}
                {outlets.length === 0 ? <tr><td colSpan={6} className="fs-muted">No outlets yet. Add the first one above.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'orders' ? (
        <>
          {driver ? null : <section className="fs-box" aria-label="Book order">
            <Head title="Book an order" />
            <div className="fs-form">
              <label><span>Outlet</span>
                <select value={order.customer_id} onChange={(e) => setOrder({ ...order, customer_id: e.target.value })} aria-label="Order outlet">
                  <option value="">Choose</option>
                  {outlets.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </label>
              <label><span>Paying</span>
                <select value={order.terms} onChange={(e) => setOrder({ ...order, terms: e.target.value })} aria-label="Order terms">
                  <option value="credit">On credit</option>
                  <option value="cash">On delivery</option>
                </select>
              </label>
            </div>
            {basket.map((line, i) => (
              <div className="fs-form" key={i}>
                <label><span>Product</span>
                  <select
                    value={line.product_id} aria-label={`Order product ${i + 1}`}
                    onChange={(e) => setBasket(basket.map((l, n) => (n === i ? { ...l, product_id: e.target.value } : l)))}
                  >
                    <option value="">Choose</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.name} · {money(p.price)} · {p.stock_qty} in stock</option>)}
                  </select>
                </label>
                <label><span>How many</span>
                  <input
                    type="number" min="1" value={line.quantity} aria-label={`Order quantity ${i + 1}`}
                    onChange={(e) => setBasket(basket.map((l, n) => (n === i ? { ...l, quantity: e.target.value } : l)))}
                  />
                </label>
                {basket.length > 1 ? <button type="button" onClick={() => setBasket(basket.filter((_, n) => n !== i))}>Remove</button> : null}
              </div>
            ))}
            {needsOverride ? (
              <label><span>Reason to go over the credit limit (managers only)</span>
                <input value={order.override_reason} onChange={(e) => setOrder({ ...order, override_reason: e.target.value })} aria-label="Credit override reason" />
              </label>
            ) : null}
            <div className="fs-row">
              <button type="button" onClick={() => setBasket([...basket, { product_id: '', quantity: '1' }])}>Add another product</button>
              <button
                type="button" className="fs-primary" onClick={() => void bookOrder()}
                disabled={busy || !order.customer_id || !basket.some((l) => l.product_id && Number(l.quantity) > 0)}
              >
                Book order
              </button>
            </div>
            <p className="fs-muted">Prices come from the catalogue. Running trade schemes come off automatically.</p>
          </section>}
          <section className="fs-box fs-scroll" aria-label="Open orders">
            <Head title="To load and deliver" />
            <table>
              <thead><tr><th>Order</th><th>Outlet</th><th>What</th><th>Total</th><th>Paying</th><th>Status</th><th /></tr></thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td>{o.order_number}</td>
                    <td>{o.customer_name}<br /><small className="fs-muted">{o.route_name || 'No route'}</small></td>
                    <td>{o.lines.map((l: Row) => `${l.quantity} x ${l.name}`).join(', ')}{o.failed_reason ? <><br /><small className="fs-muted">Last try: {o.failed_reason}</small></> : null}</td>
                    <td className="fs-num">{money(o.total)}{Number(o.discount) > 0 ? <><br /><small className="fs-muted">{money(o.discount)} off</small></> : null}</td>
                    <td>{o.terms === 'cash' ? 'On delivery' : 'Credit'}</td>
                    <td>{o.status === 'loaded' ? 'On truck' : 'To load'}</td>
                    <td>
                      <div className="fs-row">
                        {o.status === 'booked' && !rep && !driver ? <button type="button" onClick={() => setDialog({ kind: 'load', row: o, dispatch_id: '' })}>Load</button> : null}
                        {rep ? null : <button type="button" className="fs-primary" onClick={() => setDialog({ kind: 'deliver', row: o, method: 'cash' })}>Deliver</button>}
                        {o.status === 'loaded' && !rep ? <button type="button" onClick={() => setDialog({ kind: 'failed', row: o, reason: '' })}>Could not deliver</button> : null}
                        {rep || driver ? null : <button type="button" className="fs-danger" onClick={() => setDialog({ kind: 'cancel', row: o, reason: '' })}>Cancel</button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {orders.length === 0 ? <tr><td colSpan={7} className="fs-muted">Nothing waiting.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="fs-box fs-scroll" aria-label="Delivered orders">
            <Head title="Delivered" />
            <table>
              <thead><tr><th>Order</th><th>Outlet</th><th>Total</th><th>Left to pay</th><th>Due</th><th /></tr></thead>
              <tbody>
                {delivered.slice(0, 50).map((o) => (
                  <tr key={o.id}>
                    <td>{o.order_number}</td><td>{o.customer_name}</td><td className="fs-num">{money(o.total)}</td><td className="fs-num">{money(o.balance_due)}</td><td>{o.due_date}</td>
                    <td>{rep ? null : <button type="button" onClick={() => setDialog({ kind: 'return', row: o, quantities: {}, reason: 'damaged', resaleable: false })}>Return</button>}</td>
                  </tr>
                ))}
                {delivered.length === 0 ? <tr><td colSpan={6} className="fs-muted">No deliveries yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          {dispatches.length && !rep && !driver ? (
            <section className="fs-box fs-scroll" aria-label="Open dispatches">
              <Head title="Trucks out" />
              <table>
                <thead><tr><th>Dispatch</th><th>Route</th><th>Date</th><th>Driver</th><th /></tr></thead>
                <tbody>
                  {dispatches.map((d) => (
                    <tr key={d.id}>
                      <td>{d.dispatch_number}</td><td>{d.route_code}</td><td>{d.dispatch_date}</td><td>{d.driver_name || '—'}</td>
                      <td><button type="button" onClick={() => void openSettle(d)}>Settle</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </>
      ) : null}

      {tab === 'collections' ? (
        <>
          <section className="fs-box" aria-label="Record payment">
            <Head title="Record a payment" />
            <div className="fs-form">
              <label><span>Outlet</span>
                <select value={pay.customer_id} onChange={(e) => setPay({ ...pay, customer_id: e.target.value })} aria-label="Payment outlet">
                  <option value="">Choose</option>
                  {owing.map((o) => <option key={o.id} value={o.id}>{o.name} · owes {money(o.balance)}</option>)}
                </select>
              </label>
              <label><span>Amount</span><input type="number" min="0" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} aria-label="Payment amount" /></label>
              <label><span>How</span>
                <select value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })} aria-label="Payment method">
                  {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
              </label>
              <label><span>Collected on dispatch</span>
                <select value={pay.dispatch_id} onChange={(e) => setPay({ ...pay, dispatch_id: e.target.value })} aria-label="Payment dispatch">
                  <option value="">Not on a truck</option>
                  {dispatches.map((d) => <option key={d.id} value={d.id}>{d.dispatch_number}</option>)}
                </select>
              </label>
              <button
                type="button" className="fs-primary" disabled={busy || !pay.customer_id || !(Number(pay.amount) > 0)}
                onClick={async () => {
                  const ok = await run('/fmcg/collections', { customer_id: pay.customer_id, amount: Number(pay.amount), method: pay.method, dispatch_id: pay.dispatch_id || null }, 'Payment recorded');
                  if (ok) setPay({ customer_id: '', amount: '', method: 'cash', dispatch_id: '' });
                }}
              >
                Record payment
              </button>
            </div>
          </section>
          <section className="fs-box fs-scroll" aria-label="Recent payments">
            <Head title="Recent payments" />
            <table>
              <thead><tr><th>Receipt</th><th>Outlet</th><th>How</th><th>Amount</th><th>When</th></tr></thead>
              <tbody>
                {payments.map((p) => <tr key={p.id}><td>{p.payment_number}</td><td>{p.customer_name}</td><td>{METHODS.find((x) => x.id === p.method)?.label || p.method}</td><td className="fs-num">{money(p.amount)}</td><td>{String(p.created_at || '').slice(0, 10)}</td></tr>)}
                {payments.length === 0 ? <tr><td colSpan={5} className="fs-muted">No payments yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="fs-box fs-scroll" aria-label="Recent returns">
            <Head title="Recent returns" />
            <table>
              <thead><tr><th>Return</th><th>Order</th><th>Outlet</th><th>Reason</th><th>Credit</th></tr></thead>
              <tbody>
                {returns.map((r) => <tr key={r.id}><td>{r.return_number}</td><td>{r.order_number}</td><td>{r.customer_name}</td><td>{RETURN_REASONS.find((x) => x.id === r.reason)?.label || r.reason}</td><td className="fs-num">{money(r.total)}</td></tr>)}
                {returns.length === 0 ? <tr><td colSpan={5} className="fs-muted">No returns.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'reports' && report ? (
        <>
          <section className="fs-box" aria-label="Report dates">
            <div className="fs-form">
              <label><span>From</span><input type="date" value={range.start} onChange={(e) => setRange((r) => ({ ...r, start: e.target.value }))} aria-label="Report from" /></label>
              <label><span>To</span><input type="date" value={range.end} onChange={(e) => setRange((r) => ({ ...r, end: e.target.value }))} aria-label="Report to" /></label>
            </div>
          </section>
          <div className="fs-tiles">
            <div className="fs-tile"><span>Net sales</span><b>{money(report.net_sales)}</b><small>{report.delivered_orders} deliveries</small></div>
            <div className="fs-tile"><span>Returns</span><b>{money(report.returns)}</b></div>
            <div className="fs-tile"><span>Scheme discounts</span><b>{money(report.scheme_discounts)}</b></div>
            <div className="fs-tile"><span>Gross profit</span><b>{money(report.gross_profit)}</b><small>{report.gross_margin_percent}% margin</small></div>
            <div className="fs-tile"><span>Collected</span><b>{money(report.collected)}</b></div>
            <div className="fs-tile"><span>Tax</span><b>{money(report.tax)}</b></div>
          </div>
          <section className="fs-box fs-scroll" aria-label="Who owes">
            <Head title="Who owes" />
            <table>
              <thead><tr><th>Outlet</th><th>Not due</th><th>1–30 days late</th><th>31–60</th><th>Over 60</th><th>Total</th></tr></thead>
              <tbody>
                {report.aging.rows.map((a: Row) => <tr key={a.customer_id}><td>{a.name}</td><td className="fs-num">{money(a.current)}</td><td className="fs-num">{money(a.d1_30)}</td><td className="fs-num">{money(a.d31_60)}</td><td className="fs-num">{money(a.d61_plus)}</td><td className="fs-num">{money(a.total)}</td></tr>)}
                {report.aging.rows.length === 0 ? <tr><td colSpan={6} className="fs-muted">Nothing owed.</td></tr> : null}
              </tbody>
            </table>
          </section>
          {[['By route', report.by_route], ['By sales rep', report.by_rep]].map(([title, rows]) => (
            <section className="fs-box fs-scroll" key={title as string} aria-label={title as string}>
              <h2>{title as string}</h2>
              <table>
                <tbody>
                  {(rows as Row[]).map((r) => <tr key={r.name}><td>{r.name}</td><td className="fs-num">{money(r.total)}</td></tr>)}
                  {(rows as Row[]).length === 0 ? <tr><td className="fs-muted">No deliveries in these dates.</td></tr> : null}
                </tbody>
              </table>
            </section>
          ))}
          <section className="fs-box fs-scroll" aria-label="Best sellers">
            <Head title="Best sellers" />
            <table>
              <thead><tr><th>Product</th><th>Sold</th><th>Takings</th></tr></thead>
              <tbody>
                {report.best_sellers.map((b: Row) => <tr key={b.name}><td>{b.name}</td><td>{b.quantity}</td><td className="fs-num">{money(b.total)}</td></tr>)}
                {report.best_sellers.length === 0 ? <tr><td colSpan={3} className="fs-muted">No sales in these dates.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}
