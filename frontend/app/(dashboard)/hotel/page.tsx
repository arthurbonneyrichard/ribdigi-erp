'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';

type Room = {
  id: string;
  code: string;
  name: string;
  room_type: string;
  floor?: string | null;
  max_occupancy: number;
  rate_amount: number;
  status: string;
  is_active: boolean;
};

type Guest = {
  id: string;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  is_active: boolean;
};

type Reservation = {
  id: string;
  reservation_number: string;
  room_id: string;
  guest_id: string;
  room_code?: string | null;
  room_name?: string | null;
  guest_name?: string | null;
  check_in_date: string;
  check_out_date: string;
  nights: number;
  adults: number;
  children: number;
  status: string;
  nightly_rate: number;
  estimated_total: number;
  can_check_in?: boolean;
  can_check_out?: boolean;
  can_cancel?: boolean;
};

type Summary = {
  rooms_total: number;
  rooms_available: number;
  rooms_occupied: number;
  rooms_maintenance: number;
  reservations_booked: number;
  reservations_in_house: number;
  guests_total: number;
};

const ROOM_TYPES = ['standard', 'deluxe', 'suite', 'family', 'other'];
const ROOM_STATUSES = ['available', 'occupied', 'maintenance', 'out_of_order'];

export default function HotelPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [roomForm, setRoomForm] = useState({
    code: '',
    name: '',
    room_type: 'standard',
    floor: '',
    max_occupancy: '2',
    rate_amount: '0',
    status: 'available',
  });
  const [guestForm, setGuestForm] = useState({
    full_name: '',
    email: '',
    phone: '',
  });
  const [resForm, setResForm] = useState({
    room_id: '',
    guest_id: '',
    check_in_date: '',
    check_out_date: '',
    adults: '1',
    children: '0',
  });

  const availableRooms = useMemo(
    () => rooms.filter((r) => r.is_active && r.status !== 'maintenance' && r.status !== 'out_of_order'),
    [rooms]
  );

  async function refresh() {
    const [s, r, g, res] = await Promise.all([
      api('/hotel/summary'),
      api('/hotel/rooms?is_active=true'),
      api('/hotel/guests?is_active=true'),
      api('/hotel/reservations'),
    ]);
    setSummary(s.data || null);
    setRooms(r.data || []);
    setGuests(g.data || []);
    setReservations(res.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load hotel'));
  }, []);

  async function createRoom(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/hotel/rooms', {
        method: 'POST',
        body: JSON.stringify({
          code: roomForm.code.trim(),
          name: roomForm.name.trim(),
          room_type: roomForm.room_type,
          floor: roomForm.floor.trim() || null,
          max_occupancy: Number(roomForm.max_occupancy) || 1,
          rate_amount: Number(roomForm.rate_amount) || 0,
          status: roomForm.status,
        }),
      });
      setRoomForm({
        code: '',
        name: '',
        room_type: 'standard',
        floor: '',
        max_occupancy: '2',
        rate_amount: '0',
        status: 'available',
      });
      setMessage('Room created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create room');
    } finally {
      setBusy(false);
    }
  }

  async function createGuest(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/hotel/guests', {
        method: 'POST',
        body: JSON.stringify({
          full_name: guestForm.full_name.trim(),
          email: guestForm.email.trim() || null,
          phone: guestForm.phone.trim() || null,
        }),
      });
      setGuestForm({ full_name: '', email: '', phone: '' });
      setMessage('Guest created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create guest');
    } finally {
      setBusy(false);
    }
  }

  async function createReservation(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/hotel/reservations', {
        method: 'POST',
        body: JSON.stringify({
          room_id: resForm.room_id.trim(),
          guest_id: resForm.guest_id.trim(),
          check_in_date: resForm.check_in_date.trim(),
          check_out_date: resForm.check_out_date.trim(),
          adults: Number(resForm.adults) || 1,
          children: Number(resForm.children) || 0,
        }),
      });
      setResForm({
        room_id: '',
        guest_id: '',
        check_in_date: '',
        check_out_date: '',
        adults: '1',
        children: '0',
      });
      setMessage('Reservation created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create reservation');
    } finally {
      setBusy(false);
    }
  }

  async function act(path: string, okMessage: string) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(path, { method: 'POST', body: '{}' });
      setMessage(okMessage);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Hotel</h1>
      <p className="muted">
        Manage rooms, guests, and reservations — book stays, check guests in and out.
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
            <div className="muted">Rooms</div>
            <div className="kpi">{summary.rooms_total}</div>
            <div className="muted">
              {summary.rooms_available} available · {summary.rooms_occupied} occupied
            </div>
          </div>
          <div className="card">
            <div className="muted">In house</div>
            <div className="kpi">{summary.reservations_in_house}</div>
            <div className="muted">{summary.reservations_booked} booked ahead</div>
          </div>
          <div className="card">
            <div className="muted">Guests</div>
            <div className="kpi">{summary.guests_total}</div>
            <div className="muted">{summary.rooms_maintenance} rooms offline</div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Add room</h2>
        <form
          onSubmit={createRoom}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
        >
          <label>
            <span>Code</span>
            <input
              value={roomForm.code}
              onChange={(e) => setRoomForm((f) => ({ ...f, code: e.target.value }))}
              aria-label="Hotel room code"
              required
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={roomForm.name}
              onChange={(e) => setRoomForm((f) => ({ ...f, name: e.target.value }))}
              aria-label="Hotel room name"
              required
            />
          </label>
          <label>
            <span>Type</span>
            <select
              value={roomForm.room_type}
              onChange={(e) => setRoomForm((f) => ({ ...f, room_type: e.target.value }))}
              aria-label="Hotel room type"
            >
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Floor</span>
            <input
              value={roomForm.floor}
              onChange={(e) => setRoomForm((f) => ({ ...f, floor: e.target.value }))}
              aria-label="Hotel room floor"
            />
          </label>
          <label>
            <span>Max guests</span>
            <input
              type="number"
              min={1}
              value={roomForm.max_occupancy}
              onChange={(e) => setRoomForm((f) => ({ ...f, max_occupancy: e.target.value }))}
              aria-label="Hotel room max occupancy"
            />
          </label>
          <label>
            <span>Nightly rate</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={roomForm.rate_amount}
              onChange={(e) => setRoomForm((f) => ({ ...f, rate_amount: e.target.value }))}
              aria-label="Hotel room nightly rate"
            />
          </label>
          <label>
            <span>Status</span>
            <select
              value={roomForm.status}
              onChange={(e) => setRoomForm((f) => ({ ...f, status: e.target.value }))}
              aria-label="Hotel room status"
            >
              {ROOM_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel room">
              {busy ? 'Saving…' : 'Create room'}
            </button>
          </div>
        </form>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Rooms</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Rate</th>
              <th>Max</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id}>
                <td>
                  <code>{r.code}</code>
                </td>
                <td>{r.name}</td>
                <td>{r.room_type}</td>
                <td>{r.status.replace('_', ' ')}</td>
                <td>{Number(r.rate_amount || 0).toFixed(2)}</td>
                <td>{r.max_occupancy}</td>
              </tr>
            ))}
            {!rooms.length && (
              <tr>
                <td colSpan={6} className="muted">
                  No rooms yet — add your first room above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Add guest</h2>
        <form
          onSubmit={createGuest}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label>
            <span>Full name</span>
            <input
              value={guestForm.full_name}
              onChange={(e) => setGuestForm((f) => ({ ...f, full_name: e.target.value }))}
              aria-label="Hotel guest full name"
              required
            />
          </label>
          <label>
            <span>Email</span>
            <input
              type="email"
              value={guestForm.email}
              onChange={(e) => setGuestForm((f) => ({ ...f, email: e.target.value }))}
              aria-label="Hotel guest email"
            />
          </label>
          <label>
            <span>Phone</span>
            <input
              value={guestForm.phone}
              onChange={(e) => setGuestForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="+233..."
              aria-label="Hotel guest phone"
            />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel guest">
              {busy ? 'Saving…' : 'Create guest'}
            </button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
            </tr>
          </thead>
          <tbody>
            {guests.map((g) => (
              <tr key={g.id}>
                <td>{g.full_name}</td>
                <td>{g.email || '—'}</td>
                <td>{g.phone || '—'}</td>
              </tr>
            ))}
            {!guests.length && (
              <tr>
                <td colSpan={3} className="muted">
                  No guests yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>New reservation</h2>
        <form
          onSubmit={createReservation}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label>
            <span>Room</span>
            <select
              value={resForm.room_id}
              onChange={(e) => setResForm((f) => ({ ...f, room_id: e.target.value }))}
              aria-label="Hotel reservation room"
              required
            >
              <option value="">Select room</option>
              {availableRooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.code} — {r.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Guest</span>
            <select
              value={resForm.guest_id}
              onChange={(e) => setResForm((f) => ({ ...f, guest_id: e.target.value }))}
              aria-label="Hotel reservation guest"
              required
            >
              <option value="">Select guest</option>
              {guests.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Check-in</span>
            <input
              type="date"
              value={resForm.check_in_date}
              onChange={(e) => setResForm((f) => ({ ...f, check_in_date: e.target.value }))}
              aria-label="Hotel reservation check-in date"
              required
            />
          </label>
          <label>
            <span>Check-out</span>
            <input
              type="date"
              value={resForm.check_out_date}
              onChange={(e) => setResForm((f) => ({ ...f, check_out_date: e.target.value }))}
              aria-label="Hotel reservation check-out date"
              required
            />
          </label>
          <label>
            <span>Adults</span>
            <input
              type="number"
              min={1}
              value={resForm.adults}
              onChange={(e) => setResForm((f) => ({ ...f, adults: e.target.value }))}
              aria-label="Hotel reservation adults"
            />
          </label>
          <label>
            <span>Children</span>
            <input
              type="number"
              min={0}
              value={resForm.children}
              onChange={(e) => setResForm((f) => ({ ...f, children: e.target.value }))}
              aria-label="Hotel reservation children"
            />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel reservation">
              {busy ? 'Saving…' : 'Book stay'}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Reservations</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Guest</th>
              <th>Room</th>
              <th>Dates</th>
              <th>Status</th>
              <th>Total</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id}>
                <td>
                  <code>{r.reservation_number}</code>
                </td>
                <td>{r.guest_name || '—'}</td>
                <td>{r.room_code || r.room_name || '—'}</td>
                <td>
                  {r.check_in_date} → {r.check_out_date}
                  <div className="muted">{r.nights} night(s)</div>
                </td>
                <td>{r.status.replace('_', ' ')}</td>
                <td>{Number(r.estimated_total || 0).toFixed(2)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {r.can_check_in && (
                      <button
                        type="button"
                        className="btn-ok"
                        disabled={busy}
                        onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')}
                        aria-label={`Check in reservation ${r.reservation_number}`}
                      >
                        Check in
                      </button>
                    )}
                    {r.can_check_out && (
                      <button
                        type="button"
                        className="btn-ok"
                        disabled={busy}
                        onClick={() => act(`/hotel/reservations/${r.id}/check-out`, 'Checked out')}
                        aria-label={`Check out reservation ${r.reservation_number}`}
                      >
                        Check out
                      </button>
                    )}
                    {r.can_cancel && (
                      <button
                        type="button"
                        className="btn-danger"
                        disabled={busy}
                        onClick={() => act(`/hotel/reservations/${r.id}/cancel`, 'Reservation cancelled')}
                        aria-label={`Cancel reservation ${r.reservation_number}`}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!reservations.length && (
              <tr>
                <td colSpan={7} className="muted">
                  No reservations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
