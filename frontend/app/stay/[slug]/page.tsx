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

type RoomChoice = {
  id: string;
  code: string;
  name: string;
  room_type: string;
  max_occupancy: number;
  nightly_rate: number;
  nights: number;
};

function todayInput() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

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

export default function HotelStayPage() {
  const params = useParams<{ slug: string }>();
  const slug = String(params?.slug || '');
  const [info, setInfo] = useState<PageInfo | null>(null);
  const [guestName, setGuestName] = useState('');
  const [phone, setPhone] = useState('');
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');
  const [adults, setAdults] = useState('1');
  const [children, setChildren] = useState('0');
  const [rooms, setRooms] = useState<RoomChoice[]>([]);
  const [roomId, setRoomId] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!slug) return;
    publicJson(`/public/hotel-booking/${encodeURIComponent(slug)}`)
      .then((body) => setInfo(body.data || null))
      .catch((err: Error) => setError(err.message));
  }, [slug]);

  async function loadRooms(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    setRooms([]);
    setRoomId('');
    try {
      const qs = new URLSearchParams({
        check_in: checkIn,
        check_out: checkOut,
        adults: String(Number(adults) || 1),
        children: String(Number(children) || 0),
      });
      const body = await publicJson(`/public/hotel-booking/${encodeURIComponent(slug)}/rooms?${qs}`);
      const rows = Array.isArray(body.data) ? body.data : [];
      setRooms(rows);
      if (!rows.length) setError('No room is free for those dates.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not load rooms');
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = await publicJson(`/public/hotel-booking/${encodeURIComponent(slug)}`, {
        method: 'POST',
        body: JSON.stringify({
          guest_name: guestName.trim(),
          phone: phone.trim(),
          check_in_date: checkIn,
          check_out_date: checkOut,
          adults: Number(adults) || 1,
          children: Number(children) || 0,
          room_id: roomId,
          notes: notes.trim() || null,
        }),
      });
      const number = saved?.data?.reservation_number || '';
      const heldId = roomId;
      setMessage(`Request ${number} is with the hotel. The room is held until the hotel confirms it. This does not take a payment.`);
      setGuestName('');
      setPhone('');
      setNotes('');
      setRoomId('');
      setRooms((current) => current.filter((room) => room.id !== heldId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not send the stay request');
    } finally {
      setBusy(false);
    }
  }

  const today = todayInput();

  return (
    <main className="card" style={{ maxWidth: 560, margin: '32px auto' }} aria-label="Hotel online booking">
      <h1>{info?.company_name || 'Book a stay'}</h1>
      <p className="muted">
        Request a stay. The hotel sees it in the ERP. This page does not take a payment.
        {info?.hostname
          ? ` Linked from ${info.link_kind === 'new' ? 'the new domain' : 'the existing website'} ${info.hostname}.`
          : ''}
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      {info?.open ? (
        <>
          <form onSubmit={loadRooms} style={{ display: 'grid', gap: 10 }}>
            <label>
              <span>Check in</span>
              <input aria-label="Stay check in" type="date" min={today} value={checkIn} onChange={(e) => setCheckIn(e.target.value)} required />
            </label>
            <label>
              <span>Check out</span>
              <input aria-label="Stay check out" type="date" min={checkIn || today} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} required />
            </label>
            <label>
              <span>Adults</span>
              <input aria-label="Stay adults" type="number" min={1} max={20} value={adults} onChange={(e) => setAdults(e.target.value)} required />
            </label>
            <label>
              <span>Children</span>
              <input aria-label="Stay children" type="number" min={0} max={20} value={children} onChange={(e) => setChildren(e.target.value)} required />
            </label>
            <button type="submit" disabled={busy} aria-label="See free rooms">
              {busy ? 'Looking…' : 'See free rooms'}
            </button>
          </form>
          {rooms.length ? (
            <form onSubmit={submit} style={{ display: 'grid', gap: 10, marginTop: 16 }}>
              <label>
                <span>Room</span>
                <select aria-label="Stay room" value={roomId} onChange={(e) => setRoomId(e.target.value)} required>
                  <option value="">Select</option>
                  {rooms.map((room) => (
                    <option key={room.id} value={room.id}>
                      {room.code} · {room.name} · {room.nights} nights · {room.nightly_rate} a night
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Name</span>
                <input aria-label="Stay guest name" value={guestName} onChange={(e) => setGuestName(e.target.value)} required />
              </label>
              <label>
                <span>Phone</span>
                <input aria-label="Stay phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+233241234567" required />
              </label>
              <label>
                <span>Note</span>
                <input aria-label="Stay note" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </label>
              <button type="submit" disabled={busy || !roomId} aria-label="Request a stay">
                {busy ? 'Sending…' : 'Request a stay'}
              </button>
            </form>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
