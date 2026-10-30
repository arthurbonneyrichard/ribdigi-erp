'use client';

/**
 * Hotel shop till. Hotel's own screen and tables (hotel_shop_sales), not the retail POS:
 * walk-up sales go through the front-desk cashier shift; "Charge to room" puts the items
 * on the guest's folio, paid at checkout.
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { formatMoney } from '../../../../lib/format';
import './hotel-shop.css';

type Row = Record<string, any>;
type Method = 'cash' | 'card' | 'mobile_money' | 'wallet' | 'room';

const METHODS: { id: Method; label: string; hint: string }[] = [
  { id: 'cash', label: 'Cash', hint: 'Into the front-desk drawer' },
  { id: 'card', label: 'Card', hint: 'Recorded, not charged here' },
  { id: 'mobile_money', label: 'Mobile Money', hint: 'Recorded, not charged here' },
  { id: 'wallet', label: 'Wallet', hint: 'Recorded, not charged here' },
  { id: 'room', label: 'Charge to room', hint: 'Paid at checkout' },
];

const METHOD_WORDS: Record<string, string> = {
  cash: 'Cash',
  card: 'Card',
  mobile_money: 'Mobile Money',
  wallet: 'Wallet',
  room: 'Room charge',
};

function money(value: unknown) {
  return formatMoney(Number(value || 0));
}

function problem(err: unknown) {
  return (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
}

export default function HotelShopPage() {
  const [items, setItems] = useState<Row[]>([]);
  const [rooms, setRooms] = useState<Row[]>([]);
  const [sales, setSales] = useState<Row[]>([]);
  const [takings, setTakings] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [basket, setBasket] = useState<Record<string, number>>({});
  const [paying, setPaying] = useState(false);
  const [method, setMethod] = useState<Method>('cash');
  const [folioId, setFolioId] = useState('');
  const [tendered, setTendered] = useState('');
  const [done, setDone] = useState<Row | null>(null);
  const [floatDraft, setFloatDraft] = useState('');
  const [refunding, setRefunding] = useState('');

  const load = useCallback(async () => {
    try {
      const [itemRes, roomRes, saleRes, takingRes] = await Promise.all([
        api('/hotel/shop/items'),
        api('/hotel/shop/rooms'),
        api('/hotel/shop/sales?limit=30'),
        api('/hotel/shop/takings'),
      ]);
      setItems(itemRes?.data || []);
      setRooms(roomRes?.data || []);
      setSales(saleRes?.data || []);
      setTakings(takingRes?.data || null);
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

  const categories = useMemo(() => Array.from(new Set(items.map((i) => String(i.category)))).sort(), [items]);
  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((i) => (!category || i.category === category) && (!q || String(i.name).toLowerCase().includes(q)));
  }, [items, category, search]);
  const lines = useMemo(
    () =>
      Object.entries(basket)
        .map(([id, qty]) => ({ item: items.find((i) => i.id === id), qty }))
        .filter((l): l is { item: Row; qty: number } => Boolean(l.item) && l.qty > 0),
    [basket, items],
  );
  const basketTotal = lines.reduce((sum, l) => sum + l.qty * Number(l.item.price || 0), 0);
  const shift = takings?.shift || null;

  function setQty(id: string, qty: number) {
    setBasket((current) => {
      const next = { ...current };
      if (qty <= 0) delete next[id];
      else next[id] = qty;
      return next;
    });
  }

  async function openShift() {
    setBusy(true);
    setError('');
    try {
      await api('/hotel/cashier/shift/open', {
        method: 'POST',
        body: JSON.stringify({ opening_float: Number(floatDraft || 0) }),
      });
      setNotice('Front-desk shift opened');
      setFloatDraft('');
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function sell() {
    if (!lines.length) return;
    if (method === 'room' && !folioId) {
      setError('Choose the guest’s room.');
      return;
    }
    if (method !== 'room' && !shift) {
      setError('Open the front-desk shift before taking money.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await api('/hotel/shop/sales', {
        method: 'POST',
        body: JSON.stringify({
          payment_method: method,
          folio_id: method === 'room' ? folioId : null,
          lines: lines.map((l) => ({ product_id: l.item.id, quantity: l.qty })),
        }),
      });
      const sale = res?.data || {};
      const cash = Number(tendered || 0);
      setDone({ ...sale, change: method === 'cash' && tendered ? Math.max(0, cash - Number(sale.total || 0)) : 0 });
      setBasket({});
      setPaying(false);
      setTendered('');
      setFolioId('');
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function refund(sale: Row) {
    setBusy(true);
    setError('');
    try {
      await api(`/hotel/shop/sales/${sale.id}/refund`, { method: 'POST' });
      setNotice(`Sale ${sale.sale_number} refunded`);
      setRefunding('');
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="hshop hshop-loading">Opening the shop…</div>;

  return (
    <div className="hshop">
      <header className="hs-top">
        <div>
          <h1>Shop till</h1>
          <p>Walk-up shop sales, or charge them to a guest&apos;s room.</p>
        </div>
        <div className={`hs-shift ${shift ? 'on' : ''}`} aria-label="Front-desk shift">
          {shift ? (
            <>
              <span className="dot" aria-hidden />
              <span>
                <strong>Front-desk shift open</strong>
                <small>
                  Shop takings {money(takings?.total)} · {takings?.sale_count || 0} {Number(takings?.sale_count) === 1 ? 'sale' : 'sales'} ·{' '}
                  <Link href="/hotel?tab=cashier">Close it at the front desk</Link>
                </small>
              </span>
            </>
          ) : (
            <>
              <span className="dot" aria-hidden />
              <span>
                <strong>No front-desk shift</strong>
                <small>Open it to take cash, card or Mobile Money.</small>
              </span>
              <input
                aria-label="Opening float"
                inputMode="decimal"
                placeholder="Float"
                value={floatDraft}
                onChange={(e) => setFloatDraft(e.target.value.replace(/[^0-9.]/g, ''))}
              />
              <button type="button" className="hs-primary" aria-label="Open front-desk shift" disabled={busy} onClick={() => void openShift()}>
                Open shift
              </button>
            </>
          )}
        </div>
      </header>

      {notice ? (
        <div className="hs-notice" role="status" onClick={() => setNotice('')}>
          {notice}
        </div>
      ) : null}
      {error ? (
        <div className="hs-error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="hs-body">
        <section className="hs-items" aria-label="Shop items">
          <div className="hs-filter">
            <input className="hs-search" type="search" placeholder="Find an item" aria-label="Find an item" value={search} onChange={(e) => setSearch(e.target.value)} />
            <div className="hs-chips" role="tablist" aria-label="Shop sections">
              <button type="button" role="tab" aria-selected={!category} className={!category ? 'on' : ''} onClick={() => setCategory('')}>
                All
              </button>
              {categories.map((c) => (
                <button key={c} type="button" role="tab" aria-selected={category === c} className={category === c ? 'on' : ''} onClick={() => setCategory(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          {shown.length === 0 ? (
            <p className="hs-empty">
              {items.length ? 'Nothing matches.' : 'No items with a price yet. Add them under Supplies and purchasing.'}
            </p>
          ) : (
            <div className="hs-grid">
              {shown.map((item) => {
                const qty = basket[item.id] || 0;
                const out = Number(item.stock_qty) <= 0;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`hs-item${qty ? ' in' : ''}${out ? ' out' : ''}`}
                    aria-label={out ? `${item.name}, out of stock` : `Add ${item.name}`}
                    disabled={out}
                    onClick={() => setQty(item.id, qty + 1)}
                  >
                    <span className="hs-mono" aria-hidden>{String(item.name).slice(0, 1)}</span>
                    <span className="hs-name">{item.name}</span>
                    <span className="hs-price">{money(item.price)}</span>
                    <span className="hs-stock">{out ? 'Out of stock' : `${Number(item.stock_qty)} in stock`}</span>
                    {qty ? <span className="hs-qty">{qty}</span> : null}
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <aside className="hs-basket" aria-label="Basket">
          <h2>Basket</h2>
          {lines.length === 0 ? <p className="hs-empty">Tap an item to add it.</p> : null}
          <ul>
            {lines.map(({ item, qty }) => (
              <li key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>{money(item.price)} each</small>
                </div>
                <div className="hs-step">
                  <button type="button" aria-label={`One less ${item.name}`} onClick={() => setQty(item.id, qty - 1)}>−</button>
                  <span>{qty}</span>
                  <button type="button" aria-label={`One more ${item.name}`} onClick={() => setQty(item.id, qty + 1)}>+</button>
                </div>
                <b>{money(qty * Number(item.price || 0))}</b>
              </li>
            ))}
          </ul>
          <div className="hs-total">
            <span>Before tax</span>
            <strong>{money(basketTotal)}</strong>
          </div>
          <button type="button" className="hs-primary hs-big" aria-label="Take payment" disabled={!lines.length} onClick={() => setPaying(true)}>
            Take payment
          </button>
          {lines.length ? (
            <button type="button" className="hs-link" onClick={() => setBasket({})}>
              Clear basket
            </button>
          ) : null}
        </aside>
      </div>

      <section className="hs-sales" aria-label="Recent shop sales">
        <h2>Recent sales</h2>
        {sales.length === 0 ? <p className="hs-empty">No shop sales yet.</p> : null}
        <ul>
          {sales.map((sale) => (
            <li key={sale.id} className={sale.status === 'refunded' ? 'refunded' : ''}>
              <div>
                <strong>{sale.sale_number}</strong>
                <small>
                  {(sale.items || []).map((i: Row) => `${Number(i.quantity)}× ${i.name}`).join(', ')}
                </small>
              </div>
              <span className={`hs-pill ${sale.payment_method === 'room' ? 'room' : ''}`}>{METHOD_WORDS[sale.payment_method] || sale.payment_method}</span>
              <b>{money(sale.total)}</b>
              {sale.status === 'refunded' ? (
                <span className="hs-pill grey">Refunded</span>
              ) : refunding === sale.id ? (
                <span className="hs-confirm">
                  <button type="button" onClick={() => setRefunding('')}>Keep</button>
                  <button type="button" className="hs-danger" aria-label={`Yes, refund ${sale.sale_number}`} disabled={busy} onClick={() => void refund(sale)}>
                    Yes, refund
                  </button>
                </span>
              ) : (
                <button type="button" className="hs-link" aria-label={`Refund ${sale.sale_number}`} onClick={() => setRefunding(sale.id)}>
                  Refund
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      {paying ? (
        <div className="hs-sheet" role="dialog" aria-modal="true" aria-label="Take payment">
          <div className="hs-card">
            <div className="hs-card-head">
              <h2>Take payment</h2>
              <button type="button" className="hs-link" onClick={() => setPaying(false)}>Back</button>
            </div>
            <p className="hs-due">
              {money(basketTotal)} <small>before tax; tax is added on the receipt</small>
            </p>
            <div className="hs-methods" role="radiogroup" aria-label="How the guest pays">
              {METHODS.map((m) => (
                <button key={m.id} type="button" role="radio" aria-checked={method === m.id} className={method === m.id ? 'on' : ''} onClick={() => setMethod(m.id)}>
                  <strong>{m.label}</strong>
                  <small>{m.hint}</small>
                </button>
              ))}
            </div>
            {method === 'room' ? (
              <label className="hs-field">
                <span>Guest&apos;s room</span>
                <select aria-label="Guest room" value={folioId} onChange={(e) => setFolioId(e.target.value)}>
                  <option value="">{rooms.length ? 'Choose the room' : 'No guests checked in'}</option>
                  {rooms.map((r) => (
                    <option key={r.folio_id} value={r.folio_id}>
                      {r.room ? `Room ${r.room} · ` : ''}
                      {r.guest_name} · {r.folio_number}
                    </option>
                  ))}
                </select>
              </label>
            ) : method === 'cash' ? (
              <label className="hs-field">
                <span>Cash received (optional)</span>
                <input aria-label="Cash received" inputMode="decimal" value={tendered} onChange={(e) => setTendered(e.target.value.replace(/[^0-9.]/g, ''))} />
              </label>
            ) : null}
            {method !== 'room' && !shift ? <p className="hs-warn">Open the front-desk shift first.</p> : null}
            {error ? (
              <div className="hs-error" role="alert">
                {error}
              </div>
            ) : null}
            <button type="button" className="hs-primary hs-big" aria-label="Complete sale" disabled={busy} onClick={() => void sell()}>
              {busy ? 'Saving…' : method === 'room' ? 'Charge to room' : 'Paid'}
            </button>
          </div>
        </div>
      ) : null}

      {done ? (
        <div className="hs-sheet" role="dialog" aria-modal="true" aria-label="Sale complete">
          <div className="hs-card hs-done">
            <div className="hs-tick" aria-hidden>✓</div>
            <h2>Sale {done.sale_number}</h2>
            <p>
              {money(done.total)} · {METHOD_WORDS[done.payment_method] || done.payment_method}
            </p>
            {Number(done.change) > 0 ? (
              <p className="hs-change">
                Give change <strong>{money(done.change)}</strong>
              </p>
            ) : null}
            <button type="button" className="hs-primary hs-big" aria-label="Next sale" onClick={() => setDone(null)}>
              Next sale
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
