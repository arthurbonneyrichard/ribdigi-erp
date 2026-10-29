'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { apiRoot } from '../../../lib/api';
import { formatMoney } from '../../../lib/format';

type MenuItem = { id: string; name: string; price: number | string };
type PageInfo = { company_name?: string; open?: boolean; menu?: MenuItem[] };

async function publicJson(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${apiRoot()}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Online food orders are not available');
  }
  return body;
}

export default function RestaurantOrderPage() {
  const params = useParams<{ slug: string }>();
  const slug = String(params?.slug || '');
  const [info, setInfo] = useState<PageInfo | null>(null);
  const [guestName, setGuestName] = useState('');
  const [notes, setNotes] = useState('');
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!slug) return;
    publicJson(`/public/restaurant-order/${encodeURIComponent(slug)}`)
      .then((body) => setInfo(body.data || null))
      .catch((err: Error) => setError(err.message));
  }, [slug]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    const lines = (info?.menu || [])
      .map((item) => ({ product_id: item.id, quantity: Number(quantities[item.id] || 0) }))
      .filter((line) => line.quantity > 0);
    if (!lines.length) {
      setError('Choose a menu item.');
      setBusy(false);
      return;
    }
    try {
      const saved = await publicJson(`/public/restaurant-order/${encodeURIComponent(slug)}`, {
        method: 'POST',
        body: JSON.stringify({
          customer_name: guestName.trim(),
          notes: notes.trim() || null,
          lines,
        }),
      });
      setMessage(
        `Order ${saved?.data?.order_number || ''} is with the restaurant. Pay at the counter. This does not charge a card.`,
      );
      setGuestName('');
      setNotes('');
      setQuantities({});
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not send the order');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="card" style={{ maxWidth: 560, margin: '32px auto' }} aria-label="Restaurant online food order">
      <h1>{info?.company_name || 'Order food'}</h1>
      <p className="muted">
        Send an order to the restaurant. Pay at the counter. This page does not charge a card.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      {info?.open ? (
        <form onSubmit={submit} style={{ display: 'grid', gap: 10 }}>
          {(info.menu || []).map((item) => (
            <label key={item.id}>
              <span>{item.name} · {formatMoney(item.price)}</span>
              <input
                aria-label={`Order quantity ${item.name}`}
                type="number"
                min={0}
                max={40}
                value={quantities[item.id] || ''}
                onChange={(e) => setQuantities((current) => ({ ...current, [item.id]: e.target.value }))}
              />
            </label>
          ))}
          {!info.menu?.length ? <p className="muted">No menu items yet.</p> : null}
          <label>
            <span>Name</span>
            <input aria-label="Online order guest name" value={guestName} onChange={(e) => setGuestName(e.target.value)} required />
          </label>
          <label>
            <span>Note</span>
            <input aria-label="Online order note" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button type="submit" disabled={busy} aria-label="Send online food order">
            {busy ? 'Sending…' : 'Send order'}
          </button>
        </form>
      ) : null}
    </main>
  );
}
