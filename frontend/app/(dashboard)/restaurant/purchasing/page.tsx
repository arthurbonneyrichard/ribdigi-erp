'use client';

/**
 * Restaurant purchasing: order ingredients from suppliers and receive the delivery.
 * Uses the shared purchasing engine (purchase orders, goods received, supplier balances)
 * with restaurant words and three steps: Order → Sent → Received.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { dayAndTime, money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Tab = 'orders' | 'suppliers';
type Line = { product_id: string; quantity: string; unit_price: string };
type Sheet =
  | { kind: 'new-order'; lines: Line[]; supplierId?: string }
  | { kind: 'order'; po: Row }
  | { kind: 'add-supplier' }
  | { kind: 'market' }
  | null;

const OPEN = new Set(['draft', 'sent', 'partially_received']);
const STATUS_WORDS: Record<string, string> = {
  draft: 'Not sent yet',
  sent: 'Waiting for delivery',
  partially_received: 'Part delivered',
  received: 'Delivered',
  cancelled: 'Cancelled',
};

function qty(value: unknown) {
  const n = Number(value || 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function blankLine(): Line {
  return { product_id: '', quantity: '', unit_price: '' };
}

export default function RestaurantPurchasingPage() {
  const router = useRouter();
  const tab: Tab = useSearchParams().get('tab') === 'suppliers' ? 'suppliers' : 'orders';
  const setTab = (next: Tab) => router.replace(next === 'orders' ? '?' : `?tab=${next}`, { scroll: false });
  const [orders, setOrders] = useState<Row[]>([]);
  const [suppliers, setSuppliers] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [menuIds, setMenuIds] = useState<Set<string>>(new Set());
  const [low, setLow] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showDone, setShowDone] = useState(false);
  const [sheet, setSheet] = useState<Sheet>(null);

  const load = useCallback(async () => {
    try {
      const [poRes, supRes, prodRes, recipeRes, lowRes] = await Promise.all([
        api('/purchasing/orders'),
        api('/suppliers'),
        api('/products?is_active=true'),
        api('/restaurant/recipes').catch(() => ({ data: [] })),
        api('/purchasing/suggestions/low-stock?include_open=true').catch(() => ({ data: { lines: [] } })),
      ]);
      setOrders(poRes?.data || []);
      setSuppliers(((supRes?.data as Row[]) || []).filter((s) => s.status !== 'inactive'));
      const list = prodRes?.data;
      const all: Row[] = Array.isArray(list) ? list : list?.items || [];
      const menu = new Set<string>(((recipeRes?.data as Row[]) || []).map((r) => r.product_id));
      for (const p of all) if (p.prep_station === 'kitchen' || p.prep_station === 'bar') menu.add(p.id);
      setProducts(all);
      setMenuIds(menu);
      setLow(((lowRes?.data?.lines as Row[]) || []).filter((l) => !menu.has(l.product_id)));
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ingredients = useMemo(() => products.filter((p) => !menuIds.has(p.id)), [products, menuIds]);
  const productName = useMemo(() => Object.fromEntries(products.map((p) => [p.id, p.name])), [products]);
  const supplierName = useMemo(() => Object.fromEntries(suppliers.map((s) => [s.id, s.name])), [suppliers]);

  const openOrders = orders.filter((o) => OPEN.has(o.status));
  const shown = showDone ? orders : openOrders;
  const waitingValue = openOrders.reduce((s, o) => s + Number(o.total_amount || 0), 0);
  const owed = suppliers.reduce((s, x) => s + Math.max(0, Number(x.balance || 0)), 0);

  function startOrder(fromLow: boolean) {
    const lines = fromLow
      ? low.map((l) => ({
          product_id: l.product_id,
          quantity: qty(Math.max(1, Number(l.suggested_order_qty || 0))),
          unit_price: String(products.find((p) => p.id === l.product_id)?.cost_price ?? ''),
        }))
      : [blankLine()];
    setSheet({ kind: 'new-order', lines: lines.length ? lines : [blankLine()] });
  }

  async function done(message: string) {
    setSheet(null);
    setNotice(message);
    await load();
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Purchasing</h1>
          <p>Order ingredients from your suppliers, then receive the delivery into stock.</p>
        </div>
        <div className="rd-head-actions">
          <Link className="rd-linkish" href="/restaurant/ingredients">← Stock</Link>
          {tab === 'orders' ? (
            <button type="button" aria-label="Record a market run" onClick={() => setSheet({ kind: 'market' })}>
              Market run
            </button>
          ) : null}
          {tab === 'orders' ? (
            <button type="button" className="rd-primary" aria-label="New supplier order" onClick={() => startOrder(false)}>
              + New order
            </button>
          ) : (
            <button type="button" className="rd-primary" aria-label="Add a supplier" onClick={() => setSheet({ kind: 'add-supplier' })}>
              + Supplier
            </button>
          )}
        </div>
      </header>

      <div className="rd-tabs" role="tablist" aria-label="Purchasing sections">
        <button type="button" role="tab" aria-selected={tab === 'orders'} className={tab === 'orders' ? 'on' : ''} onClick={() => setTab('orders')}>
          Orders <small>{openOrders.length}</small>
        </button>
        <button type="button" role="tab" aria-selected={tab === 'suppliers'} className={tab === 'suppliers' ? 'on' : ''} onClick={() => setTab('suppliers')}>
          Suppliers <small>{suppliers.length}</small>
        </button>
      </div>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      {loading ? <div className="rd-empty">Loading purchasing…</div> : null}

      {!loading && tab === 'orders' ? (
        <>
          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Waiting to arrive</span>
              <strong>{money(waitingValue)}</strong>
              <small>{openOrders.length} open {openOrders.length === 1 ? 'order' : 'orders'}</small>
            </div>
            <div className="rd-kpi">
              <span>Ingredients running low</span>
              <strong>{low.length}</strong>
              {low.length ? (
                <button type="button" className="rd-link" aria-label="Order the low ingredients" onClick={() => startOrder(true)}>
                  Order them →
                </button>
              ) : (
                <small>All stocked</small>
              )}
            </div>
            <div className="rd-kpi">
              <span>Owed to suppliers</span>
              <strong>{money(owed)}</strong>
              <small>
                <Link href="/restaurant/payables">Pay suppliers</Link>
              </small>
            </div>
          </div>

          <div className="rd-chips" role="tablist" aria-label="Which orders">
            <button type="button" role="tab" aria-selected={!showDone} className={!showDone ? 'on' : ''} onClick={() => setShowDone(false)}>
              Open <small>{openOrders.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={showDone} className={showDone ? 'on' : ''} onClick={() => setShowDone(true)}>
              All <small>{orders.length}</small>
            </button>
          </div>

          <div className="rd-list" aria-label="Supplier orders">
            {shown.length === 0 ? (
              <div className="rd-empty">
                <strong>{showDone ? 'No supplier orders yet' : 'Nothing on order'}</strong>
                {low.length ? `${low.length === 1 ? '1 ingredient is' : `${low.length} ingredients are`} running low. Order in one go with “Order them”.` : 'Start a new order when you need stock.'}
              </div>
            ) : null}
            {shown.map((po) => {
              const items: Row[] = po.items || [];
              const names = items.map((i) => productName[i.product_id] || i.product_name || 'Item');
              return (
                <button key={po.id} type="button" className="rd-row" aria-label={`Open order ${po.po_number}`} onClick={() => setSheet({ kind: 'order', po })}>
                  <span className="when">{dayAndTime(po.created_at)}</span>
                  <span className="who">
                    <strong>{supplierName[po.supplier_id] || 'Supplier'}</strong>
                    <small>
                      {po.po_number} · {names.slice(0, 3).join(', ')}
                      {names.length > 3 ? ` +${names.length - 3}` : ''}
                    </small>
                  </span>
                  <span className={`rd-pill ${po.status === 'draft' ? 'wait' : po.status === 'cancelled' ? 'grey' : ''}`}>
                    {STATUS_WORDS[po.status] || po.status}
                  </span>
                  <span className="amt">{money(po.total_amount)}</span>
                </button>
              );
            })}
          </div>
        </>
      ) : null}

      {!loading && tab === 'suppliers' ? (
        <div className="rd-list" aria-label="Suppliers">
          {suppliers.length === 0 ? (
            <div className="rd-empty">
              <strong>No suppliers yet</strong>Add the market, butcher or distributor you buy from.
            </div>
          ) : null}
          {suppliers.map((s) => {
            const theirs = orders.filter((o) => o.supplier_id === s.id);
            const waiting = theirs.filter((o) => OPEN.has(o.status)).length;
            return (
              <div key={s.id} className="rd-stock-row">
                <div className="what">
                  <strong>{s.name}</strong>
                  <small>{[s.phone, s.email].filter(Boolean).join(' · ') || 'No contact saved'}</small>
                </div>
                <div className="onhand">
                  <strong>{theirs.length}</strong>
                  <small>{waiting ? `${waiting} waiting` : 'orders'}</small>
                </div>
                <span className="value">{Number(s.balance || 0) > 0 ? `${money(s.balance)} owed` : 'Nothing owed'}</span>
                <div className="acts">
                  <button
                    type="button"
                    className="rd-go"
                    aria-label={`Order from ${s.name}`}
                    onClick={() => {
                      setTab('orders');
                      setSheet({ kind: 'new-order', lines: [blankLine()], supplierId: s.id });
                    }}
                  >
                    Order
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      {sheet?.kind === 'new-order' ? (
        <NewOrderSheet
          initial={sheet.lines}
          initialSupplier={sheet.supplierId}
          suppliers={suppliers}
          ingredients={ingredients}
          onClose={() => setSheet(null)}
          onDone={done}
        />
      ) : null}
      {sheet?.kind === 'order' ? (
        <OrderSheet po={sheet.po} supplier={supplierName[sheet.po.supplier_id] || 'Supplier'} productName={productName} onClose={() => setSheet(null)} onDone={done} />
      ) : null}
      {sheet?.kind === 'add-supplier' ? <SupplierSheet onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === 'market' ? <MarketRunSheet suppliers={suppliers} ingredients={ingredients} onClose={() => setSheet(null)} onDone={done} /> : null}
    </div>
  );
}

function NewOrderSheet({
  initial,
  initialSupplier,
  suppliers,
  ingredients,
  onClose,
  onDone,
}: {
  initial: Line[];
  initialSupplier?: string;
  suppliers: Row[];
  ingredients: Row[];
  onClose: () => void;
  onDone: (message: string) => Promise<void>;
}) {
  const [supplierId, setSupplierId] = useState(initialSupplier || (suppliers.length === 1 ? suppliers[0].id : ''));
  const [lines, setLines] = useState<Line[]>(initial);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const total = lines.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_price || 0), 0);

  function setLine(index: number, patch: Partial<Line>) {
    setLines((prev) =>
      prev.map((l, i) => {
        if (i !== index) return l;
        const next = { ...l, ...patch };
        if (patch.product_id && !l.unit_price) {
          const cost = ingredients.find((p) => p.id === patch.product_id)?.cost_price;
          if (cost) next.unit_price = String(cost);
        }
        return next;
      }),
    );
  }

  async function save(send: boolean) {
    const ready = lines.filter((l) => l.product_id && Number(l.quantity) > 0);
    if (!supplierId) return setError('Pick the supplier.');
    if (!ready.length) return setError('Add at least one ingredient with a quantity.');
    setBusy(true);
    setError('');
    try {
      const res = await api('/purchasing/orders', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supplierId,
          notes: notes.trim() || null,
          items: ready.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity), unit_price: Number(l.unit_price || 0) })),
        }),
      });
      const po = res?.data || {};
      if (send && po.id) await api(`/purchasing/orders/${po.id}/issue`, { method: 'POST' });
      await onDone(send ? `Order ${po.po_number || ''} sent` : `Order ${po.po_number || ''} saved, not sent yet`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label="New supplier order" onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>New supplier order</h2>
            <p>Prices start at each ingredient’s last cost.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Supplier</span>
            <select aria-label="Supplier" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              <option value="">Pick a supplier</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
        </div>
        {!suppliers.length ? <p className="rd-hint-line">Add a supplier first under the Suppliers tab.</p> : null}
        <div className="rd-po-lines">
          <div className="rd-po-head">
            <span>Ingredient</span>
            <span>Qty</span>
            <span>Cost each</span>
            <span className="sum">Line</span>
            <span />
          </div>
          {lines.map((line, i) => (
            <div key={i} className="rd-po-line">
              <select aria-label={`Ingredient ${i + 1}`} value={line.product_id} onChange={(e) => setLine(i, { product_id: e.target.value })}>
                <option value="">Pick an ingredient</option>
                {ingredients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.unit_name ? ` (${p.unit_name})` : ''}
                  </option>
                ))}
              </select>
              <input aria-label={`Quantity ${i + 1}`} inputMode="decimal" value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value.replace(/[^0-9.]/g, '') })} />
              <input aria-label={`Cost each ${i + 1}`} inputMode="decimal" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value.replace(/[^0-9.]/g, '') })} />
              <span className="sum">{money(Number(line.quantity || 0) * Number(line.unit_price || 0))}</span>
              <button type="button" aria-label={`Remove line ${i + 1}`} onClick={() => setLines((prev) => (prev.length > 1 ? prev.filter((_, j) => j !== i) : [blankLine()]))}>
                ×
              </button>
            </div>
          ))}
          <button type="button" className="rd-link" onClick={() => setLines((prev) => [...prev, blankLine()])}>
            + Add ingredient
          </button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Note to supplier (optional)</span>
            <input aria-label="Order note" placeholder="Deliver before 9am" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>
        <div className="rd-po-total">
          <span>Before tax</span>
          <strong>{money(total)}</strong>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" aria-label="Save order without sending" disabled={busy} onClick={() => void save(false)}>
            Save, send later
          </button>
          <button type="button" className="rd-primary" aria-label="Send order to supplier" disabled={busy} onClick={() => void save(true)}>
            {busy ? 'Saving…' : 'Send order'}
          </button>
        </div>
      </aside>
    </div>
  );
}

function OrderSheet({
  po,
  supplier,
  productName,
  onClose,
  onDone,
}: {
  po: Row;
  supplier: string;
  productName: Record<string, string>;
  onClose: () => void;
  onDone: (message: string) => Promise<void>;
}) {
  const items: Row[] = po.items || [];
  const [received, setReceived] = useState<Record<string, string>>(() =>
    Object.fromEntries(items.map((i) => [i.id, qty(i.outstanding_qty)])),
  );
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const canReceive = po.status === 'draft' || po.status === 'sent' || po.status === 'partially_received';
  const steps = ['draft', 'sent', 'received'];
  const at = po.status === 'partially_received' ? 1 : steps.indexOf(po.status);

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError('');
    try {
      await onDone(await fn());
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  function receive() {
    return run(async () => {
      const lines = items
        .map((i) => ({ i, n: Number(received[i.id] || 0) }))
        .filter(({ n }) => n > 0);
      if (!lines.length) throw new Error('Enter what arrived.');
      // An unsent order goes out the moment its delivery is booked.
      if (po.status === 'draft') await api(`/purchasing/orders/${po.id}/issue`, { method: 'POST' });
      await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({
          purchase_order_id: po.id,
          items: lines.map(({ i, n }) => ({ po_item_id: i.id, received_qty: n, accepted_qty: n })),
        }),
      });
      return `Delivery from ${supplier} is in stock`;
    });
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={`Order ${po.po_number}`} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{supplier}</h2>
            <p>
              {po.po_number} · {dayAndTime(po.created_at)}
            </p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        {po.status === 'cancelled' ? (
          <span className="rd-pill grey">Cancelled</span>
        ) : (
          <div className="rd-steps" aria-label="Order progress">
            {['Ordered', po.status === 'partially_received' ? 'Part delivered' : 'Sent', 'Delivered'].map((label, i) => (
              <span key={label} className={i < at || po.status === 'received' ? 'done' : i === at ? 'now' : ''}>
                {label}
              </span>
            ))}
          </div>
        )}
        <div className="rd-po-lines">
          <div className="rd-po-head">
            <span>Ingredient</span>
            <span>Ordered</span>
            <span>{canReceive ? 'Arrived now' : 'Received'}</span>
            <span className="sum">Line</span>
            <span />
          </div>
          {items.map((i) => (
            <div key={i.id} className="rd-po-line">
              <span>
                <strong>{productName[i.product_id] || i.product_name || 'Item'}</strong>
                <br />
                <small>{money(i.unit_price)} each{Number(i.received_qty) > 0 ? ` · ${qty(i.received_qty)} in already` : ''}</small>
              </span>
              <span>{qty(i.quantity)}</span>
              {canReceive && Number(i.outstanding_qty) > 0 ? (
                <input
                  aria-label={`Arrived ${productName[i.product_id] || 'item'}`}
                  inputMode="decimal"
                  value={received[i.id] ?? ''}
                  onChange={(e) => setReceived((prev) => ({ ...prev, [i.id]: e.target.value.replace(/[^0-9.]/g, '') }))}
                />
              ) : (
                <span>{qty(i.received_qty)}</span>
              )}
              <span className="sum">{money(i.line_total)}</span>
              <span />
            </div>
          ))}
        </div>
        <div className="rd-po-total">
          <span>Order total (with tax)</span>
          <strong>{money(po.total_amount)}</strong>
        </div>
        {po.notes ? <p className="rd-hint-line">Note: {po.notes}</p> : null}
        {cancelling ? (
          <div className="rd-form-grid">
            <label className="rd-span">
              <span>Why cancel?</span>
              <input aria-label="Cancel reason" placeholder="Supplier out of stock" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            </label>
          </div>
        ) : null}
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          {cancelling ? (
            <>
              <button type="button" onClick={() => setCancelling(false)}>Keep order</button>
              <button
                type="button"
                className="rd-danger"
                aria-label="Confirm cancel order"
                disabled={busy || !reason.trim()}
                onClick={() =>
                  void run(async () => {
                    await api(`/purchasing/orders/${po.id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) });
                    return `Order ${po.po_number} cancelled`;
                  })
                }
              >
                Cancel order
              </button>
            </>
          ) : (
            <>
              {po.can_cancel ? (
                <button type="button" className="rd-danger" aria-label="Cancel this order" onClick={() => setCancelling(true)}>
                  Cancel order
                </button>
              ) : (
                <button type="button" onClick={onClose}>Close</button>
              )}
              {po.status === 'draft' ? (
                <button
                  type="button"
                  aria-label="Mark order sent"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await api(`/purchasing/orders/${po.id}/issue`, { method: 'POST' });
                      return `Order ${po.po_number} sent`;
                    })
                  }
                >
                  Mark sent
                </button>
              ) : null}
              {canReceive ? (
                <button type="button" className="rd-primary full" aria-label="Receive delivery" disabled={busy} onClick={() => void receive()}>
                  {busy ? 'Saving…' : 'Receive delivery into stock'}
                </button>
              ) : null}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

/**
 * A market run: ingredients bought and paid for on the spot. Recorded as a supplier order that is
 * sent, delivered and paid in one go, so stock, cost and cash all move together. No VAT on market buys.
 */
function MarketRunSheet({
  suppliers,
  ingredients,
  onClose,
  onDone,
}: {
  suppliers: Row[];
  ingredients: Row[];
  onClose: () => void;
  onDone: (message: string) => Promise<void>;
}) {
  const [where, setWhere] = useState('Market');
  const [method, setMethod] = useState('cash');
  const [lines, setLines] = useState<Line[]>([blankLine()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const total = lines.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_price || 0), 0);

  function setLine(index: number, patch: Partial<Line>) {
    setLines((prev) =>
      prev.map((l, i) => {
        if (i !== index) return l;
        const next = { ...l, ...patch };
        if (patch.product_id && !l.unit_price) {
          const cost = ingredients.find((p) => p.id === patch.product_id)?.cost_price;
          if (cost) next.unit_price = String(cost);
        }
        return next;
      }),
    );
  }

  async function save() {
    const ready = lines.filter((l) => l.product_id && Number(l.quantity) > 0);
    if (!where.trim()) return setError('Say where you bought it.');
    if (!ready.length) return setError('Add at least one ingredient with a quantity.');
    if (ready.some((l) => !(Number(l.unit_price) > 0))) return setError('Enter what each ingredient cost.');
    setBusy(true);
    setError('');
    let step = 'saving the seller';
    try {
      let seller = suppliers.find((s) => String(s.name).trim().toLowerCase() === where.trim().toLowerCase());
      if (!seller) seller = (await api('/suppliers', { method: 'POST', body: JSON.stringify({ name: where.trim() }) }))?.data;
      if (!seller) throw new Error('The seller could not be saved.');
      step = 'saving the purchase';
      const po = (
        await api('/purchasing/orders', {
          method: 'POST',
          body: JSON.stringify({
            supplier_id: seller.id,
            notes: 'Market run',
            items: ready.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity), unit_price: Number(l.unit_price), tax_rate: 0 })),
          }),
        })
      )?.data;
      step = `putting ${po.po_number} into stock`;
      await api(`/purchasing/orders/${po.id}/issue`, { method: 'POST' });
      await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({
          purchase_order_id: po.id,
          notes: 'Market run',
          items: (po.items as Row[]).map((i) => ({ po_item_id: i.id, received_qty: Number(i.quantity), accepted_qty: Number(i.quantity) })),
        }),
      });
      step = `recording the payment for ${po.po_number}`;
      await api(`/suppliers/${seller.id}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: seller.id,
          amount: Number(po.total_amount),
          payment_method: method,
          purchase_order_id: po.id,
          reference: 'Market run',
        }),
      });
      await onDone(`Market run of ${money(po.total_amount)} is in stock and paid`);
    } catch (err) {
      setError(`Stopped while ${step}: ${problem(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label="Market run" onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>Market run</h2>
            <p>Ingredients bought and paid for on the spot. They go into stock and the money comes off your cash.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label>
            <span>Bought from</span>
            <input aria-label="Bought from" list="rd-market-sellers" value={where} onChange={(e) => setWhere(e.target.value)} />
            <datalist id="rd-market-sellers">
              {suppliers.map((s) => (
                <option key={s.id} value={s.name} />
              ))}
            </datalist>
          </label>
          <div>
            <span className="rd-field-label">Paid with</span>
            <div className="rd-chips" role="radiogroup" aria-label="Market run paid with">
              {([['cash', 'Cash'], ['mobile_money', 'MoMo']] as const).map(([key, label]) => (
                <button key={key} type="button" role="radio" aria-checked={method === key} className={method === key ? 'on' : ''} onClick={() => setMethod(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="rd-po-lines">
          <div className="rd-po-head">
            <span>Ingredient</span>
            <span>Qty</span>
            <span>Cost each</span>
            <span className="sum">Line</span>
            <span />
          </div>
          {lines.map((line, i) => (
            <div key={i} className="rd-po-line">
              <select aria-label={`Market ingredient ${i + 1}`} value={line.product_id} onChange={(e) => setLine(i, { product_id: e.target.value })}>
                <option value="">Pick an ingredient</option>
                {ingredients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.unit_name ? ` (${p.unit_name})` : ''}
                  </option>
                ))}
              </select>
              <input aria-label={`Market quantity ${i + 1}`} inputMode="decimal" value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value.replace(/[^0-9.]/g, '') })} />
              <input aria-label={`Market cost each ${i + 1}`} inputMode="decimal" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value.replace(/[^0-9.]/g, '') })} />
              <span className="sum">{money(Number(line.quantity || 0) * Number(line.unit_price || 0))}</span>
              <button type="button" aria-label={`Remove market line ${i + 1}`} onClick={() => setLines((prev) => (prev.length > 1 ? prev.filter((_, j) => j !== i) : [blankLine()]))}>
                ×
              </button>
            </div>
          ))}
          <button type="button" className="rd-link" onClick={() => setLines((prev) => [...prev, blankLine()])}>
            + Add ingredient
          </button>
        </div>
        <div className="rd-po-total">
          <span>Paid</span>
          <strong>{money(total)}</strong>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save market run" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : `Save ${money(total)}`}
          </button>
        </div>
      </aside>
    </div>
  );
}

function SupplierSheet({ onClose, onDone }: { onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (!name.trim()) return setError('Name the supplier.');
    const cleanPhone = phone.replace(/[\s-]/g, '');
    if (cleanPhone && !/^\+\d{8,15}$/.test(cleanPhone)) return setError('Phone needs the country code, like +233 24 123 4567.');
    setBusy(true);
    setError('');
    try {
      await api('/suppliers', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), phone: cleanPhone || null, email: email.trim() || null }),
      });
      await onDone(`${name.trim()} added`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label="New supplier" onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>New supplier</h2>
            <p>Who you buy ingredients or drinks from.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Name</span>
            <input aria-label="Supplier name" placeholder="Makola market, Kofi's poultry…" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          <label>
            <span>Phone</span>
            <input aria-label="Supplier phone" placeholder="+233 24 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            <span>Email</span>
            <input aria-label="Supplier email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save supplier" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}
