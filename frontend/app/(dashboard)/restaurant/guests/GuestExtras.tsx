'use client';

/**
 * Gift cards (sell, check a balance, see every card) and guest feedback (rate a visit, see the scores).
 * Gift cards are money owed to the guest until spent; points live on each guest (see the till).
 */

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';

const SALE_METHODS = [
  { id: 'cash', label: 'Cash' },
  { id: 'card', label: 'Card' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'wallet', label: 'Wallet' },
];

function stars(n: number) {
  return '★'.repeat(n) + '☆'.repeat(Math.max(0, 5 - n));
}

export default function GuestExtras() {
  const [cards, setCards] = useState<Row[]>([]);
  const [board, setBoard] = useState<Row>({ count: 0, average: null, by_rating: {}, items: [] });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [sale, setSale] = useState({ amount: '', method: 'cash', buyer: '' });
  const [lookup, setLookup] = useState('');
  const [found, setFound] = useState<Row | null>(null);
  const [fb, setFb] = useState({ rating: '5', comment: '', guest_name: '', order_number: '' });

  const load = useCallback(async () => {
    try {
      const [c, f] = await Promise.all([api('/restaurant/gift-cards'), api('/restaurant/feedback')]);
      setCards(c?.data || []);
      setBoard(f?.data || { count: 0, average: null, by_rating: {}, items: [] });
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function sellCard(event: FormEvent) {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      const res = await api('/restaurant/gift-cards', {
        method: 'POST',
        body: JSON.stringify({
          amount: Number(sale.amount),
          method: sale.method,
          ...(sale.buyer.trim() ? { buyer: sale.buyer.trim() } : {}),
        }),
      });
      setMessage(`Gift card ${res?.data?.code} sold for ${money(res?.data?.balance)}. Give the guest this code.`);
      setSale({ amount: '', method: sale.method, buyer: '' });
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  async function checkCard(event: FormEvent) {
    event.preventDefault();
    setError('');
    setFound(null);
    try {
      const res = await api(`/restaurant/gift-cards/${encodeURIComponent(lookup.trim().toUpperCase())}`);
      setFound(res?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  async function saveFeedback(event: FormEvent) {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      await api('/restaurant/feedback', {
        method: 'POST',
        body: JSON.stringify({
          rating: Number(fb.rating),
          ...(fb.comment.trim() ? { comment: fb.comment.trim() } : {}),
          ...(fb.guest_name.trim() ? { guest_name: fb.guest_name.trim() } : {}),
          ...(fb.order_number.trim() ? { order_number: fb.order_number.trim() } : {}),
        }),
      });
      setMessage('Feedback saved');
      setFb({ rating: '5', comment: '', guest_name: '', order_number: '' });
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <div className="rdesk" aria-label="Gift cards and feedback" style={{ marginTop: 24, display: 'grid', gap: 24 }}>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {message ? <p className="success" role="status">{message}</p> : null}

      <section aria-label="Gift cards">
        <h3>Gift cards</h3>
        <p className="muted">A gift card is money owed to the guest until it is spent. A guest pays with it as one part of the bill on the till.</p>
        <form onSubmit={sellCard} className="rest-order-form rd-form-grid">
          <label>
            <span>Amount</span>
            <input aria-label="Gift card amount" inputMode="decimal" value={sale.amount} onChange={(e) => setSale({ ...sale, amount: e.target.value.replace(/[^0-9.]/g, '') })} />
          </label>
          <label>
            <span>Paid by</span>
            <select aria-label="Gift card paid by" value={sale.method} onChange={(e) => setSale({ ...sale, method: e.target.value })}>
              {SALE_METHODS.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Buyer (optional)</span>
            <input aria-label="Gift card buyer" value={sale.buyer} onChange={(e) => setSale({ ...sale, buyer: e.target.value })} />
          </label>
          <button type="submit" className="rd-primary" aria-label="Sell gift card" disabled={!Number(sale.amount)}>
            Sell gift card
          </button>
        </form>
        <form onSubmit={checkCard} className="rest-order-form rd-form-grid">
          <label>
            <span>Check a card</span>
            <input aria-label="Gift card code to check" placeholder="Card code" value={lookup} onChange={(e) => setLookup(e.target.value)} />
          </label>
          <button type="submit" aria-label="Check gift card balance" disabled={lookup.trim().length < 3}>Check balance</button>
          {found ? (
            <p>
              <strong>{found.code}</strong>: {money(found.balance)} left ({found.status === 'active' ? 'active' : 'used up'})
            </p>
          ) : null}
        </form>
        <ul className="rest-scan-list" aria-label="Gift cards list">
          {cards.map((c) => (
            <li key={c.id} className="rest-order">
              <strong>{c.code}</strong> · {money(c.balance)} left · {c.status === 'active' ? 'Active' : 'Used up'}
            </li>
          ))}
          {!cards.length ? <li className="muted">No gift cards sold yet.</li> : null}
        </ul>
      </section>

      <section aria-label="Guest feedback">
        <h3>Guest feedback</h3>
        <p className="muted">
          {board.count
            ? `${board.average} out of 5 from ${board.count} ${board.count === 1 ? 'rating' : 'ratings'}.`
            : 'No ratings yet. Guests can also rate an online order on the tracking page.'}
        </p>
        <form onSubmit={saveFeedback} className="rest-order-form rd-form-grid">
          <label>
            <span>Rating</span>
            <select aria-label="Feedback rating" value={fb.rating} onChange={(e) => setFb({ ...fb, rating: e.target.value })}>
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>{n} · {stars(n)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Order number (optional)</span>
            <input aria-label="Feedback order number" value={fb.order_number} onChange={(e) => setFb({ ...fb, order_number: e.target.value })} />
          </label>
          <label>
            <span>Guest (optional)</span>
            <input aria-label="Feedback guest name" value={fb.guest_name} onChange={(e) => setFb({ ...fb, guest_name: e.target.value })} />
          </label>
          <label>
            <span>What they said</span>
            <input aria-label="Feedback comment" value={fb.comment} onChange={(e) => setFb({ ...fb, comment: e.target.value })} />
          </label>
          <button type="submit" className="rd-primary" aria-label="Save feedback">Save feedback</button>
        </form>
        <ul className="rest-scan-list" aria-label="Feedback list">
          {(board.items || []).map((f: Row) => (
            <li key={f.id} className="rest-order">
              <strong>{stars(f.rating)}</strong> {f.guest_name || 'Guest'}
              {f.order_number ? ` · ${f.order_number}` : ''}
              {f.source === 'website' ? ' · website' : ''}
              {f.comment ? <small style={{ display: 'block' }}>{f.comment}</small> : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
