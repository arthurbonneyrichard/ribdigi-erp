'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { moduleEnabledForTenant } from '../../../lib/industryModules';
import { HotelRoomNightGrid } from '../../../components/HotelRoomNightGrid';

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
  can_confirm?: boolean;
  can_check_out?: boolean;
  can_cancel?: boolean;
  can_no_show?: boolean;
  can_extend?: boolean;
  can_move?: boolean;
  folio_balance?: number | null;
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
  ooo_starts_on?: string | null;
  ooo_ends_on?: string | null;
};

type Summary = {
  rooms_total: number;
  rooms_available: number;
  rooms_occupied: number;
  rooms_reserved?: number;
  rooms_dirty?: number;
  rooms_maintenance: number;
  reservations_booked: number;
  reservations_tentative?: number;
  reservations_cancelled?: number;
  reservations_no_show?: number;
  reservations_in_house: number;
  arrivals_today?: number;
  expected_arrivals?: number;
  departures_today?: number;
  occupancy_rate?: number;
  physical_occupancy_rate?: number;
  rooms_sold_night?: number;
  room_status_mix?: Record<string, number>;
  reservation_status_mix?: Record<string, number>;
  occupancy_trend?: { date: string; sold: number; occupancy_rate: number }[];
  outstanding_folio_balance?: number;
  revenue_today?: number;
  room_revenue?: number;
  service_revenue?: number;
  payments_received?: number;
  housekeeping_pending?: number;
  housekeeping_overdue?: number;
  maintenance_open?: number;
  as_of?: string;
  guests_total: number;
  recent_reservations?: Reservation[];
  alerts?: { code: string; message: string; href?: string }[];
  low_stock?: { id: string; name: string; stock_qty: number }[];
};

type HotelService = {
  id: string;
  code: string;
  name: string;
  category: string;
  unit_amount: number;
  tax_percent: number;
  is_active: boolean;
};

type FolioRow = {
  id: string;
  folio_number: string;
  status: string;
  balance: number;
  guest_name?: string | null;
  reservation_number?: string | null;
};

function localIso(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

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
const BOOKING_SOURCES: { value: string; label: string }[] = [
  { value: 'direct', label: 'Direct' },
  { value: 'walk_in', label: 'Walk-in' },
  { value: 'phone', label: 'Phone' },
  { value: 'corporate', label: 'Corporate' },
  { value: 'group', label: 'Group' },
  { value: 'ota', label: 'OTA (logged manually)' },
  { value: 'staff', label: 'Staff' },
  { value: 'other', label: 'Other' },
];

function hotelErr(err: unknown, fallback: string) {
  const m = err instanceof Error ? err.message : '';
  if (!m || m === 'The server could not complete this request.' || m === 'Request failed') {
    return fallback;
  }
  return m;
}

function shiftIso(iso: string, days: number) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return localIso(d);
}

function pctChange(curr: number, prev: number | null | undefined): number | null {
  if (prev == null || !Number.isFinite(Number(prev))) return null;
  const p = Number(prev);
  if (p === 0) return Number(curr) === 0 ? 0 : null;
  return ((Number(curr) - p) / Math.abs(p)) * 100;
}

function HotelDelta({ value }: { value: number | null }) {
  if (value == null || !Number.isFinite(value)) return null;
  const cls = value > 0.05 ? 'up' : value < -0.05 ? 'down' : 'flat';
  const sign = value > 0.05 ? '+' : '';
  return (
    <span className={`hotel-kpi-delta ${cls}`}>
      {sign}
      {value.toFixed(1)}%
    </span>
  );
}

type MixSeg = { key: string; n: number; color: string };

function hotelPolar(cx: number, cy: number, r: number, angleDeg: number) {
  const a = ((angleDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)] as const;
}

function HotelDonut({
  segments,
  size = 88,
  stroke = 10,
}: {
  segments: MixSeg[];
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke) / 2 - 2;
  const cx = size / 2;
  const circ = 2 * Math.PI * r;
  const total = segments.reduce((s, x) => s + Math.max(0, x.n), 0);
  let offset = 0;
  return (
    <svg className="hotel-donut" viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true">
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
      {total > 0 &&
        segments.map((s) => {
          if (s.n <= 0) return null;
          const len = (s.n / total) * circ;
          const el = (
            <circle
              key={s.key}
              cx={cx}
              cy={cx}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${len} ${circ}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cx})`}
            />
          );
          offset += len;
          return el;
        })}
    </svg>
  );
}

function HotelPie({ slices, size = 92 }: { slices: MixSeg[]; size?: number }) {
  const cx = size / 2;
  const r = size / 2 - 2;
  const total = slices.reduce((s, x) => s + Math.max(0, x.n), 0);
  let start = 0;
  if (total <= 0) {
    return (
      <svg className="hotel-pie" viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true">
        <circle cx={cx} cy={cx} r={r} fill="var(--mist)" stroke="var(--line)" />
      </svg>
    );
  }
  return (
    <svg className="hotel-pie" viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true">
      {slices.map((s) => {
        if (s.n <= 0) return null;
        const sweep = (s.n / total) * 360;
        const end = start + sweep;
        const slice =
          sweep >= 359.9 ? (
            <circle key={s.key} cx={cx} cy={cx} r={r} fill={s.color} />
          ) : (
            <path
              key={s.key}
              d={`M ${cx} ${cx} L ${hotelPolar(cx, cx, r, start).join(' ')} A ${r} ${r} 0 ${sweep > 180 ? 1 : 0} 1 ${hotelPolar(cx, cx, r, end).join(' ')} Z`}
              fill={s.color}
            />
          );
        start = end;
        return slice;
      })}
    </svg>
  );
}

function HotelAreaChart({ points }: { points: { date: string; occupancy_rate: number }[] }) {
  if (!points.length) return <p className="empty">No occupancy nights yet.</p>;
  const w = 220;
  const h = 120;
  const max = Math.max(100, ...points.map((p) => p.occupancy_rate));
  const coords = points.map((p, i) => {
    const x = points.length <= 1 ? w / 2 : (i / (points.length - 1)) * (w - 8) + 4;
    const y = h - 18 - (p.occupancy_rate / max) * (h - 28);
    return { x, y, p };
  });
  const line = coords.map((c) => `${c.x},${c.y}`).join(' ');
  const area = `M ${coords[0].x},${h - 16} L ${coords.map((c) => `${c.x},${c.y}`).join(' L ')} L ${coords[coords.length - 1].x},${h - 16} Z`;
  return (
    <svg className="hotel-area-chart" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="Occupancy rate over recent nights">
      <path d={area} fill="var(--leaf)" opacity="0.85" />
      <polyline fill="none" stroke="var(--brand)" strokeWidth="2.2" points={line} />
      {coords.map((c) => (
        <circle key={c.p.date} cx={c.x} cy={c.y} r="2.2" fill="var(--brand-dark)" />
      ))}
    </svg>
  );
}

function statusClass(status: string) {
  const key = status.replace(/\s+/g, '_');
  return `hotel-st hotel-st-${key}`;
}

export default function HotelPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = (searchParams?.get('tab') || '').trim().toLowerCase();
  const tab = rawTab || 'dashboard';
  const show = (section: string) => tab === section;
  const [moduleAllowed, setModuleAllowed] = useState<boolean | null>(null);
  const [canReadCompany, setCanReadCompany] = useState(false);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [hkTasks, setHkTasks] = useState<HkTask[]>([]);
  const [maint, setMaint] = useState<MaintTicket[]>([]);
  const [services, setServices] = useState<HotelService[]>([]);
  const [folioRows, setFolioRows] = useState<FolioRow[]>([]);
  const [availRooms, setAvailRooms] = useState<Room[]>([]);
  const [availForm, setAvailForm] = useState({ check_in_date: '', check_out_date: '', room_type: '' });
  const [serviceForm, setServiceForm] = useState({
    code: '',
    name: '',
    category: 'laundry',
    unit_amount: '0',
    tax_percent: '0',
  });
  const [serviceCharge, setServiceCharge] = useState({ service_id: '', quantity: '1' });
  const [guestHistory, setGuestHistory] = useState<any>(null);
  const [folio, setFolio] = useState<Folio | null>(null);
  const [listKind, setListKind] = useState('');
  const [deskKind, setDeskKind] = useState('arrivals');
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
    consent_marketing: false,
  });
  const [resForm, setResForm] = useState({
    room_id: '',
    guest_id: '',
    new_guest_name: '',
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
  const [hkForm, setHkForm] = useState({ room_id: '', assigned_to: '', priority: 'normal', task_type: 'cleaning' });
  const [maintForm, setMaintForm] = useState({
    room_id: '',
    title: '',
    priority: 'normal',
    ooo_starts_on: '',
    ooo_ends_on: '',
  });
  const [extendDate, setExtendDate] = useState('');
  const [moveRoomId, setMoveRoomId] = useState('');
  const [report, setReport] = useState<any>(null);
  const [calendar, setCalendar] = useState<any>(null);
  const [resGridStart, setResGridStart] = useState(() => localIso());
  const [resGridSpan, setResGridSpan] = useState(21);
  const [availTonightIds, setAvailTonightIds] = useState<string[]>([]);
  const [calTick, setCalTick] = useState(0);
  const [settings, setSettings] = useState<any>(null);
  const [groupRooms, setGroupRooms] = useState<string[]>([]);
  const [dashDate, setDashDate] = useState(() => localIso());
  const [ratePlans, setRatePlans] = useState<any[]>([]);
  const [guestRequests, setGuestRequests] = useState<any[]>([]);
  const [lostFound, setLostFound] = useState<any[]>([]);
  const [cashierShift, setCashierShift] = useState<any>(null);
  const [nightAudits, setNightAudits] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [eventForm, setEventForm] = useState({
    title: '',
    space_name: '',
    starts_on: '',
    ends_on: '',
    expected_guests: '20',
    room_id: '',
    guest_id: '',
  });
  const [rateForm, setRateForm] = useState({ code: '', name: '', amount: '0' });
  const [reqForm, setReqForm] = useState({ title: '', kind: 'service', reservation_id: '' });
  const [lfForm, setLfForm] = useState({ description: '', kind: 'lost', room_id: '' });
  const [mergeSource, setMergeSource] = useState('');
  const [transferChargeId, setTransferChargeId] = useState('');
  const [transferFolioId, setTransferFolioId] = useState('');
  const [settingsForm, setSettingsForm] = useState({
    check_in_time: '14:00',
    check_out_time: '11:00',
    cancellation_hours: '24',
    tax_percent: '0',
    early_checkin_fee: '0',
    late_checkout_fee: '0',
    property_name: '',
  });

  const availableRooms = useMemo(
    () =>
      rooms.filter(
        (r) =>
          r.is_active &&
          !['maintenance', 'out_of_order', 'blocked', 'dirty', 'occupied'].includes(r.status)
      ),
    [rooms]
  );

  async function soft<T>(path: string, fallback: T): Promise<T> {
    try {
      const res = await api(path);
      return (res.data ?? fallback) as T;
    } catch {
      return fallback;
    }
  }

  async function refresh() {
    const filter = tab === 'front-desk' ? deskKind : listKind;
    const qs = filter ? `?list_kind=${filter}` : '';
    const startD = new Date();
    startD.setDate(startD.getDate() - 7);
    try {
      const [s, r, g, resv, set] = await Promise.all([
        api(`/hotel/summary?on_date=${dashDate}`),
        api('/hotel/rooms?is_active=true'),
        api('/hotel/guests?is_active=true'),
        api(`/hotel/reservations${qs}`),
        api('/hotel/settings'),
      ]);
      setSummary(s.data || null);
      setRooms(r.data || []);
      setGuests(g.data || []);
      setReservations(resv.data || []);
      setSettings(set.data || null);
      if (set.data) {
        setSettingsForm({
          check_in_time: set.data.check_in_time || '14:00',
          check_out_time: set.data.check_out_time || '11:00',
          cancellation_hours: String(set.data.cancellation_hours ?? 24),
          tax_percent: String(set.data.tax_percent ?? 0),
          early_checkin_fee: String(set.data.early_checkin_fee ?? 0),
          late_checkout_fee: String(set.data.late_checkout_fee ?? 0),
          property_name: set.data.property_name || '',
        });
      }
      setError('');
    } catch (err: any) {
      setError(hotelErr(err, 'Could not load rooms and reservations. Try again.'));
    }
    const [hk, mt, rep, svc, fol, plans, reqs, lf, shift, audits, ev] = await Promise.all([
      soft<HkTask[]>('/hotel/housekeeping', []),
      soft<MaintTicket[]>('/hotel/maintenance', []),
      soft<any>(`/hotel/reports?start_date=${localIso(startD)}&end_date=${localIso()}`, null),
      soft<HotelService[]>('/hotel/services', []),
      soft<FolioRow[]>('/hotel/folios', []),
      soft<any[]>('/hotel/rate-plans', []),
      soft<any[]>('/hotel/guest-requests', []),
      soft<any[]>('/hotel/lost-found', []),
      soft<any>('/hotel/cashier/shift', null),
      soft<any[]>('/hotel/night-audits', []),
      soft<any[]>('/hotel/events', []),
    ]);
    setHkTasks(hk);
    setMaint(mt);
    setReport(rep);
    setServices(svc);
    setFolioRows(fol);
    setRatePlans(plans);
    setGuestRequests(reqs);
    setLostFound(lf);
    setCashierShift(shift);
    setNightAudits(audits);
    setEvents(ev);
    setCalTick((n) => n + 1);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const me = await getMe();
        const ok = moduleEnabledForTenant(
          me.data?.enabled_modules,
          me.data?.industry,
          'hotel'
        );
        if (!active) return;
        setModuleAllowed(ok);
        const perms = (me.data?.permissions || {}) as Record<string, string[]>;
        const companyActions = perms.company || [];
        setCanReadCompany(
          Boolean(perms['*']?.includes('*')) ||
            companyActions.includes('*') ||
            companyActions.includes('read') ||
            companyActions.includes('write')
        );
        if (!ok) {
          setError(
            'Hotel module is not available for this business type. It activates only for Hotel industry tenants (package entitlement still required).'
          );
          return;
        }
        await refresh();
      } catch (err: any) {
        if (active) setError(hotelErr(err, 'Could not load hotel'));
      }
    })();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKind, deskKind, dashDate, tab]);

  useEffect(() => {
    if (!moduleAllowed) return;
    let live = true;
    const start = tab === 'dashboard' ? dashDate : resGridStart;
    const span = tab === 'dashboard' ? 7 : resGridSpan;
    const end = shiftIso(start, Math.max(span, 1) - 1);
    (async () => {
      try {
        const res = await api(`/hotel/calendar?start_date=${start}&end_date=${end}`);
        if (live) setCalendar(res.data || null);
      } catch {
        if (live) setCalendar(null);
      }
      try {
        const rows = await api(`/hotel/availability?check_in_date=${start}&check_out_date=${shiftIso(start, 1)}`);
        if (live) setAvailTonightIds((rows.data || []).map((r: Room) => r.id));
      } catch {
        if (live) setAvailTonightIds([]);
      }
    })();
    return () => {
      live = false;
    };
  }, [moduleAllowed, tab, dashDate, resGridStart, resGridSpan, calTick]);

  function prefillStay(roomId: string, dateIso: string, roomCode: string) {
    setResForm((f) => ({
      ...f,
      room_id: roomId,
      check_in_date: dateIso,
      check_out_date: shiftIso(dateIso, 1),
    }));
    setAvailForm((f) => ({
      ...f,
      check_in_date: dateIso,
      check_out_date: shiftIso(dateIso, 1),
    }));
    setMessage(`Prefilling ${roomCode} from ${dateIso}. Add a guest and book.`);
    if (tab !== 'reservations') {
      router.push('/hotel?tab=reservations');
    }
  }

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
          consent_marketing: guestForm.consent_marketing,
        }),
      });
      setGuestForm({ full_name: '', email: '', phone: '', nationality: '', consent_marketing: false });
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
      let guestId = resForm.guest_id.trim();
      if (!guestId && resForm.new_guest_name.trim()) {
        const created = await api('/hotel/guests', {
          method: 'POST',
          body: JSON.stringify({ full_name: resForm.new_guest_name.trim() }),
        });
        guestId = created.data?.id || '';
      }
      if (!guestId) {
        setError('Select a guest or type a new guest name.');
        setBusy(false);
        return;
      }
      const wasWalkIn = resForm.walk_in;
      const booked = await api('/hotel/reservations', {
        method: 'POST',
        body: JSON.stringify({
          room_id: resForm.room_id.trim(),
          guest_id: guestId,
          check_in_date: resForm.check_in_date.trim(),
          check_out_date: resForm.check_out_date.trim(),
          adults: Number(resForm.adults) || 1,
          children: Number(resForm.children) || 0,
          booking_source: resForm.walk_in ? 'walk_in' : resForm.booking_source,
          deposit_amount: Number(resForm.deposit_amount) || 0,
          deposit_method: Number(resForm.deposit_amount) > 0 ? 'cash' : null,
          walk_in: resForm.walk_in,
          status: resForm.walk_in ? 'booked' : undefined,
        }),
      });
      if (wasWalkIn && booked.data?.id) {
        await api(`/hotel/reservations/${booked.data.id}/check-in`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
      }
      setResForm({
        room_id: '',
        guest_id: '',
        new_guest_name: '',
        check_in_date: '',
        check_out_date: '',
        adults: '1',
        children: '0',
        booking_source: 'direct',
        deposit_amount: '0',
        walk_in: false,
      });
      setMessage(wasWalkIn ? 'Walk-in checked in' : 'Reservation created');
      await refresh();
    } catch (err: any) {
      setError(hotelErr(err, 'Could not create reservation'));
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
      setError(hotelErr(err, 'Could not complete that action'));
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
      setError(hotelErr(err, 'No folio yet — check the guest in first'));
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
          task_type: hkForm.task_type,
        }),
      });
      setHkForm({ room_id: '', assigned_to: '', priority: 'normal', task_type: 'cleaning' });
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
          ooo_starts_on: maintForm.ooo_starts_on || null,
          ooo_ends_on: maintForm.ooo_ends_on || null,
        }),
      });
      setMaintForm({ room_id: '', title: '', priority: 'normal', ooo_starts_on: '', ooo_ends_on: '' });
      setMessage('Maintenance ticket created');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not create ticket');
    } finally {
      setBusy(false);
    }
  }

  if (moduleAllowed === null) {
    return (
      <>
        <h1>Hotel management</h1>
        <p className="muted">Loading hotel data…</p>
      </>
    );
  }

  if (moduleAllowed === false) {
    return (
      <>
        <h1>Hotel</h1>
        <p className="login-error" role="alert">
          {error ||
            'Hotel module is not available for this business type. Switch the company industry to Hotel (and ensure the package includes hotel) to use rooms and reservations.'}
        </p>
      </>
    );
  }

  return (
    <>
      <h1>Hotel management</h1>
      <p className="muted">
        {tab === 'dashboard' && 'Occupancy, arrivals, and alerts for today.'}
        {tab === 'reservations' && 'Search rooms, then book a stay. Same room cannot overlap.'}
        {tab === 'front-desk' && 'Check guests in and out, and log requests.'}
        {tab === 'rooms' && 'Room list, nightly rates, and rate plans.'}
        {tab === 'housekeeping' && 'Cleaning tasks and lost-and-found notes.'}
        {tab === 'maintenance' && 'Repair tickets. Dated blocks only close those nights.'}
        {tab === 'guests' && 'Guest profiles, stay history, and merge duplicates.'}
        {tab === 'billing' && 'Guest bills and payment notes. Cards are not charged here.'}
        {tab === 'cashier' && 'Open a shift and post night audit. Payment notes only.'}
        {tab === 'supplies' && 'Hotel stock uses the same inventory as the rest of the business.'}
        {tab === 'services' && 'Extras (laundry, spa) posted onto a guest bill.'}
        {tab === 'reports' && 'Occupancy, revenue, and stock on hand.'}
        {tab === 'events' && 'Banquets and meeting space. Optional room hold blocks that room.'}
        {tab === 'settings' && 'Property name, check-in times, and fees.'}
      </p>
      {error && (
        <p className="hotel-banner warn" role="alert">
          {error}
        </p>
      )}
      {message && <p className="hotel-banner ok">{message}</p>}

      {show('dashboard') && (
        <div className="hotel-ops">
          <div className="hotel-ops-head">
            <div>
              <h2>{settings?.property_name || 'Hotel dashboard'}</h2>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                Occupancy is rooms sold on the selected business date
                ({summary?.rooms_sold_night ?? 0} of {summary?.rooms_total ?? 0}
                {summary?.as_of || dashDate ? ` · ${summary?.as_of || dashDate}` : ''}).
              </p>
            </div>
            <label className="hotel-ops-date">
              <span>Business date</span>
              <input
                type="date"
                value={dashDate}
                onChange={(e) => setDashDate(e.target.value)}
                aria-label="Hotel dashboard date"
              />
            </label>
          </div>
          {!summary && !error && <p className="empty">Loading operational totals…</p>}
          {summary && (() => {
            const mix = summary.room_status_mix || {};
            const tot = Math.max(1, summary.rooms_total || 0);
            const occupiedN = mix.occupied || summary.rooms_occupied || 0;
            const reservedN = mix.reserved || summary.rooms_reserved || 0;
            const availableN = mix.available ?? summary.rooms_available;
            const notReadyN = (mix.dirty || summary.rooms_dirty || 0) + (mix.out_of_service || summary.rooms_maintenance || 0);
            const segs = [
              { key: 'occupied', color: 'var(--brand-dark)', n: occupiedN },
              { key: 'reserved', color: 'var(--brand)', n: reservedN },
              { key: 'available', color: 'var(--brand-light)', n: availableN },
              { key: 'not ready', color: 'var(--warn)', n: notReadyN },
            ];
            const trend = summary.occupancy_trend || [];
            const occPrev = trend.length >= 2 ? trend[trend.length - 2].occupancy_rate : null;
            const yest = shiftIso(summary.as_of || dashDate, -1);
            const depPrev = reservations.filter(
              (r) =>
                r.check_out_date === yest && (r.status === 'checked_in' || r.status === 'checked_out')
            ).length;
            const occPct = Number(summary.occupancy_rate || 0);
            const soldN = summary.rooms_sold_night ?? 0;
            const unsoldN = Math.max(0, tot - soldN);
            const rmix = summary.reservation_status_mix || {};
            const reqOpen = guestRequests.filter((q) => q.status !== 'completed').length;
            const reqDone = guestRequests.filter((q) => q.status === 'completed').length;
            const sourceCounts = reservations.reduce<Record<string, number>>((acc, r) => {
              const k = (r.booking_source || 'direct').replace(/_/g, ' ');
              acc[k] = (acc[k] || 0) + 1;
              return acc;
            }, {});
            const sourceMax = Math.max(1, ...Object.values(sourceCounts), 0);
            const purpose = reservations.reduce(
              (acc, r) => {
                const src = (r.booking_source || 'direct').toLowerCase();
                if (src === 'corporate' || src === 'group') acc.business += 1;
                else acc.leisure += 1;
                return acc;
              },
              { business: 0, leisure: 0 }
            );
            const purposeTotal = purpose.business + purpose.leisure;
            const mixDonut: MixSeg[] = segs.map((s) => ({ key: s.key, n: s.n, color: s.color }));
            const cioSlices: MixSeg[] = [
              { key: 'arrivals', n: summary.expected_arrivals ?? summary.arrivals_today ?? 0, color: 'var(--brand)' },
              { key: 'departures', n: summary.departures_today ?? 0, color: 'var(--brand-light)' },
              { key: 'in house', n: summary.reservations_in_house || 0, color: 'var(--forest)' },
            ];
            const bookMixMax = Math.max(
              1,
              ...trend.map((p) => {
                const cx = reservations.filter(
                  (r) =>
                    r.check_in_date === p.date && (r.status === 'cancelled' || r.status === 'canceled' || r.status === 'no_show')
                ).length;
                return p.sold + cx;
              })
            );
            const occAvg =
              trend.length > 0 ? trend.reduce((s, p) => s + p.occupancy_rate, 0) / trend.length : occPct;
            const liveRooms = rooms.filter((r) => r.is_active).slice(0, 10);
            const assigned = rooms.filter((r) => r.status === 'occupied' || r.status === 'reserved').slice(0, 8);
            return (
              <>
                <div className="hotel-ops-kpis">
                  <div className="hotel-kpi hotel-kpi-graphic">
                    <div className="lbl">Occupancy</div>
                    <div className="val">{occPct.toFixed(1)}%</div>
                    <HotelDelta value={pctChange(occPct, occPrev)} />
                    <div className="hotel-kpi-visual">
                      <HotelDonut
                        segments={[
                          { key: 'sold', n: soldN, color: 'var(--brand)' },
                          { key: 'unsold', n: unsoldN, color: 'var(--line)' },
                        ]}
                        size={86}
                        stroke={12}
                      />
                      <div className="hotel-kpi-spark tall" aria-hidden="true">
                        {trend.map((p) => (
                          <span key={p.date} style={{ height: `${Math.max(8, Math.min(100, p.occupancy_rate))}%` }} />
                        ))}
                      </div>
                    </div>
                    <div className="hint">{soldN} rooms sold this night of {summary.rooms_total}</div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic">
                    <div className="lbl">Available rooms</div>
                    <div className="val">{availableN}</div>
                    <div className="hotel-kpi-visual center">
                      <HotelDonut segments={mixDonut} size={96} stroke={14} />
                    </div>
                    <div className="hint">Live house mix · {summary.rooms_total} rooms in inventory</div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic">
                    <div className="lbl">Revenue</div>
                    <div className="val">{Number(summary.revenue_today || 0).toFixed(2)}</div>
                    <div className="hotel-rev-bars" aria-label="Room, extras, and payments">
                      {[
                        { k: 'Room', n: Number(summary.room_revenue || 0), c: 'var(--brand)' },
                        { k: 'Extras', n: Number(summary.service_revenue || 0), c: 'var(--brand-dark)' },
                        { k: 'Paid', n: Number(summary.payments_received || 0), c: 'var(--forest)' },
                      ].map((b) => {
                        const mx = Math.max(1, Number(summary.revenue_today || 0), Number(summary.payments_received || 0), b.n);
                        return (
                          <span key={b.k} title={`${b.k} ${b.n.toFixed(2)}`} style={{ height: `${Math.max(10, (b.n / mx) * 100)}%`, background: b.c }} />
                        );
                      })}
                    </div>
                    <div className="hint">
                      Room {Number(summary.room_revenue || 0).toFixed(2)} · extras{' '}
                      {Number(summary.service_revenue || 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic">
                    <div className="lbl">Check-in / out</div>
                    <div className="val">
                      {summary.expected_arrivals ?? summary.arrivals_today ?? 0}
                      <span className="hotel-kpi-sub">
                        {' '}/ {summary.departures_today ?? 0}
                      </span>
                    </div>
                    <HotelDelta value={pctChange(summary.departures_today ?? 0, depPrev)} />
                    <div className="hotel-kpi-visual center">
                      <HotelPie slices={cioSlices} size={88} />
                    </div>
                    <div className="hint">{summary.reservations_in_house} in house · payments {Number(summary.payments_received || 0).toFixed(2)}</div>
                  </div>
                </div>

                <div className="hotel-ops-split">
                  <div className="panel">
                    <h3>Room availability</h3>
                    <p className="hint">Live house status for this tenant — not a forecast.</p>
                    <div className="hotel-avail-bar" role="img" aria-label="Room availability mix">
                      {segs.map((s) => (
                        <span
                          key={s.key}
                          className="hotel-occ-seg"
                          style={{ width: `${Math.max(0, (s.n / tot) * 100)}%`, background: s.color }}
                          title={`${s.key} ${s.n}`}
                        />
                      ))}
                    </div>
                    <div className="hotel-avail-quad">
                      {segs.map((s) => (
                        <div key={s.key}>
                          <div className="k">
                            <span className="mark" style={{ background: s.color }} />
                            {s.key}
                          </div>
                          <div className="n">{s.n}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Reservation mix</h3>
                    <p className="hint">
                      Rooms sold each night from occupancy trend, stacked with cancelled or no-show check-ins that date.
                      Booked {rmix.booked ?? summary.reservations_booked} · cancelled {rmix.cancelled ?? summary.reservations_cancelled ?? 0}.
                    </p>
                    <div className="hotel-mix-legend">
                      <span><i style={{ background: 'var(--forest)' }} /> Sold nights</span>
                      <span><i style={{ background: 'var(--brand-light)' }} /> Cancelled / no-show</span>
                    </div>
                    <div className="hotel-gbar" aria-label="Reservation mix by night">
                      {trend.map((p) => {
                        const cx = reservations.filter(
                          (r) =>
                            r.check_in_date === p.date &&
                            (r.status === 'cancelled' || r.status === 'canceled' || r.status === 'no_show')
                        ).length;
                        const soldH = (p.sold / bookMixMax) * 100;
                        const cxH = (cx / bookMixMax) * 100;
                        return (
                          <div className="col" key={p.date} title={`${p.date}: ${p.sold} sold, ${cx} cancelled`}>
                            <div className="stack">
                              <div className="seg sold" style={{ height: `${soldH}%` }} />
                              <div className="seg cx" style={{ height: `${cxH}%` }} />
                            </div>
                            <span className="dl">{p.date.slice(8)}</span>
                          </div>
                        );
                      })}
                      {!trend.length && <p className="empty">No stay nights yet.</p>}
                    </div>
                  </div>
                </div>

                <div className="panel">
                  <HotelRoomNightGrid
                    rooms={rooms}
                    reservations={reservations}
                    calendar={calendar}
                    maint={maint}
                    availableRoomIds={availTonightIds}
                    startDate={dashDate}
                    dayCount={7}
                    compact
                    onEmptyNight={prefillStay}
                  />
                  <p className="hint" style={{ marginTop: 8 }}>
                    <Link href="/hotel?tab=reservations">Open full booking calendar</Link>
                  </p>
                </div>

                <div className="hotel-ops-triple">
                  <div className="panel">
                    <h3>Quick access</h3>
                    <p className="hint">Hotel workspace only.</p>
                    <div className="hotel-quick">
                      <Link href="/hotel?tab=rooms"><span className="qico">Rm</span>Rooms and rates</Link>
                      <Link href="/hotel?tab=front-desk"><span className="qico">FD</span>Front desk</Link>
                      <Link href="/hotel?tab=reports"><span className="qico">Rp</span>Hotel reports</Link>
                      <Link href="/hotel?tab=maintenance">
                        <span className="qico">
                          Mt
                          {(summary.maintenance_open || 0) > 0 && (
                            <span className="qbadge">{summary.maintenance_open}</span>
                          )}
                        </span>
                        Maintenance
                      </Link>
                      <Link href="/hotel?tab=housekeeping">
                        <span className="qico">
                          Hk
                          {(summary.housekeeping_pending || 0) > 0 && (
                            <span className="qbadge">{summary.housekeeping_pending}</span>
                          )}
                        </span>
                        Housekeeping
                      </Link>
                      <Link href="/hotel?tab=billing"><span className="qico">Bl</span>Billing</Link>
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Guest requests</h3>
                    <p className="hint">From the guest-request API. Completing a request is recorded here only.</p>
                    <div className="hotel-req-stats">
                      <div>
                        <div className="n">{reqOpen}</div>
                        <div className="k">Open</div>
                      </div>
                      <div>
                        <div className="n">{summary.housekeeping_overdue ?? 0}</div>
                        <div className="k">HK overdue</div>
                      </div>
                      <div>
                        <div className="n">{reqDone}</div>
                        <div className="k">Done</div>
                      </div>
                    </div>
                    <ul className="hotel-req-list">
                      {guestRequests.slice(0, 5).map((q) => (
                        <li key={q.id}>
                          {q.title} · {String(q.kind || '').replace('_', ' ')}{' '}
                          <span className={statusClass(q.status)}>{q.status}</span>
                        </li>
                      ))}
                      {!guestRequests.length && <li className="muted">No guest requests.</li>}
                    </ul>
                    <p className="hint" style={{ marginTop: 10 }}>
                      {(summary.alerts || []).length
                        ? (summary.alerts || []).map((a) => (a.href ? <Link key={a.code} href={a.href}>{a.message}. </Link> : <span key={a.code}>{a.message}. </span>))
                        : 'No operational alerts.'}
                    </p>
                  </div>
                  <div className="panel">
                    <h3>Guest purpose</h3>
                    <p className="hint">
                      Corporate and group bookings vs other stored sources. Not an OTA marketplace mix.
                    </p>
                    <div className="hotel-purpose">
                      <HotelDonut
                        segments={[
                          { key: 'business', n: purpose.business, color: 'var(--forest)' },
                          { key: 'leisure', n: purpose.leisure, color: 'var(--brand)' },
                        ]}
                        size={148}
                        stroke={22}
                      />
                      <div className="hotel-purpose-center">
                        <span className="k">Guests</span>
                        <span className="n">{summary.guests_total}</span>
                      </div>
                    </div>
                    <ul className="hotel-purpose-legend">
                      <li>
                        <span className="sw" style={{ background: 'var(--forest)' }} />
                        Business {purpose.business}
                        {purposeTotal ? ` (${Math.round((purpose.business / purposeTotal) * 100)}%)` : ''}
                      </li>
                      <li>
                        <span className="sw" style={{ background: 'var(--brand)' }} />
                        Leisure {purpose.leisure}
                        {purposeTotal ? ` (${Math.round((purpose.leisure / purposeTotal) * 100)}%)` : ''}
                      </li>
                    </ul>
                    <div className="hotel-source compact">
                      {Object.entries(sourceCounts).map(([label, n]) => (
                        <div className="bar-row" key={label}>
                          <span className="bl">{label}</span>
                          <span className="bar-track">
                            <span className="bar-fill" style={{ width: `${Math.min(100, (n / sourceMax) * 100)}%`, background: 'var(--brand)' }} />
                          </span>
                          <span className="bv">{n}</span>
                        </div>
                      ))}
                      {!Object.keys(sourceCounts).length && <p className="empty">No reservations yet.</p>}
                    </div>
                  </div>
                </div>

                <div className="hotel-ops-split">
                  <div className="panel hotel-occ-hero">
                    <h3>Hotel occupancy rate</h3>
                    <p className="hint">Sold room-nights on each business date — not live occupied tiles.</p>
                    <div className="hotel-occ-hero-pct">
                      {occPct.toFixed(1)}%
                      <HotelDelta value={pctChange(occPct, occPrev)} />
                    </div>
                    <div className="hint">Selected night occupancy</div>
                    <div className="hotel-occ-hero-meta">
                      <div>
                        <div className="k">Previous night</div>
                        <div className="n">{occPrev != null ? `${Number(occPrev).toFixed(1)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="k">14-night average</div>
                        <div className="n">{occAvg.toFixed(1)}%</div>
                      </div>
                    </div>
                    <HotelAreaChart points={trend} />
                  </div>
                  <div className="panel">
                    <h3>Arrivals and departures</h3>
                    <p className="hint">Expected arrivals, departures, and in-house from the hotel summary.</p>
                    <div className="hotel-cio">
                      <div className="hotel-cio-item">
                        <HotelDonut
                          segments={[
                            { key: 'in', n: summary.expected_arrivals ?? summary.arrivals_today ?? 0, color: 'var(--brand)' },
                            { key: 'rest', n: Math.max(0, tot - (summary.expected_arrivals ?? summary.arrivals_today ?? 0)), color: 'var(--line)' },
                          ]}
                          size={72}
                          stroke={9}
                        />
                        <div>
                          <div className="k">Arrivals</div>
                          <div className="n">{summary.expected_arrivals ?? summary.arrivals_today ?? 0}</div>
                        </div>
                      </div>
                      <div className="hotel-cio-item">
                        <HotelDonut
                          segments={[
                            { key: 'out', n: summary.departures_today ?? 0, color: 'var(--brand-light)' },
                            { key: 'rest', n: Math.max(0, tot - (summary.departures_today ?? 0)), color: 'var(--line)' },
                          ]}
                          size={72}
                          stroke={9}
                        />
                        <div>
                          <div className="k">Departures</div>
                          <div className="n">{summary.departures_today ?? 0}</div>
                        </div>
                      </div>
                      <div className="hotel-cio-item">
                        <HotelDonut
                          segments={[
                            { key: 'stay', n: summary.reservations_in_house || 0, color: 'var(--forest)' },
                            { key: 'rest', n: Math.max(0, tot - (summary.reservations_in_house || 0)), color: 'var(--line)' },
                          ]}
                          size={72}
                          stroke={9}
                        />
                        <div>
                          <div className="k">In house</div>
                          <div className="n">{summary.reservations_in_house}</div>
                        </div>
                      </div>
                    </div>
                    <div className="hotel-gbar short" aria-label="Rooms sold over recent nights">
                      {trend.map((p) => (
                        <div className="col" key={`sold-${p.date}`} title={`${p.date}: ${p.sold} sold`}>
                          <div className="stack">
                            <div className="seg sold" style={{ height: `${Math.max(4, (p.sold / Math.max(1, tot)) * 100)}%` }} />
                          </div>
                          <span className="dl">{p.date.slice(8)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="hotel-ops-pair">
                  <div className="panel">
                    <h3>Recent bookings</h3>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Room</th>
                          <th>Guest</th>
                          <th>Check in</th>
                          <th>Check out</th>
                          <th>Status</th>
                          <th>Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(summary.recent_reservations || []).map((r) => (
                          <tr key={r.id}>
                            <td>{r.room_code || '—'}</td>
                            <td>{r.guest_name || '—'}</td>
                            <td>{r.check_in_date}</td>
                            <td>{r.check_out_date}</td>
                            <td><span className={statusClass(r.status)}>{r.status.replace('_', ' ')}</span></td>
                            <td>{r.folio_balance != null ? Number(r.folio_balance).toFixed(2) : '—'}</td>
                          </tr>
                        ))}
                        {!(summary.recent_reservations || []).length && (
                          <tr><td colSpan={6} className="muted">No reservations for this tenant yet.</td></tr>
                        )}
                      </tbody>
                    </table>
                    {(summary.low_stock || []).length > 0 && (
                      <p className="hint" style={{ marginTop: 12 }}>
                        Low stock: {(summary.low_stock || []).map((p) => p.name).join(', ')}. <Link href="/inventory?tab=lowstock">Open inventory</Link>
                      </p>
                    )}
                  </div>
                  <div className="panel">
                    <h3>Room status</h3>
                    <p className="hint">Assigned and in-house rooms first, then inventory.</p>
                    <div className="hotel-room-chips">
                      {(assigned.length ? assigned : liveRooms).map((r) => (
                        <div className="hotel-room-chip" key={r.id}>
                          <span>{r.code} · {r.name}</span>
                          <span className={statusClass(r.status)}>{r.status.replace(/_/g, ' ')}</span>
                        </div>
                      ))}
                      {!rooms.length && <p className="empty">No rooms yet.</p>}
                    </div>
                    <p className="hint" style={{ marginTop: 12 }}>
                      Outstanding folios {Number(summary.outstanding_folio_balance || 0).toFixed(2)} · payment notes only
                    </p>
                  </div>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {show('front-desk') && (
        <>
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Front desk</h2>
          <p className="muted">
            Filter arrivals, departures, or in-house guests. Check-in and check-out keep room status in sync.
          </p>
          <select value={deskKind} onChange={(e) => setDeskKind(e.target.value)} aria-label="Front desk list filter">
            <option value="arrivals">Arrivals today</option>
            <option value="departures">Departures today</option>
            <option value="in_house">In house</option>
            <option value="">All reservations</option>
          </select>
          <table className="table" style={{ marginTop: 12 }}>
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
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-out`, 'Checked out')}>Check out</button>
                    )}
                    {r.can_move && (
                      <button type="button" disabled={busy || !moveRoomId} onClick={() => act(`/hotel/reservations/${r.id}/move`, 'Guest moved', { new_room_id: moveRoomId })}>Change room</button>
                    )}
                  </td>
                </tr>
              ))}
              {!reservations.length && (
                <tr><td colSpan={6} className="muted">No stays in this filter.</td></tr>
              )}
            </tbody>
          </table>
          <label style={{ marginTop: 8, display: 'block' }}>
            <span>Change to room</span>
            <select value={moveRoomId} onChange={(e) => setMoveRoomId(e.target.value)} aria-label="Front desk move room">
              <option value="">Select</option>
              {availableRooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
            </select>
          </label>
        </div>
        <h2>Guest requests</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              await api('/hotel/guest-requests', {
                method: 'POST',
                body: JSON.stringify({
                  title: reqForm.title.trim(),
                  kind: reqForm.kind,
                  reservation_id: reqForm.reservation_id || null,
                }),
              });
              setReqForm({ title: '', kind: 'service', reservation_id: '' });
              setMessage('Request recorded');
              await refresh();
            } catch (err: any) {
              setError(err.message || 'Could not save request');
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginTop: 8 }}
        >
          <label><span>Title</span><input value={reqForm.title} onChange={(e) => setReqForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Guest request title" /></label>
          <label>
            <span>Kind</span>
            <select value={reqForm.kind} onChange={(e) => setReqForm((f) => ({ ...f, kind: e.target.value }))} aria-label="Guest request kind">
              {['service', 'wake_up', 'note', 'complaint'].map((k) => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}
            </select>
          </label>
          <label>
            <span>Reservation</span>
            <select value={reqForm.reservation_id} onChange={(e) => setReqForm((f) => ({ ...f, reservation_id: e.target.value }))} aria-label="Guest request reservation">
              <option value="">Optional</option>
              {reservations.map((r) => (
                <option key={r.id} value={r.id}>{r.reservation_number}</option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Record request</button></div>
        </form>
        <ul>
          {guestRequests.map((q) => (
            <li key={q.id}>
              {q.title} ({q.kind}) — {q.status}
              {q.status !== 'completed' && (
                <button type="button" disabled={busy} onClick={() => act(`/hotel/guest-requests/${q.id}/complete`, 'Request done')}>Done</button>
              )}
            </li>
          ))}
          {!guestRequests.length && <li className="muted">No guest requests.</li>}
        </ul>
        </>
      )}

      {show('rooms') && (
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
        <h2 style={{ marginTop: 20 }}>Rate plans</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              await api('/hotel/rate-plans', {
                method: 'POST',
                body: JSON.stringify({
                  code: rateForm.code.trim(),
                  name: rateForm.name.trim(),
                  amount: Number(rateForm.amount) || 0,
                }),
              });
              setRateForm({ code: '', name: '', amount: '0' });
              setMessage('Rate plan saved');
              await refresh();
            } catch (err: any) {
              setError(err.message || 'Could not save rate plan');
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
        >
          <label><span>Code</span><input value={rateForm.code} onChange={(e) => setRateForm((f) => ({ ...f, code: e.target.value }))} required aria-label="Rate plan code" /></label>
          <label><span>Name</span><input value={rateForm.name} onChange={(e) => setRateForm((f) => ({ ...f, name: e.target.value }))} required aria-label="Rate plan name" /></label>
          <label><span>Amount</span><input type="number" min={0} step="0.01" value={rateForm.amount} onChange={(e) => setRateForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Rate plan amount" /></label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Add plan</button></div>
        </form>
        <ul>
          {ratePlans.map((p) => (
            <li key={p.id}><code>{p.code}</code> {p.name} — {Number(p.amount).toFixed(2)}</li>
          ))}
          {!ratePlans.length && <li className="muted">No rate plans yet. Rooms still use their base rate.</li>}
        </ul>
      </div>
      )}

      {show('guests') && (
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
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input
              type="checkbox"
              checked={guestForm.consent_marketing}
              onChange={(e) => setGuestForm((f) => ({ ...f, consent_marketing: e.target.checked }))}
              aria-label="Marketing consent"
            />
            <span>Marketing consent</span>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel guest">{busy ? 'Saving…' : 'Create guest'}</button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {guests.map((g) => (
              <tr key={g.id}>
                <td>{g.full_name}</td>
                <td>{g.email || '—'}</td>
                <td>{g.phone || '—'}</td>
                <td>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      setError('');
                      try {
                        const h = await api(`/hotel/guests/${g.id}/history`);
                        setGuestHistory(h.data || null);
                      } catch (err: any) {
                        setError(err.message || 'Could not load history');
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Stay history
                  </button>
                </td>
              </tr>
            ))}
            {!guests.length && (
              <tr><td colSpan={4} className="muted">No guests yet.</td></tr>
            )}
          </tbody>
        </table>
        <h3 style={{ marginTop: 16 }}>Merge duplicate profiles</h3>
        <p className="muted">Keeps this guest, moves stays and folios from the duplicate, then deactivates the duplicate.</p>
        <label>
          <span>Merge into {guestHistory?.guest?.full_name || 'selected guest (load stay history first)'}</span>
          <select value={mergeSource} onChange={(e) => setMergeSource(e.target.value)} aria-label="Duplicate guest to merge">
            <option value="">Select duplicate profile</option>
            {guests
              .filter((g) => g.id !== guestHistory?.guest?.id)
              .map((g) => (
                <option key={g.id} value={g.id}>{g.full_name}</option>
              ))}
          </select>
        </label>
        <button
          type="button"
          disabled={busy || !guestHistory?.guest?.id || !mergeSource}
          onClick={async () => {
            if (!window.confirm('Merge the duplicate into this guest? This cannot be undone.')) return;
            setBusy(true);
            setError('');
            try {
              await api(`/hotel/guests/${guestHistory.guest.id}/merge`, {
                method: 'POST',
                body: JSON.stringify({ source_guest_id: mergeSource }),
              });
              setMergeSource('');
              setMessage('Guest profiles merged');
              await refresh();
            } catch (err: any) {
              setError(err.message || 'Could not merge guests');
            } finally {
              setBusy(false);
            }
          }}
        >
          Merge duplicate
        </button>
        {guestHistory && (
          <div style={{ marginTop: 12 }}>
            <h3>{guestHistory.guest?.full_name}</h3>
            <p className="muted">Outstanding {Number(guestHistory.outstanding_balance || 0).toFixed(2)}</p>
            <ul>
              {(guestHistory.reservations || []).map((r: Reservation) => (
                <li key={r.id}>
                  {r.reservation_number} · {r.status} · {r.check_in_date} → {r.check_out_date}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      )}

      {show('reservations') && (
      <>
      <div className="card" style={{ marginBottom: 16 }}>
        <HotelRoomNightGrid
          rooms={rooms}
          reservations={reservations}
          calendar={calendar}
          maint={maint}
          availableRoomIds={availTonightIds}
          startDate={resGridStart}
          dayCount={resGridSpan}
          showNav
          onStartChange={setResGridStart}
          onDayCountChange={setResGridSpan}
          onEmptyNight={prefillStay}
        />
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Search availability</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              const q = new URLSearchParams({
                check_in_date: availForm.check_in_date,
                check_out_date: availForm.check_out_date,
              });
              if (availForm.room_type) q.set('room_type', availForm.room_type);
              const rows = await api(`/hotel/availability?${q.toString()}`);
              setAvailRooms(rows.data || []);
              setMessage(`${(rows.data || []).length} room(s) available`);
            } catch (err: any) {
              setError(err.message || 'Availability search failed');
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label>
            <span>Arrival</span>
            <input type="date" value={availForm.check_in_date} onChange={(e) => setAvailForm((f) => ({ ...f, check_in_date: e.target.value }))} required aria-label="Availability check-in" />
          </label>
          <label>
            <span>Departure</span>
            <input type="date" value={availForm.check_out_date} onChange={(e) => setAvailForm((f) => ({ ...f, check_out_date: e.target.value }))} required aria-label="Availability check-out" />
          </label>
          <label>
            <span>Room type</span>
            <select value={availForm.room_type} onChange={(e) => setAvailForm((f) => ({ ...f, room_type: e.target.value }))} aria-label="Availability room type">
              <option value="">Any</option>
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Search rooms</button>
          </div>
        </form>
        {availRooms.length > 0 && (
          <ul>
            {availRooms.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => setResForm((f) => ({ ...f, room_id: r.id, check_in_date: availForm.check_in_date, check_out_date: availForm.check_out_date }))}>
                  Use {r.code} — {r.name} ({Number(r.rate_amount).toFixed(2)})
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="card" id="hotel-book-stay" style={{ marginBottom: 16 }}>
        <h2>Book a stay</h2>
        <p className="muted">Pick dates and a room. Walk-in checks the guest in now. Tick extra rooms below for a group stay.</p>
        <form onSubmit={createReservation} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Room</span>
            <select value={resForm.room_id} onChange={(e) => setResForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Hotel reservation room" required>
              <option value="">Select room</option>
              {rooms.filter((r) => r.is_active).map((r) => (
                <option key={r.id} value={r.id}>{r.code} — {r.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Guest</span>
            <select value={resForm.guest_id} onChange={(e) => setResForm((f) => ({ ...f, guest_id: e.target.value }))} aria-label="Hotel reservation guest">
              <option value="">Select guest</option>
              {guests.map((g) => (
                <option key={g.id} value={g.id}>{g.full_name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Or new guest name</span>
            <input
              value={resForm.new_guest_name}
              onChange={(e) => setResForm((f) => ({ ...f, new_guest_name: e.target.value }))}
              aria-label="New hotel guest name"
              placeholder="If not in the list"
            />
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
            <span>Source</span>
            <select value={resForm.booking_source} onChange={(e) => setResForm((f) => ({ ...f, booking_source: e.target.value }))} aria-label="Hotel booking source">
              {BOOKING_SOURCES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Deposit</span>
            <input type="number" min={0} step="0.01" value={resForm.deposit_amount} onChange={(e) => setResForm((f) => ({ ...f, deposit_amount: e.target.value }))} aria-label="Hotel deposit amount" />
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input type="checkbox" checked={resForm.walk_in} onChange={(e) => setResForm((f) => ({ ...f, walk_in: e.target.checked }))} aria-label="Walk-in reservation" />
            <span>Walk-in (check in now)</span>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel reservation">{busy ? 'Saving…' : 'Book stay'}</button>
          </div>
        </form>
        <h3 style={{ marginTop: 16 }}>Group stay</h3>
        <p className="muted">Tick two or more rooms, with guest and dates filled in above. This is not an OTA channel.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
          {availableRooms.map((r) => (
            <label key={r.id} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={groupRooms.includes(r.id)}
                onChange={(e) =>
                  setGroupRooms((ids) =>
                    e.target.checked ? [...ids, r.id] : ids.filter((id) => id !== r.id)
                  )
                }
                aria-label={`Group room ${r.code}`}
              />
              {r.code}
            </label>
          ))}
          {!availableRooms.length && <span className="muted">Add rooms first (Rooms tab).</span>}
        </div>
        <button
          type="button"
          disabled={busy || groupRooms.length < 2 || (!resForm.guest_id && !resForm.new_guest_name.trim()) || !resForm.check_in_date || !resForm.check_out_date}
          onClick={async () => {
            setBusy(true);
            setError('');
            try {
              let guestId = resForm.guest_id;
              if (!guestId && resForm.new_guest_name.trim()) {
                const created = await api('/hotel/guests', {
                  method: 'POST',
                  body: JSON.stringify({ full_name: resForm.new_guest_name.trim() }),
                });
                guestId = created.data?.id || '';
                setResForm((f) => ({ ...f, guest_id: guestId }));
              }
              await api('/hotel/reservation-groups', {
                method: 'POST',
                body: JSON.stringify({
                  guest_id: guestId,
                  room_ids: groupRooms,
                  check_in_date: resForm.check_in_date,
                  check_out_date: resForm.check_out_date,
                  adults: Number(resForm.adults) || 1,
                  children: Number(resForm.children) || 0,
                  booking_source: 'group',
                  name: 'Group stay',
                }),
              });
              setGroupRooms([]);
              setMessage('Group reservation created');
              await refresh();
            } catch (err: unknown) {
              setError(hotelErr(err, 'Group booking needs guest, dates, and two rooms. Database extras 0119+ may be required.'));
            } finally {
              setBusy(false);
            }
          }}
          aria-label="Create group reservation"
        >
          Book group ({groupRooms.length} rooms)
        </button>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="list-page-head">
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
        <div className="list-table-wrap">
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
                    {r.can_confirm && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/confirm`, 'Confirmed')} aria-label={`Confirm ${r.reservation_number}`}>Confirm booking</button>
                    )}
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')} aria-label={`Check in ${r.reservation_number}`}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-out`, 'Checked out')} aria-label={`Check out ${r.reservation_number}`}>Check out</button>
                    )}
                    {r.can_cancel && (
                      <button type="button" className="btn-danger" disabled={busy} onClick={() => {
                        if (!window.confirm(`Cancel reservation ${r.reservation_number}? This cannot be undone.`)) return;
                        void act(`/hotel/reservations/${r.id}/cancel`, 'Cancelled');
                      }} aria-label={`Cancel ${r.reservation_number}`}>Cancel</button>
                    )}
                    {r.can_no_show && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/no-show`, 'Marked no-show')} aria-label={`No-show ${r.reservation_number}`}>No-show</button>
                    )}
                    {(r.can_check_out || r.status === 'checked_in' || r.status === 'checked_out') && (
                      <button type="button" disabled={busy} onClick={() => openFolio(r.id)} aria-label={`Open folio ${r.reservation_number}`}>Folio</button>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        try {
                          const conf = await api(`/hotel/reservations/${r.id}/confirmation`);
                          window.alert(conf.data?.text || 'Confirmation loaded');
                        } catch (err: unknown) {
                          setError(hotelErr(err, 'Could not load confirmation slip'));
                        }
                      }}
                      aria-label={`View confirmation ${r.reservation_number}`}
                    >
                      View slip
                    </button>
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
        </div>
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
      </>
      )}

      {(show('billing') || show('reservations') || show('services')) && folio && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Folio {folio.folio_number}</h2>
          <p className="muted">
            Charges {Number(folio.charges_total).toFixed(2)} · Payments {Number(folio.payments_total).toFixed(2)} · Balance{' '}
            <strong>{Number(folio.balance).toFixed(2)}</strong> (payment information only — not a gateway)
          </p>
          <table className="table">
            <thead><tr><th>Charge</th><th>Total</th><th>Void</th><th></th></tr></thead>
            <tbody>
              {folio.charges.map((c) => (
                <tr key={c.id}>
                  <td>{c.description}</td>
                  <td>{Number(c.line_total).toFixed(2)}</td>
                  <td>{c.is_void ? 'void' : '—'}</td>
                  <td>
                    {!c.is_void && (
                      <button
                        type="button"
                        className="btn-danger"
                        disabled={busy}
                        onClick={() => {
                          const reason = window.prompt('Void reason');
                          if (!reason) return;
                          void act(`/hotel/folios/${folio.id}/charges/${c.id}/void`, 'Charge voided', { void_reason: reason });
                        }}
                      >
                        Void
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!folio || !transferChargeId || !transferFolioId) return;
              setBusy(true);
              setError('');
              try {
                const f = await api(`/hotel/folios/${folio.id}/charges/${transferChargeId}/transfer`, {
                  method: 'POST',
                  body: JSON.stringify({ target_folio_id: transferFolioId }),
                });
                setFolio(f.data || null);
                setTransferChargeId('');
                setTransferFolioId('');
                setMessage('Charge transferred');
                await refresh();
              } catch (err: any) {
                setError(err.message || 'Could not transfer charge');
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginTop: 8 }}
          >
            <label>
              <span>Split / transfer charge</span>
              <select value={transferChargeId} onChange={(e) => setTransferChargeId(e.target.value)} aria-label="Charge to transfer">
                <option value="">Select charge</option>
                {folio.charges.filter((c) => !c.is_void).map((c) => (
                  <option key={c.id} value={c.id}>{c.description} ({Number(c.line_total).toFixed(2)})</option>
                ))}
              </select>
            </label>
            <label>
              <span>To folio</span>
              <select value={transferFolioId} onChange={(e) => setTransferFolioId(e.target.value)} aria-label="Target folio">
                <option value="">Select folio</option>
                {folioRows.filter((f) => f.id !== folio.id && f.status === 'open').map((f) => (
                  <option key={f.id} value={f.id}>{f.folio_number} {f.guest_name || ''}</option>
                ))}
              </select>
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy || !transferChargeId || !transferFolioId}>Transfer charge</button>
            </div>
          </form>
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
          {services.length > 0 && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!folio) return;
                setBusy(true);
                setError('');
                try {
                  const f = await api(`/hotel/folios/${folio.id}/service-charges`, {
                    method: 'POST',
                    body: JSON.stringify({
                      service_id: serviceCharge.service_id,
                      quantity: Number(serviceCharge.quantity) || 1,
                    }),
                  });
                  setFolio(f.data || null);
                  setMessage('Hotel service posted to folio');
                  await refresh();
                } catch (err: any) {
                  setError(err.message || 'Could not post service');
                } finally {
                  setBusy(false);
                }
              }}
              style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', marginTop: 8 }}
            >
              <label>
                <span>Hotel service</span>
                <select value={serviceCharge.service_id} onChange={(e) => setServiceCharge((f) => ({ ...f, service_id: e.target.value }))} required aria-label="Post hotel service">
                  <option value="">Select</option>
                  {services.filter((s) => s.is_active).map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({Number(s.unit_amount).toFixed(2)})</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Qty</span>
                <input type="number" min={0.01} step="0.01" value={serviceCharge.quantity} onChange={(e) => setServiceCharge((f) => ({ ...f, quantity: e.target.value }))} aria-label="Service quantity" />
              </label>
              <div style={{ alignSelf: 'end' }}>
                <button type="submit" disabled={busy}>Post service</button>
              </div>
            </form>
          )}
        </div>
      )}

      {show('billing') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Billing and payments</h2>
          <p className="muted">Payment information only — Ribdigi does not process or settle funds.</p>
          <table className="table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Guest</th>
                <th>Stay</th>
                <th>Status</th>
                <th>Balance</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {folioRows.map((f) => (
                <tr key={f.id}>
                  <td><code>{f.folio_number}</code></td>
                  <td>{f.guest_name || '—'}</td>
                  <td>{f.reservation_number || '—'}</td>
                  <td>{f.status}</td>
                  <td>{Number(f.balance || 0).toFixed(2)}</td>
                  <td>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const d = await api(`/hotel/folios/${f.id}`);
                          setFolio(d.data || null);
                        } catch (err: any) {
                          setError(err.message || 'Could not open folio');
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
              {!folioRows.length && (
                <tr><td colSpan={6} className="muted">No guest bills yet. Check a guest in to open a folio.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {show('services') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel services</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError('');
              try {
                await api('/hotel/services', {
                  method: 'POST',
                  body: JSON.stringify({
                    code: serviceForm.code.trim(),
                    name: serviceForm.name.trim(),
                    category: serviceForm.category,
                    unit_amount: Number(serviceForm.unit_amount) || 0,
                    tax_percent: Number(serviceForm.tax_percent) || 0,
                  }),
                });
                setServiceForm({ code: '', name: '', category: 'laundry', unit_amount: '0', tax_percent: '0' });
                setMessage('Hotel service created');
                await refresh();
              } catch (err: any) {
                setError(err.message || 'Could not create service');
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
          >
            <label>
              <span>Code</span>
              <input value={serviceForm.code} onChange={(e) => setServiceForm((f) => ({ ...f, code: e.target.value }))} required aria-label="Hotel service code" />
            </label>
            <label>
              <span>Name</span>
              <input value={serviceForm.name} onChange={(e) => setServiceForm((f) => ({ ...f, name: e.target.value }))} required aria-label="Hotel service name" />
            </label>
            <label>
              <span>Category</span>
              <select value={serviceForm.category} onChange={(e) => setServiceForm((f) => ({ ...f, category: e.target.value }))} aria-label="Hotel service category">
                {['restaurant', 'laundry', 'transport', 'spa', 'extra', 'service'].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Unit amount</span>
              <input type="number" min={0} step="0.01" value={serviceForm.unit_amount} onChange={(e) => setServiceForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label="Hotel service amount" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Add service</button>
            </div>
          </form>
          <table className="table" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Category</th>
                <th>Amount</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.id}>
                  <td><code>{s.code}</code></td>
                  <td>{s.name}</td>
                  <td>{s.category}</td>
                  <td>{Number(s.unit_amount).toFixed(2)}</td>
                  <td>{s.is_active ? 'yes' : 'no'}</td>
                </tr>
              ))}
              {!services.length && (
                <tr><td colSpan={5} className="muted">No hotel services yet.</td></tr>
              )}
            </tbody>
          </table>
          <p className="muted">Open a folio under Billing to post an approved service charge to a guest bill.</p>
        </div>
      )}

      {show('housekeeping') && (
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
            <span>Task type</span>
            <select value={hkForm.task_type} onChange={(e) => setHkForm((f) => ({ ...f, task_type: e.target.value }))} aria-label="Housekeeping task type">
              {['cleaning', 'inspection', 'turndown', 'linen', 'special'].map((t) => (
                <option key={t} value={t}>{t}</option>
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
        <h2>Lost and found / damage</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              await api('/hotel/lost-found', {
                method: 'POST',
                body: JSON.stringify({
                  description: lfForm.description.trim(),
                  kind: lfForm.kind,
                  room_id: lfForm.room_id || null,
                }),
              });
              setLfForm({ description: '', kind: 'lost', room_id: '' });
              setMessage('Record saved');
              await refresh();
            } catch (err: any) {
              setError(err.message || 'Could not save record');
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label><span>Description</span><input value={lfForm.description} onChange={(e) => setLfForm((f) => ({ ...f, description: e.target.value }))} required aria-label="Lost found description" /></label>
          <label>
            <span>Kind</span>
            <select value={lfForm.kind} onChange={(e) => setLfForm((f) => ({ ...f, kind: e.target.value }))} aria-label="Lost found kind">
              {['lost', 'found', 'damage'].map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
          <label>
            <span>Room</span>
            <select value={lfForm.room_id} onChange={(e) => setLfForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Lost found room">
              <option value="">Optional</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.code}</option>)}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Save</button></div>
        </form>
        <ul>
          {lostFound.map((x) => (
            <li key={x.id}>{x.kind}: {x.description} ({x.status})</li>
          ))}
          {!lostFound.length && <li className="muted">No lost-and-found records.</li>}
        </ul>
      </div>
      )}

      {show('maintenance') && (
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Maintenance</h2>
        <p className="muted">Leave dates empty to take the room out of service until the ticket is completed. Dated OOO only blocks overlapping nights.</p>
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
            <span>Issue</span>
            <input value={maintForm.title} onChange={(e) => setMaintForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Maintenance title" />
          </label>
          <label>
            <span>OOO from</span>
            <input type="date" value={maintForm.ooo_starts_on} onChange={(e) => setMaintForm((f) => ({ ...f, ooo_starts_on: e.target.value }))} aria-label="Out of order start date" />
          </label>
          <label>
            <span>OOO through</span>
            <input type="date" value={maintForm.ooo_ends_on} onChange={(e) => setMaintForm((f) => ({ ...f, ooo_ends_on: e.target.value }))} aria-label="Out of order end date" />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Create ticket (blocks room)</button>
          </div>
        </form>
        <table className="table" style={{ marginTop: 12 }}>
          <thead><tr><th>Room</th><th>Title</th><th>OOO</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {maint.map((t) => (
              <tr key={t.id}>
                <td>{t.room_code || t.room_id}</td>
                <td>{t.title}</td>
                <td>
                  {t.ooo_starts_on || t.ooo_ends_on
                    ? `${t.ooo_starts_on || '—'} → ${t.ooo_ends_on || '—'}`
                    : 'Until completed'}
                </td>
                <td>{t.status}</td>
                <td>
                  {t.status !== 'completed' && (
                    <button type="button" disabled={busy} onClick={() => act(`/hotel/maintenance/${t.id}/complete`, 'Ticket completed')}>Complete</button>
                  )}
                </td>
              </tr>
            ))}
            {!maint.length && <tr><td colSpan={5} className="muted">No maintenance tickets.</td></tr>}
          </tbody>
        </table>
      </div>
      )}

      {show('cashier') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel finance and cashiering</h2>
          <p className="muted">
            This records payment information only. It does not process cards, hold funds, or settle to a bank.
            Ledger posting uses existing{' '}
            <Link href="/accounting">Accounting</Link> and <Link href="/expenses">Expenses</Link>.
          </p>
          {cashierShift ? (
            <p>Open shift from {cashierShift.opened_at} · opening float {Number(cashierShift.opening_float || 0).toFixed(2)}</p>
          ) : (
            <p className="muted">No cashier shift is open.</p>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" disabled={busy || !!cashierShift} onClick={() => act('/hotel/cashier/shift/open', 'Shift opened', { opening_float: 0 })}>Open shift</button>
            <button type="button" disabled={busy || !cashierShift} onClick={() => act('/hotel/cashier/shift/close', 'Shift closed', { closing_float: 0 })}>Close shift</button>
            <button type="button" disabled={busy} onClick={() => act('/hotel/night-audits', 'Night audit posted')}>Run night audit</button>
          </div>
          <h3>Night audits</h3>
          <ul>
            {nightAudits.map((n) => (
              <li key={n.id}>{n.business_date} — occupancy {n.snapshot?.occupancy_rate ?? '—'}%</li>
            ))}
            {!nightAudits.length && <li className="muted">No night audits posted yet.</li>}
          </ul>
        </div>
      )}

      {show('supplies') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Inventory and procurement</h2>
          <p className="muted">
            Hotel stock (linen, toiletries, F&amp;B, cleaning supplies) uses the shared ERP inventory and purchasing
            workflows. There is no second stock ledger.
          </p>
          <ul>
            <li><Link href="/inventory?tab=products">Products and stock</Link></li>
            <li><Link href="/inventory?tab=lowstock">Low stock</Link></li>
            <li><Link href="/inventory?tab=adjust">Stock adjustments</Link></li>
            <li><Link href="/purchasing?tab=orders">Purchase orders</Link></li>
            <li><Link href="/purchasing?tab=grn">Goods received</Link></li>
            <li><Link href="/purchasing?tab=suppliers">Suppliers</Link></li>
          </ul>
        </div>
      )}

      {show('reports') && !report && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel reports</h2>
          <p className="muted">Reports could not be loaded. Occupancy on the dashboard still uses rooms and reservations.</p>
        </div>
      )}
      {show('reports') && report && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel reports</h2>
          <p className="muted">
            Occupancy {report.occupancy_rate}% · ADR {Number(report.adr || 0).toFixed(2)} · RevPAR{' '}
            {Number(report.revpar || 0).toFixed(2)} · Room revenue {Number(report.room_revenue || 0).toFixed(2)}
          </p>
          <p className="muted">
            Cancellations {report.cancellations} · No-shows {report.no_shows} · Occupied nights{' '}
            {report.occupied_nights}/{report.room_nights_available}
          </p>
          <p className="muted">
            Payments {Number(report.payments_total || 0).toFixed(2)} · Outstanding{' '}
            {Number(report.outstanding_guest_balances || 0).toFixed(2)}
          </p>
          <h3>Hotel-service sales</h3>
          <ul>
            {Object.entries(report.service_sales || {}).map(([k, v]) => (
              <li key={k}>{k}: {Number(v as number).toFixed(2)}</li>
            ))}
            {!Object.keys(report.service_sales || {}).length && <li className="muted">No service sales in this period.</li>}
          </ul>
          <h3>Inventory on hand</h3>
          <p className="muted">
            Uses the existing tenant inventory catalog (toiletries, linen, food, drinks).{' '}
            <Link href="/inventory?tab=products">Open inventory</Link>
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Stock</th>
              </tr>
            </thead>
            <tbody>
              {(report.inventory_usage || []).map((p: { id: string; sku?: string; name: string; stock_qty: number }) => (
                <tr key={p.id}>
                  <td>{p.sku || '—'}</td>
                  <td>{p.name}</td>
                  <td>{Number(p.stock_qty || 0)}</td>
                </tr>
              ))}
              {!(report.inventory_usage || []).length && (
                <tr><td colSpan={3} className="muted">No inventory products on this tenant yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {show('events') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Events and banquets</h2>
          <p className="muted">
            Book a named space. If you attach a guest room, overlapping reservations are blocked. This is not an OTA listing.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError('');
              try {
                await api('/hotel/events', {
                  method: 'POST',
                  body: JSON.stringify({
                    title: eventForm.title.trim(),
                    space_name: eventForm.space_name.trim(),
                    starts_on: eventForm.starts_on,
                    ends_on: eventForm.ends_on,
                    expected_guests: Number(eventForm.expected_guests) || 1,
                    room_id: eventForm.room_id || null,
                    guest_id: eventForm.guest_id || null,
                    status: 'confirmed',
                  }),
                });
                setEventForm({
                  title: '',
                  space_name: '',
                  starts_on: '',
                  ends_on: '',
                  expected_guests: '20',
                  room_id: '',
                  guest_id: '',
                });
                setMessage('Event booked');
                await refresh();
              } catch (err: any) {
                setError(err.message || 'Could not book event');
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
          >
            <label>
              <span>Title</span>
              <input value={eventForm.title} onChange={(e) => setEventForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Event title" />
            </label>
            <label>
              <span>Space</span>
              <input value={eventForm.space_name} onChange={(e) => setEventForm((f) => ({ ...f, space_name: e.target.value }))} required aria-label="Event space name" />
            </label>
            <label>
              <span>Starts</span>
              <input type="date" value={eventForm.starts_on} onChange={(e) => setEventForm((f) => ({ ...f, starts_on: e.target.value }))} required aria-label="Event start date" />
            </label>
            <label>
              <span>Ends</span>
              <input type="date" value={eventForm.ends_on} onChange={(e) => setEventForm((f) => ({ ...f, ends_on: e.target.value }))} required aria-label="Event end date" />
            </label>
            <label>
              <span>Expected guests</span>
              <input type="number" min={1} value={eventForm.expected_guests} onChange={(e) => setEventForm((f) => ({ ...f, expected_guests: e.target.value }))} aria-label="Event expected guests" />
            </label>
            <label>
              <span>Hold room (optional)</span>
              <select value={eventForm.room_id} onChange={(e) => setEventForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Event room hold">
                <option value="">None</option>
                {rooms.filter((r) => r.is_active).map((r) => (
                  <option key={r.id} value={r.id}>{r.code}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Organizer</span>
              <select value={eventForm.guest_id} onChange={(e) => setEventForm((f) => ({ ...f, guest_id: e.target.value }))} aria-label="Event organizer guest">
                <option value="">Optional</option>
                {guests.map((g) => (
                  <option key={g.id} value={g.id}>{g.full_name}</option>
                ))}
              </select>
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Book event</button>
            </div>
          </form>
          <table className="table" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Title</th>
                <th>Space</th>
                <th>Dates</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {events.map((evRow) => (
                <tr key={evRow.id}>
                  <td>{evRow.title}</td>
                  <td>{evRow.space_name}</td>
                  <td>{evRow.starts_on} → {evRow.ends_on}</td>
                  <td>{evRow.status}</td>
                  <td>
                    {evRow.status === 'inquiry' && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/events/${evRow.id}/confirm`, 'Event confirmed')}>Confirm</button>
                    )}
                    {evRow.status !== 'cancelled' && evRow.status !== 'completed' && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/events/${evRow.id}/cancel`, 'Event cancelled')}>Cancel</button>
                    )}
                  </td>
                </tr>
              ))}
              {!events.length && (
                <tr><td colSpan={5} className="muted">No events booked yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {show('settings') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel settings</h2>
          {canReadCompany && (
            <p className="muted">
              Logo, legal name, address, and tax IDs:{' '}
              <Link href="/company">Company profile</Link>
            </p>
          )}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError('');
              try {
                await api('/hotel/settings', {
                  method: 'PATCH',
                  body: JSON.stringify({
                    check_in_time: settingsForm.check_in_time,
                    check_out_time: settingsForm.check_out_time,
                    cancellation_hours: Number(settingsForm.cancellation_hours) || 24,
                    tax_percent: Number(settingsForm.tax_percent) || 0,
                    early_checkin_fee: Number(settingsForm.early_checkin_fee) || 0,
                    late_checkout_fee: Number(settingsForm.late_checkout_fee) || 0,
                    property_name: settingsForm.property_name.trim() || null,
                  }),
                });
                setMessage('Hotel settings saved');
                await refresh();
              } catch (err: any) {
                setError(err.message || 'Could not save settings');
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
          >
            <label>
              <span>Property name</span>
              <input value={settingsForm.property_name} onChange={(e) => setSettingsForm((f) => ({ ...f, property_name: e.target.value }))} aria-label="Hotel property name" />
            </label>
            <label>
              <span>Check-in time</span>
              <input value={settingsForm.check_in_time} onChange={(e) => setSettingsForm((f) => ({ ...f, check_in_time: e.target.value }))} aria-label="Hotel check-in time" />
            </label>
            <label>
              <span>Check-out time</span>
              <input value={settingsForm.check_out_time} onChange={(e) => setSettingsForm((f) => ({ ...f, check_out_time: e.target.value }))} aria-label="Hotel check-out time" />
            </label>
            <label>
              <span>Cancel hours</span>
              <input type="number" min={0} value={settingsForm.cancellation_hours} onChange={(e) => setSettingsForm((f) => ({ ...f, cancellation_hours: e.target.value }))} aria-label="Hotel cancellation hours" />
            </label>
            <label>
              <span>Tax %</span>
              <input type="number" min={0} step="0.01" value={settingsForm.tax_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, tax_percent: e.target.value }))} aria-label="Hotel tax percent" />
            </label>
            <label>
              <span>Early check-in fee</span>
              <input type="number" min={0} step="0.01" value={settingsForm.early_checkin_fee} onChange={(e) => setSettingsForm((f) => ({ ...f, early_checkin_fee: e.target.value }))} aria-label="Early check-in fee" />
            </label>
            <label>
              <span>Late checkout fee</span>
              <input type="number" min={0} step="0.01" value={settingsForm.late_checkout_fee} onChange={(e) => setSettingsForm((f) => ({ ...f, late_checkout_fee: e.target.value }))} aria-label="Late checkout fee" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Save settings</button>
            </div>
          </form>
        </div>
      )}

    </>
  );
}
