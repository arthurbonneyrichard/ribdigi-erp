'use client';

/**
 * Bakery desk. Its own screens on its own tables (bakery_*), never the retail till:
 * dashboard, counter, orders, deliveries, baking, waste, stock, expenses and reports.
 * The sidebar is the only menu; each screen has one heading and one job.
 */

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';
import DeskDashboard, { DeskTiles, TrendChart, type DeskTile } from '../../../components/DeskDashboard';
import DeskIcon from '../../../components/DeskIcon';
import './bakery.css';

type Row = Record<string, any>;

const SCREENS: Record<string, { title: string; sub: string; icon: string }> = {
  today: { title: 'Dashboard', sub: '', icon: 'home' },
  counter: { title: 'Counter', sub: 'Tap items to sell. Money goes into the open till.', icon: 'cart' },
  orders: { title: 'Orders', sub: 'Bread and bulk orders for a later day, picked up or delivered.', icon: 'calendar' },
  deliveries: { title: 'Deliveries', sub: 'Orders going out by van, and the cash that comes back.', icon: 'truck' },
  baking: { title: 'Baking', sub: 'Recipes, what one batch costs, and what was baked.', icon: 'flame' },
  waste: { title: 'Waste', sub: 'What was thrown away and why. It comes off your profit.', icon: 'trash' },
  stock: { title: 'Stock', sub: 'Items for sale, ingredients, and what you buy in.', icon: 'box' },
  expenses: { title: 'Expenses', sub: 'Rent, gas, wages and the rest, so the report shows what you really kept.', icon: 'wallet' },
  reports: { title: 'Reports', sub: 'How the bakery did, item by item and day by day.', icon: 'chart' },
};

function Head({ icon, title, meta }: { icon: string; title: string; meta?: React.ReactNode }) {
  return (
    <div className="bk-cardhead">
      <span className="bk-ico" aria-hidden="true"><DeskIcon name={icon} size={18} /></span>
      <h2>{title}</h2>
      {meta ? <span className="bk-meta">{meta}</span> : null}
    </div>
  );
}
const ROLE_SCREENS: Record<string, string[]> = {
  bakery_baker: ['today', 'baking', 'waste', 'orders'],
  bakery_cashier: ['today', 'counter', 'orders', 'deliveries', 'waste'],
  bakery_driver: ['today', 'deliveries', 'counter'],
};
const METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'card', label: 'Card' },
  { id: 'wallet', label: 'Wallet' },
];
const PAID_WITH = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'bank_transfer', label: 'Bank transfer' },
  { id: 'card', label: 'Card' },
];
const WASTE_REASONS = [
  { id: 'unsold', label: 'Unsold at close' },
  { id: 'burnt', label: 'Burnt' },
  { id: 'damaged', label: 'Damaged' },
  { id: 'expired', label: 'Past its date' },
  { id: 'other', label: 'Other' },
];
const DELIVERY_WORDS: Record<string, string> = {
  waiting: 'Waiting at the shop',
  out: 'On the road',
  failed: 'Came back',
  delivered: 'Delivered',
};

const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const iso = (offset = 0, from?: Date) => {
  const d = from ? new Date(from) : new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const label = (list: { id: string; label: string }[], id: string) => list.find((x) => x.id === id)?.label || id;
const safe = (value: unknown) =>
  String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);

function printReceipt(sale: Row) {
  const rows = (sale.items || [])
    .map((i: Row) => `<tr><td>${safe(i.quantity)} x ${safe(i.name)}</td><td style="text-align:right">${money(i.line_total)}</td></tr>`)
    .join('');
  const page = window.open('', '_blank', 'width=360,height=600');
  if (!page) return;
  page.document.write(
    `<html><body style="font-family:monospace"><h3>${safe(sale.sale_number)}</h3><table style="width:100%">${rows}</table><hr/><p>Tax ${money(sale.tax)}</p><h3>Total ${money(sale.total)}</h3></body></html>`,
  );
  page.document.close();
  page.print();
}

function downloadCsv(name: string, rows: (string | number)[][]) {
  const text = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function compare(now: number, before: number): DeskTile['before'] {
  return { now, value: before, word: 'the period before' };
}

type Dialog =
  | { kind: 'cancel'; row: Row; reason: string; choice: string }
  | { kind: 'refund'; row: Row; reason: string; choice: string }
  | { kind: 'collect'; row: Row; method: string }
  | { kind: 'failed'; row: Row; reason: string }
  | { kind: 'handin'; row: Row; counted: string }
  | { kind: 'edit'; row: Row; price: string; cost: string; reorder: string };

function BakeryDesk() {
  const params = useSearchParams();
  const [role, setRole] = useState('');
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const screens = useMemo(() => Object.keys(SCREENS).filter((s) => !ROLE_SCREENS[role] || ROLE_SCREENS[role].includes(s)), [role]);
  const wanted = params.get('tab') || 'today';
  const tab = screens.includes(wanted) ? wanted : 'today';
  const isDriver = role === 'bakery_driver';
  const isManager = Boolean(role) && !ROLE_SCREENS[role];
  // Managers sometimes drive: they get the same cash bag, pick-up and van sales as a driver.
  const canDrive = isDriver || isManager;
  const [myId, setMyId] = useState('');
  const [fromBag, setFromBag] = useState(false);

  const [summary, setSummary] = useState<Row | null>(null);
  const [driverDay, setDriverDay] = useState<Row | null>(null);
  const [items, setItems] = useState<Row[]>([]);
  const [ingredients, setIngredients] = useState<Row[]>([]);
  const [recipes, setRecipes] = useState<Row[]>([]);
  const [batches, setBatches] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [deliveries, setDeliveries] = useState<Row[]>([]);
  const [drivers, setDrivers] = useState<Row[]>([]);
  const [sales, setSales] = useState<Row[]>([]);
  const [waste, setWaste] = useState<Row[]>([]);
  const [stock, setStock] = useState<Row | null>(null);
  const [expenses, setExpenses] = useState<Row | null>(null);
  const [shift, setShift] = useState<Row | null>(null);
  const [report, setReport] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [basket, setBasket] = useState<Record<string, number>>({});
  const [method, setMethod] = useState('cash');
  const [given, setGiven] = useState('');
  const [find, setFind] = useState('');
  const [lastSale, setLastSale] = useState<Row | null>(null);
  const [floatCash, setFloatCash] = useState('');
  const [counted, setCounted] = useState('');
  const [recipeForm, setRecipeForm] = useState({ product_id: '', name: '', yield_qty: '1', ingredient_id: '', quantity: '' });
  const [recipeLines, setRecipeLines] = useState<Row[]>([]);
  const [bakeQty, setBakeQty] = useState<Record<string, string>>({});
  const [wasteForm, setWasteForm] = useState({ product_id: '', quantity: '', reason: 'unsold' });
  const blankOrder = { customer_name: '', phone: '', due_date: iso(1), deposit: '0', deposit_method: 'cash', notes: '', delivery: false, address: '', driver_id: '' };
  const [orderForm, setOrderForm] = useState(blankOrder);
  const [orderLines, setOrderLines] = useState<{ product_id: string; quantity: string; note: string }[]>([{ product_id: '', quantity: '1', note: '' }]);
  const [orderFilter, setOrderFilter] = useState('all');
  const [stockForm, setStockForm] = useState({ name: '', kind: 'item', price: '', reorder_level: '' });
  const [buyForm, setBuyForm] = useState({ product_id: '', quantity: '', unit_cost: '', paid_with: 'cash', supplier: '' });
  const [expenseForm, setExpenseForm] = useState({ category: 'rent', description: '', amount: '', paid_with: 'cash', spent_on: iso(0), from_till: false });
  const [range, setRange] = useState({ start: iso(-6), end: iso(0) });

  const load = useCallback(async () => {
    try {
      const me = await api('/me');
      const myRole = String(me?.data?.role || '');
      setRole(myRole);
      setMyId(String(me?.data?.id || ''));
      const jobs = ROLE_SCREENS[myRole];
      const may = (screen: string) => !jobs || jobs.includes(screen);
      const driver = myRole === 'bakery_driver';
      const soft = async (path: string) => {
        try {
          return (await api(path))?.data;
        } catch {
          return null;
        }
      };
      const want = new URLSearchParams(window.location.search).get('tab') || 'today';
      const drives = driver || !jobs;
      // Load only what this screen shows, all at once: the dashboard figures are not needed on Stock.
      const [day, sum, itemRows] = await Promise.all([
        drives && ['today', 'counter', 'deliveries'].includes(want) ? soft('/bakery/driver/today') : Promise.resolve(undefined),
        !driver && want === 'today' ? soft('/bakery/summary') : Promise.resolve(undefined),
        ['counter', 'orders', 'waste', 'baking', 'today'].includes(want) ? soft('/bakery/items') : Promise.resolve(undefined),
      ]);
      if (day !== undefined) setDriverDay(day);
      if (sum !== undefined) setSummary(sum);
      if (itemRows !== undefined) setItems(itemRows || []);
      if (want === 'orders' && may('orders')) {
        setOrders((await soft('/bakery/orders')) || []);
        if (!driver) setDrivers((await soft('/bakery/drivers')) || []);
      }
      if (want === 'deliveries' && may('deliveries')) {
        setDeliveries((await soft('/bakery/deliveries')) || []);
        if (!driver) setDrivers((await soft('/bakery/drivers')) || []);
      }
      if (want === 'baking' && may('baking')) {
        setRecipes((await soft('/bakery/recipes')) || []);
        setBatches((await soft('/bakery/batches')) || []);
        setIngredients((await soft('/bakery/ingredients')) || []);
      }
      if (want === 'counter' && may('counter') && !driver) {
        setShift(await soft('/bakery/till/shift'));
        setSales((await soft('/bakery/sales?limit=30')) || []);
      }
      if (want === 'waste' && may('waste')) setWaste((await soft('/bakery/waste')) || []);
      if (want === 'stock' && !jobs) setStock(await soft('/bakery/stock'));
      if (want === 'expenses' && !jobs) setExpenses(await soft('/bakery/expenses'));
      if (want === 'reports' && !jobs) setReport(await soft(`/bakery/reports/full?start_date=${range.start}&end_date=${range.end}`));
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, [range.start, range.end]);

  useEffect(() => {
    setError('');
    setNotice('');
    void load();
  }, [load, tab]);

  async function run(path: string, body: object | null, done: string, method_ = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api(path, { method: method_, body: body ? JSON.stringify(body) : undefined });
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

  const myBag = driverDay?.bag ?? null;
  const usingBag = isDriver || (fromBag && Boolean(myBag));
  const till = usingBag ? myBag : shift;
  const basketLines = items.filter((i) => basket[i.id]).map((i) => ({ item: i, qty: basket[i.id] }));
  const pays = (item: Row) => Number(item.price_to_pay ?? item.price ?? 0);
  // Rounded per line, the same way the sale is worked out, so the screen and the charge agree.
  const basketTotal = basketLines.reduce((sum, l) => sum + Math.round(l.qty * pays(l.item) * 100) / 100, 0);
  const change = method === 'cash' && Number(given) > 0 ? Number(given) - basketTotal : null;
  const setQty = (id: string, qty: number) =>
    setBasket((b) => {
      const next = { ...b };
      if (qty > 0) next[id] = qty;
      else delete next[id];
      return next;
    });
  const shownItems = find.trim() ? items.filter((i) => i.name.toLowerCase().includes(find.trim().toLowerCase())) : items;

  async function charge() {
    const sale = await run(
      '/bakery/sales',
      { payment_method: method, lines: basketLines.map((l) => ({ product_id: l.item.id, quantity: l.qty })), ...(usingBag && !isDriver ? { from_bag: true } : {}) },
      change != null && change > 0 ? `Sale complete. Give ${money(change)} change.` : 'Sale complete',
    );
    if (sale) {
      setLastSale(sale as Row);
      setBasket({});
      setGiven('');
    }
  }

  async function saveRecipe() {
    const ok = await run(
      '/bakery/recipes',
      {
        product_id: recipeForm.product_id,
        name: recipeForm.name.trim(),
        yield_qty: Number(recipeForm.yield_qty),
        lines: recipeLines.map((l) => ({ ingredient_id: l.ingredient_id, quantity: l.quantity })),
      },
      'Recipe saved',
    );
    if (ok) {
      setRecipeForm({ product_id: '', name: '', yield_qty: '1', ingredient_id: '', quantity: '' });
      setRecipeLines([]);
    }
  }

  const orderTotal = orderLines.reduce((sum, l) => {
    const found = items.find((i) => i.id === l.product_id);
    return sum + (found ? Math.round(Number(l.quantity || 0) * pays(found) * 100) / 100 : 0);
  }, 0);

  async function takeOrder() {
    const deposit = Number(orderForm.deposit) || 0;
    const ok = await run(
      '/bakery/orders',
      {
        customer_name: orderForm.customer_name.trim(),
        phone: orderForm.phone.replace(/[\s-]/g, '') || null,
        due_date: orderForm.due_date,
        lines: orderLines.filter((l) => l.product_id).map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity), note: l.note.trim() || null })),
        deposit,
        deposit_method: deposit > 0 ? orderForm.deposit_method : null,
        notes: orderForm.notes.trim() || null,
        delivery: orderForm.delivery,
        address: orderForm.delivery ? orderForm.address.trim() || null : null,
        driver_id: orderForm.delivery && orderForm.driver_id ? orderForm.driver_id : null,
      },
      orderForm.delivery ? 'Order taken for delivery' : 'Order taken',
    );
    if (ok) {
      setOrderForm(blankOrder);
      setOrderLines([{ product_id: '', quantity: '1', note: '' }]);
    }
  }

  async function confirmDialog() {
    if (!dialog) return;
    let ok: unknown = null;
    if (dialog.kind === 'cancel') {
      ok = await run(`/bakery/orders/${dialog.row.id}/cancel`, { reason: dialog.reason.trim(), deposit_action: Number(dialog.row.deposit) > 0 ? dialog.choice : null }, 'Order cancelled');
    }
    if (dialog.kind === 'refund') ok = await run(`/bakery/sales/${dialog.row.id}/refund`, { reason: dialog.reason.trim(), restock: dialog.choice === 'restock' }, 'Sale refunded');
    if (dialog.kind === 'collect') {
      ok = await run(`/bakery/orders/${dialog.row.id}/collect`, { payment_method: Number(dialog.row.balance) > 0 ? dialog.method : null }, dialog.row.delivery ? 'Delivered and paid' : 'Order handed over');
    }
    if (dialog.kind === 'failed') ok = await run(`/bakery/orders/${dialog.row.id}/delivery-failed`, { reason: dialog.reason.trim() }, 'Brought back to the shop');
    if (dialog.kind === 'handin') {
      const res = (await run(`/bakery/driver/bags/${dialog.row.bag.id}/hand-in`, { counted_cash: Number(dialog.counted) }, 'Cash handed in')) as Row | null;
      if (res) {
        const gap = Number(res.over_short);
        const who = dialog.row.full_name === 'Your' ? 'Your cash bag is counted.' : `${dialog.row.full_name} handed in.`;
        setNotice(gap === 0 ? `${who} The cash matches.` : `${who} ${gap < 0 ? 'Short' : 'Over'} by ${money(Math.abs(gap))}.`);
      }
      ok = res;
    }
    if (dialog.kind === 'edit') {
      ok = await run(
        `/bakery/stock/${dialog.row.id}`,
        {
          ...(dialog.row.kind === 'item' ? { price: Number(dialog.price || 0) } : {}),
          cost_price: Number(dialog.cost || 0),
          reorder_level: Number(dialog.reorder || 0),
        },
        'Saved',
        'PATCH',
      );
    }
    if (ok) setDialog(null);
  }

  const dialogReady = !dialog
    ? false
    : dialog.kind === 'cancel' || dialog.kind === 'refund' || dialog.kind === 'failed'
      ? dialog.reason.trim().length >= 3
      : dialog.kind === 'handin'
        ? dialog.counted !== ''
        : true;

  const shownOrders = orders.filter((o) =>
    orderFilter === 'today' ? o.due_date <= iso(0) : orderFilter === 'delivery' ? o.delivery : orderFilter === 'pickup' ? !o.delivery : true,
  );

  const reportTiles: DeskTile[] = report
    ? [
        { label: 'Sales before tax', icon: 'cash', value: money(report.revenue), before: compare(report.revenue, report.previous.revenue), spark: (report.trend?.points || []).map((p: Row) => Number(p.value)) },
        { label: 'Gross profit', icon: 'chart', value: money(report.gross_profit), sub: `${report.gross_margin_percent}% of sales, after waste` },
        { label: 'Expenses', icon: 'wallet', value: money(report.expenses), href: '/bakery?tab=expenses' },
        { label: 'Net profit', icon: 'leaf', value: money(report.net_profit), before: compare(report.net_profit, report.previous.net_profit), warn: report.net_profit < 0 },
        { label: 'Sales', icon: 'receipt', value: report.sale_count, sub: `Average ${money(report.average_sale)}` },
        { label: 'Waste', icon: 'trash', value: money(report.waste_cost), sub: `${report.waste_percent_of_baked}% of what was baked`, warn: report.waste_percent_of_baked > 10 },
      ]
    : [];
  const peak = report?.by_hour?.length ? Math.max(...report.by_hour.map((h: Row) => h.total)) : 0;

  if (loading) return <div className="bakery"><p>Loading…</p></div>;

  return (
    <div className="bakery">
      {dialog ? (
        <div className="bk-veil">
          <div className="bk-dialog" role="dialog" aria-modal="true" aria-label="Bakery action">
            {dialog.kind === 'cancel' || dialog.kind === 'refund' || dialog.kind === 'failed' ? (
              <>
                <h2>{dialog.kind === 'cancel' ? `Cancel ${dialog.row.order_number}` : dialog.kind === 'refund' ? `Refund ${dialog.row.sale_number}` : `Could not deliver ${dialog.row.order_number}`}</h2>
                <label><span>{dialog.kind === 'failed' ? 'What happened' : 'Reason'}</span>
                  <input autoFocus value={dialog.reason} onChange={(e) => setDialog({ ...dialog, reason: e.target.value })} aria-label="Reason" />
                </label>
              </>
            ) : null}
            {dialog.kind === 'cancel' && Number(dialog.row.deposit) > 0 ? (
              <label><span>The {money(dialog.row.deposit)} deposit</span>
                <select value={dialog.choice} onChange={(e) => setDialog({ ...dialog, choice: e.target.value })} aria-label="Deposit">
                  <option value="refund">Give it back to the customer</option>
                  <option value="keep">Keep it as income</option>
                </select>
              </label>
            ) : null}
            {dialog.kind === 'refund' ? (
              <label><span>The items</span>
                <select value={dialog.choice} onChange={(e) => setDialog({ ...dialog, choice: e.target.value })} aria-label="Items">
                  <option value="restock">Back on the shelf</option>
                  <option value="discard">Cannot be sold again</option>
                </select>
              </label>
            ) : null}
            {dialog.kind === 'collect' ? (
              <>
                <h2>{dialog.row.delivery ? 'Delivered' : 'Hand over'} {dialog.row.order_number}</h2>
                <p>{dialog.row.customer_name} · {(dialog.row.items || []).map((i: Row) => `${i.quantity} x ${i.name}`).join(', ')}</p>
                {Number(dialog.row.balance) > 0 ? (
                  <>
                    <p className="bk-big">Take {money(dialog.row.balance)}</p>
                    <label><span>How they paid</span>
                      <select value={dialog.method} onChange={(e) => setDialog({ ...dialog, method: e.target.value })} aria-label="How they paid">
                        {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                      </select>
                    </label>
                  </>
                ) : <p className="bk-muted">Already paid in full.</p>}
              </>
            ) : null}
            {dialog.kind === 'handin' ? (
              <>
                <h2>{dialog.row.full_name === 'Your' ? 'Count your cash bag' : `${dialog.row.full_name} hands in cash`}</h2>
                <p>The bag should hold <b>{money(dialog.row.bag.expected_cash)}</b> in cash.</p>
                <label><span>Cash you counted</span>
                  <input autoFocus type="number" min="0" step="0.01" value={dialog.counted} onChange={(e) => setDialog({ ...dialog, counted: e.target.value })} aria-label="Cash you counted" />
                </label>
              </>
            ) : null}
            {dialog.kind === 'edit' ? (
              <>
                <h2>{dialog.row.name}</h2>
                {dialog.row.kind === 'item' ? (
                  <label><span>Selling price</span><input type="number" min="0" step="0.01" value={dialog.price} onChange={(e) => setDialog({ ...dialog, price: e.target.value })} aria-label="Selling price" /></label>
                ) : null}
                <label><span>Cost each</span><input type="number" min="0" step="0.01" value={dialog.cost} onChange={(e) => setDialog({ ...dialog, cost: e.target.value })} aria-label="Cost each" /></label>
                <label><span>Warn me when stock falls to</span><input type="number" min="0" value={dialog.reorder} onChange={(e) => setDialog({ ...dialog, reorder: e.target.value })} aria-label="Low stock level" /></label>
              </>
            ) : null}
            {error ? <div className="bk-banner bad">{error}</div> : null}
            <div className="bk-row">
              <button type="button" className="bk-primary" disabled={busy || !dialogReady} onClick={() => void confirmDialog()}>Confirm</button>
              <button type="button" onClick={() => setDialog(null)}>Go back</button>
            </div>
          </div>
        </div>
      ) : null}

      {tab !== 'today' ? (
        <header className="bk-head">
          <span className="bk-head-ico" aria-hidden="true"><DeskIcon name={SCREENS[tab].icon} size={26} /></span>
          <div className="bk-head-text">
            <h1>{SCREENS[tab].title}</h1>
            <p>{tab === 'counter' && usingBag ? 'Selling from the van. Money goes into your cash bag, not the shop till.' : SCREENS[tab].sub}</p>
          </div>
          <div className="bk-head-status">
            {tab === 'counter' ? (
              <span className={`bk-status ${till ? 'on' : 'off'}`}>
                <span className="bk-dot" aria-hidden="true" />
                {usingBag ? (till ? `Van bag: ${money(till.expected_cash)}` : 'Cash bag not started') : till ? `Till open: ${money(till.expected_cash)}` : 'Till closed'}
              </span>
            ) : null}
            {tab === 'deliveries' && canDrive ? (
              <span className={`bk-status ${myBag ? 'on' : 'off'}`}>
                <span className="bk-dot" aria-hidden="true" />
                {myBag ? `You are driving: ${money(myBag.expected_cash)}` : 'Not driving'}
              </span>
            ) : null}
          </div>
        </header>
      ) : null}
      {error && !dialog ? <p className="bk-banner bad" role="alert">{error}</p> : null}
      {notice ? <p className="bk-banner" role="status">{notice}</p> : null}

      {tab === 'today' && isDriver && driverDay ? (
        <DeskDashboard
          desk="Driver dashboard"
          actions={[
            { label: 'My deliveries', href: '/bakery?tab=deliveries', primary: true, icon: 'truck', hint: 'Pick up and deliver' },
            { label: 'Sell from the van', href: '/bakery?tab=counter', icon: 'cart', hint: 'Into your cash bag' },
          ]}
          tiles={[
            { label: 'Cash bag', icon: 'bag', value: driverDay.bag ? money(driverDay.bag.expected_cash) : 'Not started', sub: driverDay.bag ? 'cash you should have' : 'Start it before you go', warn: !driverDay.bag, href: '/bakery?tab=deliveries' },
            { label: 'To pick up', icon: 'box', value: driverDay.to_pick_up, href: '/bakery?tab=deliveries' },
            { label: 'On the road', icon: 'truck', value: driverDay.on_the_road, href: '/bakery?tab=deliveries' },
            { label: 'Delivered today', icon: 'check', value: driverDay.delivered_today },
            { label: 'Sold on the road', icon: 'cart', value: driverDay.road_sales_today, sub: 'sales today' },
          ]}
          attention={[
            ...(!driverDay.bag ? [{ level: 'warning' as const, text: 'Start your cash bag before you pick up', href: '/bakery?tab=deliveries' }] : []),
            ...(driverDay.to_pick_up ? [{ level: 'info' as const, text: `${driverDay.to_pick_up} waiting at the shop for you`, href: '/bakery?tab=deliveries' }] : []),
          ]}
        />
      ) : null}

      {tab === 'today' && !isDriver && summary ? (
        <DeskDashboard
          desk="Bakery dashboard"
          actions={[
            ...(role === 'bakery_baker' ? [] : [{ label: 'Open the counter', href: '/bakery?tab=counter', primary: true, icon: 'cart', hint: 'Sell from the shelf' }]),
            { label: 'Take an order', href: '/bakery?tab=orders', icon: 'calendar', hint: 'Bread and bulk orders' },
            ...(role === 'bakery_cashier' ? [] : [{ label: 'Record a bake', href: '/bakery?tab=baking', primary: role === 'bakery_baker', icon: 'flame', hint: 'Fill the shelf' }]),
            ...(isManager ? [{ label: myBag ? 'You are driving' : 'Drive today', href: '/bakery?tab=deliveries', icon: 'truck', hint: myBag ? `Bag ${money(myBag.expected_cash)}` : 'Deliver and sell' }] : []),
            ...(isManager ? [{ label: 'Buy stock', href: '/bakery?tab=stock', icon: 'box', hint: 'Flour, sugar and more' }] : [{ label: 'Record waste', href: '/bakery?tab=waste', icon: 'trash', hint: 'Burnt or unsold' }]),
          ]}
          tiles={[
            ...(summary.sales_today !== undefined
              ? [{ label: 'Sales today', icon: 'cash', value: money(summary.sales_today), before: { now: Number(summary.sales_today), value: Number(summary.sales_yesterday || 0), word: 'yesterday' }, spark: (summary.trend?.points || []).map((p: Row) => Number(p.value)) }]
              : []),
            ...(summary.gross_profit_today !== undefined ? [{ label: 'Profit after waste', icon: 'chart', value: money(summary.gross_profit_today), sub: `Waste ${money(summary.waste_today)}` }] : []),
            { label: 'Orders to hand over', icon: 'calendar', value: summary.orders_due_today, sub: summary.orders_overdue ? `${summary.orders_overdue} past due` : `${summary.orders_open} open in all`, warn: Boolean(summary.orders_overdue), href: '/bakery?tab=orders' },
            { label: 'Batches baked', icon: 'flame', value: summary.baked_batches_today, sub: 'today', href: role === 'bakery_cashier' ? undefined : '/bakery?tab=baking' },
            ...(summary.sales_today !== undefined
              ? [{ label: 'Till', icon: 'cash', value: summary.till_open ? 'Open' : 'Closed', sub: summary.shift ? `Cash should be ${money(summary.shift.expected_cash)}` : 'Open it before selling', warn: !summary.till_open, href: '/bakery?tab=counter' }]
              : []),
          ]}
          trend={summary.trend}
          attention={summary.attention}
        >
          <section className="bk-box" aria-label="To bake">
            <Head icon="flame" title="To bake for orders due by tomorrow" />
            {(summary.to_bake || []).filter((r: Row) => Number(r.to_bake) > 0).length === 0 ? (
              <p className="bk-muted">The shelf covers every order due by tomorrow.</p>
            ) : (
              <table>
                <thead><tr><th>Item</th><th>Ordered</th><th>On the shelf</th><th>To bake</th></tr></thead>
                <tbody>
                  {summary.to_bake.filter((r: Row) => Number(r.to_bake) > 0).map((r: Row) => (
                    <tr key={r.product_id}><td>{r.name}</td><td>{r.ordered}</td><td>{r.on_hand}</td><td><b>{r.to_bake}</b></td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </DeskDashboard>
      ) : null}

      {tab === 'counter' && (
        <div className="bk-grid2">
          <section className="bk-box" aria-label="Items">
            <div className="bk-row bk-spread">
              <Head icon="bread" title="Items" />
              <input className="bk-find" placeholder="Find an item" value={find} onChange={(e) => setFind(e.target.value)} aria-label="Find an item" />
            </div>
            {items.length === 0 ? <p className="bk-muted">No items for sale yet. {isManager ? <Link href="/bakery?tab=stock">Add them under Stock.</Link> : 'Ask a manager to add them.'}</p> : null}
            <div className="bk-items">
              {shownItems.map((item) => {
                const out = Number(item.stock_qty) <= 0;
                return (
                  <button key={item.id} type="button" disabled={out || !till} className={`bk-item${basket[item.id] ? ' in' : ''}`} aria-label={out ? `${item.name}, none left` : `Add ${item.name}`} onClick={() => setQty(item.id, (basket[item.id] || 0) + 1)}>
                    {basket[item.id] ? <span className="bk-count">{basket[item.id]}</span> : null}
                    <span>{item.name}</span>
                    <b>{money(pays(item))}</b>
                    <small>{out ? 'None left' : `${item.stock_qty} left`}</small>
                  </button>
                );
              })}
            </div>
          </section>
          <aside className="bk-box bk-basket" aria-label="Basket">
            {isManager && myBag ? (
              <div className="bk-seg" role="radiogroup" aria-label="Selling from">
                <button type="button" role="radio" aria-checked={!fromBag} className={!fromBag ? 'on' : ''} onClick={() => setFromBag(false)}>Shop till</button>
                <button type="button" role="radio" aria-checked={fromBag} className={fromBag ? 'on' : ''} onClick={() => setFromBag(true)}>My van bag</button>
              </div>
            ) : null}
            {!till ? (
              <>
                <Head icon={usingBag || isDriver ? 'bag' : 'cash'} title={isDriver ? 'Start your cash bag' : 'Open the till'} />
                <p className="bk-muted">{isDriver ? 'Count the change you are taking out. Your sales and deliveries go into this bag.' : 'Count the cash in the drawer before the first sale.'}</p>
                <label><span>Cash to start with</span><input type="number" min={0} step="0.01" value={floatCash} onChange={(e) => setFloatCash(e.target.value)} aria-label="Opening cash" /></label>
                <button type="button" className="bk-primary bk-wide" disabled={busy} onClick={() => run(isDriver ? '/bakery/driver/bag' : '/bakery/till/shift/open', { opening_cash: Number(floatCash) || 0 }, isDriver ? 'Cash bag started' : 'Till open')}>
                  {isDriver ? 'Start cash bag' : 'Open till'}
                </button>
              </>
            ) : (
              <>
                <Head icon="cart" title="Basket" />
                {basketLines.length === 0 ? <p className="bk-muted">Tap an item to add it.</p> : null}
                {basketLines.map(({ item, qty }) => (
                  <div className="bk-line" key={item.id}>
                    <span>{item.name}</span>
                    <span className="bk-row bk-qty">
                      <button type="button" aria-label={`One less ${item.name}`} onClick={() => setQty(item.id, qty - 1)}>−</button>
                      <b>{qty}</b>
                      <button type="button" aria-label={`One more ${item.name}`} onClick={() => setQty(item.id, qty + 1)}>+</button>
                      <span className="bk-amount">{money(qty * pays(item))}</span>
                    </span>
                  </div>
                ))}
                <div className="bk-total"><span>To pay</span><span>{money(basketTotal)}</span></div>
                <p className="bk-muted bk-small">Prices include tax.</p>
                <div className="bk-methods" role="radiogroup" aria-label="Payment method">
                  {METHODS.map((x) => (
                    <button key={x.id} type="button" role="radio" aria-checked={method === x.id} className={method === x.id ? 'on' : ''} onClick={() => setMethod(x.id)}>{x.label}</button>
                  ))}
                </div>
                {method === 'cash' ? (
                  <label><span>Cash given</span><input type="number" min="0" step="0.01" value={given} onChange={(e) => setGiven(e.target.value)} aria-label="Cash given" /></label>
                ) : null}
                {change != null ? <p className={change < 0 ? 'bk-banner bad' : 'bk-change'}>{change < 0 ? `${money(-change)} more needed` : `Change ${money(change)}`}</p> : null}
                <button type="button" className="bk-primary bk-wide bk-charge" disabled={busy || basketLines.length === 0 || (change != null && change < 0)} onClick={() => void charge()}>
                  Charge {money(basketTotal)}
                </button>
                {lastSale ? <button type="button" className="bk-wide" onClick={() => printReceipt(lastSale)}>Print receipt {lastSale.sale_number}</button> : null}
                <div className="bk-drawer">
                  <span>{usingBag ? 'Cash in your bag' : 'Cash in the drawer'}</span><b>{money(till.expected_cash)}</b>
                </div>
                {!usingBag ? (
                  <div className="bk-form bk-close">
                    <label><span>Cash counted at close</span><input type="number" min={0} step="0.01" value={counted} onChange={(e) => setCounted(e.target.value)} aria-label="Counted cash" /></label>
                    <button type="button" disabled={busy || counted === ''} onClick={async () => { if (await run('/bakery/till/shift/close', { counted_cash: Number(counted) || 0 }, 'Till closed')) setCounted(''); }}>Close till</button>
                  </div>
                ) : <p className="bk-muted bk-small">Hand your bag in at the shop when you are back.</p>}
              </>
            )}
          </aside>
          {!isDriver ? (
            <section className="bk-box bk-scroll" aria-label="Recent sales" style={{ gridColumn: '1 / -1' }}>
              <Head icon="receipt" title="Recent sales" />
              <table>
                <thead><tr><th>Sale</th><th>Paid by</th><th>Total</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {sales.map((s) => (
                    <tr key={s.id}>
                      <td>{s.sale_number}</td><td>{label(METHODS, s.payment_method)}</td><td className="bk-num">{money(s.total)}</td>
                      <td><span className={`bk-pill ${s.status === 'refunded' ? 'bad' : 'ok'}`}>{s.status === 'refunded' ? 'Refunded' : 'Paid'}</span></td>
                      <td>{isManager && s.status === 'completed' && !s.order_id ? <button type="button" className="bk-danger" disabled={busy} onClick={() => setDialog({ kind: 'refund', row: s, reason: '', choice: 'restock' })}>Refund</button> : null}</td>
                    </tr>
                  ))}
                  {sales.length === 0 ? <tr><td colSpan={5} className="bk-muted">No sales yet.</td></tr> : null}
                </tbody>
              </table>
            </section>
          ) : null}
        </div>
      )}

      {tab === 'orders' && (
        <>
          {role !== 'bakery_baker' ? (
            <section className="bk-box" aria-label="Take an order">
              <Head icon="plus" title="Take an order" />
              <div className="bk-form">
                <label><span>Customer</span><input value={orderForm.customer_name} onChange={(e) => setOrderForm((f) => ({ ...f, customer_name: e.target.value }))} aria-label="Order customer" /></label>
                <label><span>Phone</span><input value={orderForm.phone} placeholder="+233..." onChange={(e) => setOrderForm((f) => ({ ...f, phone: e.target.value }))} aria-label="Order phone" /></label>
                <label><span>{orderForm.delivery ? 'Deliver on' : 'Collect on'}</span><input type="date" min={iso(0)} value={orderForm.due_date} onChange={(e) => setOrderForm((f) => ({ ...f, due_date: e.target.value }))} aria-label="Order date" /></label>
                <label><span>How it goes</span>
                  <select value={orderForm.delivery ? 'delivery' : 'pickup'} onChange={(e) => setOrderForm((f) => ({ ...f, delivery: e.target.value === 'delivery' }))} aria-label="Pick up or delivery">
                    <option value="pickup">Customer picks it up</option>
                    <option value="delivery">We deliver it</option>
                  </select>
                </label>
                {orderForm.delivery ? (
                  <>
                    <label className="bk-span2"><span>Delivery address</span><input value={orderForm.address} onChange={(e) => setOrderForm((f) => ({ ...f, address: e.target.value }))} aria-label="Delivery address" /></label>
                    <label><span>Driver</span>
                      <select value={orderForm.driver_id} onChange={(e) => setOrderForm((f) => ({ ...f, driver_id: e.target.value }))} aria-label="Driver">
                        <option value="">Any driver</option>
                        {drivers.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
                      </select>
                    </label>
                  </>
                ) : null}
              </div>
              <h3 className="bk-sub">What they want</h3>
              {orderLines.map((line, i) => (
                <div className="bk-form" key={i}>
                  <label><span>Item</span>
                    <select value={line.product_id} onChange={(e) => setOrderLines(orderLines.map((l, n) => (n === i ? { ...l, product_id: e.target.value } : l)))} aria-label={`Order item ${i + 1}`}>
                      <option value="">Choose</option>
                      {items.map((it) => <option key={it.id} value={it.id}>{it.name} · {money(pays(it))}</option>)}
                    </select>
                  </label>
                  <label><span>How many</span><input type="number" min={1} value={line.quantity} onChange={(e) => setOrderLines(orderLines.map((l, n) => (n === i ? { ...l, quantity: e.target.value } : l)))} aria-label={`Order quantity ${i + 1}`} /></label>
                  <label><span>Writing or design</span><input value={line.note} onChange={(e) => setOrderLines(orderLines.map((l, n) => (n === i ? { ...l, note: e.target.value } : l)))} aria-label={`Order note ${i + 1}`} /></label>
                  {orderLines.length > 1 ? <button type="button" onClick={() => setOrderLines(orderLines.filter((_, n) => n !== i))}>Remove</button> : null}
                </div>
              ))}
              <p><button type="button" onClick={() => setOrderLines([...orderLines, { product_id: '', quantity: '1', note: '' }])}>Add another item</button></p>
              <div className="bk-form">
                <label><span>Deposit now</span><input type="number" min={0} step="0.01" value={orderForm.deposit} onChange={(e) => setOrderForm((f) => ({ ...f, deposit: e.target.value }))} aria-label="Order deposit" /></label>
                <label><span>Deposit paid by</span>
                  <select value={orderForm.deposit_method} disabled={Number(orderForm.deposit) <= 0} onChange={(e) => setOrderForm((f) => ({ ...f, deposit_method: e.target.value }))} aria-label="Deposit method">
                    {METHODS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                  </select>
                </label>
                <div className="bk-sumline"><span>Order total with tax</span><b>{money(orderTotal)}</b></div>
                <button
                  type="button" className="bk-primary" onClick={() => void takeOrder()}
                  disabled={busy || !orderForm.customer_name.trim() || !orderLines.some((l) => l.product_id) || (orderForm.delivery && !orderForm.address.trim())}
                >Take order</button>
              </div>
            </section>
          ) : null}
          <section className="bk-box bk-scroll" aria-label="Open orders">
            <div className="bk-row bk-spread">
              <Head icon="calendar" title="Open orders" />
              <div className="bk-chips" role="group" aria-label="Show orders">
                {[['all', 'All'], ['today', 'Due today'], ['pickup', 'Pick up'], ['delivery', 'Delivery']].map(([id, text]) => (
                  <button key={id} type="button" className={orderFilter === id ? 'on' : ''} aria-pressed={orderFilter === id} onClick={() => setOrderFilter(id)}>{text}</button>
                ))}
              </div>
            </div>
            <table>
              <thead><tr><th>Order</th><th>Customer</th><th>Date</th><th>What</th>{role !== 'bakery_baker' ? <th>Left to pay</th> : null}<th>Status</th><th /></tr></thead>
              <tbody>
                {shownOrders.map((o) => (
                  <tr key={o.id}>
                    <td>{o.order_number}</td>
                    <td>{o.customer_name}{o.phone ? <div className="bk-muted">{o.phone}</div> : null}</td>
                    <td className="bk-num">{o.due_date}{o.due_date < iso(0) ? <div><span className="bk-pill bad">Late</span></div> : null}</td>
                    <td>{(o.items || []).map((i: Row) => <div key={`${o.id}-${i.name}`}>{i.quantity} x {i.name}{i.note ? <span className="bk-muted"> · {i.note}</span> : null}</div>)}</td>
                    {role !== 'bakery_baker' ? <td className="bk-num">{money(o.balance)}</td> : null}
                    <td>
                      <span className={`bk-pill ${o.status === 'ready' ? 'ok' : ''}`}>{o.status === 'ready' ? 'Ready' : 'Booked'}</span>
                      {o.delivery ? <div className="bk-muted">{DELIVERY_WORDS[o.delivery_status] || 'Delivery'}{o.driver_name ? ` · ${o.driver_name}` : ''}</div> : null}
                    </td>
                    <td className="bk-row">
                      {o.status === 'booked' ? <button type="button" disabled={busy} onClick={() => run(`/bakery/orders/${o.id}/ready`, {}, 'Order ready')}>Ready</button> : null}
                      {role !== 'bakery_baker' && !o.delivery ? <button type="button" className="bk-primary" disabled={busy} onClick={() => setDialog({ kind: 'collect', row: o, method: 'cash' })}>Hand over</button> : null}
                      {isManager ? <button type="button" className="bk-danger" disabled={busy} onClick={() => setDialog({ kind: 'cancel', row: o, reason: '', choice: 'refund' })}>Cancel</button> : null}
                    </td>
                  </tr>
                ))}
                {shownOrders.length === 0 ? <tr><td colSpan={7} className="bk-muted">No orders here.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === 'deliveries' && (
        <>
          {canDrive ? (
            <section className="bk-box bk-bagbar" aria-label="Cash bag">
              {driverDay?.bag ? (
                <>
                  <div className="bk-bagnum">
                    <span className="bk-ico" aria-hidden="true"><DeskIcon name="bag" size={20} /></span>
                    <div><span className="bk-muted">{isDriver ? 'Cash in your bag' : 'You are driving. Cash in your bag'}</span><b>{money(driverDay.bag.expected_cash)}</b></div>
                  </div>
                  <div className="bk-row">
                    <Link href="/bakery?tab=counter" className="bk-linkbtn" onClick={() => setFromBag(true)}>Sell from the van</Link>
                    {isManager ? <button type="button" onClick={() => setDialog({ kind: 'handin', row: { full_name: 'Your', bag: driverDay.bag }, counted: '' })}>Back at the shop: count my bag</button> : null}
                  </div>
                </>
              ) : (
                <div className="bk-form">
                  {isManager ? <p className="bk-muted bk-span2">Driving yourself today? Start a cash bag. Your deliveries and van sales go into it, not the shop till.</p> : null}
                  <label><span>Change you are taking out</span><input type="number" min={0} step="0.01" value={floatCash} onChange={(e) => setFloatCash(e.target.value)} aria-label="Opening cash" /></label>
                  <button type="button" className="bk-primary" disabled={busy} onClick={() => run('/bakery/driver/bag', { opening_cash: Number(floatCash) || 0 }, 'Cash bag started')}>{isManager ? 'Start driving' : 'Start cash bag'}</button>
                </div>
              )}
            </section>
          ) : null}
          {!isDriver ? (
            <section className="bk-box bk-scroll" aria-label="Drivers">
              <Head icon="users" title="Drivers" />
              {drivers.length === 0 ? <p className="bk-muted">No drivers yet. Add a user with the Bakery Driver role under Staff.</p> : (
                <table>
                  <thead><tr><th>Driver</th><th>Cash bag</th><th>Cash they should have</th><th /></tr></thead>
                  <tbody>
                    {drivers.map((d) => (
                      <tr key={d.id}>
                        <td>{d.full_name}{!d.is_driver ? <div className="bk-muted">Manager</div> : null}</td>
                        <td>{d.bag ? <span className="bk-pill ok">Out</span> : <span className="bk-pill">At the shop</span>}</td>
                        <td>{d.bag ? money(d.bag.expected_cash) : '—'}</td>
                        <td>{d.bag ? <button type="button" onClick={() => setDialog({ kind: 'handin', row: d, counted: '' })}>Hand in cash</button> : null}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          ) : null}
          <div className="bk-cards">
            {deliveries.map((o) => {
              const mine = Boolean(myBag) && o.delivery_status === 'out' && (isDriver || o.driver_id === myId);
              // A driver takes their own or unclaimed ones; a manager covering can take over any not yet on the road.
              const canTake = canDrive && Boolean(myBag) && o.delivery_status !== 'out' && (isManager || !o.driver_id || o.driver_id === myId);
              return (
                <article className={`bk-card ${o.delivery_status}`} key={o.id}>
                  <div className="bk-row bk-spread">
                    <b>{o.order_number}</b>
                    <span className={`bk-pill ${o.delivery_status === 'out' ? 'ok' : o.delivery_status === 'failed' ? 'bad' : ''}`}>{DELIVERY_WORDS[o.delivery_status] || 'Waiting'}</span>
                  </div>
                  <p className="bk-who">{o.customer_name}{o.phone ? <> · <a href={`tel:${o.phone}`}>{o.phone}</a></> : null}</p>
                  <p>{o.address} · <a href={`https://maps.google.com/?q=${encodeURIComponent(o.address || '')}`} target="_blank" rel="noreferrer">Map</a></p>
                  <p className="bk-muted">{(o.items || []).map((i: Row) => `${i.quantity} x ${i.name}`).join(', ')} · due {o.due_date}</p>
                  {o.delivery_note ? <p className="bk-muted">Last try: {o.delivery_note}</p> : null}
                  <div className="bk-row bk-spread">
                    <span>{Number(o.balance) > 0 ? <>Take <b>{money(o.balance)}</b></> : 'Paid'}</span>
                    {canTake || mine ? (
                      <span className="bk-row">
                        {canTake ? (
                          <button type="button" className="bk-primary" disabled={busy} onClick={() => run(`/bakery/orders/${o.id}/pick-up`, null, 'Picked up')}>Pick up</button>
                        ) : null}
                        {mine ? (
                          <>
                            <button type="button" className="bk-primary" disabled={busy} onClick={() => setDialog({ kind: 'collect', row: o, method: 'cash' })}>Delivered</button>
                            <button type="button" onClick={() => setDialog({ kind: 'failed', row: o, reason: '' })}>Could not deliver</button>
                          </>
                        ) : null}
                      </span>
                    ) : null}
                    {isDriver && !myBag && o.delivery_status !== 'out' ? <span className="bk-muted">Start your cash bag to pick up</span> : null}
                    {!isDriver ? (
                      <select
                        value={o.driver_id || ''} disabled={o.delivery_status === 'out' || busy} aria-label={`Driver for ${o.order_number}`}
                        onChange={(e) => run(`/bakery/orders/${o.id}/driver`, { driver_id: e.target.value || null }, 'Driver set')}
                        style={{ maxWidth: 190 }}
                      >
                        <option value="">Any driver</option>
                        {drivers.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
                      </select>
                    ) : null}
                  </div>
                </article>
              );
            })}
            {deliveries.length === 0 ? <section className="bk-box bk-muted">No deliveries waiting. {isDriver ? 'You can still sell from the van.' : 'Take an order and choose “We deliver it”.'}</section> : null}
          </div>
        </>
      )}

      {tab === 'baking' && (
        <>
          <section className="bk-box bk-scroll" aria-label="Recipes">
            <Head icon="flame" title="Recipes" />
            <table>
              <thead><tr><th>Recipe</th><th>Makes</th><th>Cost each</th><th>Sells at</th><th>Margin</th><th>Bake</th></tr></thead>
              <tbody>
                {recipes.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}<div className="bk-muted">{(r.lines || []).map((l: Row) => `${l.quantity} ${l.name}`).join(', ')}</div></td>
                    <td>{r.yield_qty}</td><td className="bk-num">{money(r.unit_cost)}</td><td className="bk-num">{money(r.selling_price)}</td>
                    <td>{r.margin_percent === null ? '—' : <span className={`bk-pill ${Number(r.margin_percent) < 30 ? 'bad' : 'ok'}`}>{r.margin_percent}%</span>}</td>
                    <td className="bk-row">
                      <input style={{ width: 80 }} type="number" min={0.1} step="0.1" value={bakeQty[r.id] ?? '1'} onChange={(e) => setBakeQty((b) => ({ ...b, [r.id]: e.target.value }))} aria-label={`Batches of ${r.name}`} />
                      <button type="button" className="bk-primary" disabled={busy} onClick={() => run('/bakery/batches', { recipe_id: r.id, batches: Number(bakeQty[r.id] ?? 1) }, `${r.name} baked`)}>Bake</button>
                    </td>
                  </tr>
                ))}
                {recipes.length === 0 ? <tr><td colSpan={6} className="bk-muted">No recipes yet. Add your first one below.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="bk-box" aria-label="New recipe">
            <Head icon="plus" title="New recipe" />
            <div className="bk-form">
              <label><span>Makes this item</span>
                <select value={recipeForm.product_id} onChange={(e) => setRecipeForm((f) => ({ ...f, product_id: e.target.value }))} aria-label="Recipe item">
                  <option value="">Choose</option>
                  {items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
                </select>
              </label>
              <label><span>Recipe name</span><input value={recipeForm.name} onChange={(e) => setRecipeForm((f) => ({ ...f, name: e.target.value }))} aria-label="Recipe name" /></label>
              <label><span>One batch makes</span><input type="number" min={1} value={recipeForm.yield_qty} onChange={(e) => setRecipeForm((f) => ({ ...f, yield_qty: e.target.value }))} aria-label="Recipe yield" /></label>
            </div>
            <h3 className="bk-sub">Ingredients for one batch</h3>
            <div className="bk-form">
              <label><span>Ingredient</span>
                <select value={recipeForm.ingredient_id} onChange={(e) => setRecipeForm((f) => ({ ...f, ingredient_id: e.target.value }))} aria-label="Recipe ingredient">
                  <option value="">Choose</option>
                  {ingredients.map((i) => <option key={i.id} value={i.id}>{i.name} ({i.stock_qty} in stock)</option>)}
                </select>
              </label>
              <label><span>Amount</span><input type="number" min={0} step="0.001" value={recipeForm.quantity} onChange={(e) => setRecipeForm((f) => ({ ...f, quantity: e.target.value }))} aria-label="Ingredient amount" /></label>
              <button type="button" disabled={!recipeForm.ingredient_id || !(Number(recipeForm.quantity) > 0)} onClick={() => {
                const found = ingredients.find((i) => i.id === recipeForm.ingredient_id);
                setRecipeLines((l) => [...l.filter((x) => x.ingredient_id !== recipeForm.ingredient_id), { ingredient_id: recipeForm.ingredient_id, quantity: Number(recipeForm.quantity), name: found?.name }]);
                setRecipeForm((f) => ({ ...f, ingredient_id: '', quantity: '' }));
              }}>Add ingredient</button>
            </div>
            {recipeLines.map((l) => (
              <div className="bk-line" key={l.ingredient_id}>
                <span>{l.quantity} {l.name}</span>
                <button type="button" aria-label={`Remove ${l.name}`} onClick={() => setRecipeLines((x) => x.filter((y) => y.ingredient_id !== l.ingredient_id))}>Remove</button>
              </div>
            ))}
            <p><button type="button" className="bk-primary" disabled={busy || !recipeForm.product_id || !recipeForm.name.trim() || recipeLines.length === 0} onClick={() => void saveRecipe()}>Save recipe</button></p>
          </section>
          <section className="bk-box bk-scroll" aria-label="Baked">
            <Head icon="clock" title="Recently baked" />
            <table>
              <thead><tr><th>Batch</th><th>Item</th><th>Made</th><th>Cost each</th></tr></thead>
              <tbody>
                {batches.map((b) => <tr key={b.id}><td>{b.batch_number}</td><td>{b.product_name}</td><td>{b.made_qty}</td><td className="bk-num">{money(b.unit_cost)}</td></tr>)}
                {batches.length === 0 ? <tr><td colSpan={4} className="bk-muted">Nothing baked yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === 'waste' && (
        <>
          <section className="bk-box" aria-label="Record waste">
            <Head icon="trash" title="Record waste" />
            <div className="bk-form">
              <label><span>Item</span>
                <select value={wasteForm.product_id} onChange={(e) => setWasteForm((f) => ({ ...f, product_id: e.target.value }))} aria-label="Waste item">
                  <option value="">Choose</option>
                  {items.filter((i) => Number(i.stock_qty) > 0).map((i) => <option key={i.id} value={i.id}>{i.name} ({i.stock_qty} left)</option>)}
                </select>
              </label>
              <label><span>How many</span><input type="number" min={0} value={wasteForm.quantity} onChange={(e) => setWasteForm((f) => ({ ...f, quantity: e.target.value }))} aria-label="Waste quantity" /></label>
              <label><span>Why</span>
                <select value={wasteForm.reason} onChange={(e) => setWasteForm((f) => ({ ...f, reason: e.target.value }))} aria-label="Waste reason">
                  {WASTE_REASONS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
              </label>
              <button type="button" className="bk-primary" disabled={busy || !wasteForm.product_id || !(Number(wasteForm.quantity) > 0)} onClick={async () => {
                const ok = await run('/bakery/waste', { product_id: wasteForm.product_id, quantity: Number(wasteForm.quantity), reason: wasteForm.reason }, 'Waste recorded');
                if (ok) setWasteForm((f) => ({ ...f, product_id: '', quantity: '' }));
              }}>Record waste</button>
            </div>
          </section>
          <section className="bk-box bk-scroll" aria-label="Waste list">
            <Head icon="clock" title="Recent waste" />
            <table>
              <thead><tr><th>Item</th><th>How many</th><th>Why</th>{role !== 'bakery_baker' ? <th>Cost</th> : null}</tr></thead>
              <tbody>
                {waste.map((w) => <tr key={w.id}><td>{w.product_name}</td><td>{w.quantity}</td><td>{label(WASTE_REASONS, w.reason)}</td>{role !== 'bakery_baker' ? <td className="bk-num">{money(w.total_cost)}</td> : null}</tr>)}
                {waste.length === 0 ? <tr><td colSpan={4} className="bk-muted">No waste recorded.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === 'stock' && stock && (
        <>
          <div className="bk-grid2 bk-even">
            <section className="bk-box" aria-label="Buy stock">
              <Head icon="cart" title="Buy stock" />
              <div className="bk-form">
                <label className="bk-span2"><span>What you bought</span>
                  <select value={buyForm.product_id} onChange={(e) => setBuyForm({ ...buyForm, product_id: e.target.value })} aria-label="What you bought">
                    <option value="">Choose</option>
                    {stock.items.filter((s: Row) => s.is_active).map((s: Row) => <option key={s.id} value={s.id}>{s.name} ({s.kind === 'item' ? 'for sale' : 'ingredient'})</option>)}
                  </select>
                </label>
                <label><span>How many</span><input type="number" min="0" step="0.001" value={buyForm.quantity} onChange={(e) => setBuyForm({ ...buyForm, quantity: e.target.value })} aria-label="How many bought" /></label>
                <label><span>Cost each</span><input type="number" min="0" step="0.01" value={buyForm.unit_cost} onChange={(e) => setBuyForm({ ...buyForm, unit_cost: e.target.value })} aria-label="Cost each" /></label>
                <label><span>Paid with</span>
                  <select value={buyForm.paid_with} onChange={(e) => setBuyForm({ ...buyForm, paid_with: e.target.value })} aria-label="Paid with">
                    {PAID_WITH.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                    <option value="credit">Not paid yet (owe the supplier)</option>
                  </select>
                </label>
                <label><span>Supplier</span><input value={buyForm.supplier} onChange={(e) => setBuyForm({ ...buyForm, supplier: e.target.value })} aria-label="Supplier" /></label>
                <div className="bk-sumline"><span>Total</span><b>{money(Number(buyForm.quantity || 0) * Number(buyForm.unit_cost || 0))}</b></div>
                <button
                  type="button" className="bk-primary" disabled={busy || !buyForm.product_id || !(Number(buyForm.quantity) > 0)}
                  onClick={async () => {
                    const ok = await run('/bakery/stock/receive', {
                      product_id: buyForm.product_id, quantity: Number(buyForm.quantity), unit_cost: Number(buyForm.unit_cost || 0),
                      paid_with: buyForm.paid_with, supplier: buyForm.supplier.trim() || null,
                    }, 'Stock received');
                    if (ok) setBuyForm({ product_id: '', quantity: '', unit_cost: '', paid_with: buyForm.paid_with, supplier: '' });
                  }}
                >Receive stock</button>
              </div>
            </section>
            <section className="bk-box" aria-label="Add to stock list">
              <Head icon="plus" title="Add something new" />
              <div className="bk-form">
                <label className="bk-span2"><span>Name</span><input value={stockForm.name} onChange={(e) => setStockForm({ ...stockForm, name: e.target.value })} aria-label="New name" /></label>
                <label><span>It is</span>
                  <select value={stockForm.kind} onChange={(e) => setStockForm({ ...stockForm, kind: e.target.value })} aria-label="Kind">
                    <option value="item">Something we sell</option>
                    <option value="ingredient">An ingredient</option>
                  </select>
                </label>
                {stockForm.kind === 'item' ? (
                  <label><span>Selling price</span><input type="number" min="0" step="0.01" value={stockForm.price} onChange={(e) => setStockForm({ ...stockForm, price: e.target.value })} aria-label="New selling price" /></label>
                ) : null}
                <label><span>Warn me at</span><input type="number" min="0" value={stockForm.reorder_level} placeholder="Low stock level" onChange={(e) => setStockForm({ ...stockForm, reorder_level: e.target.value })} aria-label="New low stock level" /></label>
                <button
                  type="button" className="bk-primary" disabled={busy || !stockForm.name.trim() || (stockForm.kind === 'item' && !(Number(stockForm.price) > 0))}
                  onClick={async () => {
                    const ok = await run('/bakery/stock', {
                      name: stockForm.name.trim(), kind: stockForm.kind,
                      price: stockForm.kind === 'item' ? Number(stockForm.price) : null,
                      reorder_level: stockForm.reorder_level ? Number(stockForm.reorder_level) : null,
                    }, 'Added');
                    if (ok) setStockForm({ name: '', kind: stockForm.kind, price: '', reorder_level: '' });
                  }}
                >Add</button>
              </div>
              <p className="bk-muted bk-small">Then use Buy stock to put the first quantity in.</p>
            </section>
          </div>
          {[['item', 'For sale'], ['ingredient', 'Ingredients']].map(([kind, title]) => {
            const rows = stock.items.filter((s: Row) => s.kind === kind && s.is_active);
            return (
              <section className="bk-box bk-scroll" key={kind} aria-label={title}>
                <div className="bk-row bk-spread">
                  <Head icon={kind === 'item' ? 'bread' : 'leaf'} title={title} />
                  <span className="bk-muted">Worth {money(rows.reduce((t: number, r: Row) => t + Number(r.value || 0), 0))} at cost</span>
                </div>
                <table>
                  <thead><tr><th>Name</th><th>In stock</th><th>Cost each</th>{kind === 'item' ? <th>Price</th> : null}<th>Worth</th><th /></tr></thead>
                  <tbody>
                    {rows.map((r: Row) => (
                      <tr key={r.id}>
                        <td>{r.name}{kind === 'item' && !r.has_recipe ? <div className="bk-muted">No recipe yet</div> : null}</td>
                        <td>{r.stock_qty}{r.low ? <> <span className="bk-pill bad">Low</span></> : null}</td>
                        <td className="bk-num">{money(r.cost_price)}</td>
                        {kind === 'item' ? <td className="bk-num">{money(r.price)}</td> : null}
                        <td className="bk-num">{money(r.value)}</td>
                        <td className="bk-row">
                          <button type="button" onClick={() => setDialog({ kind: 'edit', row: r, price: String(r.price), cost: String(r.cost_price), reorder: String(r.reorder_level) })}>Change</button>
                          <button type="button" className="bk-danger" onClick={() => run(`/bakery/stock/${r.id}`, { is_active: false }, `${r.name} put away`, 'PATCH')}>Stop using</button>
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 ? <tr><td colSpan={6} className="bk-muted">Nothing yet.</td></tr> : null}
                  </tbody>
                </table>
              </section>
            );
          })}
          <section className="bk-box bk-scroll" aria-label="Bought in">
            <Head icon="receipt" title="Recently bought" />
            <table>
              <thead><tr><th>Date</th><th>What</th><th>How many</th><th>Total</th><th>Paid with</th><th>Supplier</th></tr></thead>
              <tbody>
                {stock.receipts.map((r: Row) => (
                  <tr key={r.id}>
                    <td>{String(r.created_at || '').slice(0, 10)}</td><td>{r.name}</td><td>{r.quantity}</td><td className="bk-num">{money(r.total)}</td>
                    <td>{r.paid_with === 'credit' ? <span className="bk-pill bad">Owed</span> : label(PAID_WITH, r.paid_with)}</td><td>{r.supplier || '—'}</td>
                  </tr>
                ))}
                {stock.receipts.length === 0 ? <tr><td colSpan={6} className="bk-muted">Nothing bought in yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === 'expenses' && expenses && (
        <>
          <section className="bk-box" aria-label="Record an expense">
            <Head icon="plus" title="Record an expense" />
            <div className="bk-form">
              <label><span>What for</span>
                <select value={expenseForm.category} onChange={(e) => setExpenseForm({ ...expenseForm, category: e.target.value })} aria-label="What for">
                  {expenses.kinds.map((k: Row) => <option key={k.id} value={k.id}>{k.label}</option>)}
                </select>
              </label>
              <label className="bk-span2"><span>Details</span><input value={expenseForm.description} placeholder="e.g. November rent" onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })} aria-label="Details" /></label>
              <label><span>Amount</span><input type="number" min="0" step="0.01" value={expenseForm.amount} onChange={(e) => setExpenseForm({ ...expenseForm, amount: e.target.value })} aria-label="Amount" /></label>
              <label><span>Paid with</span>
                <select value={expenseForm.paid_with} onChange={(e) => setExpenseForm({ ...expenseForm, paid_with: e.target.value, from_till: e.target.value === 'cash' && expenseForm.from_till })} aria-label="Expense paid with">
                  {PAID_WITH.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
              </label>
              <label><span>Date</span><input type="date" max={iso(0)} value={expenseForm.spent_on} onChange={(e) => setExpenseForm({ ...expenseForm, spent_on: e.target.value })} aria-label="Expense date" /></label>
              {expenseForm.paid_with === 'cash' ? (
                <label className="bk-check"><input type="checkbox" checked={expenseForm.from_till} onChange={(e) => setExpenseForm({ ...expenseForm, from_till: e.target.checked })} /> <span>Taken from the till</span></label>
              ) : null}
              <button
                type="button" className="bk-primary" disabled={busy || expenseForm.description.trim().length < 2 || !(Number(expenseForm.amount) > 0)}
                onClick={async () => {
                  const ok = await run('/bakery/expenses', {
                    category: expenseForm.category, description: expenseForm.description.trim(), amount: Number(expenseForm.amount),
                    paid_with: expenseForm.paid_with, spent_on: expenseForm.spent_on, from_till: expenseForm.from_till,
                  }, 'Expense recorded');
                  if (ok) setExpenseForm({ ...expenseForm, description: '', amount: '', from_till: false });
                }}
              >Record expense</button>
            </div>
          </section>
          <section className="bk-box bk-scroll" aria-label="Expenses">
            <div className="bk-row bk-spread">
              <Head icon="wallet" title="Expenses" />
              <span className="bk-muted">This month {money(expenses.rows.filter((r: Row) => r.spent_on.slice(0, 7) === iso(0).slice(0, 7)).reduce((t: number, r: Row) => t + Number(r.amount), 0))}</span>
            </div>
            <table>
              <thead><tr><th>Date</th><th>What for</th><th>Details</th><th>Paid with</th><th>Amount</th></tr></thead>
              <tbody>
                {expenses.rows.map((r: Row) => (
                  <tr key={r.id}><td>{r.spent_on}</td><td>{r.category_label}</td><td>{r.description}</td><td>{label(PAID_WITH, r.paid_with)}{r.from_till ? ' · from till' : ''}</td><td className="bk-num">{money(r.amount)}</td></tr>
                ))}
                {expenses.rows.length === 0 ? <tr><td colSpan={5} className="bk-muted">No expenses yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === 'reports' && report && (
        <div className="deskdash bk-report">
          <section className="bk-box bk-noprint" aria-label="Report dates">
            <div className="bk-row bk-spread">
              <div className="bk-chips" role="group" aria-label="Period">
                {[
                  ['Today', iso(0), iso(0)],
                  ['Last 7 days', iso(-6), iso(0)],
                  ['This month', `${iso(0).slice(0, 8)}01`, iso(0)],
                  ['Last month', iso(-1, new Date(new Date().getFullYear(), new Date().getMonth(), 1)).slice(0, 8) + '01', iso(-1, new Date(new Date().getFullYear(), new Date().getMonth(), 1))],
                ].map(([text, start, end]) => (
                  <button key={text} type="button" className={range.start === start && range.end === end ? 'on' : ''} onClick={() => setRange({ start, end })}>{text}</button>
                ))}
              </div>
              <div className="bk-row">
                <input type="date" value={range.start} max={range.end} onChange={(e) => setRange((r) => ({ ...r, start: e.target.value }))} aria-label="Report from" style={{ width: 160 }} />
                <span>to</span>
                <input type="date" value={range.end} min={range.start} max={iso(0)} onChange={(e) => setRange((r) => ({ ...r, end: e.target.value }))} aria-label="Report to" style={{ width: 160 }} />
                <button type="button" onClick={() => window.print()}>Print</button>
                <button
                  type="button"
                  onClick={() => downloadCsv(`bakery-${range.start}-to-${range.end}.csv`, [
                    ['Item', 'Sold', 'Sales before tax', 'Cost', 'Profit', 'Margin %'],
                    ...report.by_item.map((r: Row) => [r.name, r.quantity, r.sales, r.cost, r.profit, r.margin_percent]),
                  ])}
                >Download CSV</button>
              </div>
            </div>
          </section>
          <p className="bk-muted">{range.start} to {range.end}, compared with {report.previous.start_date} to {report.previous.end_date}.</p>
          <DeskTiles tiles={reportTiles} />
          <div className="dd-grid2">
            {report.trend ? <section className="dd-box"><TrendChart trend={report.trend} /></section> : <section className="dd-box bk-muted">Choose 92 days or fewer to see the daily chart.</section>}
            <section className="dd-box" aria-label="Profit and loss">
              <Head icon="leaf" title="Profit and loss" />
              <div className="bk-pl">
                <div><span>Sales before tax</span><b>{money(report.revenue)}</b></div>
                <div><span>Cost of what sold</span><b>− {money(report.cost_of_sales)}</b></div>
                <div><span>Waste</span><b>− {money(report.waste_cost)}</b></div>
                <div className="sum"><span>Gross profit</span><b>{money(report.gross_profit)}</b></div>
                {report.expenses_by_kind.map((e: Row) => <div key={e.name}><span>{e.name}</span><b>− {money(e.total)}</b></div>)}
                <div className={`sum big${report.net_profit < 0 ? ' neg' : ''}`}><span>Net profit</span><b>{money(report.net_profit)}</b></div>
                <div className="note"><span>Tax collected for GRA</span><b>{money(report.tax)}</b></div>
                <div className="note"><span>Refunds</span><b>{report.refunds.count} · {money(report.refunds.total)}</b></div>
              </div>
            </section>
          </div>
          <section className="bk-box bk-scroll" aria-label="By item">
            <Head icon="bread" title="Item by item" />
            <table>
              <thead><tr><th>Item</th><th>Sold</th><th>Sales before tax</th><th>Cost</th><th>Profit</th><th>Margin</th></tr></thead>
              <tbody>
                {report.by_item.map((r: Row) => (
                  <tr key={r.name}><td>{r.name}</td><td>{r.quantity}</td><td className="bk-num">{money(r.sales)}</td><td className="bk-num">{money(r.cost)}</td><td className="bk-num">{money(r.profit)}</td><td><span className={`bk-pill ${r.margin_percent < 30 ? 'bad' : 'ok'}`}>{r.margin_percent}%</span></td></tr>
                ))}
                {report.by_item.length === 0 ? <tr><td colSpan={6} className="bk-muted">No sales in these dates.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <div className="bk-grid2 bk-even">
            <section className="bk-box" aria-label="Busy hours">
              <Head icon="clock" title="Busy hours" />
              {report.by_hour.length === 0 ? <p className="bk-muted">No sales in these dates.</p> : report.by_hour.map((h: Row) => (
                <div className="bk-hbar" key={h.hour}>
                  <span>{String(h.hour).padStart(2, '0')}:00</span>
                  <span className="bk-hbar-track"><span style={{ width: `${peak ? (h.total / peak) * 100 : 0}%` }} /></span>
                  <span>{money(h.total)} · {h.sales}</span>
                </div>
              ))}
            </section>
            <section className="bk-box" aria-label="How customers paid">
              <Head icon="cash" title="How customers paid" />
              {Object.entries(report.payments_by_method as Record<string, number>).map(([k, v]) => (
                <div className="bk-line" key={k}><span>{label(METHODS, k)}</span><b>{money(v)}</b></div>
              ))}
              {Object.keys(report.payments_by_method).length === 0 ? <p className="bk-muted">No money taken in these dates.</p> : null}
            </section>
            <section className="bk-box" aria-label="Waste by item">
              <Head icon="trash" title="Waste by item" />
              {report.waste_by_item.map((w: Row) => <div className="bk-line" key={w.name}><span>{w.quantity} {w.name}</span><b>{money(w.cost)}</b></div>)}
              {report.waste_by_item.length === 0 ? <p className="bk-muted">Nothing thrown away.</p> : null}
            </section>
            <section className="bk-box" aria-label="Orders and stock">
              <Head icon="box" title="Orders and stock" />
              <div className="bk-line"><span>Orders taken</span><b>{report.orders.taken} · {money(report.orders.value)}</b></div>
              <div className="bk-line"><span>Handed over</span><b>{report.orders.collected}</b></div>
              <div className="bk-line"><span>Cancelled</span><b>{report.orders.cancelled}</b></div>
              <div className="bk-line"><span>Deposits held now</span><b>{money(report.orders.deposits_held_now)}</b></div>
              <div className="bk-line"><span>Stock bought</span><b>{money(report.stock_bought)}</b></div>
              <div className="bk-line"><span>Stock worth now, at cost</span><b>{money(report.stock_value_now)}</b></div>
            </section>
          </div>
          <section className="bk-box bk-scroll" aria-label="Till and cash bags">
            <Head icon="bag" title="Till and cash bags closed" />
            <table>
              <thead><tr><th>Closed</th><th>Should have</th><th>Counted</th><th>Over or short</th></tr></thead>
              <tbody>
                {report.shifts.map((s: Row) => (
                  <tr key={s.id}>
                    <td>{String(s.closed_at || '').slice(0, 16).replace('T', ' ')}</td><td className="bk-num">{money(s.expected_cash)}</td><td className="bk-num">{money(s.counted_cash)}</td>
                    <td>{Number(s.over_short) === 0 ? 'Exact' : <span className="bk-pill bad">{Number(s.over_short) < 0 ? 'Short' : 'Over'} {money(Math.abs(s.over_short))}</span>}</td>
                  </tr>
                ))}
                {report.shifts.length === 0 ? <tr><td colSpan={4} className="bk-muted">None closed in these dates.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  );
}

export default function BakeryPage() {
  return (
    <Suspense fallback={<div className="bakery"><p>Loading…</p></div>}>
      <BakeryDesk />
    </Suspense>
  );
}
