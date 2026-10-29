'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { apiRoot } from '../../../lib/api';

type PageInfo = {
  company_name?: string;
  hostname?: string | null;
  link_kind?: string | null;
  path?: string;
  open?: boolean;
};

async function publicJson(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${apiRoot()}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Booking is not available');
  }
  return body;
}

export default function RestaurantBookingPage() {
  const params = useParams<{ slug: string }>();
  const slug = String(params?.slug || '');
  const [info, setInfo] = useState<PageInfo | null>(null);
  const [guestName, setGuestName] = useState('');
  const [phone, setPhone] = useState('');
  const [partySize, setPartySize] = useState('2');
  const [bookedFor, setBookedFor] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!slug) return;
    publicJson(`/public/restaurant-booking/${encodeURIComponent(slug)}`)
      .then((body) => setInfo(body.data || null))
      .catch((err: Error) => setError(err.message));
  }, [slug]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = await publicJson(`/public/restaurant-booking/${encodeURIComponent(slug)}`, {
        method: 'POST',
        body: JSON.stringify({
          guest_name: guestName.trim(),
          phone: phone.trim(),
          party_size: Number(partySize) || 0,
          booked_for: bookedFor,
          notes: notes.trim() || null,
        }),
      });
      setMessage(`Request ${saved?.data?.booking_number || ''} is with the restaurant. This does not take a payment.`);
      setGuestName('');
      setNotes('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not send the booking');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="card" style={{ maxWidth: 560, margin: '32px auto' }} aria-label="Restaurant online booking">
      <h1>{info?.company_name || 'Book a table'}</h1>
      <p className="muted">
        Request a table. The restaurant sees it in the ERP. This page does not take a payment.
        {info?.hostname
          ? ` Linked from ${info.link_kind === 'new' ? 'the new domain' : 'the existing website'} ${info.hostname}.`
          : ''}
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      {info?.open ? (
        <form onSubmit={submit} style={{ display: 'grid', gap: 10 }}>
          <label>
            <span>Name</span>
            <input aria-label="Booking guest name" value={guestName} onChange={(e) => setGuestName(e.target.value)} required />
          </label>
          <label>
            <span>Phone</span>
            <input aria-label="Booking phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+233241234567" required />
          </label>
          <label>
            <span>Party size</span>
            <input aria-label="Booking party size" type="number" min={1} max={40} value={partySize} onChange={(e) => setPartySize(e.target.value)} required />
          </label>
          <label>
            <span>Date and time</span>
            <input
              aria-label="Booking date and time"
              type="datetime-local"
              min={new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)}
              value={bookedFor}
              onChange={(e) => setBookedFor(e.target.value)}
              required
            />
          </label>
          <label>
            <span>Note</span>
            <input aria-label="Booking note" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button type="submit" disabled={busy} aria-label="Request a table">
            {busy ? 'Sending…' : 'Request a table'}
          </button>
        </form>
      ) : null}
    </main>
  );
}
