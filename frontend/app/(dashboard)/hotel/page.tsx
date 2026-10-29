'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import DashboardGreeting from '../../../components/DashboardGreeting';
import PageHeader from '../../../components/PageHeader';
import EmptyState from '../../../components/EmptyState';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { moduleEnabledForTenant } from '../../../lib/industryModules';
import { HotelRoomNightGrid } from '../../../components/HotelRoomNightGrid';
import { AmountField } from '../../../components/AmountField';
import { formatDate, formatDateTime, formatMoney } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { printDocumentHtml } from '../../../lib/documentPrint';

type Room = {
  id: string;
  code: string;
  name: string;
  room_type: string;
  floor?: string | null;
  bed_type?: string | null;
  max_occupancy: number;
  rate_amount: number;
  weekend_rate?: number | null;
  extra_person_charge?: number;
  status: string;
  housekeeping_status?: string;
  description?: string | null;
  notes?: string | null;
  amenities?: Record<string, unknown> | null;
  is_active: boolean;
};

type Guest = {
  id: string;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  nationality?: string | null;
  company_name?: string | null;
  loyalty_tier?: string | null;
  is_active: boolean;
};

type Reservation = {
  id: string;
  reservation_number: string;
  room_id: string;
  guest_id: string;
  room_code?: string | null;
  guest_name?: string | null;
  guest_phone?: string | null;
  check_in_date: string;
  check_out_date: string;
  nights: number;
  status: string;
  booking_source?: string;
  special_requests?: string | null;
  notes?: string | null;
  estimated_total: number;
  folio_id?: string | null;
  can_check_in?: boolean;
  can_confirm?: boolean;
  can_check_out?: boolean;
  can_cancel?: boolean;
  cancellation_hours?: number;
  inside_cancellation_window?: boolean;
  can_no_show?: boolean;
  can_extend?: boolean;
  can_move?: boolean;
  can_duplicate?: boolean;
  folio_balance?: number | null;
  checked_out_at?: string | null;
  deposit_amount?: number | null;
  deposit_method?: string | null;
  group_name?: string | null;
  discount_percent?: number | null;
};

type Folio = {
  id: string;
  folio_number: string;
  status?: string;
  balance: number;
  notes?: string | null;
  guest_name?: string | null;
  reservation_number?: string | null;
  reservation_status?: string | null;
  room_code?: string | null;
  check_in_date?: string | null;
  check_out_date?: string | null;
  checked_out_at?: string | null;
  charges_total: number;
  payments_total: number;
  charges: { id: string; description: string; charge_type?: string | null; quantity?: number; unit_amount?: number; discount_amount?: number; line_total: number; is_void: boolean }[];
  payments: { id: string; method: string; amount: number; reference?: string | null; notes?: string | null }[];
};

type HkTask = {
  id: string;
  room_id: string;
  room_code?: string | null;
  status: string;
  priority: string;
  assigned_to?: string | null;
  due_at?: string | null;
  notes?: string | null;
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
  assigned_to?: string | null;
  notes?: string | null;
  block_room?: boolean;
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
  online_stay_requests?: number;
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
  open_folio_count?: number;
  outstanding_folio_balance?: number;
  revenue_today?: number;
  room_revenue?: number;
  service_revenue?: number;
  meal_revenue?: number;
  drink_revenue?: number;
  payments_received?: number;
  housekeeping_pending?: number;
  housekeeping_overdue?: number;
  maintenance_open?: number;
  as_of?: string;
  guests_total: number;
  recent_reservations?: Reservation[];
  alerts?: { code: string; message: string; href?: string }[];
  low_stock?: { id: string; name: string; stock_qty: number }[];
  out_of_stock?: { id: string; name: string; stock_qty: number }[];
};

type HotelService = {
  id: string;
  code: string;
  name: string;
  category: string;
  unit_amount: number;
  tax_percent: number;
  notes?: string | null;
  is_active: boolean;
};

type FolioRow = {
  id: string;
  folio_number: string;
  status: string;
  balance: number;
  guest_name?: string | null;
  reservation_number?: string | null;
  reservation_status?: string | null;
  room_code?: string | null;
  check_in_date?: string | null;
  check_out_date?: string | null;
  checked_out_at?: string | null;
};

function localIso(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const ROOM_TYPES = ['standard', 'deluxe', 'executive', 'suite', 'family', 'other'];
const ROOM_AMENITIES = [
  'wifi',
  'air_conditioning',
  'television',
  'minibar',
  'safe',
  'balcony',
  'breakfast',
  'accessible',
] as const;
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
  { value: 'online', label: 'Online' },
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
  if (value == null || !Number.isFinite(value) || Math.abs(value) <= 0.05) return null;
  const cls = value > 0 ? 'up' : 'down';
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
        <circle cx={cx} cy={cx} r={r * 0.62} fill="var(--warn-bg)" stroke="var(--warn)" strokeWidth="8" />
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

function hotelWord(value: string | null | undefined) {
  const text = String(value || '').replace(/_/g, ' ').trim();
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function folioChargeWord(value: string | null | undefined) {
  const key = String(value || '').trim().toLowerCase();
  if (key === 'restaurant') return 'Meal';
  if (key === 'bar') return 'Drink';
  return hotelWord(key);
}

function bookingSourceWord(value: string | null | undefined) {
  const key = String(value || 'direct').trim().toLowerCase();
  const words: Record<string, string> = {
    direct: 'Direct',
    walk_in: 'Walk-in',
    corporate: 'Corporate',
    group: 'Group',
    phone: 'Phone',
    email: 'Email',
    website: 'Website',
    online: 'Online',
  };
  return words[key] || hotelWord(key);
}

function tenderWord(value: string | null | undefined) {
  const key = String(value || '').trim().toLowerCase();
  const words: Record<string, string> = {
    cash: 'Cash',
    momo: 'Mobile money',
    mobile_money: 'Mobile money',
    card: 'Card',
    bank: 'Bank transfer',
    credit: 'Credit',
    other: 'Other',
  };
  return words[key] || hotelWord(key);
}

function stayWhen(value: string | null | undefined, prefs: Parameters<typeof formatDate>[1]) {
  if (!value) return '—';
  const raw = String(value);
  const shown = formatDate(raw.includes('T') ? raw : `${raw.slice(0, 10)}T12:00:00`, prefs);
  return shown || '—';
}

function leftEarlyWhen(row: { status?: string; check_out_date?: string | null; checked_out_at?: string | null }): string {
  if (row.status !== 'checked_out') return '';
  const left = String(row.checked_out_at || '').slice(0, 10);
  const planned = String(row.check_out_date || '').slice(0, 10);
  if (!left || !planned || left >= planned) return '';
  return left;
}

function nextStayAfter(rows: Reservation[], roomId: string, night: string): string {
  const nightKey = String(night || '').slice(0, 10);
  const starts = rows
    .filter((r) => r.room_id === roomId && !['cancelled', 'no_show', 'waitlisted', 'checked_out'].includes(r.status))
    .map((r) => String(r.check_in_date || '').slice(0, 10))
    .filter((start) => start && nightKey && start > nightKey)
    .sort();
  return starts[0] || '';
}

function heldStay(rows: Reservation[], roomId: string, checkIn: string, checkOut: string): Reservation | null {
  const start = String(checkIn || '').slice(0, 10);
  const end = String(checkOut || '').slice(0, 10);
  if (!roomId || !start || !end || end <= start) return null;
  return rows.find((r) => {
    if (r.room_id !== roomId) return false;
    if (['cancelled', 'no_show', 'waitlisted', 'checked_out'].includes(r.status)) return false;
    const stayIn = String(r.check_in_date || '').slice(0, 10);
    const stayOut = String(r.check_out_date || '').slice(0, 10);
    return Boolean(stayIn && stayOut && stayIn < end && stayOut > start);
  }) || null;
}

function HotelDateInput({
  value,
  onChange,
  ariaLabel,
  required,
  prefs,
}: {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  required?: boolean;
  prefs: Parameters<typeof formatDate>[1];
}) {
  return (
    <span className="hotel-ops-date hotel-field-date">
      <span className="hotel-ops-date-face">{value ? stayWhen(value, prefs) : 'Select date'}</span>
      <input
        type="date"
        value={value}
        required={required}
        aria-label={ariaLabel}
        onChange={(e) => onChange(e.target.value)}
      />
    </span>
  );
}

function stayClock(value: string | null | undefined, prefs: Parameters<typeof formatDate>[1]) {
  if (!value) return '—';
  const shown = formatDateTime(value, prefs);
  return shown || '—';
}

function roomChipLabel(code?: string | null, name?: string | null) {
  const roomCode = String(code || '').trim();
  let roomName = String(name || '').trim();
  if (roomCode && roomName) {
    const lower = roomName.toLowerCase();
    const codeLower = roomCode.toLowerCase();
    if (lower === codeLower) roomName = '';
    else if (lower.endsWith(codeLower)) roomName = roomName.slice(0, roomName.length - roomCode.length).replace(/[\s·-]+$/g, '').trim();
    else if (lower.startsWith(codeLower)) roomName = roomName.slice(roomCode.length).replace(/^[\s·-]+/g, '').trim();
  }
  if (roomCode && roomName) return `${roomCode} · ${roomName}`;
  return roomCode || roomName || 'Room';
}

function roomPlainName(code?: string | null, name?: string | null) {
  const labeled = roomChipLabel(code, name);
  const roomCode = String(code || '').trim();
  const prefix = roomCode ? `${roomCode} · ` : '';
  if (prefix && labeled.startsWith(prefix)) return labeled.slice(prefix.length);
  return String(name || '').trim() || labeled;
}

function money(value: number | string | null | undefined) {
  return formatMoney(value ?? 0);
}

function escapeSlip(value: string) {
  return String(value || '').replace(/[&<>"]/g, (ch) =>
    ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : ch === '>' ? '&gt;' : '&quot;',
  );
}

function hotelSlipHtml(title: string, body: string) {
  return (
    `<!doctype html><html lang="en"><head><meta charset="utf-8"/>` +
    `<title>${escapeSlip(title)}</title>` +
    `<style>body{margin:24px;color:#10211b;font-family:"Segoe UI",Arial,sans-serif;background:#fff}` +
    `h1{color:#003d1f;font-size:18px}pre{white-space:pre-wrap;font:14px/1.45 "Segoe UI",Arial,sans-serif}` +
    `table{border-collapse:collapse;width:100%}td,th{padding:6px 8px;border-bottom:1px solid #d4e5c4;text-align:left}` +
    `th{background:#003d1f;color:#fff}@media print{body{margin:0}}</style></head>` +
    `<body><h1>${escapeSlip(title)}</h1>${body}</body></html>`
  );
}

export default function HotelPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = (searchParams?.get('tab') || '').trim().toLowerCase();
  const tab = rawTab || 'dashboard';
  const show = (section: string) => tab === section;
  const formatPrefs = useCompanyFormat();
  const [moduleAllowed, setModuleAllowed] = useState<boolean | null>(null);
  const [canReadCompany, setCanReadCompany] = useState(false);
  const [staffId, setStaffId] = useState('');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [listsReady, setListsReady] = useState(false);
  const [sectionHash, setSectionHash] = useState('');
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [hkTasks, setHkTasks] = useState<HkTask[]>([]);
  const [maint, setMaint] = useState<MaintTicket[]>([]);
  const [services, setServices] = useState<HotelService[]>([]);
  const [folioRows, setFolioRows] = useState<FolioRow[]>([]);
  const [availRooms, setAvailRooms] = useState<Room[]>([]);
  const [availForm, setAvailForm] = useState(() => {
    const checkIn = localIso();
    return { check_in_date: checkIn, check_out_date: shiftIso(checkIn, 1), room_type: '' };
  });
  const [serviceForm, setServiceForm] = useState({
    code: '',
    name: '',
    category: 'laundry',
    unit_amount: '0',
    tax_percent: '0',
    notes: '',
  });
  const [serviceCharge, setServiceCharge] = useState({ service_id: '', quantity: '1' });
  const [mealForm, setMealForm] = useState({
    folio_id: '',
    service_id: '',
    quantity: '1',
    description: '',
    unit_amount: '0',
    charge_type: '',
  });
  const [guestHistory, setGuestHistory] = useState<any>(null);
  const [folio, setFolio] = useState<Folio | null>(null);
  const [folioNote, setFolioNote] = useState('');
  const [listKind, setListKind] = useState('');
  const [deskKind, setDeskKind] = useState('arrivals');
  const [error, setError] = useState('');
  const [extrasNotice, setExtrasNotice] = useState('');
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
    weekend_rate: '',
    extra_person_charge: '0',
    description: '',
    notes: '',
    amenities: {
      wifi: false,
      air_conditioning: false,
      television: false,
      minibar: false,
      safe: false,
      balcony: false,
      breakfast: false,
      accessible: false,
    },
    status: 'available',
  });
  const [guestForm, setGuestForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    nationality: '',
    address: '',
    company_name: '',
    travel_agent: '',
    loyalty_tier: '',
    id_type: '',
    id_document: '',
    emergency_contact: '',
    preferences: '',
    notes: '',
    consent_marketing: false,
  });
  const [resForm, setResForm] = useState(() => {
    const checkIn = localIso();
    return {
      room_id: '',
      guest_id: '',
      new_guest_name: '',
      check_in_date: checkIn,
      check_out_date: shiftIso(checkIn, 1),
      adults: '1',
      children: '0',
      booking_source: 'direct',
      rate_plan_id: '',
      special_requests: '',
      notes: '',
      deposit_amount: '0',
      deposit_method: 'cash',
      discount_percent: '0',
      walk_in: false,
      waitlist: false,
    };
  });
  const refreshSeq = useRef(0);
  const [chargeForm, setChargeForm] = useState({ description: '', unit_amount: '0', quantity: '1', discount_amount: '0', charge_type: 'extra' });
  const [payForm, setPayForm] = useState({ method: 'cash', amount: '0', reference: '', notes: '' });
  const [hkForm, setHkForm] = useState({
    room_id: '',
    assigned_to: '',
    priority: 'normal',
    task_type: 'cleaning',
    notes: '',
    due_on: '',
    due_time: '',
  });
  const [maintForm, setMaintForm] = useState({
    room_id: '',
    title: '',
    priority: 'normal',
    block_room: true,
    ooo_starts_on: '',
    ooo_ends_on: '',
    assigned_to: '',
    notes: '',
  });
  const [extendDate, setExtendDate] = useState('');
  const [moveRoomId, setMoveRoomId] = useState('');
  const [report, setReport] = useState<any>(null);
  const [calendar, setCalendar] = useState<any>(null);
  const [resGridStart, setResGridStart] = useState(() => localIso());
  const [resGridSpan, setResGridSpan] = useState(14);
  const [availTonightIds, setAvailTonightIds] = useState<string[]>([]);
  const [calTick, setCalTick] = useState(0);
  const [settings, setSettings] = useState<any>(null);
  const [groupRooms, setGroupRooms] = useState<string[]>([]);
  const [groupName, setGroupName] = useState('');
  const [groupNotes, setGroupNotes] = useState('');
  const [dashDate] = useState(() => localIso());
  const [reportStart, setReportStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return localIso(d);
  });
  const [reportEnd, setReportEnd] = useState(() => localIso());
  const [cashierFloat, setCashierFloat] = useState('0');
  const [cashierNotes, setCashierNotes] = useState('');
  const [auditNote, setAuditNote] = useState('');
  const [ratePlans, setRatePlans] = useState<any[]>([]);
  const [guestRequests, setGuestRequests] = useState<any[]>([]);
  const [lostFound, setLostFound] = useState<any[]>([]);
  const [cashierShift, setCashierShift] = useState<any>(null);
  const [closedShifts, setClosedShifts] = useState<any[]>([]);
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
    deposit_amount: '0',
    notes: '',
  });
  const [rateForm, setRateForm] = useState({
    code: '',
    name: '',
    amount: '0',
    room_type: '',
    min_nights: '1',
    weekday_only: false,
    weekend_only: false,
    starts_on: '',
    ends_on: '',
  });
  const [reqForm, setReqForm] = useState({
    title: '',
    kind: 'service',
    reservation_id: '',
    room_id: '',
    due_on: '',
    due_time: '',
    notes: '',
  });
  const [lfForm, setLfForm] = useState({ description: '', kind: 'lost', room_id: '', notes: '' });
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
    no_show_fee_percent: '0',
    service_charge_percent: '0',
    property_name: '',
    notes: '',
    food_outlet_mode: 'together',
  });
  const [stayLink, setStayLink] = useState<Record<string, any> | null>(null);
  const [stayForm, setStayForm] = useState({ hostname: '', link_kind: 'existing' });
  const [stayOrigin, setStayOrigin] = useState('');

  const availableRooms = useMemo(
    () =>
      rooms.filter(
        (r) =>
          r.is_active &&
          !['maintenance', 'out_of_order', 'blocked', 'dirty', 'occupied'].includes(r.status)
      ),
    [rooms]
  );

  async function soft<T>(path: string, fallback: T, failed: string[]): Promise<T> {
    try {
      const res = await api(path);
      return (res.data ?? fallback) as T;
    } catch {
      failed.push(path);
      return fallback;
    }
  }

  async function refresh() {
    const seq = ++refreshSeq.current;
    const filter = tab === 'front-desk' ? deskKind : listKind;
    const qs = filter ? `?list_kind=${filter}` : '';
    const [sRes, rRes, gRes, resvRes, setRes] = await Promise.allSettled([
      api(`/hotel/summary?on_date=${dashDate}`),
      api('/hotel/rooms?is_active=true'),
      api('/hotel/guests?is_active=true'),
      api(`/hotel/reservations${qs}`),
      api('/hotel/settings'),
    ]);
    if (seq !== refreshSeq.current) return;
    if (sRes.status === 'fulfilled') setSummary(sRes.value.data || null);
    if (rRes.status === 'fulfilled') setRooms(rRes.value.data || []);
    if (gRes.status === 'fulfilled') setGuests(gRes.value.data || []);
    if (resvRes.status === 'fulfilled') setReservations(resvRes.value.data || []);
    if (setRes.status === 'fulfilled') {
      const setData = setRes.value.data || null;
      setSettings(setData);
      if (setData) {
        setSettingsForm({
          check_in_time: setData.check_in_time || '14:00',
          check_out_time: setData.check_out_time || '11:00',
          cancellation_hours: String(setData.cancellation_hours ?? 24),
          tax_percent: String(setData.tax_percent ?? 0),
          early_checkin_fee: String(setData.early_checkin_fee ?? 0),
          late_checkout_fee: String(setData.late_checkout_fee ?? 0),
          no_show_fee_percent: String(setData.no_show_fee_percent ?? 0),
          service_charge_percent: String(setData.service_charge_percent ?? 0),
          property_name: setData.property_name || '',
          notes: setData.notes || '',
          food_outlet_mode: setData.food_outlet_mode === 'separate' ? 'separate' : 'together',
        });
      }
    }
    const roomFail = rRes.status === 'rejected' ? rRes.reason : null;
    const stayFail = resvRes.status === 'rejected' ? resvRes.reason : null;
    const guestFail = gRes.status === 'rejected' ? gRes.reason : null;
    if (roomFail || stayFail) {
      setError(hotelErr(roomFail || stayFail, 'Could not load rooms and reservations. Try again.'));
    } else {
      setError('');
    }
    const extraFailed: string[] = [];
    if (guestFail) extraFailed.push('/hotel/guests');
    if (sRes.status === 'rejected') extraFailed.push('/hotel/summary');
    if (setRes.status === 'rejected') extraFailed.push('/hotel/settings');

    const extraPaths: string[] = [];
    if (tab === 'dashboard' || tab === 'front-desk') extraPaths.push('/hotel/guest-requests');
    if (tab === 'rooms' || tab === 'reservations') extraPaths.push('/hotel/rate-plans');
    if (tab === 'reservations') extraPaths.push('/hotel/booking-link');
    if (tab === 'housekeeping' || tab === 'dashboard') extraPaths.push('/hotel/housekeeping');
    if (tab === 'maintenance') extraPaths.push('/hotel/maintenance');
    if (tab === 'services' || tab === 'restaurant' || tab === 'bar') extraPaths.push('/hotel/services');
    if (tab === 'restaurant' || tab === 'bar') extraPaths.push('/hotel/folios');
    if (tab === 'billing' || tab === 'reservations' || tab === 'front-desk') extraPaths.push('/hotel/folios');
    if (tab === 'reports') extraPaths.push(`/hotel/reports?start_date=${reportStart}&end_date=${reportEnd}`);
    if (tab === 'front-desk' || tab === 'housekeeping') extraPaths.push('/hotel/lost-found');
    if (tab === 'cashier') {
      extraPaths.push('/hotel/cashier/shift', '/hotel/cashier/shifts', '/hotel/night-audits');
    }
    if (tab === 'events') extraPaths.push('/hotel/events');

    const extraResults = await Promise.all(
      extraPaths.map(async (path) => ({
        path,
        data: await soft<any>(
          path,
          path.includes('/reports') || path.includes('/shift') || path === '/hotel/booking-link' ? null : [],
          extraFailed
        ),
      }))
    );
    if (seq !== refreshSeq.current) return;
    for (const row of extraResults) {
      if (row.path === '/hotel/housekeeping') setHkTasks(row.data || []);
      else if (row.path === '/hotel/maintenance') setMaint(row.data || []);
      else if (row.path.startsWith('/hotel/reports')) setReport(row.data);
      else if (row.path === '/hotel/services') setServices(row.data || []);
      else if (row.path === '/hotel/folios') setFolioRows(row.data || []);
      else if (row.path === '/hotel/rate-plans') setRatePlans(row.data || []);
      else if (row.path === '/hotel/guest-requests') setGuestRequests(row.data || []);
      else if (row.path === '/hotel/lost-found') setLostFound(row.data || []);
      else if (row.path === '/hotel/cashier/shift') setCashierShift(row.data);
      else if (row.path === '/hotel/cashier/shifts') setClosedShifts(row.data || []);
      else if (row.path === '/hotel/night-audits') setNightAudits(row.data || []);
      else if (row.path === '/hotel/events') setEvents(row.data || []);
      else if (row.path === '/hotel/booking-link') {
        const link = row.data || null;
        setStayLink(link);
        if (link?.hostname) setStayForm({ hostname: link.hostname, link_kind: link.link_kind || 'existing' });
      }
    }
    setExtrasNotice(
      extraFailed.length
        ? 'Some hotel extras could not load (housekeeping, reports, cashier, or events). Rooms and reservations are still available.'
        : ''
    );
    setCalTick((n) => n + 1);
    setListsReady(true);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('ribdigi-onboarding-refresh'));
    }
  }

  useEffect(() => {
    setStayOrigin(window.location.origin);
    const read = () => setSectionHash(window.location.hash.replace(/^#/, ''));
    read();
    window.addEventListener('hashchange', read);
    const timer = window.setInterval(read, 300);
    return () => {
      window.removeEventListener('hashchange', read);
      window.clearInterval(timer);
    };
  }, [tab]);

  useEffect(() => {
    if (!sectionHash) return;
    const timer = window.setTimeout(() => {
      document.getElementById(sectionHash)?.scrollIntoView({ block: 'start' });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [sectionHash, listsReady, tab]);

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
        setStaffId(typeof me.data?.id === 'string' ? me.data.id : '');
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
        if (active) {
          setListsReady(true);
          setError(hotelErr(err, 'Could not load hotel'));
        }
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
        if (live) {
          setCalendar(null);
          setExtrasNotice((n) => n || 'Room calendar could not load. Rooms and reservations are still available.');
        }
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

  useEffect(() => {
    setFolioNote(folio?.notes || '');
  }, [folio?.id, folio?.notes]);

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
          weekend_rate: roomForm.weekend_rate.trim() ? Number(roomForm.weekend_rate) : null,
          extra_person_charge: Number(roomForm.extra_person_charge) || 0,
          description: roomForm.description.trim() || null,
          notes: roomForm.notes.trim() || null,
          amenities: roomForm.amenities,
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
        weekend_rate: '',
        extra_person_charge: '0',
        description: '',
        notes: '',
        amenities: {
          wifi: false,
          air_conditioning: false,
          television: false,
          minibar: false,
          safe: false,
          balcony: false,
          breakfast: false,
          accessible: false,
        },
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
          address: guestForm.address.trim() || null,
          company_name: guestForm.company_name.trim() || null,
          travel_agent: guestForm.travel_agent.trim() || null,
          loyalty_tier: guestForm.loyalty_tier.trim() || null,
          id_type: guestForm.id_type.trim() || null,
          id_document: guestForm.id_document.trim() || null,
          emergency_contact: guestForm.emergency_contact.trim() || null,
          preferences: guestForm.preferences.trim() || null,
          notes: guestForm.notes.trim() || null,
          consent_marketing: guestForm.consent_marketing,
        }),
      });
      setGuestForm({
        full_name: '',
        email: '',
        phone: '',
        nationality: '',
        address: '',
        company_name: '',
        travel_agent: '',
        loyalty_tier: '',
        id_type: '',
        id_document: '',
        emergency_contact: '',
        preferences: '',
        notes: '',
        consent_marketing: false,
      });
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
      const discountPercent = Number(resForm.discount_percent) || 0;
      if (discountPercent > 100) {
        setError('Stay discount percent cannot be above 100.');
        setBusy(false);
        return;
      }
      if (discountPercent > 0 && !staffId) {
        setError('Sign in again before applying a stay discount.');
        setBusy(false);
        return;
      }
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
          rate_plan_id: resForm.rate_plan_id.trim() || null,
          special_requests: resForm.special_requests.trim() || null,
          notes: resForm.notes.trim() || null,
          deposit_amount: Number(resForm.deposit_amount) || 0,
          deposit_method: Number(resForm.deposit_amount) > 0 ? resForm.deposit_method : null,
          discount_percent: discountPercent,
          discount_authorized_by: discountPercent > 0 ? staffId : null,
          walk_in: resForm.walk_in,
          status: resForm.walk_in ? 'booked' : resForm.waitlist ? 'waitlisted' : 'booked',
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
        check_in_date: localIso(),
        check_out_date: shiftIso(localIso(), 1),
        adults: '1',
        children: '0',
        booking_source: 'direct',
        rate_plan_id: '',
        special_requests: '',
        notes: '',
        deposit_amount: '0',
        deposit_method: 'cash',
        discount_percent: '0',
        walk_in: false,
        waitlist: false,
      });
      setMessage(wasWalkIn ? 'Walk-in checked in' : resForm.waitlist ? 'Added to the waiting list' : 'Reservation created');
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
      return true;
    } catch (err: any) {
      setError(hotelErr(err, 'Could not complete that action'));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function checkOutStay(reservationId: string) {
    setError('');
    setMessage('');
    try {
      let bal = 0;
      try {
        const f = await api(`/hotel/reservations/${reservationId}/folio`);
        if (f.data) setFolio(f.data);
        bal = Number(f.data?.balance || 0);
      } catch {
        bal = 0;
      }
      if (bal > 0.009) {
        const ok = window.confirm(
          `This guest bill still has ${money(bal)} outstanding. Check out anyway and leave the balance, or cancel and record payment first.`,
        );
        if (!ok) {
          setError('Record a folio payment before check-out, or confirm leaving the balance.');
          return;
        }
        await act(`/hotel/reservations/${reservationId}/check-out`, 'Checked out', { allow_balance: true });
        return;
      }
      await act(`/hotel/reservations/${reservationId}/check-out`, 'Checked out');
    } catch (err: unknown) {
      setError(hotelErr(err, 'Could not check out'));
    }
  }

  async function printStaySlip(reservationId: string, reservationNumber: string) {
    try {
      const conf = await api(`/hotel/reservations/${reservationId}/confirmation`);
      const text = String(conf.data?.text || 'Confirmation loaded');
      const html = hotelSlipHtml(
        `Reservation ${reservationNumber}`,
        `<pre>${escapeSlip(text)}</pre>`,
      );
      if (!printDocumentHtml(html)) {
        setError('Could not open the confirmation slip for printing.');
        return;
      }
      setMessage('Confirmation slip sent to print');
    } catch (err: unknown) {
      setError(hotelErr(err, 'Could not load confirmation slip'));
    }
  }

  function printFolioSlip() {
    if (!folio) return;
    const left = leftEarlyWhen({
      status: folio.reservation_status || undefined,
      check_out_date: folio.check_out_date,
      checked_out_at: folio.checked_out_at,
    });
    const stayLines = [
      folio.guest_name ? `Guest: ${folio.guest_name}` : '',
      folio.room_code ? `Room: ${folio.room_code}` : '',
      folio.reservation_number ? `Stay: ${folio.reservation_number}` : '',
      folio.check_in_date ? `Check-in: ${String(folio.check_in_date).slice(0, 10)}` : '',
      folio.check_out_date ? `Check-out: ${String(folio.check_out_date).slice(0, 10)}` : '',
      left ? `Left: ${left}` : '',
    ].filter(Boolean);
    const chargeRows = folio.charges
      .map(
        (c) =>
          `<tr><td>${escapeSlip(folioChargeWord(c.charge_type))} · ${escapeSlip(c.description)}</td><td>${escapeSlip(money(c.line_total))}${c.is_void ? ' (void)' : ''}</td></tr>`,
      )
      .join('');
    const payRows = folio.payments
      .map((p) => {
        const label = p.reference ? `${tenderWord(p.method)} · ${p.reference}` : tenderWord(p.method);
        return `<tr><td>${escapeSlip(label)}</td><td>${escapeSlip(money(p.amount))}</td></tr>`;
      })
      .join('');
    const html = hotelSlipHtml(
      `Folio ${folio.folio_number}`,
      `${stayLines.map((line) => `<p>${escapeSlip(line)}</p>`).join('')}` +
        `<p>Charges ${escapeSlip(money(folio.charges_total))} · Payments ${escapeSlip(money(folio.payments_total))} · Balance <strong>${escapeSlip(money(folio.balance))}</strong></p>` +
        `<h2>Charges</h2><table><thead><tr><th>Description</th><th>Amount</th></tr></thead><tbody>${chargeRows || '<tr><td colspan="2">No charges</td></tr>'}</tbody></table>` +
        `<h2>Payments</h2><table><thead><tr><th>Method</th><th>Amount</th></tr></thead><tbody>${payRows || '<tr><td colspan="2">No payments</td></tr>'}</tbody></table>`,
    );
    if (!printDocumentHtml(html)) {
      setError('Could not open the folio for printing.');
      return;
    }
    setMessage('Folio sent to print');
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

  async function saveFolioNote() {
    if (!folio) return;
    const note = folioNote.trim();
    if (!note) {
      setError('Leave the note empty and the saved note stays.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/folios/${folio.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notes: note }),
      });
      setFolio(f.data || folio);
      setMessage('Folio note saved');
    } catch (err: any) {
      setError(hotelErr(err, 'Could not save the folio note'));
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
      const quantity = Number(chargeForm.quantity);
      const discount = Number(chargeForm.discount_amount) || 0;
      const unit = Number(chargeForm.unit_amount) || 0;
      if (!Number.isFinite(quantity) || quantity <= 0) {
        setError('Folio charge quantity must be above zero.');
        setBusy(false);
        return;
      }
      if (!Number.isFinite(discount) || discount < 0 || discount > quantity * unit) {
        setError('Folio charge discount cannot be above the line.');
        setBusy(false);
        return;
      }
      const f = await api(`/hotel/folios/${folio.id}/charges`, {
        method: 'POST',
        body: JSON.stringify({
          charge_type: chargeForm.charge_type,
          description: chargeForm.description.trim(),
          unit_amount: unit,
          quantity,
          discount_amount: discount,
        }),
      });
      setFolio(f.data || null);
      setChargeForm({ description: '', unit_amount: '0', quantity: '1', discount_amount: '0', charge_type: 'extra' });
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
          reference: payForm.reference.trim() || null,
          notes: payForm.notes.trim() || null,
        }),
      });
      setFolio(f.data || null);
      setPayForm({ method: 'cash', amount: '0', reference: '', notes: '' });
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
      const dueOn = hkForm.due_on.trim();
      const dueTime = hkForm.due_time.trim();
      const dueAt = dueOn && dueTime
        ? `${dueOn}T${dueTime.length === 5 ? `${dueTime}:00` : dueTime}`
        : (dueOn || dueTime || null);
      await api('/hotel/housekeeping', {
        method: 'POST',
        body: JSON.stringify({
          room_id: hkForm.room_id,
          assigned_to: hkForm.assigned_to.trim() || null,
          priority: hkForm.priority,
          task_type: hkForm.task_type,
          notes: hkForm.notes.trim() || null,
          due_at: dueAt,
        }),
      });
      setHkForm({
        room_id: '',
        assigned_to: '',
        priority: 'normal',
        task_type: 'cleaning',
        notes: '',
        due_on: '',
        due_time: '',
      });
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
          block_room: maintForm.block_room,
          ooo_starts_on: maintForm.ooo_starts_on || null,
          ooo_ends_on: maintForm.ooo_ends_on || null,
          assigned_to: maintForm.assigned_to.trim() || null,
          notes: maintForm.notes.trim() || null,
        }),
      });
      setMaintForm({ room_id: '', title: '', priority: 'normal', block_room: true, ooo_starts_on: '', ooo_ends_on: '', assigned_to: '', notes: '' });
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
        <PageHeader title="Hotel management" subtitle="Loading hotel data…" />
      </>
    );
  }

  if (moduleAllowed === false) {
    return (
      <>
        <PageHeader title="Hotel" />
        <p className="login-error" role="alert">
          {error ||
            'Hotel module is not available for this business type. Switch the company industry to Hotel (and ensure the package includes hotel) to use rooms and reservations.'}
        </p>
      </>
    );
  }

  const foodTogether = (settingsForm.food_outlet_mode || 'together') !== 'separate';
  const foodKind = tab === 'bar' ? 'bar' : 'restaurant';
  const foodCategories = foodTogether ? ['restaurant', 'bar'] : [foodKind];
  const foodCharge =
    foodTogether && (mealForm.charge_type === 'bar' || mealForm.charge_type === 'restaurant')
      ? mealForm.charge_type
      : foodKind;
  const foodNoun = foodCharge === 'bar' ? 'drink' : 'meal';

  return (
    <>
      {show('dashboard') ? (
        <DashboardGreeting desk="Hotel dashboard" place={settings?.property_name || ''} />
      ) : (
      <PageHeader
        title="Hotel management"
        subtitle={
          ({
            dashboard: 'Occupancy, arrivals, and alerts for today.',
            reservations: 'Search rooms, then book a stay. Same room cannot overlap.',
            'front-desk': 'Check guests in and out, and log requests.',
            rooms: 'Room list, nightly rates, and rate plans.',
            housekeeping: 'Cleaning tasks and lost-and-found notes.',
            maintenance: 'Repair tickets. Dated blocks only close those nights.',
            guests: 'Guest profiles, stay history, and merge duplicates.',
            billing: 'Guest bills and payment notes. Cards are not charged here.',
            cashier: 'Front-desk float and night audit. This is a payment note, not the shop till and not a card charge.',
            supplies: 'Linen, toiletries, food and beverage, and cleaning supplies.',
            services: 'Extras (laundry, spa, meals, drinks) posted onto a guest bill.',
            restaurant: foodTogether
              ? 'Meals and drinks on one desk. Both post to the guest bill. This is not the sales till.'
              : 'Meals on the restaurant desk. Drinks stay on the bar desk. Both post to the guest bill.',
            bar: foodTogether
              ? 'Meals and drinks on one desk. Both post to the guest bill. This is not the sales till.'
              : 'Drinks on the bar desk. Meals stay on the restaurant desk. Both post to the guest bill.',
            reports: 'Occupancy, room revenue, payments, and supplies.',
            events: 'Banquets and meeting space. Optional room hold blocks that room.',
            settings: 'Property name, check-in times, and fees.',
          } as Record<string, string>)[tab]
        }
      />
      )}
      {error && (
        <p className="hotel-banner warn" role="alert">
          {error}
        </p>
      )}
      {extrasNotice && !error && (
        <p className="hotel-banner warn" role="status">
          {extrasNotice}
        </p>
      )}
      {message && <p className="hotel-banner ok">{message}</p>}

      {show('dashboard') && (
        <div className="hotel-ops">
          {!summary && !error && <p className="empty">Loading operational totals…</p>}
          {summary && (() => {
            const mix = summary.room_status_mix || {};
            const tot = Math.max(1, summary.rooms_total || 0);
            const occupiedN = mix.occupied ?? summary.rooms_occupied ?? 0;
            const reservedN = mix.reserved ?? summary.rooms_reserved ?? 0;
            const availableN = mix.available ?? summary.rooms_available;
            const notReadyN = (mix.dirty || summary.rooms_dirty || 0) + (mix.out_of_service || summary.rooms_maintenance || 0);
            const segs = [
              { key: 'occupied', color: 'var(--brand-dark)', n: occupiedN },
              { key: 'reserved', color: 'var(--brand)', n: reservedN },
              { key: 'available', color: 'var(--deep-green)', n: availableN },
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
              const k = bookingSourceWord(r.booking_source);
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
            const liveRooms = rooms.filter((r) => r.is_active);
            const night = summary.as_of || dashDate;
            const soldTonightIds = new Set(
              reservations
                .filter((r) => {
                  if (['cancelled', 'no_show', 'waitlisted'].includes(r.status)) return false;
                  const start = String(r.check_in_date || '').slice(0, 10);
                  let end = String(r.check_out_date || '').slice(0, 10);
                  if (r.status === 'checked_out' && r.checked_out_at) {
                    const left = r.checked_out_at.slice(0, 10);
                    if (left && left < end) end = left;
                  }
                  return Boolean(start && end && night >= start && night < end);
                })
                .map((r) => r.room_id)
            );
            const assigned = [
              ...liveRooms.filter((r) => soldTonightIds.has(r.id)),
              ...liveRooms.filter((r) => !soldTonightIds.has(r.id)),
            ].slice(0, 10);
            return (
              <>
                <div className="hotel-ops-kpis">
                  <div className="hotel-kpi hotel-kpi-graphic is-occ">
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
                        {trend.slice(-14).map((p) => {
                          const rate = Number(p.occupancy_rate);
                          const filled = rate > 0.05 ? Math.min(100, rate) : 0;
                          return (
                            <span key={p.date} className="tick">
                              <i style={{ height: filled > 0 ? `${filled}%` : '0%' }} />
                            </span>
                          );
                        })}
                      </div>
                    </div>
                    <div className="hint">
                      {soldN} of {summary.rooms_total} {Number(summary.rooms_total) === 1 ? 'room' : 'rooms'} sold tonight
                    </div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic is-avail">
                    <div className="lbl">Available rooms</div>
                    <div className="val">{availableN}</div>
                    <div className="hotel-kpi-visual center">
                      <HotelDonut segments={mixDonut} size={96} stroke={14} />
                    </div>
                    <div className="hint">{summary.rooms_total} rooms on the property</div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic is-rev">
                    <div className="lbl">Revenue</div>
                    <div className="val">{money(summary.revenue_today)}</div>
                    <div className="hotel-rev-bars" aria-label="Room, extras, and payments">
                      {[
                        { k: 'Room', n: Number(summary.room_revenue || 0), c: 'var(--brand)' },
                        { k: 'Extras', n: Number(summary.service_revenue || 0), c: 'var(--brand-dark)' },
                        { k: 'Paid', n: Number(summary.payments_received || 0), c: 'var(--forest)' },
                      ].map((b) => {
                        const mx = Math.max(1, Number(summary.revenue_today || 0), Number(summary.payments_received || 0), b.n);
                        const filled = b.n > 0 ? Math.max(22, (b.n / mx) * 100) : 0;
                        return (
                          <span key={b.k} className="rev-col" title={`${b.k} ${money(b.n)}`}>
                            <i style={{ height: `${filled}%`, background: b.c }} />
                            <em>{b.k}</em>
                          </span>
                        );
                      })}
                    </div>
                    <div className="hint">
                      Room {money(summary.room_revenue)} · meals {money(summary.meal_revenue)} · drinks{' '}
                      {money(summary.drink_revenue)} · other extras{' '}
                      {money(Math.max(0, Number(summary.service_revenue || 0) - Number(summary.meal_revenue || 0) - Number(summary.drink_revenue || 0)))}
                    </div>
                  </div>
                  <div className="hotel-kpi hotel-kpi-graphic is-cio">
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
                    <div className="hint">{summary.reservations_in_house} in house · payments {money(summary.payments_received)}</div>
                  </div>
                </div>

                <div className="hotel-ops-split">
                  <div className="panel">
                    <h3>Room availability</h3>
                    <p className="hint">How the rooms stand on this date.</p>
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
                        <div key={s.key} className={`q is-${s.key.replace(' ', '-')}`}>
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
                    <p className="hint">Sold nights, plus cancellations and no-shows.</p>
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
                    <p className="hint">Open a hotel desk.</p>
                    <div className="hotel-quick">
                      <Link href="/hotel?tab=rooms">Rooms and rates</Link>
                      <Link href="/hotel?tab=front-desk">Front desk</Link>
                      <Link href="/hotel?tab=reports">Hotel reports</Link>
                      <Link href="/hotel?tab=maintenance">
                        Maintenance
                        {(summary.maintenance_open || 0) > 0 ? <span className="qbadge">{summary.maintenance_open}</span> : null}
                      </Link>
                      <Link href="/hotel?tab=housekeeping">
                        Housekeeping
                        {(summary.housekeeping_pending || 0) > 0 ? <span className="qbadge">{summary.housekeeping_pending}</span> : null}
                      </Link>
                      <Link href="/hotel?tab=billing">Billing</Link>
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Guest requests</h3>
                    <p className="hint">Open requests and housekeeping still due.</p>
                    <div className="hotel-req-stats">
                      <div>
                        <div className="n">{reqOpen}</div>
                        <div className="k">Open</div>
                      </div>
                      <div>
                        <div className="n">{summary.housekeeping_overdue ?? 0}</div>
                        <div className="k">Overdue</div>
                      </div>
                      <div>
                        <div className="n">{reqDone}</div>
                        <div className="k">Done</div>
                      </div>
                    </div>
                    <ul className="hotel-req-list">
                      {guestRequests.slice(0, 5).map((q) => (
                        <li key={q.id}>
                          {q.title} · {hotelWord(q.kind)}{' '}
                          <span className={statusClass(String(q.status || ''))}>{hotelWord(q.status)}</span>
                          {q.due_at ? <div className="muted">{stayClock(q.due_at, formatPrefs)}</div> : null}
                          {q.room_id ? <div className="muted">{rooms.find((r) => r.id === q.room_id)?.code}</div> : null}
                        </li>
                      ))}
                      {!guestRequests.length && <li className="muted">No guest requests.</li>}
                    </ul>
                    {(summary.online_stay_requests || 0) > 0 && (
                      <p className="hint" style={{ marginTop: 10 }}>
                        <Link href="/hotel?tab=reservations">
                          {(summary.online_stay_requests || 0) === 1
                            ? '1 stay request is waiting.'
                            : `${summary.online_stay_requests} stay requests are waiting.`}
                        </Link>
                      </p>
                    )}
                    {(summary.alerts || []).length ? (
                      <ul className="hotel-alert-list">
                        {(summary.alerts || []).map((a) => (
                          <li key={a.code}>
                            {a.href ? <Link href={a.href}>{a.message}</Link> : <span>{a.message}</span>}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="hint" style={{ marginTop: 10 }}>No operational alerts.</p>
                    )}
                  </div>
                  <div className="panel">
                    <h3>Guest purpose</h3>
                    <p className="hint">Corporate and group stays, and other bookings.</p>
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
                        {purpose.business ? ` (${Math.round((purpose.business / purposeTotal) * 100)}%)` : ''}
                      </li>
                      <li>
                        <span className="sw" style={{ background: 'var(--brand)' }} />
                        Leisure {purpose.leisure}
                        {purpose.leisure ? ` (${Math.round((purpose.leisure / purposeTotal) * 100)}%)` : ''}
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
                    <p className="hint">Share of rooms sold each night.</p>
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
                    <p className="hint">Arrivals, departures, and who is in house.</p>
                    <div className="hotel-cio">
                      <div className="hotel-cio-item is-in">
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
                      <div className="hotel-cio-item is-out">
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
                      <div className="hotel-cio-item is-stay">
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
                            <div className="seg sold" style={{ height: p.sold ? `${Math.max(8, (p.sold / Math.max(1, tot)) * 100)}%` : '0%' }} />
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
                    <ul className="hotel-book-list">
                      {(summary.recent_reservations || []).map((r) => (
                        <li key={r.id}>
                          <div className="hotel-book-main">
                            <strong>{r.room_code || '—'}</strong>
                            <span>{r.guest_name || '—'}</span>
                            {r.guest_phone ? <span className="muted">{r.guest_phone}</span> : null}
                            <span className={statusClass(String(r.status || ''))}>{hotelWord(r.status)}</span>
                          </div>
                          <div className="hotel-book-meta">
                            <span>
                              {r.check_in_date ? formatDate(String(r.check_in_date).includes('T') ? r.check_in_date : `${r.check_in_date}T12:00:00`, formatPrefs) : '—'}
                              {' – '}
                              {r.check_out_date ? formatDate(String(r.check_out_date).includes('T') ? r.check_out_date : `${r.check_out_date}T12:00:00`, formatPrefs) : '—'}
                            </span>
                            {leftEarlyWhen(r) ? <span className="muted">Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</span> : null}
                            <span>{r.folio_balance != null ? money(r.folio_balance) : '—'}</span>
                          </div>
                        </li>
                      ))}
                      {!(summary.recent_reservations || []).length && <li className="muted">No reservations yet.</li>}
                    </ul>
                    {(summary.low_stock || []).length > 0 && (
                      <p className="hint" style={{ marginTop: 12 }}>
                        Low supplies: {(summary.low_stock || []).map((p) => p.name).join(', ')}. <Link href="/inventory?tab=lowstock">Open low supplies</Link>
                      </p>
                    )}
                    {(summary.out_of_stock || []).length > 0 && (
                      <p className="hint" style={{ marginTop: 12 }}>
                        None left: {(summary.out_of_stock || []).map((p) => p.name).join(', ')}. <Link href="/inventory?tab=products">Open supplies</Link>
                      </p>
                    )}
                  </div>
                  <div className="panel">
                    <h3>Room status</h3>
                    <p className="hint">Rooms sold tonight are listed first.</p>
                    <div className="hotel-room-chips">
                      {(assigned.length ? assigned : liveRooms).map((r) => {
                        const later = soldTonightIds.has(r.id) ? '' : nextStayAfter(reservations, r.id, night);
                        return (
                        <div className={`hotel-room-chip is-${r.status}`} key={r.id}>
                          <span>{roomChipLabel(r.code, r.name)}</span>
                          <span className={statusClass(r.status)}>{hotelWord(r.status)}</span>
                          {later ? <span className="muted">Next stay {stayWhen(later, formatPrefs)}</span> : null}
                        </div>
                        );
                      })}
                      {!rooms.length && <p className="empty">No rooms yet.</p>}
                    </div>
                    {(summary.open_folio_count ?? 0) > 0 ? (
                      <p className="hint" style={{ marginTop: 12 }}>
                        {(summary.open_folio_count ?? 0) === 1
                          ? '1 guest folio still open'
                          : `${summary.open_folio_count} guest folios still open`}
                        {Number(summary.outstanding_folio_balance || 0) > 0
                          ? ` · ${money(summary.outstanding_folio_balance)}`
                          : ''}
                      </p>
                    ) : null}
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
                  <td>
                    {r.guest_name || '—'}
                    {r.guest_phone ? <div className="muted">{r.guest_phone}</div> : null}
                  </td>
                  <td>{r.room_code || '—'}</td>
                  <td>
                    {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                    {leftEarlyWhen(r) ? <div className="muted">Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</div> : null}
                  </td>
                  <td><span className={statusClass(r.status)}>{hotelWord(r.status)}</span></td>
                  <td>
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => checkOutStay(r.id)}>Check out</button>
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
          </div>
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
        <h2 id="guest-requests">Guest requests</h2>
        <p className="muted">Leave the room empty when the request is not for a specific room.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError('');
            try {
              const dueOn = reqForm.due_on.trim();
              const dueTime = reqForm.due_time.trim();
              const dueAt = dueOn && dueTime
                ? `${dueOn}T${dueTime.length === 5 ? `${dueTime}:00` : dueTime}`
                : (dueOn || dueTime || null);
              await api('/hotel/guest-requests', {
                method: 'POST',
                body: JSON.stringify({
                  title: reqForm.title.trim(),
                  kind: reqForm.kind,
                  reservation_id: reqForm.reservation_id || null,
                  room_id: reqForm.room_id || null,
                  due_at: dueAt,
                  notes: reqForm.notes.trim() || null,
                }),
              });
              setReqForm({ title: '', kind: 'service', reservation_id: '', room_id: '', due_on: '', due_time: '', notes: '' });
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
              {[['service', 'Service'], ['wake_up', 'Wake-up'], ['note', 'Note'], ['complaint', 'Complaint']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
          <label>
            <span>Room</span>
            <select value={reqForm.room_id} onChange={(e) => setReqForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Guest request room">
              <option value="">Optional</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
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
          <label>
            <span>Due date</span>
            <HotelDateInput
              value={reqForm.due_on}
              onChange={(due_on) => setReqForm((f) => ({ ...f, due_on }))}
              ariaLabel="Guest request due date"
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Due time</span>
            <input type="time" value={reqForm.due_time} onChange={(e) => setReqForm((f) => ({ ...f, due_time: e.target.value }))} aria-label="Guest request due time" />
          </label>
          <label>
            <span>Notes</span>
            <input value={reqForm.notes} onChange={(e) => setReqForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Guest request notes" />
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Record request</button></div>
        </form>
        <ul>
          {guestRequests.map((q) => (
            <li key={q.id}>
              {q.title} · {hotelWord(q.kind)} — {hotelWord(q.status)}
              {q.due_at ? <div className="muted">{stayClock(q.due_at, formatPrefs)}</div> : null}
              {q.room_id ? <div className="muted">{rooms.find((r) => r.id === q.room_id)?.code}</div> : null}
              {q.notes ? <div className="muted">{q.notes}</div> : null}
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
                <option key={t} value={t}>{hotelWord(t)}</option>
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
            <span>Max guests</span>
            <input type="number" min={1} max={20} value={roomForm.max_occupancy} onChange={(e) => setRoomForm((f) => ({ ...f, max_occupancy: e.target.value }))} aria-label="Hotel room max guests" />
          </label>
          <label>
            <span>Rate</span>
            <input type="number" min={0} step="0.01" value={roomForm.rate_amount} onChange={(e) => setRoomForm((f) => ({ ...f, rate_amount: e.target.value }))} aria-label="Hotel room rate" />
          </label>
          <label>
            <span>Weekend rate</span>
            <input type="number" min={0} step="0.01" value={roomForm.weekend_rate} onChange={(e) => setRoomForm((f) => ({ ...f, weekend_rate: e.target.value }))} aria-label="Hotel weekend rate" />
          </label>
          <label>
            <span>Extra guest</span>
            <input type="number" min={0} step="0.01" value={roomForm.extra_person_charge} onChange={(e) => setRoomForm((f) => ({ ...f, extra_person_charge: e.target.value }))} aria-label="Hotel extra guest charge" />
          </label>
          <label>
            <span>Status</span>
            <select value={roomForm.status} onChange={(e) => setRoomForm((f) => ({ ...f, status: e.target.value }))} aria-label="Hotel room status">
              {ROOM_STATUSES.map((s) => (
                <option key={s} value={s}>{hotelWord(s)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Description</span>
            <input value={roomForm.description} onChange={(e) => setRoomForm((f) => ({ ...f, description: e.target.value }))} aria-label="Hotel room description" />
          </label>
          <label>
            <span>Note</span>
            <input value={roomForm.notes} onChange={(e) => setRoomForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel room notes" />
          </label>
          <fieldset style={{ gridColumn: '1 / -1', border: 'none', padding: 0, margin: 0, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <legend>Amenities</legend>
            {ROOM_AMENITIES.map((key) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <input
                  type="checkbox"
                  checked={roomForm.amenities[key]}
                  onChange={(e) => setRoomForm((f) => ({ ...f, amenities: { ...f.amenities, [key]: e.target.checked } }))}
                  aria-label={`Hotel amenity ${hotelWord(key)}`}
                />
                <span>{hotelWord(key)}</span>
              </label>
            ))}
          </fieldset>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel room">{busy ? 'Saving…' : 'Create room'}</button>
          </div>
        </form>
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Status</th>
              <th>Housekeeping</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id}>
                <td><code>{r.code}</code></td>
                <td>
                  {roomPlainName(r.code, r.name)}
                  {r.description ? <div className="muted">{r.description}</div> : null}
                  {r.notes ? <div className="muted">Note: {r.notes}</div> : null}
                  {Object.keys(r.amenities || {}).length ? (
                    <div className="muted">{Object.keys(r.amenities || {}).map((key) => hotelWord(key)).join(', ')}</div>
                  ) : null}
                </td>
                <td>
                  <span className={statusClass(r.status)}>{hotelWord(r.status)}</span>
                  {nextStayAfter(reservations, r.id, dashDate) ? (
                    <div className="muted">Next stay {stayWhen(nextStayAfter(reservations, r.id, dashDate), formatPrefs)}</div>
                  ) : null}
                </td>
                <td>{hotelWord(r.housekeeping_status) || '—'}</td>
                <td>
                  {money(r.rate_amount)}
                  {r.weekend_rate != null ? <div className="muted">Weekend {money(r.weekend_rate)}</div> : null}
                  {Number(r.extra_person_charge) > 0 ? <div className="muted">Extra guest {money(r.extra_person_charge)}</div> : null}
                </td>
              </tr>
            ))}
            {!rooms.length && (
              <tr><td colSpan={5} className="muted">No rooms yet.</td></tr>
            )}
          </tbody>
        </table>
        </div>
        <h2 id="rate-plans" style={{ marginTop: 20 }}>Rate plans</h2>
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
                  room_type: rateForm.room_type || null,
                  min_nights: Number(rateForm.min_nights) || 1,
                  weekday_only: rateForm.weekday_only,
                  weekend_only: rateForm.weekend_only,
                  starts_on: rateForm.starts_on || null,
                  ends_on: rateForm.ends_on || null,
                }),
              });
              setRateForm({
                code: '',
                name: '',
                amount: '0',
                room_type: '',
                min_nights: '1',
                weekday_only: false,
                weekend_only: false,
                starts_on: '',
                ends_on: '',
              });
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
          <label><span>Amount</span><AmountField type="number" min={0} step="0.01" value={rateForm.amount} onChange={(e) => setRateForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Rate plan amount" /></label>
          <label>
            <span>Room type</span>
            <select value={rateForm.room_type} onChange={(e) => setRateForm((f) => ({ ...f, room_type: e.target.value }))} aria-label="Rate plan room type">
              <option value="">Any type</option>
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>{hotelWord(t)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Minimum nights</span>
            <input type="number" min={1} max={30} value={rateForm.min_nights} onChange={(e) => setRateForm((f) => ({ ...f, min_nights: e.target.value }))} aria-label="Rate plan minimum nights" />
          </label>
          <label>
            <span>Starts</span>
            <HotelDateInput value={rateForm.starts_on} onChange={(starts_on) => setRateForm((f) => ({ ...f, starts_on }))} ariaLabel="Rate plan start" prefs={formatPrefs} />
          </label>
          <label>
            <span>Ends</span>
            <HotelDateInput value={rateForm.ends_on} onChange={(ends_on) => setRateForm((f) => ({ ...f, ends_on }))} ariaLabel="Rate plan end" prefs={formatPrefs} />
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input type="checkbox" checked={rateForm.weekday_only} onChange={(e) => setRateForm((f) => ({ ...f, weekday_only: e.target.checked, weekend_only: e.target.checked ? false : f.weekend_only }))} aria-label="Rate plan weekday only" />
            <span>Weekdays only</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input type="checkbox" checked={rateForm.weekend_only} onChange={(e) => setRateForm((f) => ({ ...f, weekend_only: e.target.checked, weekday_only: e.target.checked ? false : f.weekday_only }))} aria-label="Rate plan weekend only" />
            <span>Weekends only</span>
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Add plan</button></div>
        </form>
        <ul>
          {ratePlans.map((p) => (
            <li key={p.id}>
              <code>{p.code}</code> {p.name} — {money(p.amount)}
              {p.min_nights > 1 ? ` · ${p.min_nights} nights` : ''}
              {p.room_type ? ` · ${hotelWord(p.room_type)}` : ''}
              {p.weekday_only ? ' · weekdays' : ''}
              {p.weekend_only ? ' · weekends' : ''}
            </li>
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
          <label>
            <span>Address</span>
            <input value={guestForm.address} onChange={(e) => setGuestForm((f) => ({ ...f, address: e.target.value }))} aria-label="Hotel guest address" />
          </label>
          <label>
            <span>Company</span>
            <input value={guestForm.company_name} onChange={(e) => setGuestForm((f) => ({ ...f, company_name: e.target.value }))} aria-label="Hotel guest company" />
          </label>
          <label>
            <span>Travel agent</span>
            <input value={guestForm.travel_agent} onChange={(e) => setGuestForm((f) => ({ ...f, travel_agent: e.target.value }))} aria-label="Hotel guest travel agent" />
          </label>
          <label>
            <span>Loyalty</span>
            <input value={guestForm.loyalty_tier} onChange={(e) => setGuestForm((f) => ({ ...f, loyalty_tier: e.target.value }))} aria-label="Hotel guest loyalty" />
          </label>
          <label>
            <span>ID type</span>
            <input value={guestForm.id_type} onChange={(e) => setGuestForm((f) => ({ ...f, id_type: e.target.value }))} aria-label="Hotel guest id type" />
          </label>
          <label>
            <span>ID document</span>
            <input value={guestForm.id_document} onChange={(e) => setGuestForm((f) => ({ ...f, id_document: e.target.value }))} aria-label="Hotel guest id document" />
          </label>
          <label>
            <span>Emergency contact</span>
            <input value={guestForm.emergency_contact} onChange={(e) => setGuestForm((f) => ({ ...f, emergency_contact: e.target.value }))} aria-label="Hotel guest emergency contact" />
          </label>
          <label>
            <span>Preferences</span>
            <input value={guestForm.preferences} onChange={(e) => setGuestForm((f) => ({ ...f, preferences: e.target.value }))} aria-label="Hotel guest preferences" />
          </label>
          <label>
            <span>Notes</span>
            <input value={guestForm.notes} onChange={(e) => setGuestForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel guest notes" />
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
        <div className="list-table-wrap">
        <table className="table">
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
                <td>
                  <div>{g.full_name}</div>
                  {(g.company_name || g.loyalty_tier) ? (
                    <div className="muted">
                      {[g.company_name, g.loyalty_tier].filter(Boolean).join(' · ')}
                    </div>
                  ) : null}
                  {reservations
                    .filter((r) => r.guest_id === g.id)
                    .map((r) => (
                      <div className="muted" key={r.id}>
                        {r.reservation_number} · {hotelWord(r.status)} · {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                        {leftEarlyWhen(r) ? <span> · Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</span> : null}
                      </div>
                    ))}
                </td>
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
              <tr><td colSpan={4} className="muted">{listsReady ? 'No guests yet.' : 'Loading guests…'}</td></tr>
            )}
          </tbody>
        </table>
        </div>
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
            <p className="muted">Outstanding {money(guestHistory.outstanding_balance)}</p>
            <ul>
              {(guestHistory.reservations || []).map((r: Reservation) => (
                <li key={r.id}>
                  {r.reservation_number} · {hotelWord(r.status)} · {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                  {leftEarlyWhen(r) ? <span> · Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</span> : null}
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
              const n = (rows.data || []).length;
              setMessage(n === 1 ? '1 room available' : `${n} rooms available`);
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
            <HotelDateInput
              value={availForm.check_in_date}
              onChange={(check_in_date) => setAvailForm((f) => ({ ...f, check_in_date }))}
              ariaLabel="Availability check-in"
              required
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Departure</span>
            <HotelDateInput
              value={availForm.check_out_date}
              onChange={(check_out_date) => setAvailForm((f) => ({ ...f, check_out_date }))}
              ariaLabel="Availability check-out"
              required
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Room type</span>
            <select value={availForm.room_type} onChange={(e) => setAvailForm((f) => ({ ...f, room_type: e.target.value }))} aria-label="Availability room type">
              <option value="">Any</option>
              {ROOM_TYPES.map((t) => (
                <option key={t} value={t}>{hotelWord(t)}</option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Search rooms</button>
          </div>
        </form>
        {availRooms.length > 0 && (
          <ul>
            {availRooms.map((r) => {
              const later = nextStayAfter(reservations, r.id, shiftIso(availForm.check_out_date, -1));
              return (
              <li key={r.id}>
                <button type="button" onClick={() => setResForm((f) => ({ ...f, room_id: r.id, check_in_date: availForm.check_in_date, check_out_date: availForm.check_out_date }))}>
                  Use {r.code} — {r.name} ({money(r.rate_amount)})
                  {later ? <span className="muted"> Next stay {stayWhen(later, formatPrefs)}</span> : null}
                </button>
              </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="card" id="hotel-book-stay" style={{ marginBottom: 16 }}>
        <h2>Book a stay</h2>
        <p className="muted">Pick dates and a room. Walk-in checks the guest in now. Tick extra rooms below for a group stay. A discount percent above zero lowers the nightly rate and records the signed-in staff member. Zero leaves the rate unchanged. A group stay uses that same discount on each room.</p>
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
          {(() => {
            const clash = heldStay(reservations, resForm.room_id, resForm.check_in_date, resForm.check_out_date);
            const later = clash ? '' : nextStayAfter(reservations, resForm.room_id, shiftIso(resForm.check_out_date, -1));
            const code = rooms.find((r) => r.id === resForm.room_id)?.code || 'This room';
            if (clash) {
              return (
                <p className="hint" style={{ gridColumn: '1 / -1' }}>
                  {code} is already held {stayWhen(clash.check_in_date, formatPrefs)} – {stayWhen(clash.check_out_date, formatPrefs)}
                  {clash.guest_name ? ` by ${clash.guest_name}` : ''}.
                </p>
              );
            }
            if (later) {
              return <p className="hint" style={{ gridColumn: '1 / -1' }}>Next stay {stayWhen(later, formatPrefs)}</p>;
            }
            return null;
          })()}
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
            <HotelDateInput
              value={resForm.check_in_date}
              onChange={(check_in_date) => setResForm((f) => ({ ...f, check_in_date }))}
              ariaLabel="Hotel check-in date"
              required
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Check-out</span>
            <HotelDateInput
              value={resForm.check_out_date}
              onChange={(check_out_date) => setResForm((f) => ({ ...f, check_out_date }))}
              ariaLabel="Hotel check-out date"
              required
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Adults</span>
            <input type="number" min={1} max={20} value={resForm.adults} onChange={(e) => setResForm((f) => ({ ...f, adults: e.target.value }))} aria-label="Hotel stay adults" />
          </label>
          <label>
            <span>Children</span>
            <input type="number" min={0} max={20} value={resForm.children} onChange={(e) => setResForm((f) => ({ ...f, children: e.target.value }))} aria-label="Hotel stay children" />
          </label>
          <label>
            <span>Discount %</span>
            <input type="number" min={0} max={100} step="0.01" value={resForm.discount_percent} onChange={(e) => setResForm((f) => ({ ...f, discount_percent: e.target.value }))} aria-label="Hotel stay discount percent" />
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
            <span>Rate plan</span>
            <select value={resForm.rate_plan_id} onChange={(e) => setResForm((f) => ({ ...f, rate_plan_id: e.target.value }))} aria-label="Hotel rate plan">
              <option value="">Room rate</option>
              {ratePlans.filter((p) => p.is_active !== false).map((p) => (
                <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Special requests</span>
            <input value={resForm.special_requests} onChange={(e) => setResForm((f) => ({ ...f, special_requests: e.target.value }))} aria-label="Hotel special requests" />
          </label>
          <label>
            <span>Desk note</span>
            <input value={resForm.notes} onChange={(e) => setResForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel reservation notes" />
          </label>
          <label>
            <span>Deposit</span>
            <AmountField type="number" min={0} step="0.01" value={resForm.deposit_amount} onChange={(e) => setResForm((f) => ({ ...f, deposit_amount: e.target.value }))} aria-label="Hotel deposit amount" />
          </label>
          <label>
            <span>Deposit method</span>
            <select
              value={resForm.deposit_method}
              onChange={(e) => setResForm((f) => ({ ...f, deposit_method: e.target.value }))}
              aria-label="Hotel deposit method"
              disabled={Number(resForm.deposit_amount) <= 0}
            >
              {['cash', 'momo', 'card', 'bank', 'credit', 'other'].map((method) => (
                <option key={method} value={method}>{tenderWord(method)}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input
              type="checkbox"
              checked={resForm.waitlist}
              disabled={resForm.walk_in}
              onChange={(e) => setResForm((f) => ({ ...f, waitlist: e.target.checked }))}
              aria-label="Add to waiting list"
            />
            <span>Waiting list (does not hold the room)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'end', gap: 8 }}>
            <input type="checkbox" checked={resForm.walk_in} onChange={(e) => setResForm((f) => ({ ...f, walk_in: e.target.checked, waitlist: e.target.checked ? false : f.waitlist }))} aria-label="Walk-in reservation" />
            <span>Walk-in (check in now)</span>
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy || (!resForm.waitlist && Boolean(heldStay(reservations, resForm.room_id, resForm.check_in_date, resForm.check_out_date)))} aria-label="Create hotel reservation">{busy ? 'Saving…' : resForm.waitlist ? 'Add to waiting list' : 'Book stay'}</button>
          </div>
        </form>
        <h3 id="online-booking" style={{ marginTop: 16 }}>Online booking</h3>
        <p className="muted">
          Record an existing website or a new domain. A guest request holds the room as tentative until Confirm booking.
          It does not take a payment. Saving the host does not move DNS.
        </p>
        {stayLink?.installed === false ? (
          <p className="muted">Online booking is not on this database yet.</p>
        ) : stayLink ? (
          <>
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setError('');
                try {
                  const saved = await api('/hotel/booking-link', {
                    method: 'PUT',
                    body: JSON.stringify({
                      hostname: stayForm.hostname.trim(),
                      link_kind: stayForm.link_kind,
                    }),
                  });
                  setStayLink(saved?.data || null);
                  setError('');
                } catch (err: unknown) {
                  setError(err instanceof Error ? err.message : 'Could not save the booking link');
                }
              }}
              style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', marginBottom: 8 }}
            >
              <label>
                <span>Website or domain</span>
                <input
                  aria-label="Hotel booking website"
                  value={stayForm.hostname}
                  onChange={(e) => setStayForm({ ...stayForm, hostname: e.target.value })}
                  placeholder="inn.example"
                  required
                />
              </label>
              <label>
                <span>Where this host comes from</span>
                <select
                  aria-label="Hotel booking host kind"
                  value={stayForm.link_kind}
                  onChange={(e) => setStayForm({ ...stayForm, link_kind: e.target.value })}
                >
                  <option value="existing">Existing website</option>
                  <option value="new">New domain</option>
                </select>
              </label>
              <div style={{ alignSelf: 'end' }}>
                <button type="submit" aria-label="Save hotel booking link">Save booking link</button>
              </div>
            </form>
            {stayLink.open && stayLink.path ? (
              <>
                <label>
                  <span>Link to put on the website</span>
                  <input
                    readOnly
                    aria-label="Stay link for the website"
                    value={stayOrigin ? `${stayOrigin}${stayLink.path}` : stayLink.path}
                  />
                </label>
                <p className="muted">
                  Put this link on {stayLink.hostname}. Guests who open it request a stay here.
                </p>
                {stayLink.link_kind === 'new' ? (
                  <p className="muted">
                    After {stayLink.hostname} points at this ERP, guests can open https://{stayLink.hostname}/stay.
                    Saving the domain does not move DNS.
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted">Save a website or domain before guests can request a stay.</p>
            )}
          </>
        ) : null}
        <h3 id="group-stay" style={{ marginTop: 16 }}>Group stay</h3>
        <p className="muted">Tick two or more rooms. Use the guest, dates, and discount above. A blank name is left off the stay. Zero discount leaves each room rate unchanged.</p>
        <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginBottom: 8 }}>
          <label>
            <span>Group name</span>
            <input value={groupName} onChange={(e) => setGroupName(e.target.value)} aria-label="Hotel group name" />
          </label>
          <label>
            <span>Group note</span>
            <input value={groupNotes} onChange={(e) => setGroupNotes(e.target.value)} aria-label="Hotel group notes" />
          </label>
        </div>
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
          {!availableRooms.length && <span className="muted">Add rooms first.</span>}
        </div>
        {groupRooms.map((id) => {
          const stay = heldStay(reservations, id, resForm.check_in_date, resForm.check_out_date);
          const later = stay ? '' : nextStayAfter(reservations, id, shiftIso(resForm.check_out_date, -1));
          const code = rooms.find((r) => r.id === id)?.code || 'Room';
          if (stay) {
            return (
              <p className="hint" key={id}>
                {code} is already held {stayWhen(stay.check_in_date, formatPrefs)} – {stayWhen(stay.check_out_date, formatPrefs)}
                {stay.guest_name ? ` by ${stay.guest_name}` : ''}.
              </p>
            );
          }
          if (later) return <p className="hint" key={id}>{code} next stay {stayWhen(later, formatPrefs)}</p>;
          return null;
        })}
        <button
          type="button"
          disabled={busy || groupRooms.length < 2 || (!resForm.guest_id && !resForm.new_guest_name.trim()) || !resForm.check_in_date || !resForm.check_out_date || groupRooms.some((id) => heldStay(reservations, id, resForm.check_in_date, resForm.check_out_date))}
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
              const discountPercent = Number(resForm.discount_percent) || 0;
              if (discountPercent > 100) {
                setError('Stay discount percent cannot be above 100.');
                setBusy(false);
                return;
              }
              if (discountPercent > 0 && !staffId) {
                setError('Sign in again before applying a stay discount.');
                setBusy(false);
                return;
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
                  name: groupName.trim() || null,
                  notes: groupNotes.trim() || null,
                  discount_percent: discountPercent,
                  discount_authorized_by: discountPercent > 0 ? staffId : null,
                }),
              });
              setGroupRooms([]);
              setGroupName('');
              setGroupNotes('');
              setMessage('Group reservation created');
              await refresh();
            } catch (err: unknown) {
              setError(hotelErr(err, 'Group booking needs a guest, dates, and two rooms.'));
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
        <div className="list-page-head page-head">
          <h2 style={{ margin: 0 }}>Reservations</h2>
          <select value={listKind} onChange={(e) => setListKind(e.target.value)} aria-label="Hotel reservation list filter">
            <option value="">All</option>
            <option value="arrivals">Arrivals today</option>
            <option value="departures">Departures today</option>
            <option value="in_house">In house</option>
            <option value="upcoming">Upcoming</option>
            <option value="tentative">Tentative</option>
            <option value="waitlist">Waiting list</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-show</option>
          </select>
        </div>
        <p className="muted">
          Cancel at least {Number(settingsForm.cancellation_hours) || 0} hours before {settingsForm.check_in_time || '14:00'} on the arrival date. A cancel inside that window releases the room and does not add a fee.
        </p>
        {(summary?.online_stay_requests || 0) > 0 && (
          <p className="hint">
            {(summary?.online_stay_requests || 0) === 1
              ? '1 stay request is waiting.'
              : `${summary?.online_stay_requests} stay requests are waiting.`}
          </p>
        )}
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Guest</th>
              <th>Room</th>
              <th>Dates</th>
              <th>Status</th>
              <th>Balance</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id}>
                <td><code>{r.reservation_number}</code></td>
                <td>
                  {r.guest_name || '—'}
                  {r.guest_phone ? <div className="muted">{r.guest_phone}</div> : null}
                </td>
                <td>{r.room_code || '—'}</td>
                <td>
                  {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                  {leftEarlyWhen(r) ? <div className="muted">Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</div> : null}
                  {r.special_requests ? <div className="muted">{r.special_requests}</div> : null}
                  {r.group_name ? <div className="muted">Group: {r.group_name}</div> : null}
                  {r.notes ? <div className="muted">Desk note: {r.notes}</div> : null}
                  {Number(r.deposit_amount) > 0 ? <div className="muted">Deposit {money(r.deposit_amount)} · {tenderWord(r.deposit_method)}</div> : null}
                  {Number(r.discount_percent) > 0 ? <div className="muted">Discount {r.discount_percent}%</div> : null}
                </td>
                <td>
                  <span className={statusClass(r.status)}>{hotelWord(r.status)}</span>
                  {r.booking_source && r.booking_source !== 'direct' ? (
                    <div className="muted">{bookingSourceWord(r.booking_source)}</div>
                  ) : null}
                  {r.inside_cancellation_window ? <div className="muted">Inside the cancellation window</div> : null}
                </td>
                <td>{r.folio_balance != null ? money(r.folio_balance) : '—'}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {r.can_confirm && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/confirm`, r.status === 'waitlisted' ? 'Moved off the waiting list' : 'Confirmed')} aria-label={`Confirm ${r.reservation_number}`}>{r.status === 'waitlisted' ? 'Offer room' : 'Confirm booking'}</button>
                    )}
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/check-in`, 'Checked in')} aria-label={`Check in ${r.reservation_number}`}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => checkOutStay(r.id)} aria-label={`Check out ${r.reservation_number}`}>Check out</button>
                    )}
                    {r.can_cancel && (
                      <button type="button" className="btn-danger" disabled={busy} onClick={() => {
                        const late = r.inside_cancellation_window
                          ? ` This stay is inside the ${r.cancellation_hours}-hour cancellation window. Cancelling does not add a fee.`
                          : '';
                        if (!window.confirm(`Cancel reservation ${r.reservation_number}? This cannot be undone.${late}`)) return;
                        void act(`/hotel/reservations/${r.id}/cancel`, 'Cancelled');
                      }} aria-label={`Cancel ${r.reservation_number}`}>Cancel</button>
                    )}
                    {r.can_no_show && (
                      <button type="button" disabled={busy} onClick={() => act(`/hotel/reservations/${r.id}/no-show`, 'Marked no-show')} aria-label={`No-show ${r.reservation_number}`}>No-show</button>
                    )}
                    {r.status === 'no_show' && (
                      <button type="button" disabled={busy} onClick={() => {
                        if (!window.confirm(`Post the no-show fee once for ${r.reservation_number}?`)) return;
                        void act(`/hotel/reservations/${r.id}/no-show-fee`, 'No-show fee posted');
                      }} aria-label={`Post no-show fee ${r.reservation_number}`}>Post no-show fee</button>
                    )}
                    {(r.can_check_out || r.status === 'checked_in' || r.status === 'checked_out') && (
                      <button type="button" disabled={busy} onClick={() => openFolio(r.id)} aria-label={`Open folio ${r.reservation_number}`}>Folio</button>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => printStaySlip(r.id, r.reservation_number)}
                      aria-label={`Print confirmation ${r.reservation_number}`}
                    >
                      Print slip
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
                    {r.can_duplicate && (
                      <button
                        type="button"
                        disabled={busy || !extendDate}
                        onClick={() =>
                          act(`/hotel/reservations/${r.id}/duplicate`, 'Stay duplicated', {
                            check_in_date: extendDate,
                            check_out_date: shiftIso(extendDate, Math.max(1, r.nights || 1)),
                          })
                        }
                        aria-label={`Duplicate ${r.reservation_number}`}
                      >
                        Duplicate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!reservations.length && (
              <tr><td colSpan={7} className="muted">No reservations.</td></tr>
            )}
          </tbody>
        </table>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
          <label>
            <span>Extend to</span>
            <HotelDateInput
              value={extendDate}
              onChange={setExtendDate}
              ariaLabel="Extend stay date"
              prefs={formatPrefs}
            />
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
          {(folio.guest_name || folio.room_code || folio.check_in_date) ? (
            <p className="muted">
              {[folio.guest_name, folio.room_code ? `Room ${folio.room_code}` : '', folio.reservation_number].filter(Boolean).join(' · ')}
              {folio.check_in_date && folio.check_out_date
                ? ` · ${stayWhen(folio.check_in_date, formatPrefs)} – ${stayWhen(folio.check_out_date, formatPrefs)}`
                : ''}
              {leftEarlyWhen({ status: folio.reservation_status || undefined, check_out_date: folio.check_out_date, checked_out_at: folio.checked_out_at })
                ? ` · Left ${stayWhen(leftEarlyWhen({ status: folio.reservation_status || undefined, check_out_date: folio.check_out_date, checked_out_at: folio.checked_out_at }), formatPrefs)}`
                : ''}
            </p>
          ) : null}
          <p className="muted">
            Charges {money(folio.charges_total)} · Payments {money(folio.payments_total)} · Balance{' '}
            <strong>{money(folio.balance)}</strong> (payment information only — not a gateway)
          </p>
          <label>
            <span>Folio note</span>
            <input aria-label="Hotel folio notes" value={folioNote} onChange={(e) => setFolioNote(e.target.value)} />
          </label>
          <p className="muted">Leave the note empty and the saved note stays. It is not printed on the guest slip.</p>
          <button type="button" disabled={busy} onClick={saveFolioNote}>Save folio note</button>
          <button type="button" disabled={busy} onClick={printFolioSlip} aria-label={`Print folio ${folio.folio_number}`}>
            Print folio
          </button>
          {folio.status === 'open' && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <button
                type="button"
                disabled={busy || Number(settingsForm.early_checkin_fee) <= 0}
                onClick={() => {
                  if (!window.confirm('Post the early check-in fee once on this folio?')) return;
                  void (async () => {
                    setBusy(true);
                    setError('');
                    try {
                      const f = await api(`/hotel/folios/${folio.id}/timing-fee`, {
                        method: 'POST',
                        body: JSON.stringify({ kind: 'early_checkin' }),
                      });
                      setFolio(f.data || null);
                      setMessage('Early check-in fee posted');
                      await refresh();
                    } catch (err: unknown) {
                      setError(hotelErr(err, 'Could not post the early check-in fee'));
                    } finally {
                      setBusy(false);
                    }
                  })();
                }}
                aria-label="Post early check-in fee"
              >
                Post early check-in fee
              </button>
              <button
                type="button"
                disabled={busy || Number(settingsForm.late_checkout_fee) <= 0}
                onClick={() => {
                  if (!window.confirm('Post the late check-out fee once on this folio?')) return;
                  void (async () => {
                    setBusy(true);
                    setError('');
                    try {
                      const f = await api(`/hotel/folios/${folio.id}/timing-fee`, {
                        method: 'POST',
                        body: JSON.stringify({ kind: 'late_checkout' }),
                      });
                      setFolio(f.data || null);
                      setMessage('Late check-out fee posted');
                      await refresh();
                    } catch (err: unknown) {
                      setError(hotelErr(err, 'Could not post the late check-out fee'));
                    } finally {
                      setBusy(false);
                    }
                  })();
                }}
                aria-label="Post late check-out fee"
              >
                Post late check-out fee
              </button>
              <button
                type="button"
                disabled={busy || Number(settingsForm.service_charge_percent) <= 0}
                onClick={() => {
                  if (!window.confirm('Post the service charge once on the room total?')) return;
                  void (async () => {
                    setBusy(true);
                    setError('');
                    try {
                      const f = await api(`/hotel/folios/${folio.id}/service-charge`, {
                        method: 'POST',
                        body: JSON.stringify({}),
                      });
                      setFolio(f.data || null);
                      setMessage('Service charge posted');
                      await refresh();
                    } catch (err: unknown) {
                      setError(hotelErr(err, 'Could not post the service charge'));
                    } finally {
                      setBusy(false);
                    }
                  })();
                }}
                aria-label="Post service charge"
              >
                Post service charge
              </button>
            </div>
          )}
          <table className="table">
            <thead><tr><th>Charge</th><th>Total</th><th>Void</th><th></th></tr></thead>
            <tbody>
              {folio.charges.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.description}
                    <div className="muted">{folioChargeWord(c.charge_type)} · {c.quantity ?? 1} × {money(c.unit_amount)}</div>
                    {Number(c.discount_amount) > 0 ? <div className="muted">Discount {money(c.discount_amount)}</div> : null}
                  </td>
                  <td>{money(c.line_total)}</td>
                  <td>{c.is_void ? 'Voided' : '—'}</td>
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
                  <option key={c.id} value={c.id}>{c.description} ({money(c.line_total)})</option>
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
              <AmountField type="number" min={0} step="0.01" value={chargeForm.unit_amount} onChange={(e) => setChargeForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label="Folio charge amount" />
            </label>
            <label>
              <span>Quantity</span>
              <input type="number" min={0.01} step="0.01" value={chargeForm.quantity} onChange={(e) => setChargeForm((f) => ({ ...f, quantity: e.target.value }))} aria-label="Folio charge quantity" required />
            </label>
            <label>
              <span>Discount</span>
              <AmountField type="number" min={0} step="0.01" value={chargeForm.discount_amount} onChange={(e) => setChargeForm((f) => ({ ...f, discount_amount: e.target.value }))} aria-label="Folio charge discount" />
            </label>
            <label>
              <span>Type</span>
              <select value={chargeForm.charge_type} onChange={(e) => setChargeForm((f) => ({ ...f, charge_type: e.target.value }))} aria-label="Folio charge type">
                {['extra', 'restaurant', 'bar', 'laundry', 'service', 'damage', 'tax', 'discount'].map((t) => (
                  <option key={t} value={t}>{hotelWord(t)}</option>
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
                  <option key={m} value={m}>{tenderWord(m)}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Amount</span>
              <AmountField type="number" min={0} step="0.01" value={payForm.amount} onChange={(e) => setPayForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Folio payment amount" />
            </label>
            <label>
              <span>Reference</span>
              <input value={payForm.reference} onChange={(e) => setPayForm((f) => ({ ...f, reference: e.target.value }))} aria-label="Folio payment reference" />
            </label>
            <label>
              <span>Notes</span>
              <input value={payForm.notes} onChange={(e) => setPayForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Folio payment notes" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Record payment info</button>
            </div>
          </form>
          <ul>
            {folio.payments.map((p) => (
              <li key={p.id}>
                {tenderWord(p.method)} · {money(p.amount)}
                {p.reference ? <div className="muted">{p.reference}</div> : null}
                {p.notes ? <div className="muted">{p.notes}</div> : null}
              </li>
            ))}
            {!folio.payments.length && <li className="muted">No payments recorded.</li>}
          </ul>
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
                    <option key={s.id} value={s.id}>{s.name} ({money(s.unit_amount)})</option>
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
          <div className="list-table-wrap">
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
                  <td>
                    {f.reservation_number || '—'}
                    {f.check_in_date && f.check_out_date ? (
                      <div className="muted">
                        {stayWhen(f.check_in_date, formatPrefs)} – {stayWhen(f.check_out_date, formatPrefs)}
                        {leftEarlyWhen({ status: f.reservation_status || undefined, check_out_date: f.check_out_date, checked_out_at: f.checked_out_at })
                          ? ` · Left ${stayWhen(leftEarlyWhen({ status: f.reservation_status || undefined, check_out_date: f.check_out_date, checked_out_at: f.checked_out_at }), formatPrefs)}`
                          : ''}
                      </div>
                    ) : null}
                  </td>
                  <td><span className={statusClass(String(f.status || ''))}>{hotelWord(f.status)}</span></td>
                  <td>{money(f.balance)}</td>
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
        </div>
      )}

      {show('services') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel services</h2>
          <p className="muted">Tax percent is added when this service is posted to a bill. Room nights stay untaxed. Choose Restaurant or Bar to use the item on those desks.</p>
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
                    notes: serviceForm.notes.trim() || null,
                  }),
                });
                setServiceForm({ code: '', name: '', category: 'laundry', unit_amount: '0', tax_percent: '0', notes: '' });
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
                {['restaurant', 'bar', 'laundry', 'transport', 'spa', 'extra', 'service'].map((c) => (
                  <option key={c} value={c}>{hotelWord(c)}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Unit amount</span>
              <AmountField type="number" min={0} step="0.01" value={serviceForm.unit_amount} onChange={(e) => setServiceForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label="Hotel service amount" />
            </label>
            <label>
              <span>Tax %</span>
              <input type="number" min={0} step="0.01" value={serviceForm.tax_percent} onChange={(e) => setServiceForm((f) => ({ ...f, tax_percent: e.target.value }))} aria-label="Hotel service tax percent" />
            </label>
            <label>
              <span>Notes</span>
              <input value={serviceForm.notes} onChange={(e) => setServiceForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel service notes" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Add service</button>
            </div>
          </form>
          <div className="list-table-wrap">
          <table className="table">
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
                  <td>
                    {s.name}
                    {s.notes ? <div className="muted">{s.notes}</div> : null}
                  </td>
                  <td>{hotelWord(s.category)}</td>
                  <td>{money(s.unit_amount)}</td>
                  <td>{s.is_active ? 'Yes' : 'No'}</td>
                </tr>
              ))}
              {!services.length && (
                <tr><td colSpan={5} className="muted">No hotel services yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
          <p className="muted">Open a folio under Billing to post an approved service charge to a guest bill.</p>
        </div>
      )}

      {show('housekeeping') && (
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Housekeeping</h2>
        <p className="muted">A room with open maintenance stays out of service after cleaning is marked done. Leave the due date empty and the task is due in two hours. Priority starts at normal.</p>
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
                <option key={t} value={t}>{hotelWord(t)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Priority</span>
            <select value={hkForm.priority} onChange={(e) => setHkForm((f) => ({ ...f, priority: e.target.value }))} aria-label="Housekeeping priority">
              {['low', 'normal', 'high', 'urgent'].map((p) => (
                <option key={p} value={p}>{hotelWord(p)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Assign to</span>
            <input value={hkForm.assigned_to} onChange={(e) => setHkForm((f) => ({ ...f, assigned_to: e.target.value }))} aria-label="Housekeeping assignee" />
          </label>
          <label>
            <span>Notes</span>
            <input value={hkForm.notes} onChange={(e) => setHkForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Housekeeping notes" />
          </label>
          <label>
            <span>Due date</span>
            <HotelDateInput
              value={hkForm.due_on}
              onChange={(due_on) => setHkForm((f) => ({ ...f, due_on }))}
              ariaLabel="Housekeeping due date"
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Due time</span>
            <input type="time" value={hkForm.due_time} onChange={(e) => setHkForm((f) => ({ ...f, due_time: e.target.value }))} aria-label="Housekeeping due time" />
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Create task</button>
          </div>
        </form>
        <div className="list-table-wrap">
        <table className="table">
          <thead><tr><th>Room</th><th>Status</th><th>Priority</th><th>Due</th><th>Assignee</th><th></th></tr></thead>
          <tbody>
            {hkTasks.map((t) => (
              <tr key={t.id}>
                <td>
                  {t.room_code || t.room_id}
                  {t.notes ? <div className="muted">{t.notes}</div> : null}
                </td>
                <td><span className={statusClass(String(t.status || ''))}>{hotelWord(t.status)}</span></td>
                <td>{hotelWord(t.priority)}</td>
                <td>{t.due_at ? stayClock(t.due_at, formatPrefs) : '—'}</td>
                <td>{t.assigned_to || '—'}</td>
                <td>
                  {t.status !== 'completed' && (
                    <button type="button" disabled={busy} onClick={() => act(`/hotel/housekeeping/${t.id}/complete`, 'Housekeeping completed', { mark_inspected: true })}>
                      Complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!hkTasks.length && <tr><td colSpan={6} className="muted">No housekeeping tasks.</td></tr>}
          </tbody>
        </table>
        </div>
        <h2 id="lost-found">Lost and found</h2>
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
                  notes: lfForm.notes.trim() || null,
                }),
              });
              setLfForm({ description: '', kind: 'lost', room_id: '', notes: '' });
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
              {['lost', 'found', 'damage'].map((k) => <option key={k} value={k}>{hotelWord(k)}</option>)}
            </select>
          </label>
          <label>
            <span>Room</span>
            <select value={lfForm.room_id} onChange={(e) => setLfForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Lost found room">
              <option value="">Optional</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.code}</option>)}
            </select>
          </label>
          <label>
            <span>Notes</span>
            <input value={lfForm.notes} onChange={(e) => setLfForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Lost found notes" />
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" disabled={busy}>Save</button></div>
        </form>
        <ul>
          {lostFound.map((x) => (
            <li key={x.id}>
              {hotelWord(x.kind)}: {x.description} ({hotelWord(x.status)})
              {x.notes ? <div className="muted">{x.notes}</div> : null}
            </li>
          ))}
          {!lostFound.length && <li className="muted">No lost-and-found records.</li>}
        </ul>
      </div>
      )}

      {show('maintenance') && (
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Maintenance</h2>
        <p className="muted">Leave the dates empty to take the room out of service until the ticket is completed. A dated range only blocks those nights. Uncheck Block the room to log the issue and leave the room in service. Priority starts at normal. High or urgent takes a blocked room out of order.</p>
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
            <span>Priority</span>
            <select value={maintForm.priority} onChange={(e) => setMaintForm((f) => ({ ...f, priority: e.target.value }))} aria-label="Maintenance priority">
              {['low', 'normal', 'high', 'urgent'].map((p) => (
                <option key={p} value={p}>{hotelWord(p)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Out from</span>
            <HotelDateInput
              value={maintForm.ooo_starts_on}
              onChange={(ooo_starts_on) => setMaintForm((f) => ({ ...f, ooo_starts_on }))}
              ariaLabel="Out of order start date"
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Out through</span>
            <HotelDateInput
              value={maintForm.ooo_ends_on}
              onChange={(ooo_ends_on) => setMaintForm((f) => ({ ...f, ooo_ends_on }))}
              ariaLabel="Out of order end date"
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Assign to</span>
            <input value={maintForm.assigned_to} onChange={(e) => setMaintForm((f) => ({ ...f, assigned_to: e.target.value }))} aria-label="Maintenance assignee" />
          </label>
          <label>
            <span>Notes</span>
            <input value={maintForm.notes} onChange={(e) => setMaintForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Maintenance notes" />
          </label>
          <label style={{ alignSelf: 'end' }}>
            <input
              type="checkbox"
              checked={maintForm.block_room}
              onChange={(e) => setMaintForm((f) => ({ ...f, block_room: e.target.checked }))}
              aria-label="Block the room"
            />
            {' '}Block the room
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy}>Create ticket</button>
          </div>
        </form>
        <div className="list-table-wrap">
        <table className="table">
          <thead><tr><th>Room</th><th>Title</th><th>Out of order</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {maint.map((t) => (
              <tr key={t.id}>
                <td>{t.room_code || t.room_id}</td>
                <td>
                  {t.title}
                  <div className="muted">{hotelWord(t.priority || 'normal')}</div>
                  {t.assigned_to ? <div className="muted">{t.assigned_to}</div> : null}
                  {t.notes ? <div className="muted">{t.notes}</div> : null}
                </td>
                <td>
                  {!t.block_room
                    ? 'In service'
                    : t.ooo_starts_on || t.ooo_ends_on
                      ? `${stayWhen(t.ooo_starts_on, formatPrefs)} – ${stayWhen(t.ooo_ends_on, formatPrefs)}`
                      : 'Until completed'}
                </td>
                <td><span className={statusClass(String(t.status || ''))}>{hotelWord(t.status)}</span></td>
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
      </div>
      )}

      {show('cashier') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel finance and cashiering</h2>
          <p className="muted">
            This records the front-desk float and payment notes. It does not open the shop till, process cards, hold funds, or settle to a bank.
            Ledger posting uses existing{' '}
            <Link href="/accounting">Accounting</Link> and <Link href="/expenses">Expenses</Link>.
          </p>
          {cashierShift ? (
            <p>Front-desk float open since {cashierShift.opened_at} · opening float {money(cashierShift.opening_float)}</p>
          ) : (
            <p className="muted">No front-desk float is open.</p>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="muted" htmlFor="hotel-cashier-float">Float</label>
            <AmountField
              id="hotel-cashier-float"
              type="number"
              min={0}
              step="0.01"
              aria-label="Hotel cashier float"
              value={cashierFloat}
              onChange={(e) => setCashierFloat(e.target.value)}
            />
            <label className="muted" htmlFor="hotel-cashier-notes">Note</label>
            <input
              id="hotel-cashier-notes"
              aria-label="Hotel cashier notes"
              value={cashierNotes}
              onChange={(e) => setCashierNotes(e.target.value)}
            />
            <button
              type="button"
              disabled={busy || !!cashierShift}
              aria-label="Open front-desk float"
              onClick={() => act('/hotel/cashier/shift/open', 'Front-desk float opened', { opening_float: Number(cashierFloat) || 0 })}
            >
              Open front-desk float
            </button>
            <button
              type="button"
              disabled={busy || !cashierShift}
              aria-label="Close front-desk float"
              onClick={async () => {
                const ok = await act('/hotel/cashier/shift/close', 'Front-desk float closed', {
                  closing_float: Number(cashierFloat) || 0,
                  notes: cashierNotes.trim() || null,
                });
                if (ok) setCashierNotes('');
              }}
            >
              Close front-desk float
            </button>
            <h3 id="night-audit" style={{ margin: '12px 0 0' }}>Night audit</h3>
            <label className="muted" htmlFor="hotel-night-audit-note">Night audit note</label>
            <input
              id="hotel-night-audit-note"
              aria-label="Hotel night audit note"
              value={auditNote}
              onChange={(e) => setAuditNote(e.target.value)}
            />
            <button
              type="button"
              disabled={busy}
              aria-label="Run night audit"
              onClick={() => {
                if (auditNote && !auditNote.trim()) {
                  setError('Night audit notes cannot be blank.');
                  return;
                }
                const note = auditNote.trim();
                void act('/hotel/night-audits', 'Night audit posted', note ? { notes: note } : {}).then((ok) => {
                  if (ok) setAuditNote('');
                });
              }}
            >
              Run night audit
            </button>
            <p className="muted">Night audit saves this business date. Leave the note empty and no note is stored. Room nights already on open bills are not posted again. It is not a card charge.</p>
          </div>
          <h3>Closed floats</h3>
          <ul>
            {closedShifts.map((s) => (
              <li key={s.id}>
                {stayClock(s.closed_at, formatPrefs)} · closing float {money(s.closing_float)}
                {s.notes ? <div className="muted">{s.notes}</div> : null}
              </li>
            ))}
            {!closedShifts.length && <li className="muted">No closed front-desk floats.</li>}
          </ul>
          <h3>Night audits</h3>
          <ul>
            {nightAudits.map((n) => (
              <li key={n.id}>
                {stayWhen(n.business_date, formatPrefs)} — occupancy {n.snapshot?.occupancy_rate ?? '—'}%
                {n.snapshot?.note ? <div className="muted">{n.snapshot.note}</div> : null}
              </li>
            ))}
            {!nightAudits.length && <li className="muted">No night audits posted yet.</li>}
          </ul>
        </div>
      )}

      {show('supplies') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Supplies</h2>
          <p className="muted">
            Linen, toiletries, food and drink, and cleaning supplies are kept with purchasing.
          </p>
          <ul>
            <li><Link href="/inventory?tab=products">Supplies</Link></li>
            <li><Link href="/inventory?tab=lowstock">Low supplies</Link></li>
            <li><Link href="/inventory?tab=adjust">Stock adjustments</Link></li>
            <li><Link href="/purchasing?tab=orders">Purchase orders</Link></li>
            <li><Link href="/purchasing?tab=grn">Receive supplies</Link></li>
            <li><Link href="/inventory?tab=batches">Lots</Link></li>
            <li><Link href="/purchasing?tab=invoices">Supplier bills</Link></li>
            <li><Link href="/purchasing?tab=returns">Purchase returns</Link></li>
            <li><Link href="/purchasing?tab=suppliers">Suppliers</Link></li>
          </ul>
        </div>
      )}

      {show('reports') && !report && !listsReady && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel reports</h2>
          <p className="muted">Loading hotel reports…</p>
        </div>
      )}
      {show('reports') && !report && listsReady && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel reports</h2>
          <EmptyState
            title="Reports unavailable"
            detail="Hotel reports are not available right now. Occupancy on the dashboard still uses rooms and reservations."
          />
        </div>
      )}
      {show('reports') && report && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel reports</h2>
          <p className="muted">
            Occupancy and room revenue count planned nights in the selected date range. An early leave still counts
            here. The dashboard counts only the nights the room is still held.
          </p>
          <form
            className="hotel-report-range"
            onSubmit={(e) => {
              e.preventDefault();
              void refresh();
            }}
            style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}
          >
            <label className="hotel-ops-date" htmlFor="hotel-report-start">
              <span>From</span>
              <span className="hotel-ops-date-face">{stayWhen(reportStart, formatPrefs)}</span>
              <input
                id="hotel-report-start"
                type="date"
                aria-label="Hotel report start date"
                value={reportStart}
                onChange={(e) => setReportStart(e.target.value)}
              />
            </label>
            <label className="hotel-ops-date" htmlFor="hotel-report-end">
              <span>To</span>
              <span className="hotel-ops-date-face">{stayWhen(reportEnd, formatPrefs)}</span>
              <input
                id="hotel-report-end"
                type="date"
                aria-label="Hotel report end date"
                value={reportEnd}
                onChange={(e) => setReportEnd(e.target.value)}
              />
            </label>
            <button type="submit" disabled={busy}>Load range</button>
          </form>
          <p className="muted">
            {stayWhen(report.start_date, formatPrefs)} – {stayWhen(report.end_date, formatPrefs)}
          </p>
          <div className="hotel-ops-kpis" style={{ marginBottom: 14 }}>
            <div className="hotel-kpi">
              <div className="lbl">Occupancy</div>
              <div className="val">{Number(report.occupancy_rate || 0).toFixed(1)}%</div>
              <div className="hint">{report.occupied_nights ?? 0} of {report.room_nights_available ?? 0} planned nights</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">ADR</div>
              <div className="val">{money(report.adr)}</div>
              <div className="hint">Average nightly rate on planned nights</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">RevPAR</div>
              <div className="val">{money(report.revpar)}</div>
              <div className="hint">Room revenue for every available night</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">Room revenue</div>
              <div className="val">{money(report.room_revenue)}</div>
              <div className="hint">{report.rooms_total ?? 0} rooms in the house</div>
            </div>
          </div>
          <div className="hotel-ops-kpis" style={{ marginBottom: 14 }}>
            <div className="hotel-kpi">
              <div className="lbl">Payments</div>
              <div className="val">{money(report.payments_total)}</div>
              <div className="hint">Recorded on guest folios in this range</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">Outstanding</div>
              <div className="val">{money(report.outstanding_guest_balances)}</div>
              <div className="hint">Open guest folios</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">Cancellations</div>
              <div className="val">{report.cancellations ?? 0}</div>
              <div className="hint">Arrivals cancelled in this range</div>
            </div>
            <div className="hotel-kpi">
              <div className="lbl">No-shows</div>
              <div className="val">{report.no_shows ?? 0}</div>
              <div className="hint">Arrivals marked no-show in this range</div>
            </div>
          </div>
          <h3>Revenue by source</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Source</th><th>Room revenue</th></tr></thead>
              <tbody>
                {Object.entries(report.revenue_by_source || {}).map(([k, v]) => (
                  <tr key={k}><td>{bookingSourceWord(k)}</td><td>{money(v as number)}</td></tr>
                ))}
                {!Object.keys(report.revenue_by_source || {}).length && (
                  <tr><td colSpan={2} className="muted">No room revenue in this range.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <h3>Revenue by room type</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Room type</th><th>Room revenue</th></tr></thead>
              <tbody>
                {Object.entries(report.revenue_by_room_type || {}).map(([k, v]) => (
                  <tr key={k}><td>{hotelWord(k)}</td><td>{money(v as number)}</td></tr>
                ))}
                {!Object.keys(report.revenue_by_room_type || {}).length && (
                  <tr><td colSpan={2} className="muted">No room revenue in this range.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <h3>Hotel-service sales</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Charge</th><th>Amount</th></tr></thead>
              <tbody>
                {Object.entries(report.service_sales || {}).map(([k, v]) => (
                  <tr key={k}><td>{folioChargeWord(k)}</td><td>{money(v as number)}</td></tr>
                ))}
                {!Object.keys(report.service_sales || {}).length && (
                  <tr><td colSpan={2} className="muted">No service sales in this period.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <h3>Supplies on hand</h3>
          <p className="muted">
            Toiletries, linen, food, and drinks.{' '}
            <Link href="/inventory?tab=products">Open supplies</Link>
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Supply</th>
                <th>SKU</th>
                <th>On hand</th>
              </tr>
            </thead>
            <tbody>
              {(report.inventory_usage || []).map((p: { id: string; sku?: string; name: string; stock_qty: number }) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.sku || '—'}</td>
                  <td>{Number(p.stock_qty || 0)}</td>
                </tr>
              ))}
              {!(report.inventory_usage || []).length && (
                <tr><td colSpan={3} className="muted">No supplies yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {(show('restaurant') || show('bar')) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>{foodTogether ? 'Restaurant and bar' : foodKind === 'bar' ? 'Hotel bar' : 'Hotel restaurant'}</h2>
          <p className="muted">
            {foodTogether
              ? 'Restaurant and bar run as one desk. Post a meal or a drink on an open guest bill. This is not the sales till, it does not print a kitchen ticket, and it does not charge a card.'
              : foodKind === 'bar'
                ? 'The bar runs on its own desk. Post a drink on an open guest bill. This is not the sales till and it does not charge a card.'
                : 'The restaurant runs on its own desk. Post a meal on an open guest bill. This is not the sales till, it does not print a kitchen ticket, and it does not charge a card.'}
            {' '}A catalog {foodNoun} uses that service’s tax. A one-off {foodNoun} stays untaxed. Room nights stay untaxed.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!mealForm.folio_id || !mealForm.service_id) {
                setError(
                  foodTogether
                    ? 'Choose an open bill and a menu item.'
                    : foodKind === 'bar'
                      ? 'Choose an open bill and a bar service.'
                      : 'Choose an open bill and a restaurant service.'
                );
                return;
              }
              const quantity = Number(mealForm.quantity);
              if (!Number.isFinite(quantity) || quantity <= 0) {
                setError('Folio charge quantity must be above zero.');
                return;
              }
              setBusy(true);
              setError('');
              try {
                await api(`/hotel/folios/${mealForm.folio_id}/service-charges`, {
                  method: 'POST',
                  body: JSON.stringify({ service_id: mealForm.service_id, quantity }),
                });
                const picked = services.find((s) => s.id === mealForm.service_id);
                const postedDrink = (picked?.category || foodCharge) === 'bar';
                setMealForm((f) => ({ ...f, quantity: '1' }));
                setMessage(postedDrink ? 'Bar drink posted' : 'Restaurant meal posted');
                await refresh();
              } catch (err: unknown) {
                setError(hotelErr(err, foodCharge === 'bar' ? 'Could not post the bar drink' : 'Could not post the restaurant meal'));
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginBottom: 16 }}
          >
            <label>
              <span>Open bill</span>
              <select value={mealForm.folio_id} onChange={(e) => setMealForm((f) => ({ ...f, folio_id: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar folio' : 'Hotel restaurant folio'}>
                <option value="">Select</option>
                {folioRows.filter((f) => f.status === 'open').map((f) => (
                  <option key={f.id} value={f.id}>{f.folio_number} · {f.guest_name || 'Guest'}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Menu item</span>
              <select value={mealForm.service_id} onChange={(e) => setMealForm((f) => ({ ...f, service_id: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar service' : 'Hotel restaurant service'}>
                <option value="">Select</option>
                {services.filter((s) => foodCategories.includes(s.category)).map((s) => (
                  <option key={s.id} value={s.id}>{s.name} · {money(s.unit_amount)}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Quantity</span>
              <input type="number" min={1} step="1" value={mealForm.quantity} onChange={(e) => setMealForm((f) => ({ ...f, quantity: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar quantity' : 'Hotel restaurant quantity'} />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy} aria-label={foodTogether ? 'Post outlet service' : foodKind === 'bar' ? 'Post bar service' : 'Post restaurant service'}>
                {foodTogether ? 'Post menu item' : foodKind === 'bar' ? 'Post menu drink' : 'Post menu meal'}
              </button>
            </div>
          </form>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!mealForm.folio_id) {
                setError('Choose an open bill.');
                return;
              }
              const quantity = Number(mealForm.quantity);
              const unit = Number(mealForm.unit_amount) || 0;
              if (!mealForm.description.trim()) {
                setError(foodCharge === 'bar' ? 'Enter the drink.' : 'Enter the meal.');
                return;
              }
              if (!Number.isFinite(quantity) || quantity <= 0) {
                setError('Folio charge quantity must be above zero.');
                return;
              }
              setBusy(true);
              setError('');
              try {
                await api(`/hotel/folios/${mealForm.folio_id}/charges`, {
                  method: 'POST',
                  body: JSON.stringify({
                    charge_type: foodCharge,
                    description: mealForm.description.trim(),
                    quantity,
                    unit_amount: unit,
                    discount_amount: 0,
                  }),
                });
                setMealForm((f) => ({ ...f, description: '', unit_amount: '0', quantity: '1' }));
                setMessage(foodCharge === 'bar' ? 'Bar drink posted' : 'Restaurant meal posted');
                await refresh();
              } catch (err: unknown) {
                setError(hotelErr(err, foodCharge === 'bar' ? 'Could not post the bar drink' : 'Could not post the restaurant meal'));
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
          >
            {foodTogether && (
              <label>
                <span>Kind</span>
                <select
                  value={foodCharge}
                  onChange={(e) => setMealForm((f) => ({ ...f, charge_type: e.target.value }))}
                  aria-label="Hotel outlet charge type"
                >
                  <option value="restaurant">Meal</option>
                  <option value="bar">Drink</option>
                </select>
              </label>
            )}
            <label>
              <span>{foodCharge === 'bar' ? 'One-off drink' : 'One-off meal'}</span>
              <input value={mealForm.description} onChange={(e) => setMealForm((f) => ({ ...f, description: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar description' : 'Hotel restaurant description'} />
            </label>
            <label>
              <span>Amount</span>
              <AmountField type="number" min={0} step="0.01" value={mealForm.unit_amount} onChange={(e) => setMealForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar amount' : 'Hotel restaurant amount'} />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy} aria-label={foodCharge === 'bar' ? 'Post bar charge' : 'Post restaurant charge'}>
                {foodCharge === 'bar' ? 'Post one-off drink' : 'Post one-off meal'}
              </button>
            </div>
          </form>
        </div>
      )}

      {show('events') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Events and banquets</h2>
          <p className="muted">
            Book a named space. A guest room on the booking blocks overlapping stays. A deposit is stored on the event. When that guest has an open bill, or checks in for overlapping dates, the same amount is recorded as cash on the bill. It is not a card charge.
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
                    deposit_amount: Number(eventForm.deposit_amount) || 0,
                    notes: eventForm.notes.trim() || null,
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
                  deposit_amount: '0',
                  notes: '',
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
              <HotelDateInput
                value={eventForm.starts_on}
                onChange={(starts_on) => setEventForm((f) => ({ ...f, starts_on }))}
                ariaLabel="Event start date"
                required
                prefs={formatPrefs}
              />
            </label>
            <label>
              <span>Ends</span>
              <HotelDateInput
                value={eventForm.ends_on}
                onChange={(ends_on) => setEventForm((f) => ({ ...f, ends_on }))}
                ariaLabel="Event end date"
                required
                prefs={formatPrefs}
              />
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
            <label>
              <span>Deposit</span>
              <AmountField type="number" min={0} step="0.01" value={eventForm.deposit_amount} onChange={(e) => setEventForm((f) => ({ ...f, deposit_amount: e.target.value }))} aria-label="Event deposit" />
            </label>
            <label>
              <span>Notes</span>
              <input value={eventForm.notes} onChange={(e) => setEventForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Event notes" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy}>Book event</button>
            </div>
          </form>
          <div className="list-table-wrap">
          <table className="table">
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
                  <td>
                    {evRow.title}
                    {evRow.notes ? <div className="muted">{evRow.notes}</div> : null}
                  </td>
                  <td>
                    {evRow.space_name}
                    {Number(evRow.deposit_amount) > 0 ? <div className="muted">Deposit {money(evRow.deposit_amount)}</div> : null}
                  </td>
                  <td>{stayWhen(evRow.starts_on, formatPrefs)} – {stayWhen(evRow.ends_on, formatPrefs)}</td>
                  <td><span className={statusClass(String(evRow.status || ''))}>{hotelWord(evRow.status)}</span></td>
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
        </div>
      )}

      {show('settings') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Hotel settings</h2>
          <p className="muted">
            Tax % and the service charge % are stored for the property. Room folio lines stay nights × nightly rate.
            Post the service charge on an open folio when it applies.
            Post extras or fees on the folio when they apply.
            Leave the note empty and the saved note stays.
          </p>
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
                    no_show_fee_percent: Number(settingsForm.no_show_fee_percent) || 0,
                    service_charge_percent: Number(settingsForm.service_charge_percent) || 0,
                    property_name: settingsForm.property_name.trim() || null,
                    notes: settingsForm.notes.trim() || null,
                    food_outlet_mode: settingsForm.food_outlet_mode === 'separate' ? 'separate' : 'together',
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
            <label>
              <span>No-show fee %</span>
              <input type="number" min={0} step="0.01" value={settingsForm.no_show_fee_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, no_show_fee_percent: e.target.value }))} aria-label="Hotel no-show fee percent" />
            </label>
            <label>
              <span>Service charge %</span>
              <input type="number" min={0} max={100} step="0.01" value={settingsForm.service_charge_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, service_charge_percent: e.target.value }))} aria-label="Hotel service charge percent" />
            </label>
            <label style={{ gridColumn: '1 / -1' }}>
              <span>Restaurant and bar</span>
              <select
                value={settingsForm.food_outlet_mode === 'separate' ? 'separate' : 'together'}
                onChange={(e) => setSettingsForm((f) => ({ ...f, food_outlet_mode: e.target.value }))}
                aria-label="Hotel food outlet mode"
              >
                <option value="together">Together — one desk for meals and drinks</option>
                <option value="separate">Separate — restaurant and bar each have a desk</option>
              </select>
            </label>
            <p className="muted" style={{ gridColumn: '1 / -1' }}>
              Together uses one desk for meals and drinks. Separate gives the restaurant and the bar their own desks. Both post to the guest bill. Neither is a card charge or the sales till.
            </p>
            <label style={{ gridColumn: '1 / -1' }}>
              <span>Note</span>
              <input value={settingsForm.notes} onChange={(e) => setSettingsForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel settings notes" />
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
