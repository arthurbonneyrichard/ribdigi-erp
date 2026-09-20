'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';

type Room = {
  id: string;
  code: string;
  name: string;
  room_type: string;
  floor?: string | null;
  bed_type?: string | null;
  max_occupancy: number;
  rate_amount: number;
  status: string;
  housekeeping_status?: string;
  is_active: boolean;
};

type Guest = {
  id: string;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  nationality?: string | null;
  is_active: boolean;
};

type Reservation = {
  id: string;
  reservation_number: string;
  room_id: string;
  guest_id: string;
  room_code?: string | null;
  guest_name?: string | null;
  check_in_date: string;
  check_out_date: string;
  nights: number;
  status: string;
  booking_source?: string;
  estimated_total: number;
  folio_id?: string | null;
  can_check_in?: boolean;
  can_check_out?: boolean;
  can_cancel?: boolean;
  can_no_show?: boolean;
  can_extend?: boolean;
  can_move?: boolean;
};

type Folio = {
  id: string;
  folio_number: string;
  balance: number;
  charges_total: number;
  payments_total: number;
  charges: { id: string; description: string; line_total: number; is_void: boolean }[];
  payments: { id: string; method: string; amount: number }[];
};

type HkTask = {
  id: string;
  room_id: string;
  room_code?: string | null;
  status: string;
  priority: string;
  assigned_to?: string | null;
};

type MaintTicket = {
  id: string;
  room_id: string;
  room_code?: string | null;
  title: string;
  status: string;
  priority: string;
};

type Summary = {
  rooms_total: number;
  rooms_available: number;
  rooms_occupied: number;
  rooms_reserved?: number;
  rooms_dirty?: number;
  rooms_maintenance: number;
  reservations_booked: number;
  reservations_in_house: number;
  arrivals_today?: number;
  departures_today?: number;
  occupancy_rate?: number;
  outstanding_folio_balance?: number;
  guests_total: number;
};

const ROOM_TYPES = ['standard', 'deluxe', 'suite', 'family', 'other'];
const ROOM_STATUSES = [
  'available',
  'reserved',
  'occupied',
  'dirty',
  'clean',
  'inspected',
  'maintenance',
  'out_of_order',
  'blocked',
];

export default function HotelPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [hkTasks, setHkTasks] = useState<HkTask[]>([]);
  const [maint, setMaint] = useState<MaintTicket[]>([]);
  const [folio, setFolio] = useState<Folio | null>(null);
  const [listKind, setListKind] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [roomForm, setRoomForm] = useState({
    code: '',
    name: '',
    room_type: 'standard',
    floor: '',
    bed_type: '',
    max_occupancy: '2',
    rate_amount: '0',
    status: 'available',
  });
  const [guestForm, setGuestForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    nationality: '',
  });
  const [resForm, setResForm] = useState({
    room_id: '',
    guest_id: '',
    check_in_date: '',
    check_out_date: '',
    adults: '1',
    children: '0',
    booking_source: 'direct',
    deposit_amount: '0',
    walk_in: false,
  });
  const [chargeForm, setChargeForm] = useState({ description: '', unit_amount: '0', charge_type: 'extra' });
  const [payForm, setPayForm] = useState({ method: 'cash', amount: '0' });
  const [hkForm, setHkForm] = useState({ room_id: '', assigned_to: '', priority: 'normal' });
  const [maintForm, setMaintForm] = useState({ room_id: '', title: '', priority: 'normal' });
  const [extendDate, setExtendDate] = useState('');
  const [moveRoomId, setMoveRoomId] = useState('');

  const availableRooms = useMemo(
    () =>
      rooms.filter(
        (r) =>
          r.is_active &&
          !['maintenance', 'out_of_order', 'blocked', 'dirty', 'occupied'].includes(r.status)
      ),
    [rooms]
  );

  async function refresh() {
    const qs = listKind ? `?list_kind=${listKind}` : '';
    const [s, r, g, res, hk, mt] = await Promise.all([
      api('/hotel/summary'),
      api('/hotel/rooms?is_active=true'),
      api('/hotel/guests?is_active=true'),
      api(`/hotel/reservations${qs}`),
      api('/hotel/housekeeping'),
      api('/hotel/maintenance'),
    ]);
    setSummary(s.data || null);
    setRooms(r.data || []);
    setGuests(g.data || []);
    setReservations(res.data || []);
    setHkTasks(hk.data || []);
    setMaint(mt.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load hotel'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKind]);

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
          bed_type: roomForm.bed_type.trim() || null,
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
        bed_type: '',
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
          nationality: guestForm.nationality.trim() || null,
        }),
      });
      setGuestForm({ full_name: '', email: '', phone: '', nationality: '' });
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
          booking_source: resForm.walk_in ? 'walk_in' : resForm.booking_source,
          deposit_amount: Number(resForm.deposit_amount) || 0,
          deposit_method: Number(resForm.deposit_amount) > 0 ? 'cash' : null,
          walk_in: resForm.walk_in,
        }),
      });
      setResForm({
        room_id: '',
        guest_id: '',
        check_in_date: '',
        check_out_date: '',
        adults: '1',
        children: '0',
        booking_source: 'direct',
        deposit_amount: '0',
        walk_in: false,
      });
      setMessage('Reservation created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create reservation');
    } finally {
      setBusy(false);
    }
  }

  async function act(path: string, okMessage: string, body: object = {}) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const res = await api(path, { method: 'POST', body: JSON.stringify(body) });
      setMessage(okMessage);
      if (res.data?.folio_id) {
        const f = await api(`/hotel/folios/${res.data.folio_id}`);
        setFolio(f.data || null);
      }
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  async function openFolio(reservationId: string) {
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/reservations/${reservationId}/folio`);
      setFolio(f.data || null);
    } catch (err: any) {
      setError(err.message || 'No folio yet — check in first');
      setFolio(null);
    } finally {
      setBusy(false);
    }
  }

  async function addCharge(e: React.FormEvent) {
    e.preventDefault();
    if (!folio) return;
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/folios/${folio.id}/charges`, {
        method: 'POST',
        body: JSON.stringify({
          charge_type: chargeForm.charge_type,
          description: chargeForm.description.trim(),
          unit_amount: Number(chargeForm.unit_amount) || 0,
          quantity: 1,
        }),
      });
      setFolio(f.data || null);
      setChargeForm({ description: '', unit_amount: '0', charge_type: 'extra' });
      setMessage('Charge posted');
    } catch (err: any) {
      setError(err.message || 'Could not post charge');
    } finally {
      setBusy(false);
    }
  }

  async function addPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!folio) return;
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/folios/${folio.id}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          method: payForm.method,
          amount: Number(payForm.amount) || 0,
        }),
      });
      setFolio(f.data || null);
      setPayForm({ method: 'cash', amount: '0' });
      setMessage('Payment information recorded');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not record payment');
    } finally {
      setBusy(false);
    }
  }

  async function createHk(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/hotel/housekeeping', {
        method: 'POST',
        body: JSON.stringify({
          room_id: hkForm.room_id,
          assigned_to: hkForm.assigned_to.trim() || null,
          priority: hkForm.priority,
        }),
      });
      setHkForm({ room_id: '', assigned_to: '', priority: 'normal' });
      setMessage('Housekeeping task created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create task');
    } finally {
      setBusy(false);
    }
  }

  async function createMaint(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/hotel/maintenance', {
        method: 'POST',
        body: JSON.stringify({
          room_id: maintForm.room_id,
          title: maintForm.title.trim(),
          priority: maintForm.priority,
          block_room: true,
        }),
      });
      setMaintForm({ room_id: '', title: '', priority: 'normal' });
      setMessage('Maintenance ticket created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create ticket');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Hotel</h1>
      <p className="muted">
        Rooms, guests, reservations, folios (payment information only), housekeeping and maintenance.
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
            <div className="muted">Occupancy</div>
            <div className="kpi">{summary.occupancy_rate ?? 0}%</div>
            <div className="muted">
              {summary.rooms_occupied} occupied · {summary.rooms_available} available
            </div>
          </div>
          <div className="card">
            <div className="muted">Today</div>
            <div className="kpi">{summary.arrivals_today ?? 0}</div>
            <div className="muted">
              arrivals · {summary.departures_today ?? 0} departures · {summary.rooms_dirty ?? 0} dirty
            </div>
          </div>
          <div className="card">
            <div className="muted">In house / outstanding</div>
            <div className="kpi">{summary.reservations_in_house}</div>
            <div className="muted">
              folio bal {Number(summary.outstanding_folio_balance || 0).toFixed(2)} ·{' '}
              {summary.rooms_maintenance} offline
            </div>
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
            <input value={roomForm.code} onChange={(e) => setRoomForm((f) => ({ ...f, code: e.target.value }))} aria-label="Hotel room code" required />
          </label>
          <label>
            <span>Name</span>
            <input value={roomForm.name} onChange={(e) => setRoomForm((f) => ({ ...f, name: e.target.value }))} aria-label="Hotel room name" required />
          </label>
          <label>
            <span>Type</span>
            <select value={roomForm.room_type} onChange={(e) => setRoomForm((f) => ({ ...f, room_type: e.target.value }))} aria-label="Hotel room type">
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Bed</span>
            <input value={roomForm.bed_type} onChange={(e) => setRoomForm((f) => ({ ...f, bed_type: e.target.value }))} aria-label="Hotel bed type" />
          </label>
          <label>
            <span>Floor</span>
            <input value={roomForm.floor} onChange={(e) => setRoomForm((f) => ({ ...f, floor: e.target.value }))} aria-label="Hotel room floor" />
          </label>
          <label>
            <span>Rate</span>
            <input type="number" min={0} step="0.01" value={roomForm.rate_amount} onChange={(e) => setRoomForm((f) => ({ ...f, rate_amount: e.target.value }))} aria-label="Hotel room rate" />
          </label>
          <label>
            <span>Status</span>
            <select value={roomForm.status} onChange={(e) => setRoomForm((f) => ({ ...f, status: e.target.value }))} aria-label="Hotel room status">
              {ROOM_STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel room">{busy ? 'Saving…' : 'Create room'}</button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Status</th>
              <th>HK</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id}>
                <td><code>{r.code}</code></td>
                <td>{r.name}</td>
                <td>{r.status.replace('_', ' ')}</td>
                <td>{r.housekeeping_status || '—'}</td>
                <td>{Number(r.rate_amount || 0).toFixed(2)}</td>
              </tr>
            ))}
            {!rooms.length && (
              <tr><td colSpan={5} className="muted">No rooms yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Guests</h2>
        <form onSubmit={createGuest} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Full name</span>
            <input value={guestForm.full_name} onChange={(e) => setGuestForm((f) => ({ ...f, full_name: e.target.value }))} aria-label="Hotel guest full name" required />
          </label>
          <label>
            <span>Email</span>
            <input type="email" value={guestForm.email} onChange={(e) => setGuestForm((f) => ({ ...f, email: e.target.value }))} aria-label="Hotel guest email" />
          </label>
          <label>
            <span>Phone</span>
            <input value={guestForm.phone} onChange={(e) => setGuestForm((f) => ({ ...f, phone: e.target.value }))} placeholder="+233..." aria-label="Hotel guest phone" />
          </label>
          <label>
            <span>Nationality</span>
            <input value={guestForm.nationality} onChange={(e) => setGuestForm((f) => ({ ...f, nationality: e.target.value }))} aria-label="Hotel guest nationality" />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel guest">{busy ? 'Saving…' : 'Create guest'}</button>
          </div>
        </form>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>New reservation / walk-in</h2>
        <form onSubmit={createReservation} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Room</span>
            <select value={resForm.room_id} onChange={(e) => setResForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Hotel reservation room" required>
              <option value="">Select room</option>
              {availableRooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code} — {r.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Guest</span>
            <select value={resForm.guest_id} onChange={(e) => setResForm((f) => ({ ...f, guest_id: e.target.value }))} aria-label="Hotel reservation guest" required>
              <option value="">Select guest</option>
              {guests.map((g) => (
                <option key={g.id} value={g.id}>{g.full_name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Check-in</span>
            <input type="date" value={resForm.check_in_date} onChange={(e) => setResForm((f) => ({ ...f, check_in_date: e.target.value }))} aria-label="Hotel check-in date" required />
          </label>
          <label>
            <span>Check-out</span>
            <input type="date" value={resForm.check_out_date} onChange={(e) => setResForm((f) => ({ ...f, check_out_date: e.target.value }))} aria-label="Hotel check-out date" required />
          </label>
          <label>
            <span>Deposit</span>
            <input type="number" min={0} step="0.01" value={resForm.deposit_amount} onChange={(e) => setResForm((f) => ({ ...f, deposit_amount: e.target.value }))} aria-label="Hotel deposit amount" />
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input type="checkbox" checked={resForm.walk_in} onChange={(e) => setResForm((f) => ({ ...f, walk_in: e.target.checked }))} aria-label="Walk-in reservation" />
            <span>Walk-in</span>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel reservation">{busy ? 'Saving…' : 'Book stay'}</button>
          </div>
        </form>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0 }}>Reservations</h2>
          <select value={listKind} onChange={(e) => setListKind(e.target.value)} aria-label="Hotel reservation list filter">
            <option value="">All</option>
            <option value="arrivals">Arrivals today</option>
            <option value="departures">Departures today</option>
            <option value="in_house">In house</option>
            <option value="upcoming">Upcoming</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-show</option>
          </select>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Guest</th>
              <th>Room</th>
              <th>Dates</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id}>
                <td><code>{r.reservation_number}</code></td>
                <td>{r.guest_name || '—'}</td>
                <td>{r.room_code || '—'}</td>
                <td>{r.check_in_date} → {r.check_out_date}</td>
                <td>{r.status.replace('_', ' ')}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')} aria-label={`Check in ${r.reservation_number}`}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-out`, 'Checked out')} aria-label={`Check out ${r.reservation_number}`}>Check out</button>
                    )}
                    {r.can_cancel && (
                      <button type="button" className="btn-danger" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/cancel`, 'Cancelled')} aria-label={`Cancel ${r.reservation_number}`}>Cancel</button>
                    )}
                    {r.can_no_show && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/no-show`, 'Marked no-show')} aria-label={`No-show ${r.reservation_number}`}>No-show</button>
                    )}
                    {(r.can_check_out || r.status === 'checked_in' || r.status === 'checked_out') && (
                      <button type="button" disabled={busy} onClick={() => openFolio(r.id)} aria-label={`Open folio ${r.reservation_number}`}>Folio</button>
                    )}
                    {r.can_extend && (
                      <button
                        type="button"
                        disabled={busy || !extendDate}
                        onClick={() => act(`/hotel/reservations/${r.id}/extend`, 'Stay extended', { new_check_out_date: extendDate })}
                        aria-label={`Extend ${r.reservation_number}`}
                      >
                        Extend
                      </button>
                    )}
                    {r.can_move && (
                      <button
                        type="button"
                        disabled={busy || !moveRoomId}
                        onClick={() => act(`/hotel/reservations/${r.id}/move`, 'Guest moved', { new_room_id: moveRoomId })}
                        aria-label={`Move ${r.reservation_number}`}
                      >
                        Move
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!reservations.length && (
              <tr><td colSpan={6} className="muted">No reservations.</td></tr>
            )}
          </tbody>
        </table>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
          <label>
            <span>Extend to</span>
            <input type="date" value={extendDate} onChange={(e) => setExtendDate(e.target.value)} aria-label="Extend stay date" />
          </label>
          <label>
            <span>Move to room</span>
            <select value={moveRoomId} onChange={(e) => setMoveRoomId(e.target.value)} aria-label="Move to room">
              <option value="">Select</option>
              {availableRooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {folio && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Folio {folio.folio_number}</h2>
          <p className="muted">
            Charges {Number(folio.charges_total).toFixed(2)} · Payments {Number(folio.payments_total).toFixed(2)} · Balance{' '}
            <strong>{Number(folio.balance).toFixed(2)}</strong> (payment information only — not a gateway)
          </p>
          <table className="table">
            <thead><tr><th>Charge</th><th>Total</th><th>Void</th></tr></thead>
            <tbody>
              {folio.charges.map((c) => (
                <tr key={c.id}>
                  <td>{c.description}</td>
                  <td>{Number(c.line_total).toFixed(2)}</td>
                  <td>{c.is_void ? 'void' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <form onSubmit={addCharge} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', marginTop: 8 }}>
            <label>
              <span>Description</span>
              <input value={chargeForm.description} onChange={(e) => setChargeForm((f) => ({ ...f, description: e.target.value }))} required aria-label="Folio charge description" />
            </label>
            <label>
              <span>Amount</span>
              <input type="number" min={0} step="0.01" value={chargeForm.unit_amount} onChange={(e) => setChargeForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label="Folio charge amount" />
            </label>
            <label>
              <span>Type</span>
              <select value={chargeForm.charge_type} onChange={(e) => setChargeForm((f) => ({ ...f, charge_type: e.target.value }))} aria-label="Folio charge type">
                {['extra', 'restaurant', 'laundry', 'service', 'damage', 'tax', 'discount'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Post charge</button>
            </div>
          </form>
          <form onSubmit={addPayment} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', marginTop: 8 }}>
            <label>
              <span>Method</span>
              <select value={payForm.method} onChange={(e) => setPayForm((f) => ({ ...f, method: e.target.value }))} aria-label="Folio payment method">
                {['cash', 'momo', 'card', 'bank', 'credit', 'other'].map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Amount</span>
              <input type="number" min={0} step="0.01" value={payForm.amount} onChange={(e) => setPayForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Folio payment amount" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Record payment info</button>
            </div>
          </form>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Housekeeping</h2>
        <form onSubmit={createHk} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Room</span>
            <select value={hkForm.room_id} onChange={(e) => setHkForm((f) => ({ ...f, room_id: e.target.value }))} required aria-label="Housekeeping room">
              <option value="">Select</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Assign to</span>
            <input value={hkForm.assigned_to} onChange={(e) => setHkForm((f) => ({ ...f, assigned_to: e.target.value }))} aria-label="Housekeeping assignee" />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Create task</button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead><tr><th>Room</th><th>Status</th><th>Priority</th><th>Assignee</th><th></th></tr></thead>
          <tbody>
            {hkTasks.map((t) => (
              <tr key={t.id}>
                <td>{t.room_code || t.room_id}</td>
                <td>{t.status}</td>
                <td>{t.priority}</td>
                <td>{t.assigned_to || '—'}</td>
                <td>
                  {t.status !== 'completed' && (
                    <button type="button" disabled={busy} onClick={() => act(`/hotel/housekeeping/${t.id}/complete`, 'HK completed', { mark_inspected: true })}>
                      Complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!hkTasks.length && <tr><td colSpan={5} className="muted">No housekeeping tasks.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Maintenance</h2>
        <form onSubmit={createMaint} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Room</span>
            <select value={maintForm.room_id} onChange={(e) => setMaintForm((f) => ({ ...f, room_id: e.target.value }))} required aria-label="Maintenance room">
              <option value="">Select</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Title</span>
            <input value={maintForm.title} onChange={(e) => setMaintForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Maintenance title" />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Create ticket</button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead><tr><th>Room</th><th>Title</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {maint.map((t) => (
              <tr key={t.id}>
                <td>{t.room_code || t.room_id}</td>
                <td>{t.title}</td>
                <td>{t.status}</td>
                <td>
                  {t.status !== 'completed' && (
                    <button type="button" disabled={busy} onClick={() => act(`/hotel/maintenance/${t.id}/complete`, 'Maintenance completed')}>
                      Complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!maint.length && <tr><td colSpan={4} className="muted">No maintenance tickets.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
