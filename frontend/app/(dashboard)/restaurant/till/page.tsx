'use client';

/**
 * Restaurant till. Its own screen, not the retail POS: every sale is a restaurant
 * order (restaurant_orders), so table bills, takeaway and walk-up all go through
 * the kitchen flow and never touch the retail till tables.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../../../lib/api';
import { formatMoney } from '../../../../lib/format';
import './restaurant-till.css';

type Row = Record<string, any>;
type Mode = 'dine_in' | 'takeaway' | 'delivery';
type Method = 'cash' | 'card' | 'mobile_money' | 'wallet';

type DraftLine = {
  key: string;
  product_id: string;
  name: string;
  price: number;
  quantity: number;
  modifier_ids: string[];
  modifier_names: string[];
  modifier_total: number;
  note: string;
};

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: 'dine_in', label: 'Dine in', hint: 'Pick a table' },
  { id: 'takeaway', label: 'Takeaway', hint: 'Name on the bag' },
  { id: 'delivery', label: 'Delivery', hint: 'Address and phone' },
];

const METHODS: { id: Method; label: string }[] = [
  { id: 'cash', label: 'Cash' },
  { id: 'card', label: 'Card' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'wallet', label: 'Wallet' },
];

const OPEN_STATUSES = new Set(['open', 'sent', 'preparing', 'ready']);

const STATUS_WORDS: Record<string, string> = {
  open: 'Not sent',
  sent: 'In the kitchen',
  preparing: 'Cooking',
  ready: 'Ready',
};

const TABLE_WORDS: Record<string, string> = {
  available: 'Free',
  occupied: 'Seated',
  reserved: 'Reserved',
  held: 'Held',
};

function money(value: unknown) {
  return formatMoney(Number(value || 0));
}

function detail(err: unknown): string {
  const raw = (err as any)?.message || String(err || '');
  return raw || 'Something went wrong. Try again.';
}

/** Extras are charged once per line, the way the restaurant bill adds them. */
function lineAmount(line: DraftLine) {
  return line.quantity * line.price + line.modifier_total;
}

function isMenuItem(row: Row, recipeMenu: Set<string>, recipeIngredient: Set<string>) {
  if (row.is_active === false) return false;
  const station = String(row.prep_station || '');
  if (recipeIngredient.has(row.id) && !recipeMenu.has(row.id)) return false;
  return recipeMenu.has(row.id) || station === 'kitchen' || station === 'bar';
}

export default function RestaurantTillPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const [menu, setMenu] = useState<Row[]>([]);
  const [soldOut, setSoldOut] = useState<Set<string>>(new Set());
  const [groups, setGroups] = useState<Row[]>([]);
  const [tables, setTables] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [stores, setStores] = useState<Row[]>([]);
  const [storeId, setStoreId] = useState('');

  const [mode, setMode] = useState<Mode>('dine_in');
  const [tableId, setTableId] = useState('');
  const [guest, setGuest] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState<DraftLine[]>([]);
  const [current, setCurrent] = useState<Row | null>(null);

  const [tablePicker, setTablePicker] = useState(false);
  const [billsOpen, setBillsOpen] = useState(false);
  const [editing, setEditing] = useState<DraftLine | null>(null);
  const [paying, setPaying] = useState<Row | null>(null);
  const [method, setMethod] = useState<Method>('cash');
  const [tendered, setTendered] = useState('');
  const [done, setDone] = useState<{ number: string; total: number; change: number; method: Method } | null>(null);
  const [shift, setShift] = useState<Row | null>(null);
  const [shiftOpen, setShiftOpen] = useState(false);
  const [payAfterShift, setPayAfterShift] = useState(false);
  const deepLinked = useRef(false);

  const load = useCallback(async () => {
    setError('');
    try {
      const [productRes, recipeRes, soldRes, groupRes, tableRes, orderRes, storeRes, shiftRes] = await Promise.all([
        api('/products?is_active=true'),
        api('/restaurant/recipes').catch(() => ({ data: [] })),
        api('/restaurant/sold-out').catch(() => ({ data: { items: [] } })),
        api('/restaurant/modifiers').catch(() => ({ data: [] })),
        api('/restaurant/tables'),
        api('/restaurant/orders'),
        api('/stores?is_active=true').catch(() => ({ data: [] })),
        api('/restaurant/till/shift').catch(() => ({ data: null })),
      ]);
      const recipes: Row[] = recipeRes?.data || [];
      const recipeMenu = new Set(recipes.map((r) => r.product_id));
      const recipeIngredient = new Set(recipes.flatMap((r) => (r.lines || []).map((l: Row) => l.ingredient_id)));
      const products: Row[] = productRes?.data || [];
      setMenu(products.filter((row) => isMenuItem(row, recipeMenu, recipeIngredient)));
      setSoldOut(new Set(((soldRes?.data?.items as Row[]) || []).map((r) => r.id)));
      setGroups(groupRes?.data || []);
      setTables((tableRes?.data || []).filter((t: Row) => t.is_active !== false));
      setOrders(orderRes?.data || []);
      const storeRows: Row[] = storeRes?.data || [];
      setStores(storeRows);
      setStoreId((prev) => prev || shiftRes?.data?.store_id || storeRows[0]?.id || '');
      setShift(shiftRes?.data || null);
    } catch (err) {
      setError(detail(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // The Orders and Bills screens open a bill here with ?order=<id> (and &pay=1 to take payment).
  useEffect(() => {
    if (loading || deepLinked.current || typeof window === 'undefined') return;
    deepLinked.current = true;
    const params = new URLSearchParams(window.location.search);
    const id = params.get('order');
    if (!id) return;
    const order = orders.find((o) => o.id === id && OPEN_STATUSES.has(String(o.status)));
    if (!order) {
      setError('That bill is already paid or closed.');
      return;
    }
    openBill(order);
    if (params.get('pay') === '1') void startPayment(Boolean(shift), order);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, orders]);

  const categories = useMemo(() => {
    const names = new Set<string>();
    for (const row of menu) names.add(String(row.category || 'Menu'));
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [menu]);

  const shownMenu = useMemo(() => {
    const q = search.trim().toLowerCase();
    return menu.filter((row) => {
      if (category && String(row.category || 'Menu') !== category) return false;
      if (q && !String(row.name || '').toLowerCase().includes(q)) return false;
      return true;
    });
  }, [menu, category, search]);

  const openBills = useMemo(() => orders.filter((o) => OPEN_STATUSES.has(String(o.status))), [orders]);
  const storeTables = useMemo(
    () => tables.filter((t) => !storeId || !t.store_id || t.store_id === storeId),
    [tables, storeId],
  );
  const table = tables.find((t) => t.id === tableId) || null;

  const draftTotal = draft.reduce((sum, line) => sum + lineAmount(line), 0);
  const sentTotal = Number(current?.total_amount || 0);

  function resetTicket(nextMode: Mode = mode) {
    setDraft([]);
    setCurrent(null);
    setTableId('');
    setGuest('');
    setPhone('');
    setAddress('');
    setMode(nextMode);
    setError('');
  }

  function chooseMode(next: Mode) {
    if (current) return;
    setMode(next);
    if (next === 'dine_in' && !tableId) setTablePicker(true);
    if (next !== 'dine_in') setTableId('');
  }

  function addItem(row: Row) {
    if (soldOut.has(row.id)) return;
    if (mode === 'dine_in' && !tableId && !current) {
      setTablePicker(true);
    }
    setDraft((lines) => {
      const same = lines.find(
        (l) => l.product_id === row.id && l.modifier_ids.length === 0 && !l.note,
      );
      if (same) return lines.map((l) => (l === same ? { ...l, quantity: l.quantity + 1 } : l));
      return [
        ...lines,
        {
          key: `${row.id}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          product_id: row.id,
          name: row.name,
          price: Number(row.selling_price || 0),
          quantity: 1,
          modifier_ids: [],
          modifier_names: [],
          modifier_total: 0,
          note: '',
        },
      ];
    });
  }

  function bump(key: string, by: number) {
    setDraft((lines) =>
      lines
        .map((l) => (l.key === key ? { ...l, quantity: l.quantity + by } : l))
        .filter((l) => l.quantity > 0),
    );
  }

  function saveEdit(line: DraftLine) {
    setDraft((lines) => lines.map((l) => (l.key === line.key ? line : l)));
    setEditing(null);
  }

  function linesBody() {
    return draft.map((l) => ({
      product_id: l.product_id,
      quantity: l.quantity,
      modifier_ids: l.modifier_ids,
      ...(l.note.trim() ? { note: l.note.trim() } : {}),
    }));
  }

  function headerProblem(): string | null {
    if (mode === 'dine_in' && !tableId) return 'Pick a table for this order.';
    if (mode === 'delivery' && !address.trim()) return 'Add the delivery address.';
    return null;
  }

  /** Create the order, or add the new dishes to the open one. Returns the saved order. */
  async function saveOrder(paymentMethod?: Method): Promise<Row | null> {
    if (!current) {
      const problem = headerProblem();
      if (problem) {
        setError(problem);
        if (mode === 'dine_in') setTablePicker(true);
        return null;
      }
      if (!draft.length) {
        setError('Tap a dish to start the order.');
        return null;
      }
      const res = await api('/restaurant/orders', {
        method: 'POST',
        body: JSON.stringify({
          service_mode: mode,
          payment_method: paymentMethod || 'cash',
          store_id: storeId || null,
          table_id: mode === 'dine_in' ? tableId : null,
          customer_name: guest.trim() || null,
          phone: phone.trim() || null,
          delivery_address: mode === 'delivery' ? address.trim() : null,
          lines: linesBody(),
        }),
      });
      return res?.data || null;
    }
    if (!draft.length && !paymentMethod) return current;
    const res = await api(`/restaurant/orders/${current.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        lines: linesBody(),
        ...(paymentMethod ? { payment_method: paymentMethod } : {}),
      }),
    });
    return res?.data || current;
  }

  async function refreshOrder(id: string): Promise<Row | null> {
    const res = await api('/restaurant/orders');
    const rows: Row[] = res?.data || [];
    setOrders(rows);
    return rows.find((o) => o.id === id) || null;
  }

  async function sendToKitchen() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const saved = await saveOrder();
      if (!saved) return;
      await api(`/restaurant/orders/${saved.id}/send`, { method: 'POST' });
      setNotice(`Order ${saved.order_number} sent to the kitchen`);
      resetTicket(mode);
      await load();
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusy(false);
    }
  }

  /** Save what is on the ticket, then open the payment sheet. Money goes into a drawer, so a shift must be open. */
  async function startPayment(shiftReady = Boolean(shift), bill: Row | null = null) {
    if (!shiftReady) {
      setPayAfterShift(true);
      setShiftOpen(true);
      return;
    }
    if (bill) {
      setMethod('cash');
      setTendered('');
      setPaying(bill);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const saved = await saveOrder();
      if (!saved) return;
      const fresh = (await refreshOrder(saved.id)) || saved;
      setCurrent(fresh);
      setDraft([]);
      setMethod('cash');
      setTendered('');
      setPaying(fresh);
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusy(false);
    }
  }

  async function takePayment() {
    if (!paying) return;
    const total = Number(paying.total_amount || 0);
    const cash = Number(tendered || 0);
    if (method === 'cash' && tendered && cash < total) {
      setError('Cash received is less than the bill.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api(`/restaurant/orders/${paying.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ payment_method: method }),
      });
      await api(`/restaurant/orders/${paying.id}/complete`, { method: 'POST' });
      void api('/restaurant/till/shift')
        .then((res) => setShift(res?.data || null))
        .catch(() => undefined);
      setDone({
        number: paying.order_number,
        total,
        change: method === 'cash' && tendered ? Math.max(0, cash - total) : 0,
        method,
      });
      setPaying(null);
      setNotice('');
      resetTicket(mode);
      await load();
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusy(false);
    }
  }

  function shiftChanged(next: Row | null) {
    setShift(next);
    if (next && next.status === 'open' && payAfterShift) {
      setPayAfterShift(false);
      setShiftOpen(false);
      void startPayment(true);
    }
  }

  function openBill(order: Row) {
    setCurrent(order);
    setDraft([]);
    setMode((order.service_mode as Mode) || 'dine_in');
    setTableId(order.table_id || '');
    setGuest(order.customer_name || '');
    setBillsOpen(false);
    setError('');
  }

  function quickCash(total: number): number[] {
    const out = new Set<number>([Math.ceil(total)]);
    for (const step of [5, 10, 20, 50, 100]) {
      const v = Math.ceil(total / step) * step;
      if (v > total) out.add(v);
    }
    return Array.from(out).sort((a, b) => a - b).slice(0, 4);
  }

  const ticketTitle = current
    ? `Order ${current.order_number}`
    : mode === 'dine_in'
      ? table
        ? `Table ${table.name || table.code}`
        : 'New dine-in order'
      : mode === 'takeaway'
        ? 'New takeaway'
        : 'New delivery';

  if (loading) {
    return (
      <div className="rtill rtill-loading" aria-busy="true">
        Loading the menu…
      </div>
    );
  }

  return (
    <div className="rtill">
      <header className="rtill-top">
        <div className="rtill-brand">
          <span className="rtill-mark" aria-hidden>
            ●
          </span>
          <h1>Restaurant till</h1>
        </div>
        <div className="rtill-modes" role="tablist" aria-label="Service">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="tab"
              aria-selected={mode === m.id}
              aria-label={`${m.label} order`}
              className={mode === m.id ? 'on' : ''}
              disabled={Boolean(current) && mode !== m.id}
              onClick={() => chooseMode(m.id)}
            >
              <strong>{m.label}</strong>
              <small>{m.hint}</small>
            </button>
          ))}
        </div>
        <div className="rtill-top-right">
          {stores.length > 1 ? (
            <select
              aria-label="Restaurant branch"
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              disabled={Boolean(current)}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          ) : null}
          <button
            type="button"
            className={`rtill-shift-btn${shift ? ' on' : ''}`}
            aria-label={shift ? 'Till shift and cash drawer' : 'Open till shift'}
            onClick={() => setShiftOpen(true)}
          >
            <span className="rtill-shift-dot" aria-hidden />
            <span>
              {shift ? 'Shift open' : 'Open shift'}
              <small>{shift ? `Drawer ${money(shift.expected_cash)}` : 'Count the float'}</small>
            </span>
          </button>
          <button
            type="button"
            className="rtill-bills-btn"
            aria-label="Open bills"
            onClick={() => setBillsOpen(true)}
          >
            Open bills <span className="rtill-count">{openBills.length}</span>
          </button>
        </div>
      </header>

      {notice ? (
        <div className="rtill-notice" role="status" onClick={() => setNotice('')}>
          {notice}
        </div>
      ) : null}

      <div className="rtill-body">
        <nav className="rtill-cats" aria-label="Menu sections">
          <button type="button" className={!category ? 'on' : ''} onClick={() => setCategory('')}>
            Everything
          </button>
          {categories.map((name) => (
            <button
              key={name}
              type="button"
              className={category === name ? 'on' : ''}
              aria-label={`Show ${name}`}
              onClick={() => setCategory(name)}
            >
              {name}
            </button>
          ))}
        </nav>

        <section className="rtill-menu" aria-label="Menu">
          <input
            className="rtill-search"
            type="search"
            placeholder="Find a dish"
            aria-label="Find a dish"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {shownMenu.length === 0 ? (
            <div className="rtill-empty">
              {menu.length === 0 ? (
                <>
                  No dishes on the menu yet. Add menu items under <a href="/restaurant?tab=recipes">Recipes</a>.
                </>
              ) : (
                'No dish matches.'
              )}
            </div>
          ) : (
            <div className="rtill-grid">
              {shownMenu.map((row) => {
                const out = soldOut.has(row.id);
                const inTicket = draft.filter((l) => l.product_id === row.id).reduce((n, l) => n + l.quantity, 0);
                return (
                  <button
                    key={row.id}
                    type="button"
                    className={`rtill-dish${out ? ' out' : ''}`}
                    aria-label={out ? `${row.name}, sold out` : `Add ${row.name}`}
                    disabled={out}
                    onClick={() => addItem(row)}
                  >
                    {row.has_image && row.image_url ? (
                      <img src={row.image_url} alt="" loading="lazy" />
                    ) : (
                      <span className="rtill-dish-initial" aria-hidden>
                        {String(row.name || '?').slice(0, 1)}
                      </span>
                    )}
                    <span className="rtill-dish-name">{row.name}</span>
                    <span className="rtill-dish-price">{out ? 'Sold out' : money(row.selling_price)}</span>
                    {inTicket > 0 ? <span className="rtill-dish-qty">{inTicket}</span> : null}
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <aside className="rtill-ticket" aria-label="Order ticket">
          <div className="rtill-ticket-head">
            <div>
              <h2>{ticketTitle}</h2>
              {current ? <small>{STATUS_WORDS[current.status] || current.status}</small> : null}
            </div>
            {mode === 'dine_in' && !current ? (
              <button type="button" className="rtill-link" onClick={() => setTablePicker(true)}>
                {table ? 'Change table' : 'Pick table'}
              </button>
            ) : null}
            {current || draft.length ? (
              <button type="button" className="rtill-link" aria-label="Start a new order" onClick={() => resetTicket(mode)}>
                New
              </button>
            ) : null}
          </div>

          {!current && mode !== 'dine_in' ? (
            <div className="rtill-guest">
              <input
                aria-label="Guest name"
                placeholder="Guest name"
                value={guest}
                onChange={(e) => setGuest(e.target.value)}
              />
              <input
                aria-label="Guest phone"
                placeholder="Phone (+233…)"
                inputMode="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/[\s-]/g, ''))}
              />
              {mode === 'delivery' ? (
                <input
                  aria-label="Delivery address"
                  placeholder="Delivery address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              ) : null}
            </div>
          ) : null}

          <div className="rtill-lines">
            {current
              ? (current.items || []).map((item: Row) => (
                  <div key={item.id} className="rtill-line sent">
                    <span className="rtill-line-qty">{Number(item.quantity)}×</span>
                    <span className="rtill-line-name">
                      {item.name}
                      {item.modifiers?.length || item.note ? (
                        <small>{[...(item.modifiers || []), item.note].filter(Boolean).join(' · ')}</small>
                      ) : null}
                    </span>
                    <span className="rtill-line-price">
                      {money(item.line_total ?? Number(item.quantity) * Number(item.unit_price))}
                    </span>
                  </div>
                ))
              : null}
            {current && draft.length ? <div className="rtill-divider">Adding</div> : null}
            {draft.map((line) => (
              <div key={line.key} className="rtill-line">
                <div className="rtill-stepper">
                  <button type="button" aria-label={`One less ${line.name}`} onClick={() => bump(line.key, -1)}>
                    −
                  </button>
                  <span>{line.quantity}</span>
                  <button type="button" aria-label={`One more ${line.name}`} onClick={() => bump(line.key, 1)}>
                    +
                  </button>
                </div>
                <button
                  type="button"
                  className="rtill-line-name rtill-line-edit"
                  aria-label={`Extras and note for ${line.name}`}
                  onClick={() => setEditing(line)}
                >
                  {line.name}
                  {line.modifier_names.length || line.note ? (
                    <small>{[...line.modifier_names, line.note].filter(Boolean).join(' · ')}</small>
                  ) : (
                    <small className="rtill-hint">Tap for extras or a note</small>
                  )}
                </button>
                <span className="rtill-line-price">{money(lineAmount(line))}</span>
              </div>
            ))}
            {!current && !draft.length ? (
              <div className="rtill-empty-ticket">Tap a dish to start.</div>
            ) : null}
          </div>

          {error ? (
            <div className="rtill-error" role="alert">
              {error}
            </div>
          ) : null}

          <div className="rtill-foot">
            <div className="rtill-total">
              <span>{current ? 'Bill so far' : 'Dishes'}</span>
              <strong>{money(sentTotal + draftTotal)}</strong>
            </div>
            <small className="rtill-tax-note">Tax and service charge are added on the bill.</small>
            <div className="rtill-actions">
              <button
                type="button"
                className="rtill-send"
                aria-label="Send to kitchen"
                disabled={busy || !draft.length}
                onClick={() => void sendToKitchen()}
              >
                Send to kitchen
              </button>
              <button
                type="button"
                className="rtill-pay"
                aria-label="Take payment"
                disabled={busy || (!current && !draft.length)}
                onClick={() => void startPayment()}
              >
                Pay
              </button>
            </div>
          </div>
        </aside>
      </div>

      {tablePicker ? (
        <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Pick a table">
          <div className="rtill-sheet-card wide">
            <div className="rtill-sheet-head">
              <h2>Pick a table</h2>
              <button type="button" className="rtill-link" onClick={() => setTablePicker(false)}>
                Close
              </button>
            </div>
            {storeTables.length === 0 ? (
              <p className="rtill-empty">
                No tables yet. Add them under <a href="/restaurant?tab=tables">Tables and floor</a>.
              </p>
            ) : (
              <div className="rtill-tables">
                {storeTables.map((t) => {
                  const bill = openBills.find((o) => o.table_id === t.id);
                  return (
                    <button
                      key={t.id}
                      type="button"
                      className={`rtill-table st-${bill ? 'occupied' : t.status}`}
                      aria-label={bill ? `Table ${t.name || t.code}, open bill ${bill.order_number}` : `Table ${t.name || t.code}`}
                      onClick={() => {
                        setTablePicker(false);
                        if (bill) {
                          openBill(bill);
                        } else {
                          setTableId(t.id);
                        }
                      }}
                    >
                      <strong>{t.name || t.code}</strong>
                      <small>
                        {bill ? `${money(bill.total_amount)} open` : `${TABLE_WORDS[t.status] || t.status} · ${t.seats || 0} seats`}
                      </small>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {billsOpen ? (
        <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Open bills">
          <div className="rtill-sheet-card wide">
            <div className="rtill-sheet-head">
              <h2>Open bills</h2>
              <button type="button" className="rtill-link" onClick={() => setBillsOpen(false)}>
                Close
              </button>
            </div>
            {openBills.length === 0 ? (
              <p className="rtill-empty">No open bills.</p>
            ) : (
              <div className="rtill-bills">
                {openBills.map((o) => {
                  const t = tables.find((x) => x.id === o.table_id);
                  return (
                    <button
                      key={o.id}
                      type="button"
                      className={`rtill-bill st-${o.status}`}
                      aria-label={`Open bill ${o.order_number}`}
                      onClick={() => openBill(o)}
                    >
                      <strong>{t ? `Table ${t.name || t.code}` : o.customer_name || MODES.find((m) => m.id === o.service_mode)?.label}</strong>
                      <span>{o.order_number}</span>
                      <span className="rtill-bill-status">{STATUS_WORDS[o.status] || o.status}</span>
                      <span className="rtill-bill-total">{money(o.total_amount)}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {editing ? (
        <LineEditor
          line={editing}
          groups={groups}
          onCancel={() => setEditing(null)}
          onSave={saveEdit}
        />
      ) : null}

      {paying ? (
        <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Take payment">
          <div className="rtill-sheet-card">
            <div className="rtill-sheet-head">
              <h2>Bill {paying.order_number}</h2>
              <button type="button" className="rtill-link" onClick={() => setPaying(null)}>
                Back
              </button>
            </div>
            <dl className="rtill-bill-sum">
              <div>
                <dt>Dishes</dt>
                <dd>{money(paying.subtotal)}</dd>
              </div>
              {Number(paying.service_amount || 0) > 0 ? (
                <div>
                  <dt>Service</dt>
                  <dd>{money(paying.service_amount)}</dd>
                </div>
              ) : null}
              {Number(paying.tax_amount || 0) > 0 ? (
                <div>
                  <dt>Tax</dt>
                  <dd>{money(paying.tax_amount)}</dd>
                </div>
              ) : null}
              <div className="grand">
                <dt>To pay</dt>
                <dd>{money(paying.total_amount)}</dd>
              </div>
            </dl>
            <div className="rtill-methods" role="radiogroup" aria-label="How the guest pays">
              {METHODS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="radio"
                  aria-checked={method === m.id}
                  className={method === m.id ? 'on' : ''}
                  onClick={() => setMethod(m.id)}
                >
                  {m.label}
                </button>
              ))}
            </div>
            {method === 'cash' ? (
              <div className="rtill-cash">
                <label>
                  <span>Cash received</span>
                  <input
                    aria-label="Cash received"
                    inputMode="decimal"
                    value={tendered}
                    placeholder={String(Number(paying.total_amount || 0))}
                    onChange={(e) => setTendered(e.target.value.replace(/[^0-9.]/g, ''))}
                  />
                </label>
                <div className="rtill-quick">
                  {quickCash(Number(paying.total_amount || 0)).map((v) => (
                    <button key={v} type="button" aria-label={`Cash received ${v}`} onClick={() => setTendered(String(v))}>
                      {money(v)}
                    </button>
                  ))}
                </div>
                {tendered && Number(tendered) >= Number(paying.total_amount || 0) ? (
                  <div className="rtill-change">
                    Change <strong>{money(Number(tendered) - Number(paying.total_amount || 0))}</strong>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="rtill-tax-note">Card, Mobile Money and wallet are recorded here. This till does not charge a card.</p>
            )}
            {error ? (
              <div className="rtill-error" role="alert">
                {error}
              </div>
            ) : null}
            <button
              type="button"
              className="rtill-pay big"
              aria-label="Complete payment"
              disabled={busy}
              onClick={() => void takePayment()}
            >
              {busy ? 'Saving…' : `Paid ${money(paying.total_amount)}`}
            </button>
          </div>
        </div>
      ) : null}

      {shiftOpen ? (
        <ShiftSheet
          shift={shift}
          storeId={storeId}
          explain={payAfterShift ? 'Open your shift first. The money for this bill goes into your drawer.' : ''}
          onClose={() => {
            setShiftOpen(false);
            setPayAfterShift(false);
          }}
          onChange={shiftChanged}
        />
      ) : null}

      {done ? (
        <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Payment taken">
          <div className="rtill-sheet-card rtill-done">
            <div className="rtill-done-tick" aria-hidden>
              ✓
            </div>
            <h2>Bill {done.number} paid</h2>
            <p>
              {money(done.total)} · {METHODS.find((m) => m.id === done.method)?.label}
            </p>
            {done.change > 0 ? (
              <div className="rtill-change big">
                Give change <strong>{money(done.change)}</strong>
              </div>
            ) : null}
            <button type="button" className="rtill-pay big" aria-label="Start next order" onClick={() => setDone(null)}>
              Next order
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LineEditor({
  line,
  groups,
  onCancel,
  onSave,
}: {
  line: DraftLine;
  groups: Row[];
  onCancel: () => void;
  onSave: (line: DraftLine) => void;
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set(line.modifier_ids));
  const [note, setNote] = useState(line.note);
  const all: Row[] = groups.flatMap((g) => g.modifiers || []);

  function toggle(id: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function save() {
    const chosen = all.filter((m) => picked.has(m.id));
    onSave({
      ...line,
      modifier_ids: chosen.map((m) => m.id),
      modifier_names: chosen.map((m) => m.name),
      modifier_total: chosen.reduce((sum, m) => sum + Number(m.price || 0), 0),
      note: note.trim(),
    });
  }

  return (
    <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label={`Extras for ${line.name}`}>
      <div className="rtill-sheet-card">
        <div className="rtill-sheet-head">
          <h2>{line.name}</h2>
          <button type="button" className="rtill-link" onClick={onCancel}>
            Cancel
          </button>
        </div>
        {groups.length === 0 ? (
          <p className="rtill-tax-note">No extras set up yet.</p>
        ) : (
          groups.map((g) => (
            <div key={g.id} className="rtill-mod-group">
              <h3>{g.name}</h3>
              <div className="rtill-mods">
                {(g.modifiers || []).map((m: Row) => (
                  <button
                    key={m.id}
                    type="button"
                    className={picked.has(m.id) ? 'on' : ''}
                    aria-pressed={picked.has(m.id)}
                    onClick={() => toggle(m.id)}
                  >
                    {m.name}
                    {Number(m.price || 0) > 0 ? <small>+{formatMoney(Number(m.price))}</small> : null}
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
        <label className="rtill-note">
          <span>Note for the kitchen</span>
          <input
            aria-label="Note for the kitchen"
            placeholder="No onions, extra hot…"
            value={note}
            maxLength={120}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button type="button" className="rtill-send big" onClick={save}>
          Done
        </button>
      </div>
    </div>
  );
}

const MOVE_WORDS: Record<string, string> = {
  cash_in: 'Cash in',
  cash_out: 'Cash out',
  refund: 'Refund',
};

function ShiftSheet({
  shift,
  storeId,
  explain,
  onClose,
  onChange,
}: {
  shift: Row | null;
  storeId: string;
  explain: string;
  onClose: () => void;
  onChange: (next: Row | null) => void;
}) {
  const [float, setFloat] = useState('');
  const [moveType, setMoveType] = useState<'cash_in' | 'cash_out'>('cash_in');
  const [moveAmount, setMoveAmount] = useState('');
  const [moveReason, setMoveReason] = useState('');
  const [counting, setCounting] = useState(false);
  const [counted, setCounted] = useState('');
  const [notes, setNotes] = useState('');
  const [closed, setClosed] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusy(false);
    }
  }

  const openShift = () =>
    run(async () => {
      const res = await api('/restaurant/till/shift/open', {
        method: 'POST',
        body: JSON.stringify({ opening_cash: Number(float || 0), store_id: storeId || null }),
      });
      onChange(res?.data || null);
    });

  const moveCash = () =>
    run(async () => {
      if (!(Number(moveAmount) > 0)) throw new Error('Enter how much cash.');
      if (moveReason.trim().length < 3) throw new Error('Say why the cash moved.');
      const res = await api(`/restaurant/till/shift/${shift!.id}/cash`, {
        method: 'POST',
        body: JSON.stringify({ movement_type: moveType, amount: Number(moveAmount), reason: moveReason.trim() }),
      });
      setMoveAmount('');
      setMoveReason('');
      onChange(res?.data || shift);
    });

  const closeShift = () =>
    run(async () => {
      if (counted.trim() === '') throw new Error('Count the cash in the drawer first.');
      const res = await api(`/restaurant/till/shift/${shift!.id}/close`, {
        method: 'POST',
        body: JSON.stringify({ counted_cash: Number(counted), notes: notes.trim() || null }),
      });
      setClosed(res?.data || null);
      onChange(null);
    });

  if (closed) {
    const diff = Number(closed.variance || 0);
    return (
      <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Shift closed">
        <div className="rtill-sheet-card rtill-done">
          <div className="rtill-done-tick" aria-hidden>
            ✓
          </div>
          <h2>Shift {closed.shift_number} closed</h2>
          <dl className="rtill-bill-sum">
            <div>
              <dt>Takings</dt>
              <dd>{money(closed.total_sales)}</dd>
            </div>
            {Number(closed.refunded_sales || 0) > 0 ? (
              <div>
                <dt>Refunded since</dt>
                <dd>{money(closed.refunded_sales)}</dd>
              </div>
            ) : null}
            <div>
              <dt>Cash expected</dt>
              <dd>{money(closed.expected_cash)}</dd>
            </div>
            <div>
              <dt>Cash counted</dt>
              <dd>{money(closed.counted_cash)}</dd>
            </div>
          </dl>
          <div className={`rtill-variance ${diff === 0 ? 'even' : diff > 0 ? 'over' : 'short'}`}>
            {diff === 0 ? 'The drawer is exact' : diff > 0 ? `Over by ${money(diff)}` : `Short by ${money(-diff)}`}
          </div>
          <button type="button" className="rtill-pay big" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rtill-sheet" role="dialog" aria-modal="true" aria-label="Till shift">
      <div className="rtill-sheet-card">
        <div className="rtill-sheet-head">
          <h2>{shift ? `Shift ${shift.shift_number}` : 'Open your shift'}</h2>
          <button type="button" className="rtill-link" onClick={onClose}>
            Close
          </button>
        </div>
        {explain ? <p className="rtill-explain">{explain}</p> : null}

        {!shift ? (
          <>
            <label className="rtill-note">
              <span>Cash in the drawer now (float)</span>
              <input
                aria-label="Opening cash float"
                inputMode="decimal"
                placeholder="0.00"
                value={float}
                onChange={(e) => setFloat(e.target.value.replace(/[^0-9.]/g, ''))}
              />
            </label>
            {error ? (
              <div className="rtill-error" role="alert">
                {error}
              </div>
            ) : null}
            <button type="button" className="rtill-pay big" aria-label="Start shift" disabled={busy} onClick={() => void openShift()}>
              {busy ? 'Opening…' : 'Start shift'}
            </button>
          </>
        ) : counting ? (
          <>
            <div className="rtill-expect">
              <span>The drawer should hold</span>
              <strong>{money(shift.expected_cash)}</strong>
            </div>
            <label className="rtill-note">
              <span>Cash you counted</span>
              <input
                aria-label="Counted cash"
                inputMode="decimal"
                placeholder="0.00"
                value={counted}
                onChange={(e) => setCounted(e.target.value.replace(/[^0-9.]/g, ''))}
              />
            </label>
            {counted.trim() !== '' ? (
              <div
                className={`rtill-variance ${
                  Number(counted) === Number(shift.expected_cash)
                    ? 'even'
                    : Number(counted) > Number(shift.expected_cash)
                      ? 'over'
                      : 'short'
                }`}
              >
                {Number(counted) === Number(shift.expected_cash)
                  ? 'Exact'
                  : Number(counted) > Number(shift.expected_cash)
                    ? `Over by ${money(Number(counted) - Number(shift.expected_cash))}`
                    : `Short by ${money(Number(shift.expected_cash) - Number(counted))}`}
              </div>
            ) : null}
            <label className="rtill-note">
              <span>Note (optional)</span>
              <input aria-label="Shift close note" value={notes} maxLength={200} onChange={(e) => setNotes(e.target.value)} />
            </label>
            {error ? (
              <div className="rtill-error" role="alert">
                {error}
              </div>
            ) : null}
            <div className="rtill-actions">
              <button type="button" className="rtill-ghost" onClick={() => setCounting(false)}>
                Back
              </button>
              <button type="button" className="rtill-pay" aria-label="Close shift" disabled={busy} onClick={() => void closeShift()}>
                {busy ? 'Closing…' : 'Close shift'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="rtill-expect">
              <span>Cash in drawer</span>
              <strong>{money(shift.expected_cash)}</strong>
            </div>
            <div className="rtill-shift-grid">
              <div>
                <span>Bills paid</span>
                <strong>{shift.sale_count}</strong>
              </div>
              <div>
                <span>Takings</span>
                <strong>{money(shift.total_sales)}</strong>
              </div>
              <div>
                <span>Refunded</span>
                <strong>{money(shift.refunded_sales)}</strong>
              </div>
              <div>
                <span>Cash</span>
                <strong>{money(shift.cash_sales)}</strong>
              </div>
              <div>
                <span>Card</span>
                <strong>{money(shift.card_sales)}</strong>
              </div>
              <div>
                <span>MoMo and wallet</span>
                <strong>{money(Number(shift.mobile_money_sales || 0) + Number(shift.wallet_sales || 0))}</strong>
              </div>
            </div>
            <p className="rtill-tax-note">
              Started with {money(shift.opening_cash)}
              {Number(shift.cash_in) ? ` · in ${money(shift.cash_in)}` : ''}
              {Number(shift.cash_out) ? ` · out ${money(shift.cash_out)}` : ''}
              {Number(shift.cash_refunds) ? ` · refunds ${money(shift.cash_refunds)}` : ''}
            </p>

            <div className="rtill-move">
              <div className="rtill-methods two" role="radiogroup" aria-label="Cash in or out">
                {(['cash_in', 'cash_out'] as const).map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    role="radio"
                    aria-checked={moveType === kind}
                    className={moveType === kind ? 'on' : ''}
                    onClick={() => setMoveType(kind)}
                  >
                    {MOVE_WORDS[kind]}
                  </button>
                ))}
              </div>
              <div className="rtill-move-row">
                <input
                  aria-label="Cash amount"
                  inputMode="decimal"
                  placeholder="Amount"
                  value={moveAmount}
                  onChange={(e) => setMoveAmount(e.target.value.replace(/[^0-9.]/g, ''))}
                />
                <input
                  aria-label="Why the cash moved"
                  placeholder={moveType === 'cash_in' ? 'More change' : 'Paid the gas man'}
                  value={moveReason}
                  maxLength={200}
                  onChange={(e) => setMoveReason(e.target.value)}
                />
                <button type="button" className="rtill-send" aria-label="Record cash move" disabled={busy} onClick={() => void moveCash()}>
                  Save
                </button>
              </div>
            </div>
            {(shift.moves || []).length ? (
              <ul className="rtill-moves">
                {(shift.moves || []).slice(0, 5).map((row: Row) => (
                  <li key={row.id}>
                    <span>{MOVE_WORDS[row.movement_type] || row.movement_type}</span>
                    <span>{row.reason}</span>
                    <strong>{row.movement_type === 'cash_in' ? '+' : '−'}{money(row.amount)}</strong>
                  </li>
                ))}
              </ul>
            ) : null}
            {error ? (
              <div className="rtill-error" role="alert">
                {error}
              </div>
            ) : null}
            <button type="button" className="rtill-pay big" aria-label="Count and close shift" onClick={() => setCounting(true)}>
              Count and close shift
            </button>
          </>
        )}
      </div>
    </div>
  );
}
