'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import DashboardGreeting from '../../../components/DashboardGreeting';
import PageHeader from '../../../components/PageHeader';
import RowActions, { type RowActionItem } from '../../../components/RowActions';
import { navItemVisibleForRole, roleHomePath } from '../../../lib/tenantNav';
import HotelRoomBoard from '../../../components/HotelRoomBoard';
import './hotel-desk.css';
import EmptyState from '../../../components/EmptyState';
import FormModal from '../../../components/FormModal';
import HotelGuide from '../../../components/HotelGuide';
import { DayBars, RankBars } from '../../../components/HotelReportCharts';
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
  adults?: number;
  children?: number;
  nightly_rate?: number;
};

type Folio = {
  id: string;
  reservation_id?: string | null;
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
  charges: { id: string; description: string; charge_type?: string | null; quantity?: number; unit_amount?: number; tax_amount?: number; discount_amount?: number; line_total: number; is_void: boolean }[];
  payments: { id: string; method: string; amount: number; reference?: string | null; notes?: string | null; refund_of_id?: string | null }[];
};

type HotelDialog =
  | { kind: 'extend' | 'move' | 'duplicate' | 'edit' | 'arrival'; stay: Reservation }
  | { kind: 'balance'; stayId: string; name: string; balance: number }
  | { kind: 'care'; roomId: string; roomCode: string; closed: boolean }
  | { kind: 'void'; chargeId: string; label: string }
  | { kind: 'refund'; paymentId: string; label: string }
  | { kind: 'room'; room: Room }
  | { kind: 'guest'; guest: Guest }
  | { kind: 'history' }
  | { kind: 'service'; service: HotelService }
  | { kind: 'plan'; plan: any };

type StayQuote = {
  nights: number;
  nightly_rate: number;
  total: number;
  rate_plan?: string | null;
  over_capacity?: boolean;
  max_occupancy?: number;
};

/** The hotel roles with one job. Everyone else on the desk is decided by their module grant. */
const HOTEL_STAFF_ROLES = new Set([
  'hotel_housekeeping',
  'hotel_maintenance',
  'hotel_reservations',
  'hotel_front_desk',
  'hotel_cashier',
]);

type HkTask = {
  id: string;
  room_id: string;
  room_code?: string | null;
  task_type?: string | null;
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
const GUEST_EDIT_FIELDS: [string, string][] = [
  ['full_name', 'Full name'],
  ['phone', 'Phone'],
  ['email', 'Email'],
  ['nationality', 'Nationality'],
  ['id_type', 'ID type'],
  ['id_document', 'ID number'],
  ['address', 'Address'],
  ['company_name', 'Company'],
  ['emergency_contact', 'Emergency contact'],
  ['preferences', 'Preferences'],
  ['notes', 'Notes'],
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

function HotelViews({
  label,
  value,
  items,
  onPick,
}: {
  label: string;
  value: string;
  items: [string, string, (number | null)?][];
  onPick: (key: string) => void;
}) {
  return (
    <div className="hviews" role="group" aria-label={label}>
      {items.map(([key, text, count]) => (
        <button key={key || 'all'} type="button" className="hview" aria-pressed={value === key} onClick={() => onPick(key)}>
          {text}
          {count != null ? <b>{count}</b> : null}
        </button>
      ))}
    </div>
  );
}

const DASH_ICONS: Record<string, string> = {
  arrivals: 'M10 17l5-5-5-5M15 12H3M15 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4',
  departures: 'M16 17l5-5-5-5M21 12H9M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4',
  in_house: 'M3 18v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6M3 15h18M3 18v2M21 18v2M6 10V7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v3',
  free: 'M15 7a4 4 0 1 1-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0 1 15 7zM16 10h.01',
  '/hotel?tab=reservations#book-stay': 'M8 3v3M16 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM12 12v5M9.5 14.5h5',
  '/hotel?tab=front-desk': 'M5 18h14M6 18a6 6 0 0 1 12 0M12 12V9M10 9h4M3 21h18',
  '/hotel?tab=billing': 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6',
  '/hotel?tab=housekeeping': 'M12 3v4M5 12l3-5h8l3 5M5 12h14l-1 9H6z',
  '/hotel?tab=maintenance': 'M15 6a4 4 0 0 0-5 5L4 17l3 3 6-6a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z',
  '/hotel?tab=cashier': 'M3 7h18v11H3zM3 11h18M7 15h3',
};

function HotelDashIcon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={DASH_ICONS[name] || 'M12 5v14M5 12h14'} />
    </svg>
  );
}

function countWord(n: number, word: string) {
  return `${n} ${word}${Number(n) === 1 ? '' : 's'}`;
}

function statusClass(status: string) {
  const key = status.replace(/\s+/g, '_');
  return `hotel-st hotel-st-${key}`;
}

function hotelWord(value: string | null | undefined) {
  const text = String(value || '').replace(/_/g, ' ').trim();
  if (!text) return '';
  if (text.toLowerCase() === 'ota') return 'Booking sites';
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
  const [loadedTab, setLoadedTab] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [boardStays, setBoardStays] = useState<Reservation[]>([]);
  const [sectionHash, setSectionHash] = useState('');
  const [myRole, setMyRole] = useState('');
  const [dialog, setDialog] = useState<HotelDialog | null>(null);
  const [dlg, setDlg] = useState<Record<string, string>>({});
  const [dlgAmenities, setDlgAmenities] = useState<Record<string, boolean>>({});
  const [dlgRooms, setDlgRooms] = useState<Room[] | null>(null);
  const [dlgError, setDlgError] = useState('');
  const [availReady, setAvailReady] = useState(false);
  const [quote, setQuote] = useState<StayQuote | null>(null);
  const [quoteNote, setQuoteNote] = useState('');
  const [resQuery, setResQuery] = useState('');
  const [guestQuery, setGuestQuery] = useState('');
  const [billQuery, setBillQuery] = useState('');
  const [billView, setBillView] = useState('open');
  const [hkView, setHkView] = useState('open');
  const [maintView, setMaintView] = useState('open');
  const [reqOpen, setReqOpen] = useState(false);
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
      new_guest_phone: '',
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
  const reportRange = useRef('');
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
  const [dashDate, setDashDate] = useState(() => localIso());
  const [reportStart, setReportStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return localIso(d);
  });
  const [reportEnd, setReportEnd] = useState(() => localIso());
  const [reportView, setReportView] = useState('overview');
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
  const [lfForm, setLfForm] = useState({ description: '', kind: 'found', room_id: '', notes: '' });
  const [mergeSource, setMergeSource] = useState('');
  const [transferChargeId, setTransferChargeId] = useState('');
  const [transferFolioId, setTransferFolioId] = useState('');
  const [settingsForm, setSettingsForm] = useState({
    check_in_time: '14:00',
    check_out_time: '11:00',
    cancellation_hours: '24',
    tax_percent: '0',
    room_rates_include_tax: true,
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

  const resView = ['calendar', 'book-stay', 'group-stay', 'online-booking'].includes(sectionHash) ? sectionHash : 'list';
  const roomView = sectionHash === 'rate-plans' ? 'rate-plans' : 'rooms';
  const hkPage = sectionHash === 'lost-found' ? 'lost-found' : 'tasks';
  const canManage = !HOTEL_STAFF_ROLES.has(myRole);
  const canCorrectMoney = canManage || myRole === 'hotel_cashier';

  function goView(hash: string) {
    if (hash) {
      window.location.hash = hash;
    } else {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    }
    setSectionHash(hash);
    window.scrollTo({ top: 0 });
  }

  function setStayDates(checkIn: string, checkOut: string) {
    const out = checkOut > checkIn ? checkOut : shiftIso(checkIn, 1);
    setResForm((f) => ({ ...f, check_in_date: checkIn, check_out_date: out, walk_in: checkIn === localIso() ? f.walk_in : false }));
    setAvailForm((f) => ({ ...f, check_in_date: checkIn, check_out_date: out }));
  }

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
    const extraPaths: string[] = [];
    if (tab === 'dashboard' || tab === 'front-desk') extraPaths.push('/hotel/guest-requests');
    if (tab === 'rooms' || tab === 'reservations') extraPaths.push('/hotel/rate-plans');
    const needGuests = ['reservations', 'guests', 'events'].includes(tab);
    const needSummary = tab === 'dashboard' || tab === 'reservations';
    if (tab === 'reservations') extraPaths.push('/hotel/booking-link');
    if (tab === 'housekeeping' || tab === 'dashboard') extraPaths.push('/hotel/housekeeping');
    if (tab === 'maintenance') extraPaths.push('/hotel/maintenance');
    if (['services', 'restaurant', 'bar', 'billing', 'reservations', 'front-desk'].includes(tab)) extraPaths.push('/hotel/services');
    if (tab === 'restaurant' || tab === 'bar') extraPaths.push('/hotel/folios');
    if (tab === 'billing' || tab === 'reservations' || tab === 'front-desk') extraPaths.push('/hotel/folios');
    if (tab === 'reports') extraPaths.push(`/hotel/reports?start_date=${reportStart}&end_date=${reportEnd}`);
    if (tab === 'housekeeping') extraPaths.push('/hotel/lost-found');
    if (tab === 'cashier') {
      extraPaths.push('/hotel/cashier/shift', '/hotel/cashier/shifts', '/hotel/night-audits');
    }
    if (tab === 'events') extraPaths.push('/hotel/events');
    if (['dashboard', 'front-desk', 'rooms', 'reservations'].includes(tab)) extraPaths.push('/hotel/reservations');
    const extraFailed: string[] = [];
    const extraLoad = Promise.all(
      extraPaths.map(async (path) => ({
        path,
        data: await soft<any>(
          path,
          path.includes('/reports') || path.includes('/shift') || path === '/hotel/booking-link' ? null : [],
          extraFailed
        ),
      }))
    );
    const [sRes, rRes, gRes, resvRes, setRes] = await Promise.allSettled([
      needSummary ? api(`/hotel/summary?on_date=${dashDate}`) : Promise.resolve(null),
      api(tab === 'rooms' ? '/hotel/rooms' : '/hotel/rooms?is_active=true'),
      needGuests ? api('/hotel/guests?is_active=true') : Promise.resolve(null),
      api(`/hotel/reservations${qs}`),
      api('/hotel/settings'),
    ]);
    if (seq !== refreshSeq.current) return;
    if (sRes.status === 'fulfilled' && sRes.value) setSummary(sRes.value.data || null);
    if (rRes.status === 'fulfilled') setRooms(rRes.value.data || []);
    if (gRes.status === 'fulfilled' && gRes.value) setGuests(gRes.value.data || []);
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
          room_rates_include_tax: setData.room_rates_include_tax !== false,
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
    if (guestFail) extraFailed.push('/hotel/guests');
    if (sRes.status === 'rejected') extraFailed.push('/hotel/summary');
    if (setRes.status === 'rejected') extraFailed.push('/hotel/settings');

    const extraResults = await extraLoad;
    if (seq !== refreshSeq.current) return;
    for (const row of extraResults) {
      if (row.path === '/hotel/housekeeping') setHkTasks(row.data || []);
      else if (row.path === '/hotel/reservations') setBoardStays(row.data || []);
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
    setLoadedTab(tab);
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
        const role = String(me.data?.role || '');
        setMyRole(role);
        if (ok && !navItemVisibleForRole(role, rawTab ? `/hotel?tab=${rawTab}` : '/hotel', true)) {
          router.replace(roleHomePath(role, 'hotel'));
          return;
        }
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
    if (!moduleAllowed || tab !== 'reservations' || resView !== 'calendar') return;
    let live = true;
    const start = resGridStart;
    const span = resGridSpan;
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
  }, [moduleAllowed, tab, resView, resGridStart, resGridSpan, calTick]);

  useEffect(() => {
    setAddOpen(false);
  }, [tab, sectionHash]);

  useEffect(() => {
    setMessage('');
    setError('');
  }, [tab]);

  useEffect(() => {
    setFolioNote(folio?.notes || '');
  }, [folio?.id, folio?.notes]);

  useEffect(() => {
    if (!folio?.id) return;
    const timer = window.setTimeout(() => document.getElementById('guest-bill')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 120);
    return () => window.clearTimeout(timer);
  }, [folio?.id]);

  // The amount still owed is the usual payment, so it is filled in.
  useEffect(() => {
    const owed = Number(folio?.balance || 0);
    setPayForm((f) => ({ ...f, amount: owed > 0 ? String(owed) : '0' }));
  }, [folio?.id, folio?.balance]);

  // A desk left open overnight moves to the new day by itself.
  useEffect(() => {
    const timer = window.setInterval(() => setDashDate(localIso()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  // The quick range buttons change the dates; the report follows them.
  useEffect(() => {
    if (tab !== 'reports' || !moduleAllowed) return;
    const key = `${reportStart}|${reportEnd}`;
    if (reportRange.current && reportRange.current !== key) void refresh();
    reportRange.current = key;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportStart, reportEnd, tab, moduleAllowed]);

  // Free rooms follow the dates, so there is no separate search to run.
  useEffect(() => {
    if (tab !== 'reservations' || !['book-stay', 'group-stay'].includes(resView) || !moduleAllowed) return;
    if (!(availForm.check_out_date > availForm.check_in_date)) {
      setAvailRooms([]);
      return;
    }
    let live = true;
    setAvailReady(false);
    const q = new URLSearchParams({ check_in_date: availForm.check_in_date, check_out_date: availForm.check_out_date });
    if (availForm.room_type) q.set('room_type', availForm.room_type);
    const timer = window.setTimeout(async () => {
      try {
        const rows = await api(`/hotel/availability?${q.toString()}`);
        if (live) setAvailRooms(rows.data || []);
      } catch (err: unknown) {
        if (live) setError(hotelErr(err, 'Could not check which rooms are free.'));
      } finally {
        if (live) setAvailReady(true);
      }
    }, 150);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [tab, resView, moduleAllowed, availForm.check_in_date, availForm.check_out_date, availForm.room_type, calTick]);

  // The price comes from the server, worked out the same way as the booking itself.
  useEffect(() => {
    setQuote(null);
    setQuoteNote('');
    if (tab !== 'reservations' || resView !== 'book-stay' || !resForm.room_id) return;
    if (!(resForm.check_out_date > resForm.check_in_date)) return;
    let live = true;
    const q = new URLSearchParams({
      room_id: resForm.room_id,
      check_in_date: resForm.check_in_date,
      check_out_date: resForm.check_out_date,
      adults: String(Number(resForm.adults) || 1),
      children: String(Number(resForm.children) || 0),
      discount_percent: String(Math.min(100, Math.max(0, Number(resForm.discount_percent) || 0))),
    });
    if (resForm.rate_plan_id) q.set('rate_plan_id', resForm.rate_plan_id);
    const timer = window.setTimeout(async () => {
      try {
        const res = await api(`/hotel/quote?${q.toString()}`);
        if (live) setQuote(res.data || null);
      } catch (err: unknown) {
        if (live) setQuoteNote(hotelErr(err, 'Could not work out the price.'));
      }
    }, 200);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [tab, resView, resForm.room_id, resForm.check_in_date, resForm.check_out_date, resForm.adults, resForm.children, resForm.rate_plan_id, resForm.discount_percent]);

  function prefillStay(roomId: string, dateIso: string, _roomCode: string) {
    setResForm((f) => ({ ...f, room_id: roomId }));
    setStayDates(dateIso, shiftIso(dateIso, 1));
    if (tab === 'reservations') goView('book-stay');
    else router.push('/hotel?tab=reservations#book-stay');
  }

  function openDialog(next: HotelDialog) {
    setDlgError('');
    setDlgRooms(null);
    let fields: Record<string, string> = {};
    if (next.kind === 'extend') {
      fields = { date: shiftIso(String(next.stay.check_out_date).slice(0, 10), 1) };
    } else if (next.kind === 'duplicate') {
      fields = { date: String(next.stay.check_out_date).slice(0, 10) };
    } else if (next.kind === 'move') {
      const stay = next.stay;
      const today = localIso();
      const inDate = String(stay.check_in_date).slice(0, 10);
      const outDate = String(stay.check_out_date).slice(0, 10);
      const from = inDate > today ? inDate : today;
      const to = outDate > from ? outDate : shiftIso(from, 1);
      fields = { room_id: '' };
      void (async () => {
        try {
          const rows = await api(`/hotel/availability?check_in_date=${from}&check_out_date=${to}`);
          setDlgRooms(((rows.data || []) as Room[]).filter((r) => r.id !== stay.room_id));
        } catch (err: unknown) {
          setDlgRooms([]);
          setDlgError(hotelErr(err, 'Could not check which rooms are free.'));
        }
      })();
    } else if (next.kind === 'edit') {
      const r = next.stay;
      fields = {
        check_in_date: String(r.check_in_date).slice(0, 10),
        check_out_date: String(r.check_out_date).slice(0, 10),
        adults: String(r.adults ?? 1),
        children: String(r.children ?? 0),
        nightly_rate: String(r.nightly_rate ?? 0),
        special_requests: r.special_requests || '',
        notes: r.notes || '',
      };
    } else if (next.kind === 'void') {
      fields = { reason: '' };
    } else if (next.kind === 'refund') {
      const paid = folio?.payments.find((p) => p.id === next.paymentId);
      const credit = Number(folio?.balance || 0) < 0 ? Math.abs(Number(folio?.balance)) : Number(paid?.amount || 0);
      fields = { amount: String(credit), reason: '' };
    } else if (next.kind === 'room') {
      const r = next.room;
      fields = {
        name: r.name || '',
        room_type: r.room_type || 'standard',
        floor: r.floor || '',
        bed_type: r.bed_type || '',
        max_occupancy: String(r.max_occupancy ?? 2),
        rate_amount: String(r.rate_amount ?? 0),
        weekend_rate: r.weekend_rate != null ? String(r.weekend_rate) : '',
        extra_person_charge: String(r.extra_person_charge ?? 0),
        description: r.description || '',
        notes: r.notes || '',
      };
      const had = (r.amenities || {}) as Record<string, unknown>;
      setDlgAmenities(Object.fromEntries(ROOM_AMENITIES.map((key) => [key, Boolean(had[key])])));
    } else if (next.kind === 'guest') {
      const g = next.guest as Record<string, any>;
      fields = Object.fromEntries(GUEST_EDIT_FIELDS.map(([key]) => [key, String(g[key] ?? '')]));
    } else if (next.kind === 'service') {
      const v = next.service as Record<string, any>;
      fields = {
        name: v.name || '',
        category: v.category || 'service',
        unit_amount: String(v.unit_amount ?? 0),
        tax_percent: String(v.tax_percent ?? 0),
        notes: v.notes || '',
      };
    } else if (next.kind === 'plan') {
      fields = { name: next.plan.name || '', amount: String(next.plan.amount ?? 0), min_nights: String(next.plan.min_nights ?? 1) };
    }
    setDlg(fields);
    setDialog(next);
  }

  /** Save from a dialog. A failure stays inside the dialog so nothing typed is lost. */
  async function dialogSave(path: string, body: object, okMessage: string, method = 'POST') {
    setBusy(true);
    setDlgError('');
    try {
      await api(path, { method, body: JSON.stringify(body) });
      setDialog(null);
      setMessage(okMessage);
      if (folio) {
        const f = await api(`/hotel/folios/${folio.id}`);
        setFolio(f.data || null);
      }
      await refresh();
    } catch (err: unknown) {
      setDlgError(hotelErr(err, 'Could not save that. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  function boardStay(stayId: string) {
    const stay = boardStays.find((r) => r.id === stayId);
    if (stay && stay.status !== 'checked_in') {
      openDialog({ kind: 'arrival', stay });
      return;
    }
    if (tab !== 'front-desk' && tab !== 'billing' && tab !== 'reservations') router.push('/hotel?tab=front-desk');
    void openFolio(stayId);
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

  /** Use the picked guest, or add the typed one. Kept on the form so a second try does not add them twice. */
  async function stayGuestId() {
    const picked = resForm.guest_id.trim();
    if (picked) return picked;
    const name = resForm.new_guest_name.trim();
    if (!name) return '';
    const phone = resForm.new_guest_phone.replace(/[\s()-]/g, '');
    const created = await api('/hotel/guests', {
      method: 'POST',
      body: JSON.stringify({ full_name: name, phone: phone || null }),
    });
    const guest = created.data as Guest | undefined;
    if (guest?.id) {
      setGuests((rows) => [...rows, guest]);
      setResForm((f) => ({ ...f, guest_id: guest.id, new_guest_name: '', new_guest_phone: '' }));
    }
    return guest?.id || '';
  }

  function resetStayForm() {
    setResForm({
      room_id: '',
      guest_id: '',
      new_guest_name: '',
      new_guest_phone: '',
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
    setAvailForm({ check_in_date: localIso(), check_out_date: shiftIso(localIso(), 1), room_type: '' });
  }

  async function createReservation(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (!resForm.room_id.trim()) {
      setError('Choose a room first.');
      return;
    }
    const discountPercent = Number(resForm.discount_percent) || 0;
    if (discountPercent > 100) {
      setError('Stay discount percent cannot be above 100.');
      return;
    }
    if (discountPercent > 0 && !staffId) {
      setError('Sign in again before applying a stay discount.');
      return;
    }
    setBusy(true);
    try {
      const guestId = await stayGuestId();
      if (!guestId) {
        setError('Choose a guest, or type a new guest name.');
        return;
      }
      const wasWalkIn = resForm.walk_in;
      const wasWaiting = resForm.waitlist;
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
      const number = booked.data?.reservation_number || 'The stay';
      resetStayForm();
      goView('');
      setMessage(wasWaiting ? `${number} is on the waiting list.` : `${number} is booked.`);
      if (wasWalkIn && booked.data?.id) {
        try {
          await api(`/hotel/reservations/${booked.data.id}/check-in`, {
            method: 'POST',
            body: JSON.stringify({}),
          });
          setMessage(`${number} is checked in. Take a payment or add charges on the bill.`);
          await openFolio(booked.data.id);
        } catch (err: unknown) {
          setError(`${number} is booked but not checked in. ${hotelErr(err, 'Check the guest in from the list.')}`);
          setMessage('');
        }
      }
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

  /** Early arrivals and rooms still waiting to be cleaned are allowed, but only after a clear warning. */
  function checkInStay(r: Reservation) {
    const when = String(r.check_in_date).slice(0, 10);
    const room = rooms.find((x) => x.id === r.room_id);
    const warnings: string[] = [];
    if (when > localIso()) warnings.push(`This stay starts on ${stayWhen(when, formatPrefs)}.`);
    if (room?.status === 'dirty' || room?.housekeeping_status === 'dirty') warnings.push(`Room ${r.room_code || ''} still needs cleaning.`);
    if (warnings.length && !window.confirm(`${warnings.join(' ')} Check the guest in anyway?`)) return;
    void act(`/hotel/reservations/${r.id}/check-in`, `${r.guest_name || r.reservation_number} is checked in.`);
  }

  async function checkOutStay(reservationId: string, name: string) {
    setError('');
    setMessage('');
    try {
      let bal = 0;
      try {
        const f = await api(`/hotel/reservations/${reservationId}/folio`);
        bal = Number(f.data?.balance || 0);
      } catch {
        bal = 0;
      }
      if (bal > 0.009) {
        openDialog({ kind: 'balance', stayId: reservationId, name, balance: bal });
        return;
      }
      if (await act(`/hotel/reservations/${reservationId}/check-out`, `${name} is checked out. Housekeeping has the room to clean.`)) setFolio(null);
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
        `<p>Charges ${escapeSlip(money(folio.charges_total))} (includes tax ${escapeSlip(money(folio.charges.filter((c) => !c.is_void).reduce((sum, c) => sum + Number(c.tax_amount || 0), 0)))}) · Payments ${escapeSlip(money(folio.payments_total))} · Balance <strong>${escapeSlip(money(folio.balance))}</strong></p>` +
        `<h2>Charges</h2><table><thead><tr><th>Description</th><th>Amount</th></tr></thead><tbody>${chargeRows || '<tr><td colspan="2">No charges</td></tr>'}</tbody></table>` +
        `<h2>Payments</h2><table><thead><tr><th>Method</th><th>Amount</th></tr></thead><tbody>${payRows || '<tr><td colspan="2">No payments</td></tr>'}</tbody></table>`,
    );
    if (!printDocumentHtml(html)) {
      setError('Could not open the bill for printing.');
      return;
    }
    setMessage('Bill sent to print');
  }

  async function openFolio(reservationId: string) {
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/reservations/${reservationId}/folio`);
      setFolio(f.data || null);
    } catch (err: any) {
      setError(hotelErr(err, 'No bill yet. Check the guest in first.'));
      setFolio(null);
    } finally {
      setBusy(false);
    }
  }

  /** A fee or service charge that goes on the bill once. */
  async function postBillExtra(path: string, body: object, confirmText: string, okMessage: string) {
    if (!folio || !window.confirm(confirmText)) return;
    setBusy(true);
    setError('');
    try {
      const f = await api(`/hotel/folios/${folio.id}/${path}`, { method: 'POST', body: JSON.stringify(body) });
      setFolio(f.data || null);
      setMessage(okMessage);
      await refresh();
    } catch (err: unknown) {
      setError(hotelErr(err, 'Could not post that to the bill'));
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
      setMessage('Note saved');
    } catch (err: any) {
      setError(hotelErr(err, 'Could not save the note'));
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
    if (!(Number(payForm.amount) > 0)) {
      setError('Type the amount the guest is paying.');
      return;
    }
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
      setPayForm((p) => ({ ...p, method: 'cash', reference: '', notes: '' }));
      setMessage('Payment recorded');
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
      setAddOpen(false);
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
      setAddOpen(false);
      setMessage('Fault reported');
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
  const tabReady = loadedTab === tab;
  const emptyOr = (text: string) => (tabReady ? text : 'Loading…');
  const addLabel = ({
    rooms: canManage ? (roomView === 'rate-plans' ? 'Add rate plan' : 'Add room') : '',
    guests: 'Add guest',
    housekeeping: hkPage === 'lost-found' ? 'Record an item' : 'Add task',
    maintenance: 'Report a fault',
    services: canManage ? 'Add service' : '',
    events: 'Book an event',
  } as Record<string, string>)[tab];
  const addCounts: Record<string, number> = {
    rooms: rooms.length,
    plans: ratePlans.length,
    guests: guests.length,
    housekeeping: hkTasks.length,
    lost: lostFound.length,
    maintenance: maint.length,
    services: services.length,
    events: events.length,
  };
  /** Lists come first. A form opens from the header, or by itself while the list is empty. */
  const addShown = (section: string) => addOpen || (tabReady && !addCounts[section] && Boolean(addLabel));
  const deskToday = dashDate;
  const deskArrivals = boardStays.filter((r) => r.status === 'booked' && r.check_in_date === deskToday).length;
  const deskLeaving = boardStays.filter((r) => r.status === 'checked_in' && r.check_out_date === deskToday).length;
  const deskInHouse = boardStays.filter((r) => r.status === 'checked_in').length;
  const deskTiles: [string, string, number | null][] = [
    ['arrivals', 'Arriving today', deskArrivals],
    ['departures', 'Leaving today', deskLeaving],
    ['in_house', 'In house', deskInHouse],
    ['', 'All stays', null],
  ];
  async function showStayBill(stayId: string) {
    await openFolio(stayId);
  }
  function openDesk(kind: string) {
    setDeskKind(kind);
    router.push('/hotel?tab=front-desk');
  }
  function openEmptyRoom(roomId: string, roomCode: string) {
    const room = rooms.find((r) => r.id === roomId);
    const closed = ['maintenance', 'out_of_order', 'blocked'].includes(String(room?.status));
    if (closed || room?.status === 'dirty' || room?.housekeeping_status === 'dirty') {
      openDialog({ kind: 'care', roomId, roomCode, closed });
      return;
    }
    prefillStay(roomId, dashDate, roomCode);
  }
  const needle = (text: string) => text.trim().toLowerCase();
  const hits = (query: string, ...fields: (string | null | undefined)[]) =>
    !needle(query) || fields.some((f) => String(f || '').toLowerCase().includes(needle(query)));
  const shownStays = reservations.filter((r) => hits(resQuery, r.guest_name, r.guest_phone, r.reservation_number, r.room_code));
  const shownGuests = guests.filter((g) => hits(guestQuery, g.full_name, g.phone, g.email, g.company_name));
  const billGroups: Record<string, FolioRow[]> = {
    open: folioRows.filter((f) => f.status === 'open'),
    owing: folioRows.filter((f) => Number(f.balance) > 0.004),
    closed: folioRows.filter((f) => f.status !== 'open'),
    '': folioRows,
  };
  const shownBills = (billGroups[billView] || folioRows).filter((f) => hits(billQuery, f.guest_name, f.folio_number, f.reservation_number, f.room_code));
  const hkDone = (t: HkTask) => t.status === 'completed' || t.status === 'cancelled';
  const hkShown = hkTasks.filter((t) => (hkView === 'done' ? hkDone(t) : !hkDone(t)));
  const maintDone = (t: MaintTicket) => t.status === 'completed' || t.status === 'cancelled';
  const maintShown = maint.filter((t) => (maintView === 'done' ? maintDone(t) : !maintDone(t)));
  const stayPick = guests.find((g) => g.id === resForm.guest_id) || null;
  const stayMatches = resForm.new_guest_name.trim()
    ? guests.filter((g) => hits(resForm.new_guest_name, g.full_name, g.phone)).slice(0, 6)
    : [];
  const liveRooms = rooms.filter((r) => r.is_active);
  const pickedRoom = rooms.find((r) => r.id === resForm.room_id) || null;
  const taxPercent = Number(settingsForm.tax_percent) || 0;
  const stayNights = Math.max(0, Math.round((Date.parse(resForm.check_out_date) - Date.parse(resForm.check_in_date)) / 86400000));
  const stayGuestPicker = (
    <div className="hstay-guest">
      {stayPick ? (
        <p className="hstay-chosen">
          <b>{stayPick.full_name}</b>
          {stayPick.phone ? <span className="muted"> · {stayPick.phone}</span> : null}
          <button type="button" onClick={() => setResForm((f) => ({ ...f, guest_id: '' }))} aria-label="Choose a different guest">Change</button>
        </p>
      ) : (
        <>
          <label>
            <span>Guest name or phone</span>
            <input
              value={resForm.new_guest_name}
              onChange={(e) => setResForm((f) => ({ ...f, new_guest_name: e.target.value }))}
              aria-label="New hotel guest name"
              placeholder="Start typing"
              autoComplete="off"
            />
          </label>
          {stayMatches.length > 0 && (
            <div className="hstay-matches" role="group" aria-label="Guests already on file">
              {stayMatches.map((g) => (
                <button key={g.id} type="button" onClick={() => setResForm((f) => ({ ...f, guest_id: g.id, new_guest_name: '', new_guest_phone: '' }))}>
                  {g.full_name}
                  {g.phone ? <span className="muted"> {g.phone}</span> : null}
                </button>
              ))}
            </div>
          )}
          {resForm.new_guest_name.trim() ? (
            <>
              <p className="hint">Not listed? {resForm.new_guest_name.trim()} will be added as a new guest.</p>
              <label>
                <span>New guest phone (optional)</span>
                <input
                  value={resForm.new_guest_phone}
                  onChange={(e) => setResForm((f) => ({ ...f, new_guest_phone: e.target.value }))}
                  aria-label="New hotel guest phone"
                  placeholder="+233…"
                  autoComplete="off"
                />
              </label>
            </>
          ) : null}
        </>
      )}
    </div>
  );
  const foodCategories = foodTogether ? ['restaurant', 'bar'] : [foodKind];
  const foodCharge =
    foodTogether && (mealForm.charge_type === 'bar' || mealForm.charge_type === 'restaurant')
      ? mealForm.charge_type
      : foodKind;
  const foodNoun = foodCharge === 'bar' ? 'drink' : 'meal';

  return (
    <>
      {show('dashboard') ? (
        <div className="hdash-hero"><DashboardGreeting desk="Hotel dashboard" place={settings?.property_name || ''} /></div>
      ) : (
      <PageHeader
        title={
          ({
            reservations: 'Reservations',
            'front-desk': 'Front desk',
            rooms: 'Rooms and rates',
            housekeeping: 'Housekeeping',
            maintenance: 'Maintenance',
            guests: 'Guests',
            billing: 'Guest bills',
            cashier: 'Cash and night audit',
            supplies: 'Supplies',
            services: 'Hotel services',
            restaurant: foodTogether ? 'Restaurant and bar' : 'Restaurant',
            bar: foodTogether ? 'Restaurant and bar' : 'Bar',
            reports: 'Hotel reports',
            events: 'Events and banquets',
            settings: 'Hotel settings',
          } as Record<string, string>)[tab] || 'Hotel'
        }
        actions={
          tab === 'reservations' ? (
            <button type="button" className="btn-primary" onClick={() => goView('book-stay')}>
              Book a stay
            </button>
          ) : addLabel ? (
            <button type="button" className="btn-primary" onClick={() => setAddOpen((v) => !v)} aria-expanded={addOpen}>
              {addOpen ? 'Close' : addLabel}
            </button>
          ) : undefined
        }
        subtitle={
          ({
            dashboard: 'Occupancy, arrivals, and alerts for today.',
            reservations: 'See who is coming, find a free room, and book a stay.',
            'front-desk': 'Who is arriving, who is leaving, and every room right now.',
            rooms: 'Your rooms, their nightly rates, and rate plans.',
            housekeeping: hkPage === 'lost-found' ? 'Things guests left behind, and damage found in rooms.' : 'Rooms to clean, and things guests left behind.',
            maintenance: 'Faults in rooms, and which rooms they close.',
            guests: 'Everyone who has stayed, with their stays and details.',
            billing: 'What each guest owes. Payments go to your accounts by themselves.',
            cashier: 'Count the front-desk float and close the day. This is not the shop till and not a card charge.',
            supplies: 'Linen, toiletries, food and beverage, and cleaning supplies.',
            services: 'Laundry, spa, meals and other extras you add to a guest bill.',
            restaurant: foodTogether
              ? 'Meals and drinks on one desk. Both post to the guest bill. This is not the sales till.'
              : 'Meals on the restaurant desk. Drinks stay on the bar desk. Both post to the guest bill.',
            bar: foodTogether
              ? 'Meals and drinks on one desk. Both post to the guest bill. This is not the sales till.'
              : 'Drinks on the bar desk. Meals stay on the restaurant desk. Both post to the guest bill.',
            reports: 'How full you were, what you earned, who owes, and what is booked ahead.',
            events: 'Banquets and meeting space. Optional room hold blocks that room.',
            settings: 'Your hotel name, check-in times, tax and fees.',
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
      {message && <p className="hotel-banner ok" role="status">{message}</p>}
      <HotelGuide
        id={
          tab === 'reservations'
            ? (resView === 'list' || resView === 'calendar' ? 'reservations' : resView)
            : tab === 'rooms'
              ? roomView
              : tab === 'housekeeping'
                ? (hkPage === 'lost-found' ? 'lost-found' : 'housekeeping')
                : tab === 'bar'
                  ? 'restaurant'
                  : tab
        }
      />

      {show('dashboard') && (
        <div className="hotel-ops hdash">
          {!summary && !error && <p className="empty">Loading operational totals…</p>}
          {summary && (() => {
            const mix = summary.room_status_mix || {};
            const tot = Math.max(1, summary.rooms_total || 0);
            const occupiedN = mix.occupied ?? summary.rooms_occupied ?? 0;
            const reservedN = mix.reserved ?? summary.rooms_reserved ?? 0;
            const availableN = mix.available ?? summary.rooms_available;
            const notReadyN = (mix.dirty ?? summary.rooms_dirty ?? 0) + (mix.out_of_service ?? summary.rooms_maintenance ?? 0);
            const segs = [
              { key: 'occupied', color: 'var(--brand-dark)', n: occupiedN },
              { key: 'reserved', color: 'var(--brand)', n: reservedN },
              { key: 'available', color: 'var(--deep-green)', n: availableN },
              { key: 'not ready', color: 'var(--warn)', n: notReadyN },
            ];
            const trend = summary.occupancy_trend || [];
            const occPrev = trend.length >= 2 ? trend[trend.length - 2].occupancy_rate : null;
            const occPct = Number(summary.occupancy_rate || 0);
            const soldN = summary.rooms_sold_night ?? 0;
            const reqOpen = guestRequests.filter((q) => q.status !== 'completed').length;
            const sourceCounts = reservations.reduce<Record<string, number>>((acc, r) => {
              const k = bookingSourceWord(r.booking_source);
              acc[k] = (acc[k] || 0) + 1;
              return acc;
            }, {});
            const sourceMax = Math.max(1, ...Object.values(sourceCounts), 0);
            const occAvg =
              trend.length > 0 ? trend.reduce((sum, p) => sum + p.occupancy_rate, 0) / trend.length : occPct;
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
            const mayOpen = (href: string) => navItemVisibleForRole(myRole, href, true);
            const seeMoney = canManage || myRole === 'hotel_cashier' || myRole === 'hotel_front_desk';
            const todayTiles: [string, string, number, () => void][] = [
              ['arrivals', 'Arriving today', deskArrivals, () => openDesk('arrivals')],
              ['departures', 'Leaving today', deskLeaving, () => openDesk('departures')],
              ['in_house', 'In house', deskInHouse, () => openDesk('in_house')],
              ['free', 'Free tonight', availableN, () => router.push('/hotel?tab=reservations#book-stay')],
            ];
            const attention: { key: string; text: string; href: string }[] = [];
            if ((summary.online_stay_requests || 0) > 0) {
              attention.push({
                key: 'online',
                text: (summary.online_stay_requests || 0) === 1
                  ? '1 stay request is waiting.'
                  : `${summary.online_stay_requests} stay requests are waiting.`,
                href: '/hotel?tab=reservations',
              });
            }
            if (reqOpen > 0) {
              attention.push({
                key: 'requests',
                text: reqOpen === 1 ? '1 guest request is open' : `${reqOpen} guest requests are open`,
                href: '/hotel?tab=front-desk#guest-requests',
              });
            }
            for (const alert of summary.alerts || []) {
              if (alert.code === 'arrivals' || !alert.href) continue;
              attention.push({
                key: alert.code,
                text: alert.code === 'unpaid_balances' ? `Guests owe ${money(summary.outstanding_folio_balance)}` : alert.message,
                href: alert.href,
              });
            }
            const attentionShown = attention.filter((x) => mayOpen(x.href));
            const quickActions: [string, string][] = [
              ['Book a stay', '/hotel?tab=reservations#book-stay'],
              ['Front desk', '/hotel?tab=front-desk'],
              ['Guest bills', '/hotel?tab=billing'],
              ['Housekeeping', '/hotel?tab=housekeeping'],
              ['Report a fault', '/hotel?tab=maintenance'],
              ['Cash and night audit', '/hotel?tab=cashier'],
            ];
            return (
              <>
                <section className="hdash-top" aria-label="Today at the hotel">
                  <div className="hdash-occ">
                    <div className="hdash-ring" role="img" aria-label={`Occupancy tonight ${occPct.toFixed(1)} percent`}>
                      <svg viewBox="0 0 120 120" aria-hidden="true">
                        <circle cx="60" cy="60" r="50" />
                        <circle cx="60" cy="60" r="50" className="on" pathLength={100} strokeDasharray={`${Math.min(100, occPct)} 100`} />
                      </svg>
                      <b>{occPct.toFixed(0)}%</b>
                    </div>
                    <div className="hdash-occ-text">
                      <span>Occupancy tonight</span>
                      <strong>{soldN} of {summary.rooms_total} {Number(summary.rooms_total) === 1 ? 'room' : 'rooms'} sold</strong>
                      <HotelDelta value={pctChange(occPct, occPrev)} />
                      <div className="hdash-spark" aria-hidden="true">
                        {trend.map((p) => (
                          <i key={p.date} title={`${stayWhen(p.date, formatPrefs)}: ${Number(p.occupancy_rate).toFixed(0)}%`} style={{ height: `${Math.max(6, Number(p.occupancy_rate))}%` }} />
                        ))}
                      </div>
                      <small>Last 14 nights</small>
                    </div>
                  </div>
                  <div className="hdash-tiles">
                    {todayTiles.map(([key, label, count, go]) => (
                      <button key={key} type="button" className="hdash-tile" onClick={go}>
                        <span className="hdash-icon"><HotelDashIcon name={key} /></span>
                        <b>{tabReady ? count : '–'}</b>
                        <span className="hdash-label">{label}</span>
                      </button>
                    ))}
                  </div>
                </section>

                <div className="hdash-row">
                  <div className="panel">
                    <div className="hdash-head">
                      <h3>Needs attention</h3>
                      {attentionShown.length ? <span className="hdash-count">{attentionShown.length}</span> : null}
                    </div>
                    {attentionShown.length ? (
                      <ul className="hattn">
                        {attentionShown.map((x) => (
                          <li key={x.key}>
                            <Link href={x.href}>
                              <i className={['overdue_hk', 'maintenance', 'out_of_stock', 'unpaid_balances'].includes(x.key) ? 'is-warn' : ''} aria-hidden="true" />
                              <em>{x.text}</em>
                              <span aria-hidden="true">›</span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="hint">{emptyOr('Nothing needs you right now.')}</p>
                    )}
                  </div>
                  <div className="panel">
                    <div className="hdash-head"><h3>Quick actions</h3></div>
                    <div className="hdash-quick">
                      {quickActions.filter(([, href]) => mayOpen(href)).map(([label, href]) => (
                        <Link key={href} href={href}>
                          <span className="hdash-icon"><HotelDashIcon name={href} /></span>
                          {label}
                        </Link>
                      ))}
                    </div>
                  </div>
                </div>

                {seeMoney && (
                  <div className="hdash-money">
                    <div>
                      <span>Charged today</span>
                      <b>{money(summary.revenue_today)}</b>
                      <small>Rooms {money(summary.room_revenue)} · extras {money(summary.service_revenue)}</small>
                    </div>
                    <div>
                      <span>Paid today</span>
                      <b>{money(summary.payments_received)}</b>
                      <small>All payment types</small>
                    </div>
                    <div>
                      <span>Guests still owe</span>
                      <b>{money(summary.outstanding_folio_balance)}</b>
                      <small>
                        {(summary.open_folio_count ?? 0) === 1
                          ? '1 guest bill still open'
                          : `${summary.open_folio_count ?? 0} guest bills still open`}
                      </small>
                    </div>
                  </div>
                )}

                <div className="panel">
                  <div className="hsection-head">
                    <div>
                      <h3>Rooms right now</h3>
                      <p className="hint">Tap a guest to open the bill or check them in. Tap an empty room to book it.</p>
                    </div>
                    <Link href="/hotel?tab=reservations#calendar">Open booking calendar</Link>
                  </div>
                  <HotelRoomBoard rooms={liveRooms} stays={boardStays} today={dashDate} money={money} onStay={boardStay} onEmptyRoom={openEmptyRoom} />
                </div>

                <details className="hmore hday-more">
                  <summary>More numbers: occupancy trend, booking sources, recent bookings</summary>
                  <div className="hotel-ops-split">
                    <div className="panel hotel-occ-hero">
                      <h3>Hotel occupancy rate</h3>
                      <p className="hint">Share of rooms sold each night.</p>
                      <div className="hotel-occ-hero-pct">
                        {occPct.toFixed(1)}%
                        <HotelDelta value={pctChange(occPct, occPrev)} />
                      </div>
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
                      <h3>Rooms tonight</h3>
                      <p className="hint">How the rooms stand on this date.</p>
                      <div className="hotel-avail-bar" role="img" aria-label="Room availability mix">
                        {segs.map((seg) => (
                          <span
                            key={seg.key}
                            className="hotel-occ-seg"
                            style={{ width: `${Math.max(0, (seg.n / tot) * 100)}%`, background: seg.color }}
                            title={`${seg.key} ${seg.n}`}
                          />
                        ))}
                      </div>
                      <div className="hotel-avail-quad">
                        {segs.map((seg) => (
                          <div key={seg.key} className={`q is-${seg.key.replace(' ', '-')}`}>
                            <div className="k">
                              <span className="mark" style={{ background: seg.color }} />
                              {seg.key}
                            </div>
                            <div className="n">{seg.n}</div>
                          </div>
                        ))}
                      </div>
                      <h3 style={{ marginTop: 16 }}>How guests booked</h3>
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
                              <span>{stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}</span>
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
                    </div>
                  </div>
                </details>
              </>
            );
          })()}
        </div>
      )}

      {show('front-desk') && (
        <>
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hdesk-tiles" role="group" aria-label="Front desk list filter">
            {deskTiles.map(([key, label, count]) => (
              <button key={key || 'all'} type="button" className="hdesk-tile" aria-pressed={deskKind === key} onClick={() => setDeskKind(key)}>
                <b>{count === null ? ' ' : tabReady ? count : '–'}</b>
                <span>{label}</span>
              </button>
            ))}
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
                  <td className="hdesk-actions">
                    {r.can_check_in && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => checkInStay(r)}>Check in</button>
                    )}
                    {r.can_check_out && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => checkOutStay(r.id, r.guest_name || r.reservation_number)}>Check out</button>
                    )}
                    {r.folio_id ? (
                      <button type="button" disabled={busy} onClick={() => void showStayBill(r.id)} aria-label={`Open bill for ${r.guest_name || r.reservation_number}`}>Bill</button>
                    ) : null}
                    {r.can_move && (
                      <button type="button" disabled={busy} onClick={() => openDialog({ kind: 'move', stay: r })} aria-label={`Change room for ${r.guest_name || r.reservation_number}`}>Change room</button>
                    )}
                  </td>
                </tr>
              ))}
              {!reservations.length && (
                <tr><td colSpan={6} className="muted">{emptyOr('No stays in this list.')}</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Rooms right now</h2>
          <p className="muted">Tap a guest to open the bill or check them in. Tap an empty room to book it.</p>
          <HotelRoomBoard rooms={liveRooms} stays={boardStays} today={dashDate} money={money} onStay={boardStay} onEmptyRoom={openEmptyRoom} />
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
        <div className="hsection-head">
          <div>
            <h2 id="guest-requests">Guest requests</h2>
            <p className="muted">Wake-up calls, extra towels, complaints. Write them here so the next shift sees them.</p>
          </div>
          <button type="button" className={reqOpen ? undefined : 'btn-ok'} onClick={() => setReqOpen((v) => !v)} aria-expanded={reqOpen}>{reqOpen ? 'Close' : 'New request'}</button>
        </div>
        {reqOpen && (
        <form
          className="hdesk-form"
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
              setReqOpen(false);
              setMessage('Request recorded');
              await refresh();
            } catch (err: unknown) {
              setError(hotelErr(err, 'Could not save request'));
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label><span>What is needed</span><input value={reqForm.title} onChange={(e) => setReqForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Guest request title" /></label>
          <label>
            <span>Kind</span>
            <select value={reqForm.kind} onChange={(e) => setReqForm((f) => ({ ...f, kind: e.target.value }))} aria-label="Guest request kind">
              {[['service', 'Service'], ['wake_up', 'Wake-up'], ['note', 'Note'], ['complaint', 'Complaint']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
          <label>
            <span>Room (optional)</span>
            <select value={reqForm.room_id} onChange={(e) => setReqForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Guest request room">
              <option value="">Not for one room</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.code}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Stay (optional)</span>
            <select value={reqForm.reservation_id} onChange={(e) => setReqForm((f) => ({ ...f, reservation_id: e.target.value }))} aria-label="Guest request reservation">
              <option value="">None</option>
              {boardStays.filter((r) => ['booked', 'checked_in', 'tentative'].includes(r.status)).map((r) => (
                <option key={r.id} value={r.id}>{r.guest_name || r.reservation_number} · {r.room_code}</option>
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
          <div style={{ alignSelf: 'end' }}><button type="submit" className="btn-ok" disabled={busy}>Record request</button></div>
        </form>
        )}
        <div className="list-table-wrap">
          <table className="table">
            <thead><tr><th>Request</th><th>Room</th><th>Due</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {guestRequests.map((q) => (
                <tr key={q.id}>
                  <td>
                    {q.title}
                    <div className="muted">{hotelWord(q.kind)}{q.notes ? ` · ${q.notes}` : ''}</div>
                  </td>
                  <td>{q.room_id ? rooms.find((r) => r.id === q.room_id)?.code : '—'}</td>
                  <td>{q.due_at ? stayClock(q.due_at, formatPrefs) : '—'}</td>
                  <td><span className={statusClass(String(q.status || ''))}>{hotelWord(q.status)}</span></td>
                  <td>
                    {q.status !== 'completed' && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/guest-requests/${q.id}/complete`, 'Request done')}>Done</button>
                    )}
                  </td>
                </tr>
              ))}
              {!guestRequests.length && <tr><td colSpan={5} className="muted">{emptyOr('No guest requests.')}</td></tr>}
            </tbody>
          </table>
        </div>
        </div>
        </>
      )}

      {show('rooms') && (
      <>
      <HotelViews
        label="Rooms and rate plans"
        value={roomView}
        onPick={(k) => goView(k === 'rooms' ? '' : k)}
        items={[['rooms', 'Rooms', liveRooms.length], ['rate-plans', 'Rate plans', ratePlans.filter((p) => p.is_active !== false).length]]}
      />
      {roomView === 'rooms' && (
      <>
      <div className="card" style={{ marginBottom: 16 }}>
        {addShown('rooms') && (
        <div className="hdesk-form">
        <form
          onSubmit={createRoom}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
        >
          <label>
            <span>Room number</span>
            <input value={roomForm.code} onChange={(e) => setRoomForm((f) => ({ ...f, code: e.target.value }))} aria-label="Hotel room code" required placeholder="101" />
          </label>
          <label>
            <span>Name</span>
            <input value={roomForm.name} onChange={(e) => setRoomForm((f) => ({ ...f, name: e.target.value }))} aria-label="Hotel room name" required placeholder="Garden standard" />
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
            <span>Floor</span>
            <input value={roomForm.floor} onChange={(e) => setRoomForm((f) => ({ ...f, floor: e.target.value }))} aria-label="Hotel room floor" />
          </label>
          <label>
            <span>Most guests</span>
            <input type="number" min={1} max={20} value={roomForm.max_occupancy} onChange={(e) => setRoomForm((f) => ({ ...f, max_occupancy: e.target.value }))} aria-label="Hotel room max guests" />
          </label>
          <label>
            <span>Nightly rate</span>
            <AmountField type="number" min={0} step="0.01" value={roomForm.rate_amount} onChange={(e) => setRoomForm((f) => ({ ...f, rate_amount: e.target.value }))} aria-label="Hotel room rate" />
          </label>
          <label>
            <span>Weekend rate (optional)</span>
            <AmountField type="number" min={0} step="0.01" value={roomForm.weekend_rate} onChange={(e) => setRoomForm((f) => ({ ...f, weekend_rate: e.target.value }))} aria-label="Hotel weekend rate" />
          </label>
          <details className="hmore" style={{ gridColumn: '1 / -1' }}>
            <summary>More details</summary>
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <label>
                <span>Bed</span>
                <input value={roomForm.bed_type} onChange={(e) => setRoomForm((f) => ({ ...f, bed_type: e.target.value }))} aria-label="Hotel bed type" />
              </label>
              <label>
                <span>Charge per extra guest</span>
                <AmountField type="number" min={0} step="0.01" value={roomForm.extra_person_charge} onChange={(e) => setRoomForm((f) => ({ ...f, extra_person_charge: e.target.value }))} aria-label="Hotel extra guest charge" />
              </label>
              <label>
                <span>Status</span>
                <select value={roomForm.status} onChange={(e) => setRoomForm((f) => ({ ...f, status: e.target.value }))} aria-label="Hotel room status">
                  {ROOM_STATUSES.map((st) => (
                    <option key={st} value={st}>{hotelWord(st)}</option>
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
            </div>
          </details>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" className="btn-ok" disabled={busy} aria-label="Create hotel room">{busy ? 'Saving…' : 'Create room'}</button>
          </div>
        </form>
        </div>
        )}
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Room</th>
              <th>Name</th>
              <th>Status</th>
              <th>Cleaning</th>
              <th>Rate</th>
              {canManage ? <th></th> : null}
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id} className={r.is_active ? undefined : 'hrow-off'}>
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
                  {r.is_active ? <span className={statusClass(r.status)}>{hotelWord(r.status)}</span> : <span className="muted">Not for sale</span>}
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
                {canManage ? (
                  <td><button type="button" disabled={busy} onClick={() => openDialog({ kind: 'room', room: r })} aria-label={`Edit room ${r.code}`}>Edit</button></td>
                ) : null}
              </tr>
            ))}
            {!rooms.length && (
              <tr><td colSpan={6} className="muted">{emptyOr('No rooms yet.')}</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Rooms right now</h2>
        <HotelRoomBoard rooms={liveRooms} stays={boardStays} today={dashDate} money={money} onStay={boardStay} onEmptyRoom={openEmptyRoom} />
      </div>
      </>
      )}
      {roomView === 'rate-plans' && (
      <div className="card" id="rate-plans" style={{ marginBottom: 16 }}>
        {addShown('plans') && (
        <form
          className="hdesk-form"
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
              setAddOpen(false);
              setMessage('Rate plan saved');
              await refresh();
            } catch (err: unknown) {
              setError(hotelErr(err, 'Could not save rate plan'));
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
        >
          <label><span>Code</span><input value={rateForm.code} onChange={(e) => setRateForm((f) => ({ ...f, code: e.target.value }))} required aria-label="Rate plan code" placeholder="CORP" /></label>
          <label><span>Name</span><input value={rateForm.name} onChange={(e) => setRateForm((f) => ({ ...f, name: e.target.value }))} required aria-label="Rate plan name" placeholder="Corporate rate" /></label>
          <label><span>Price per night</span><AmountField type="number" min={0} step="0.01" value={rateForm.amount} onChange={(e) => setRateForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Rate plan amount" /></label>
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
            <span>Starts (optional)</span>
            <HotelDateInput value={rateForm.starts_on} onChange={(starts_on) => setRateForm((f) => ({ ...f, starts_on }))} ariaLabel="Rate plan start" prefs={formatPrefs} />
          </label>
          <label>
            <span>Ends (optional)</span>
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
          <div style={{ alignSelf: 'end' }}><button type="submit" className="btn-ok" disabled={busy}>Add plan</button></div>
        </form>
        )}
        <div className="list-table-wrap">
          <table className="table">
            <thead><tr><th>Code</th><th>Plan</th><th>Price per night</th><th>Rules</th><th>Status</th>{canManage ? <th></th> : null}</tr></thead>
            <tbody>
              {ratePlans.map((p) => (
                <tr key={p.id} className={p.is_active === false ? 'hrow-off' : undefined}>
                  <td><code>{p.code}</code></td>
                  <td>{p.name}</td>
                  <td>{money(p.amount)}</td>
                  <td>
                    {[
                      p.min_nights > 1 ? `${p.min_nights} nights or more` : '',
                      p.room_type ? hotelWord(p.room_type) : '',
                      p.weekday_only ? 'Weekdays' : '',
                      p.weekend_only ? 'Weekends' : '',
                      p.starts_on || p.ends_on ? `${stayWhen(p.starts_on, formatPrefs)} – ${stayWhen(p.ends_on, formatPrefs)}` : '',
                    ].filter(Boolean).join(' · ') || 'Any stay'}
                  </td>
                  <td>{p.is_active === false ? 'Off' : 'On'}</td>
                  {canManage ? (
                    <td className="hdesk-actions">
                      <button type="button" disabled={busy} onClick={() => openDialog({ kind: 'plan', plan: p })} aria-label={`Edit rate plan ${p.code}`}>Edit</button>
                    </td>
                  ) : null}
                </tr>
              ))}
              {!ratePlans.length && <tr><td colSpan={6} className="muted">{emptyOr('No rate plans yet. Rooms still use their base rate.')}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      )}
      </>
      )}

      {show('guests') && (
      <div className="card" style={{ marginBottom: 16 }}>
        {addShown('guests') && (
          <div className="hdesk-form">
          <form onSubmit={createGuest} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
          <label>
            <span>Full name</span>
            <input autoComplete="off" value={guestForm.full_name} onChange={(e) => setGuestForm((f) => ({ ...f, full_name: e.target.value }))} aria-label="Hotel guest full name" required />
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
            <span>ID type</span>
            <input value={guestForm.id_type} onChange={(e) => setGuestForm((f) => ({ ...f, id_type: e.target.value }))} aria-label="Hotel guest id type" placeholder="Ghana Card" />
          </label>
          <label>
            <span>ID number</span>
            <input value={guestForm.id_document} onChange={(e) => setGuestForm((f) => ({ ...f, id_document: e.target.value }))} aria-label="Hotel guest id document" />
          </label>
          <details className="hmore" style={{ gridColumn: '1 / -1' }}>
            <summary>More details</summary>
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
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
            </div>
          </details>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" disabled={busy} aria-label="Create hotel guest">{busy ? 'Saving…' : 'Create guest'}</button>
          </div>
        </form>
          </div>
          )}
        <input
          className="hsearch"
          type="search"
          value={guestQuery}
          onChange={(e) => setGuestQuery(e.target.value)}
          placeholder="Search name, phone or email"
          aria-label="Search guests"
        />
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
            {shownGuests.map((g) => (
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
                    .slice(0, 2)
                    .map((r) => (
                      <div className="muted" key={r.id}>
                        {r.reservation_number} · {hotelWord(r.status)} · {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                        {leftEarlyWhen(r) ? <span> · Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</span> : null}
                      </div>
                    ))}
                </td>
                <td>{g.email || '—'}</td>
                <td>{g.phone || '—'}</td>
                <td className="hdesk-actions">
                  <button
                    type="button"
                    disabled={busy}
                    aria-label={`Details for ${g.full_name}`}
                    onClick={async () => {
                      setBusy(true);
                      setError('');
                      try {
                        const h = await api(`/hotel/guests/${g.id}/history`);
                        setGuestHistory(h.data || null);
                        setMergeSource('');
                        openDialog({ kind: 'history' });
                      } catch (err: unknown) {
                        setError(hotelErr(err, 'Could not load this guest'));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Details
                  </button>
                  <button type="button" disabled={busy} onClick={() => openDialog({ kind: 'guest', guest: g })} aria-label={`Edit ${g.full_name}`}>Edit</button>
                </td>
              </tr>
            ))}
            {!shownGuests.length && (
              <tr><td colSpan={4} className="muted">{listsReady ? (guests.length ? 'No guest matches that search.' : 'No guests yet.') : 'Loading guests…'}</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
      )}

      {show('reservations') && (
      <>
      <HotelViews
        label="Reservation views"
        value={resView}
        onPick={(k) => goView(k === 'list' ? '' : k)}
        items={[['list', 'Stays'], ['calendar', 'Calendar'], ['book-stay', 'Book a stay'], ['group-stay', 'Group stay'], ['online-booking', 'Online booking']]}
      />
      {resView === 'calendar' && (
      <div className="card" style={{ marginBottom: 16 }}>
        <HotelRoomNightGrid
          rooms={rooms}
          reservations={boardStays}
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
      )}
      {resView === 'book-stay' && (
      <form className="card hstay" id="book-stay" onSubmit={createReservation} style={{ marginBottom: 16 }}>
        <section className="hstay-step">
          <h2><i>1</i>When and how many</h2>
          <div className="hstay-grid">
            <label>
              <span>Check-in</span>
              <HotelDateInput
                value={resForm.check_in_date}
                onChange={(checkIn) => setStayDates(checkIn, resForm.check_out_date)}
                ariaLabel="Hotel check-in date"
                required
                prefs={formatPrefs}
              />
            </label>
            <label>
              <span>Check-out</span>
              <HotelDateInput
                value={resForm.check_out_date}
                onChange={(checkOut) => setStayDates(resForm.check_in_date, checkOut)}
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
              <span>Room type</span>
              <select value={availForm.room_type} onChange={(e) => setAvailForm((f) => ({ ...f, room_type: e.target.value }))} aria-label="Availability room type">
                <option value="">Any</option>
                {ROOM_TYPES.map((t) => (
                  <option key={t} value={t}>{hotelWord(t)}</option>
                ))}
              </select>
            </label>
          </div>
        </section>
        <section className="hstay-step">
          <h2><i>2</i>Choose a room</h2>
          {!availReady && <p className="muted">Checking free rooms…</p>}
          {availReady && !availRooms.length && <p className="hint">No room is free on these dates. Try other dates, or add the guest to the waiting list under More options.</p>}
          <div className="hroom-picks" role="group" aria-label="Free rooms">
            {availRooms.map((r) => {
              const later = nextStayAfter(reservations, r.id, shiftIso(availForm.check_out_date, -1));
              return (
                <button
                  key={r.id}
                  type="button"
                  className="hroom-pick"
                  aria-pressed={resForm.room_id === r.id}
                  aria-label={`Room ${r.code}, ${money(r.rate_amount)} a night`}
                  onClick={() => setResForm((f) => ({ ...f, room_id: f.room_id === r.id ? '' : r.id }))}
                >
                  <strong>{r.code}</strong>
                  <span>{roomPlainName(r.code, r.name)}</span>
                  <b>{money(r.rate_amount)}</b>
                  <span className="muted">Up to {r.max_occupancy} guests</span>
                  {later ? <span className="muted">Next stay {stayWhen(later, formatPrefs)}</span> : null}
                </button>
              );
            })}
          </div>
          {(() => {
            const clash = heldStay(boardStays, resForm.room_id, resForm.check_in_date, resForm.check_out_date);
            const code = pickedRoom?.code || 'This room';
            if (clash) {
              return (
                <p className="hint">
                  {code} is already held {stayWhen(clash.check_in_date, formatPrefs)} – {stayWhen(clash.check_out_date, formatPrefs)}
                  {clash.guest_name ? ` by ${clash.guest_name}` : ''}. Choose another room or other dates.
                </p>
              );
            }
            if (availReady && pickedRoom && !availRooms.some((r) => r.id === pickedRoom.id) && !availForm.room_type) {
              return <p className="hint">{code} cannot be sold on these dates. It may need cleaning or be closed. Choose another room.</p>;
            }
            return null;
          })()}
        </section>
        <section className="hstay-step">
          <h2><i>3</i>Who is staying</h2>
          {stayGuestPicker}
        </section>
        <details className="hmore">
          <summary>More options: discount, deposit, rate plan, requests</summary>
          <div className="hstay-grid">
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
              <span>Discount %</span>
              <input type="number" min={0} max={100} step="0.01" value={resForm.discount_percent} onChange={(e) => setResForm((f) => ({ ...f, discount_percent: e.target.value }))} aria-label="Hotel stay discount percent" />
            </label>
            <label>
              <span>How they booked</span>
              <select value={resForm.booking_source} onChange={(e) => setResForm((f) => ({ ...f, booking_source: e.target.value }))} aria-label="Hotel booking source">
                {BOOKING_SOURCES.map((src) => (
                  <option key={src.value} value={src.value}>{src.label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Deposit paid</span>
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
            <label>
              <span>Special requests</span>
              <input value={resForm.special_requests} onChange={(e) => setResForm((f) => ({ ...f, special_requests: e.target.value }))} aria-label="Hotel special requests" />
            </label>
            <label>
              <span>Desk note</span>
              <input value={resForm.notes} onChange={(e) => setResForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel reservation notes" />
            </label>
            <label className="hcheck">
              <input
                type="checkbox"
                checked={resForm.waitlist}
                disabled={resForm.walk_in}
                onChange={(e) => setResForm((f) => ({ ...f, waitlist: e.target.checked }))}
                aria-label="Add to waiting list"
              />
              <span>Waiting list (does not hold the room)</span>
            </label>
            {resForm.waitlist && (
              <label>
                <span>Room wanted</span>
                <select value={resForm.room_id} onChange={(e) => setResForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Hotel reservation room">
                  <option value="">Select room</option>
                  {liveRooms.map((r) => (
                    <option key={r.id} value={r.id}>{r.code} — {r.name}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </details>
        <div className="hstay-total">
          <div>
            {quote && pickedRoom ? (
              <>
                <b>{money(quote.total)}</b>
                <span>
                  Room {pickedRoom.code} · {quote.nights === 1 ? '1 night' : `${quote.nights} nights`} × {money(quote.nightly_rate)}
                  {quote.rate_plan ? ` · ${quote.rate_plan}` : ''}
                </span>
                {taxPercent > 0 ? (
                  <span>{settingsForm.room_rates_include_tax ? `Includes ${taxPercent}% tax` : `Plus ${taxPercent}% tax`}</span>
                ) : null}
              </>
            ) : (
              <span>{stayNights > 0 ? `${stayNights === 1 ? '1 night' : `${stayNights} nights`}. Choose a room to see the price.` : 'Check-out must be after check-in.'}</span>
            )}
            {quote?.over_capacity ? <span className="hstay-warn">Too many people. This room takes up to {quote.max_occupancy}.</span> : null}
            {quoteNote ? <span className="hstay-warn">{quoteNote}</span> : null}
          </div>
          <div className="hstay-go">
            {resForm.check_in_date === localIso() && (
              <label className="hcheck">
                <input type="checkbox" checked={resForm.walk_in} onChange={(e) => setResForm((f) => ({ ...f, walk_in: e.target.checked, waitlist: e.target.checked ? false : f.waitlist }))} aria-label="Walk-in reservation" />
                <span>Walk-in (check in now)</span>
              </label>
            )}
            <button type="submit" className="btn-primary" disabled={busy || (!resForm.waitlist && Boolean(heldStay(boardStays, resForm.room_id, resForm.check_in_date, resForm.check_out_date)))} aria-label="Create hotel reservation">{busy ? 'Saving…' : resForm.waitlist ? 'Add to waiting list' : resForm.walk_in ? 'Book and check in' : 'Book stay'}</button>
          </div>
        </div>
      </form>
      )}
      {resView === 'online-booking' && (
      <div className="card" id="online-booking" style={{ marginBottom: 16 }}>
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
                  setMessage('Booking link saved');
                } catch (err: unknown) {
                  setError(hotelErr(err, 'Could not save the booking link'));
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
                <button type="submit" className="btn-ok" aria-label="Save hotel booking link">Save booking link</button>
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
                <div className="hdesk-actions" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    aria-label="Copy the booking link"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(`${stayOrigin}${stayLink.path}`);
                        setMessage('Link copied');
                      } catch {
                        setError('Could not copy. Select the link and copy it by hand.');
                      }
                    }}
                  >
                    Copy link
                  </button>
                  <a href={stayLink.path} target="_blank" rel="noreferrer">Open the guest page</a>
                </div>
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
      </div>
      )}
      {resView === 'group-stay' && (
      <div className="card hstay" id="group-stay" style={{ marginBottom: 16 }}>
        <section className="hstay-step">
          <h2><i>1</i>Dates</h2>
          <div className="hstay-grid">
            <label>
              <span>Check-in</span>
              <HotelDateInput value={resForm.check_in_date} onChange={(checkIn) => setStayDates(checkIn, resForm.check_out_date)} ariaLabel="Group check-in date" required prefs={formatPrefs} />
            </label>
            <label>
              <span>Check-out</span>
              <HotelDateInput value={resForm.check_out_date} onChange={(checkOut) => setStayDates(resForm.check_in_date, checkOut)} ariaLabel="Group check-out date" required prefs={formatPrefs} />
            </label>
            <label>
              <span>Adults in each room</span>
              <input type="number" min={1} max={20} value={resForm.adults} onChange={(e) => setResForm((f) => ({ ...f, adults: e.target.value }))} aria-label="Group adults" />
            </label>
            <label>
              <span>Discount %</span>
              <input type="number" min={0} max={100} step="0.01" value={resForm.discount_percent} onChange={(e) => setResForm((f) => ({ ...f, discount_percent: e.target.value }))} aria-label="Group discount percent" />
            </label>
          </div>
        </section>
        <section className="hstay-step">
          <h2><i>2</i>Tick two or more rooms</h2>
          {!availReady && <p className="muted">Checking free rooms…</p>}
          {availReady && !availRooms.length && <p className="hint">No room is free on these dates.</p>}
          <div className="hroom-picks" role="group" aria-label="Free rooms for the group">
            {availRooms.map((r) => (
              <button
                key={r.id}
                type="button"
                className="hroom-pick"
                aria-pressed={groupRooms.includes(r.id)}
                aria-label={`Group room ${r.code}`}
                onClick={() => setGroupRooms((ids) => (ids.includes(r.id) ? ids.filter((id) => id !== r.id) : [...ids, r.id]))}
              >
                <strong>{r.code}</strong>
                <span>{roomPlainName(r.code, r.name)}</span>
                <b>{money(r.rate_amount)}</b>
              </button>
            ))}
          </div>
          {groupRooms.map((id) => {
            const stay = heldStay(boardStays, id, resForm.check_in_date, resForm.check_out_date);
            const code = rooms.find((r) => r.id === id)?.code || 'Room';
            if (stay) {
              return (
                <p className="hint" key={id}>
                  {code} is already held {stayWhen(stay.check_in_date, formatPrefs)} – {stayWhen(stay.check_out_date, formatPrefs)}
                  {stay.guest_name ? ` by ${stay.guest_name}` : ''}.
                </p>
              );
            }
            return null;
          })}
        </section>
        <section className="hstay-step">
          <h2><i>3</i>Who is booking</h2>
          {stayGuestPicker}
          <div className="hstay-grid" style={{ marginTop: 10 }}>
            <label>
              <span>Group name</span>
              <input value={groupName} onChange={(e) => setGroupName(e.target.value)} aria-label="Hotel group name" placeholder="Mensah wedding" />
            </label>
            <label>
              <span>Group note</span>
              <input value={groupNotes} onChange={(e) => setGroupNotes(e.target.value)} aria-label="Hotel group notes" />
            </label>
          </div>
        </section>
        <div className="hstay-total">
          <div><span>{groupRooms.length === 1 ? '1 room ticked' : `${groupRooms.length} rooms ticked`}. Each room gets its own stay and bill.</span></div>
          <div className="hstay-go">
        <button
          type="button"
          className="btn-primary"
          disabled={busy || groupRooms.length < 2 || (!resForm.guest_id && !resForm.new_guest_name.trim()) || !resForm.check_in_date || !resForm.check_out_date || groupRooms.some((id) => heldStay(boardStays, id, resForm.check_in_date, resForm.check_out_date))}
          onClick={async () => {
            const discountPercent = Number(resForm.discount_percent) || 0;
            if (discountPercent > 100) {
              setError('Stay discount percent cannot be above 100.');
              return;
            }
            if (discountPercent > 0 && !staffId) {
              setError('Sign in again before applying a stay discount.');
              return;
            }
            setBusy(true);
            setError('');
            try {
              const guestId = await stayGuestId();
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
              const count = groupRooms.length;
              setGroupRooms([]);
              setGroupName('');
              setGroupNotes('');
              resetStayForm();
              goView('');
              setMessage(`Group booked: ${count} rooms.`);
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
        </div>
      </div>
      )}

      {resView === 'list' && (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="hsearch-row">
          <input
            className="hsearch"
            type="search"
            value={resQuery}
            onChange={(e) => setResQuery(e.target.value)}
            placeholder="Search guest, phone, room or number"
            aria-label="Search stays"
          />
          <select value={listKind} onChange={(e) => setListKind(e.target.value)} aria-label="Hotel reservation list filter">
            <option value="">All stays</option>
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
        {(summary?.online_stay_requests || 0) > 0 && (
          <p className="hint">
            {(summary?.online_stay_requests || 0) === 1
              ? '1 stay request is waiting.'
              : `${summary?.online_stay_requests} stay requests are waiting.`}
          </p>
        )}
        <div className="list-table-wrap hdesk-res-wrap">
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
            {shownStays.map((r) => (
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
                  <RowActions
                    label={`More actions for ${r.reservation_number}`}
                    primaryMax={1}
                    items={[
                      r.can_confirm && {
                        key: 'confirm',
                        label: r.status === 'waitlisted' ? 'Take off waiting list' : 'Confirm booking',
                        variant: 'ok',
                        disabled: busy,
                        ariaLabel: `Confirm ${r.reservation_number}`,
                        onClick: () => void act(`/hotel/reservations/${r.id}/confirm`, r.status === 'waitlisted' ? 'Moved off the waiting list' : 'Booking confirmed'),
                      },
                      r.can_check_in && r.check_in_date <= localIso() && {
                        key: 'in',
                        label: 'Check in',
                        variant: 'ok',
                        disabled: busy,
                        ariaLabel: `Check in ${r.reservation_number}`,
                        onClick: () => checkInStay(r),
                      },
                      r.can_check_out && {
                        key: 'out',
                        label: 'Check out',
                        variant: 'ok',
                        disabled: busy,
                        ariaLabel: `Check out ${r.reservation_number}`,
                        onClick: () => void checkOutStay(r.id, r.guest_name || r.reservation_number),
                      },
                      (r.can_check_out || r.status === 'checked_in' || r.status === 'checked_out') && {
                        key: 'bill',
                        label: 'Open bill',
                        disabled: busy,
                        ariaLabel: `Open bill ${r.reservation_number}`,
                        onClick: () => void showStayBill(r.id),
                      },
                      r.status === 'checked_in' && r.check_out_date > localIso() && {
                        key: 'early',
                        label: 'Leaving early',
                        disabled: busy,
                        ariaLabel: `Leaving early ${r.reservation_number}`,
                        onClick: () => {
                          if (!window.confirm(`Take the unused nights off ${r.guest_name || r.reservation_number}'s bill and free the room?`)) return;
                          void act(`/hotel/reservations/${r.id}/leave-early`, 'Unused nights removed');
                        },
                      },
                      ['booked', 'tentative'].includes(r.status) && {
                        key: 'edit',
                        label: 'Edit stay',
                        disabled: busy,
                        ariaLabel: `Edit ${r.reservation_number}`,
                        onClick: () => openDialog({ kind: 'edit', stay: r }),
                      },
                      r.can_extend && {
                        key: 'extend',
                        label: 'Extend stay',
                        disabled: busy,
                        ariaLabel: `Extend ${r.reservation_number}`,
                        onClick: () => openDialog({ kind: 'extend', stay: r }),
                      },
                      r.can_move && {
                        key: 'move',
                        label: 'Change room',
                        disabled: busy,
                        ariaLabel: `Move ${r.reservation_number}`,
                        onClick: () => openDialog({ kind: 'move', stay: r }),
                      },
                      {
                        key: 'slip',
                        label: 'Print slip',
                        disabled: busy,
                        ariaLabel: `Print confirmation ${r.reservation_number}`,
                        onClick: () => void printStaySlip(r.id, r.reservation_number),
                      },
                      r.can_check_in && r.check_in_date > localIso() && {
                        key: 'in-early',
                        label: 'Check in early',
                        disabled: busy,
                        ariaLabel: `Check in ${r.reservation_number}`,
                        onClick: () => checkInStay(r),
                      },
                      r.can_duplicate && {
                        key: 'dup',
                        label: 'Duplicate',
                        disabled: busy,
                        ariaLabel: `Duplicate ${r.reservation_number}`,
                        onClick: () => openDialog({ kind: 'duplicate', stay: r }),
                      },
                      r.can_no_show && {
                        key: 'noshow',
                        label: 'No-show',
                        disabled: busy,
                        ariaLabel: `No-show ${r.reservation_number}`,
                        onClick: () => void act(`/hotel/reservations/${r.id}/no-show`, 'Marked no-show'),
                      },
                      r.status === 'no_show' && {
                        key: 'noshowfee',
                        label: 'Post no-show fee',
                        disabled: busy,
                        ariaLabel: `Post no-show fee ${r.reservation_number}`,
                        onClick: () => {
                          if (!window.confirm(`Post the no-show fee once for ${r.reservation_number}?`)) return;
                          void act(`/hotel/reservations/${r.id}/no-show-fee`, 'No-show fee posted');
                        },
                      },
                      r.can_cancel && {
                        key: 'cancel',
                        label: 'Cancel',
                        variant: 'danger',
                        disabled: busy,
                        ariaLabel: `Cancel ${r.reservation_number}`,
                        onClick: () => {
                          const late = r.inside_cancellation_window
                            ? ` This stay is inside the ${r.cancellation_hours}-hour cancellation window. Cancelling does not add a fee.`
                            : '';
                          if (!window.confirm(`Cancel reservation ${r.reservation_number}? This cannot be undone.${late}`)) return;
                          void act(`/hotel/reservations/${r.id}/cancel`, 'Cancelled');
                        },
                      },
                    ].filter(Boolean) as RowActionItem[]}
                  />
                </td>
              </tr>
            ))}
            {!shownStays.length && (
              <tr><td colSpan={7} className="muted">{emptyOr(reservations.length ? 'No stay matches that search.' : 'No reservations.')}</td></tr>
            )}
          </tbody>
        </table>
        </div>
        <p className="muted" style={{ marginTop: 10 }}>
          Cancel at least {Number(settingsForm.cancellation_hours) || 0} hours before {settingsForm.check_in_time || '14:00'} on the arrival date. A cancel inside that window releases the room and does not add a fee.
        </p>
      </div>
      )}
      </>
      )}

      {(show('billing') || show('reservations') || show('front-desk')) && folio && (
        <div className="card" id="guest-bill" style={{ marginBottom: 16 }}>
          <div className="hsection-head">
            <h2>Guest bill {folio.folio_number}</h2>
            <div className="hdesk-actions">
              {folio.status === 'open' && folio.reservation_status === 'checked_in' && folio.reservation_id ? (
                <button type="button" className="btn-ok" disabled={busy} onClick={() => void checkOutStay(String(folio.reservation_id), folio.guest_name || folio.folio_number)}>Check out</button>
              ) : null}
              <button type="button" disabled={busy} onClick={printFolioSlip} aria-label={`Print folio ${folio.folio_number}`}>Print bill</button>
              <button type="button" onClick={() => setFolio(null)} aria-label="Close this bill">Close</button>
            </div>
          </div>
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
          <div className="hbill-tiles">
            <div className="hbill-tile"><span>Charges</span><b>{money(folio.charges_total)}</b></div>
            <div className="hbill-tile"><span>Includes tax</span><b>{money(folio.charges.filter((c) => !c.is_void).reduce((sum, c) => sum + Number(c.tax_amount || 0), 0))}</b></div>
            <div className="hbill-tile"><span>Paid</span><b>{money(folio.payments_total)}</b></div>
            <div className={`hbill-tile ${Number(folio.balance) < -0.004 ? 'is-credit' : 'is-due'}`}>
              <span>{Number(folio.balance) < -0.004 ? 'Guest is in credit' : 'Still to pay'}</span>
              <b>{money(Math.abs(Number(folio.balance)))}</b>
            </div>
          </div>
          {Number(folio.balance) < -0.004 && folio.status === 'open' ? (
            <p className="hotel-banner warn" role="status">The guest has paid too much. Refund the difference from a payment below before checking out.</p>
          ) : null}
          {folio.status !== 'open' ? (
            <p className="hint">This bill is closed. {Number(folio.balance) > 0.004 ? <>Collect what is still owed under <Link href="/hotel/invoices">Guest invoices</Link>.</> : 'Nothing more can be added to it.'}</p>
          ) : null}
          {folio.status === 'open' && (
            <section className="hbill-box">
              <h3>Take a payment</h3>
              <form onSubmit={addPayment} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
                <label>
                  <span>Amount</span>
                  <AmountField type="number" min={0} step="0.01" value={payForm.amount} onChange={(e) => setPayForm((f) => ({ ...f, amount: e.target.value }))} aria-label="Folio payment amount" />
                </label>
                <label>
                  <span>Method</span>
                  <select value={payForm.method} onChange={(e) => setPayForm((f) => ({ ...f, method: e.target.value }))} aria-label="Folio payment method">
                    {['cash', 'momo', 'card', 'bank', 'credit', 'other'].map((m) => (
                      <option key={m} value={m}>{tenderWord(m)}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Reference (optional)</span>
                  <input value={payForm.reference} onChange={(e) => setPayForm((f) => ({ ...f, reference: e.target.value }))} aria-label="Folio payment reference" />
                </label>
                <label>
                  <span>Notes (optional)</span>
                  <input value={payForm.notes} onChange={(e) => setPayForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Folio payment notes" />
                </label>
                <div style={{ alignSelf: 'end' }}>
                  <button type="submit" className="btn-ok" disabled={busy}>Record payment</button>
                </div>
              </form>
              {payForm.method === 'credit' ? <p className="hint">Credit takes no money. The amount stays owed on Guest invoices after check-out.</p> : null}
            </section>
          )}
          <div className="list-table-wrap">
          <table className="table">
            <thead><tr><th>Charge</th><th>Total</th><th></th></tr></thead>
            <tbody>
              {folio.charges.map((c) => (
                <tr key={c.id} className={c.is_void ? 'hrow-off' : undefined}>
                  <td>
                    {c.description}
                    <div className="muted">{folioChargeWord(c.charge_type)} · {c.quantity ?? 1} × {money(c.unit_amount)}</div>
                    {Number(c.tax_amount) > 0 ? <div className="muted">Tax {money(c.tax_amount)}</div> : null}
                    {Number(c.discount_amount) > 0 ? <div className="muted">Discount {money(c.discount_amount)}</div> : null}
                  </td>
                  <td>{money(c.line_total)}</td>
                  <td>
                    {c.is_void ? 'Voided' : canCorrectMoney && folio.status === 'open' ? (
                      <button type="button" className="btn-danger" disabled={busy} onClick={() => openDialog({ kind: 'void', chargeId: c.id, label: c.description })}>
                        Void
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
              {!folio.charges.length && <tr><td colSpan={3} className="muted">No charges yet.</td></tr>}
            </tbody>
          </table>
          </div>
          <h3 style={{ marginTop: 16 }}>Payments</h3>
          <ul className="hbill-pays">
            {folio.payments.map((p) => (
              <li key={p.id} className="hbill-pay">
                <div>
                  {Number(p.amount) < 0 ? 'Refund' : tenderWord(p.method)} · {money(Math.abs(Number(p.amount)))}
                  {p.reference ? <div className="muted">{p.reference}</div> : null}
                  {p.notes ? <div className="muted">{p.notes}</div> : null}
                </div>
                {canCorrectMoney && folio.status === 'open' && Number(p.amount) > 0 && p.method !== 'credit' ? (
                  <button
                    type="button"
                    className="btn-danger"
                    disabled={busy}
                    aria-label={`Refund ${tenderWord(p.method)} payment of ${money(p.amount)}`}
                    onClick={() => openDialog({ kind: 'refund', paymentId: p.id, label: `${tenderWord(p.method)} ${money(p.amount)}` })}
                  >
                    Refund
                  </button>
                ) : null}
              </li>
            ))}
            {!folio.payments.length && <li className="muted">No payments recorded.</li>}
          </ul>
          {folio.status === 'open' && (
          <>
          {services.some((v) => v.is_active) && (
            <section className="hbill-box">
              <h3>Add from your services</h3>
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
                  setServiceCharge({ service_id: '', quantity: '1' });
                  setMessage('Service added to the bill');
                  await refresh();
                } catch (err: unknown) {
                  setError(hotelErr(err, 'Could not post service'));
                } finally {
                  setBusy(false);
                }
              }}
              style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}
            >
              <label>
                <span>Hotel service</span>
                <select value={serviceCharge.service_id} onChange={(e) => setServiceCharge((f) => ({ ...f, service_id: e.target.value }))} required aria-label="Post hotel service">
                  <option value="">Select</option>
                  {services.filter((v) => v.is_active).map((v) => (
                    <option key={v.id} value={v.id}>{v.name} ({money(v.unit_amount)})</option>
                  ))}
                </select>
              </label>
              <label>
                <span>How many</span>
                <input type="number" min={0.01} step="0.01" value={serviceCharge.quantity} onChange={(e) => setServiceCharge((f) => ({ ...f, quantity: e.target.value }))} aria-label="Service quantity" />
              </label>
              <div style={{ alignSelf: 'end' }}>
                <button type="submit" className="btn-ok" disabled={busy}>Post service</button>
              </div>
            </form>
            </section>
          )}
          <details className="hmore">
            <summary>Add something else to this bill</summary>
          <form onSubmit={addCharge} style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
            <label>
              <span>What it is for</span>
              <input value={chargeForm.description} onChange={(e) => setChargeForm((f) => ({ ...f, description: e.target.value }))} required aria-label="Folio charge description" />
            </label>
            <label>
              <span>Amount</span>
              <AmountField type="number" min={0} step="0.01" value={chargeForm.unit_amount} onChange={(e) => setChargeForm((f) => ({ ...f, unit_amount: e.target.value }))} aria-label="Folio charge amount" />
            </label>
            <label>
              <span>How many</span>
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
              <button type="submit" className="btn-ok" disabled={busy}>Post charge</button>
            </div>
          </form>
          </details>
          {(Number(settingsForm.early_checkin_fee) > 0 || Number(settingsForm.late_checkout_fee) > 0 || Number(settingsForm.service_charge_percent) > 0) && (
          <details className="hmore">
            <summary>Fees from Hotel settings</summary>
            <div className="hdesk-actions">
              {Number(settingsForm.early_checkin_fee) > 0 && (
                <button type="button" disabled={busy} aria-label="Post early check-in fee" onClick={() => void postBillExtra('timing-fee', { kind: 'early_checkin' }, 'Post the early check-in fee once on this bill?', 'Early check-in fee posted')}>
                  Post early check-in fee
                </button>
              )}
              {Number(settingsForm.late_checkout_fee) > 0 && (
                <button type="button" disabled={busy} aria-label="Post late check-out fee" onClick={() => void postBillExtra('timing-fee', { kind: 'late_checkout' }, 'Post the late check-out fee once on this bill?', 'Late check-out fee posted')}>
                  Post late check-out fee
                </button>
              )}
              {Number(settingsForm.service_charge_percent) > 0 && (
                <button type="button" disabled={busy} aria-label="Post service charge" onClick={() => void postBillExtra('service-charge', {}, 'Post the service charge once on the room total?', 'Service charge posted')}>
                  Post service charge
                </button>
              )}
            </div>
          </details>
          )}
          <details className="hmore">
            <summary>Move a charge to another guest’s bill</summary>
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
                setMessage('Charge moved');
                await refresh();
              } catch (err: unknown) {
                setError(hotelErr(err, 'Could not move the charge'));
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
          >
            <label>
              <span>Charge</span>
              <select value={transferChargeId} onChange={(e) => setTransferChargeId(e.target.value)} aria-label="Charge to transfer">
                <option value="">Select charge</option>
                {folio.charges.filter((c) => !c.is_void).map((c) => (
                  <option key={c.id} value={c.id}>{c.description} ({money(c.line_total)})</option>
                ))}
              </select>
            </label>
            <label>
              <span>To bill</span>
              <select value={transferFolioId} onChange={(e) => setTransferFolioId(e.target.value)} aria-label="Target folio">
                <option value="">Select bill</option>
                {folioRows.filter((f) => f.id !== folio.id && f.status === 'open').map((f) => (
                  <option key={f.id} value={f.id}>{f.room_code ? `Room ${f.room_code} · ` : ''}{f.guest_name || f.folio_number}</option>
                ))}
              </select>
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy || !transferChargeId || !transferFolioId}>Move charge</button>
            </div>
          </form>
          </details>
          <details className="hmore">
            <summary>Staff note</summary>
            <label>
              <span>Bill note</span>
              <input aria-label="Hotel folio notes" value={folioNote} onChange={(e) => setFolioNote(e.target.value)} />
            </label>
            <p className="muted">For your staff. It is not printed on the guest slip.</p>
            <button type="button" disabled={busy} onClick={saveFolioNote}>Save note</button>
          </details>
          </>
          )}
        </div>
      )}

      {show('billing') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hsearch-row">
            <input
              className="hsearch"
              type="search"
              value={billQuery}
              onChange={(e) => setBillQuery(e.target.value)}
              placeholder="Search guest, room or bill number"
              aria-label="Search guest bills"
            />
            <HotelViews
              label="Guest bill filter"
              value={billView}
              onPick={setBillView}
              items={[['open', 'Open', billGroups.open.length], ['owing', 'Owing', billGroups.owing.length], ['closed', 'Closed', billGroups.closed.length], ['', 'All', folioRows.length]]}
            />
          </div>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Bill</th>
                <th>Guest</th>
                <th>Stay</th>
                <th>Status</th>
                <th>Balance</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shownBills.map((f) => (
                <tr key={f.id}>
                  <td><code>{f.folio_number}</code></td>
                  <td>
                    {f.guest_name || '—'}
                    {f.room_code ? <div className="muted">Room {f.room_code}</div> : null}
                  </td>
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
                      aria-label={`View bill ${f.folio_number}`}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const d = await api(`/hotel/folios/${f.id}`);
                          setFolio(d.data || null);
                        } catch (err: unknown) {
                          setError(hotelErr(err, 'Could not open the bill'));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      View bill
                    </button>
                  </td>
                </tr>
              ))}
              {!shownBills.length && (
                <tr><td colSpan={6} className="muted">{emptyOr(folioRows.length ? 'No bill in this list.' : 'No guest bills yet. A bill opens when a guest checks in.')}</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {show('services') && (
        <div className="card" style={{ marginBottom: 16 }}>
          {addShown('services') && (
          <div className="hdesk-form">
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
                setAddOpen(false);
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
              <button type="submit" className="btn-ok" disabled={busy}>Add service</button>
            </div>
          </form>
          </div>
          )}
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Category</th>
                <th>Price</th>
                <th>Status</th>
                {canManage ? <th></th> : null}
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.id} className={s.is_active ? undefined : 'hrow-off'}>
                  <td><code>{s.code}</code></td>
                  <td>
                    {s.name}
                    {s.notes ? <div className="muted">{s.notes}</div> : null}
                  </td>
                  <td>{hotelWord(s.category)}</td>
                  <td>{money(s.unit_amount)}</td>
                  <td>{s.is_active ? 'On' : 'Off'}</td>
                  {canManage ? (
                    <td><button type="button" disabled={busy} onClick={() => openDialog({ kind: 'service', service: s })} aria-label={`Edit ${s.name}`}>Edit</button></td>
                  ) : null}
                </tr>
              ))}
              {!services.length && (
                <tr><td colSpan={6} className="muted">{emptyOr('No hotel services yet.')}</td></tr>
              )}
            </tbody>
          </table>
          </div>
          <p className="muted">To add a service to a stay, open the bill under <Link href="/hotel?tab=billing">Guest bills</Link>.</p>
        </div>
      )}

      {show('housekeeping') && (
      <>
      <HotelViews
        label="Housekeeping views"
        value={hkPage}
        onPick={(k) => goView(k === 'tasks' ? '' : k)}
        items={[['tasks', 'Cleaning', hkTasks.filter((t) => !hkDone(t)).length], ['lost-found', 'Lost and found', lostFound.filter((x) => x.status !== 'closed').length]]}
      />
      {hkPage === 'tasks' && (
      <div className="card" style={{ marginBottom: 16 }}>
        {addShown('housekeeping') && (
        <div className="hdesk-form">
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
            <span>Due date (blank is two hours from now)</span>
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
            <button type="submit" className="btn-ok" disabled={busy}>Create task</button>
          </div>
        </form>
        </div>
        )}
        <HotelViews
          label="Housekeeping task filter"
          value={hkView}
          onPick={setHkView}
          items={[['open', 'To do', hkTasks.filter((t) => !hkDone(t)).length], ['done', 'Done', hkTasks.filter(hkDone).length]]}
        />
        <div className="list-table-wrap">
        <table className="table">
          <thead><tr><th>Room</th><th>Job</th><th>Status</th><th>Priority</th><th>Due</th><th>Who</th><th></th></tr></thead>
          <tbody>
            {hkShown.map((t) => (
              <tr key={t.id}>
                <td>
                  {t.room_code || t.room_id}
                  {t.notes ? <div className="muted">{t.notes}</div> : null}
                </td>
                <td>{hotelWord(t.task_type) || 'Cleaning'}</td>
                <td><span className={statusClass(String(t.status || ''))}>{hotelWord(t.status)}</span></td>
                <td>{hotelWord(t.priority)}</td>
                <td>{t.due_at ? stayClock(t.due_at, formatPrefs) : '—'}</td>
                <td>{t.assigned_to || '—'}</td>
                <td>
                  {!hkDone(t) && (
                    <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/housekeeping/${t.id}/complete`, `Room ${t.room_code || ''} is done.`, { mark_inspected: true })} aria-label={`Mark room ${t.room_code || ''} clean`}>
                      {(t.task_type || 'cleaning') === 'cleaning' ? 'Mark clean' : 'Done'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!hkShown.length && <tr><td colSpan={7} className="muted">{emptyOr(hkView === 'done' ? 'Nothing finished yet.' : 'Nothing to clean right now.')}</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
      )}
      {hkPage === 'lost-found' && (
      <div className="card" id="lost-found" style={{ marginBottom: 16 }}>
        {addShown('lost') && (
        <form
          className="hdesk-form"
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
              setLfForm({ description: '', kind: 'found', room_id: '', notes: '' });
              setAddOpen(false);
              setMessage('Record saved');
              await refresh();
            } catch (err: unknown) {
              setError(hotelErr(err, 'Could not save record'));
            } finally {
              setBusy(false);
            }
          }}
          style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}
        >
          <label><span>What is it</span><input value={lfForm.description} onChange={(e) => setLfForm((f) => ({ ...f, description: e.target.value }))} required aria-label="Lost found description" placeholder="Black phone charger" /></label>
          <label>
            <span>Kind</span>
            <select value={lfForm.kind} onChange={(e) => setLfForm((f) => ({ ...f, kind: e.target.value }))} aria-label="Lost found kind">
              {[['found', 'Found by staff'], ['lost', 'Reported lost'], ['damage', 'Damage']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
          <label>
            <span>Room (optional)</span>
            <select value={lfForm.room_id} onChange={(e) => setLfForm((f) => ({ ...f, room_id: e.target.value }))} aria-label="Lost found room">
              <option value="">Not known</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.code}</option>)}
            </select>
          </label>
          <label>
            <span>Notes</span>
            <input value={lfForm.notes} onChange={(e) => setLfForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Lost found notes" />
          </label>
          <div style={{ alignSelf: 'end' }}><button type="submit" className="btn-ok" disabled={busy}>Save</button></div>
        </form>
        )}
        <div className="list-table-wrap">
          <table className="table">
            <thead><tr><th>Item</th><th>Kind</th><th>Room</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {lostFound.map((x) => (
                <tr key={x.id}>
                  <td>
                    {x.description}
                    {x.notes ? <div className="muted">{x.notes}</div> : null}
                  </td>
                  <td>{hotelWord(x.kind)}</td>
                  <td>{x.room_id ? rooms.find((r) => r.id === x.room_id)?.code : '—'}</td>
                  <td>{hotelWord(x.status)}</td>
                  <td>
                    {x.status !== 'closed' && (
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/lost-found/${x.id}/close`, 'Record closed')} aria-label={`Close ${x.description}`}>Close</button>
                    )}
                  </td>
                </tr>
              ))}
              {!lostFound.length && <tr><td colSpan={5} className="muted">{emptyOr('No lost-and-found records.')}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      )}
      </>
      )}

      {show('maintenance') && (
      <div className="card" style={{ marginBottom: 16 }}>
        {addShown('maintenance') && (
          <div className="hdesk-form">
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
            <span>What is wrong</span>
            <input placeholder="Air conditioner not cooling" value={maintForm.title} onChange={(e) => setMaintForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Maintenance title" />
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
            <span>Closed from (optional)</span>
            <HotelDateInput
              value={maintForm.ooo_starts_on}
              onChange={(ooo_starts_on) => setMaintForm((f) => ({ ...f, ooo_starts_on }))}
              ariaLabel="Out of order start date"
              prefs={formatPrefs}
            />
          </label>
          <label>
            <span>Closed until (optional)</span>
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
            {' '}Stop selling this room
          </label>
          <div style={{ alignSelf: 'end' }}>
            <button type="submit" className="btn-ok" disabled={busy}>Report fault</button>
          </div>
        </form>
          </div>
          )}
        <HotelViews
          label="Maintenance filter"
          value={maintView}
          onPick={setMaintView}
          items={[['open', 'Open', maint.filter((t) => !maintDone(t)).length], ['done', 'Fixed', maint.filter(maintDone).length]]}
        />
        <div className="list-table-wrap">
        <table className="table">
          <thead><tr><th>Room</th><th>Fault</th><th>Room closed</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {maintShown.map((t) => (
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
                    ? 'No, still in use'
                    : t.ooo_starts_on || t.ooo_ends_on
                      ? `${stayWhen(t.ooo_starts_on, formatPrefs)} – ${stayWhen(t.ooo_ends_on, formatPrefs)}`
                      : 'Until fixed'}
                </td>
                <td><span className={statusClass(String(t.status || ''))}>{hotelWord(t.status)}</span></td>
                <td>
                  {!maintDone(t) && (
                    <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/maintenance/${t.id}/complete`, 'Marked fixed')} aria-label={`Mark fixed: ${t.title}`}>Mark fixed</button>
                  )}
                </td>
              </tr>
            ))}
            {!maintShown.length && <tr><td colSpan={5} className="muted">{emptyOr(maintView === 'done' ? 'Nothing fixed yet.' : 'No open faults.')}</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
      )}

      {show('cashier') && (
        <>
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Front-desk float</h2>
          <p className="muted">
            The float is the cash in the front-desk drawer. Charges and payments on guest bills reach{' '}
            <Link href="/accounting">Accounting</Link> by themselves. Hotel costs go under <Link href="/expenses">Expenses</Link>.
          </p>
          {cashierShift ? (
            <div className="hbill-tiles">
              <div className="hbill-tile"><span>Opened {stayClock(cashierShift.opened_at, formatPrefs)}</span><b>{money(cashierShift.opening_float)}</b></div>
              <div className="hbill-tile"><span>Cash taken</span><b>{money(cashierShift.cash_taken)}</b></div>
              <div className="hbill-tile is-due"><span>Should be in the drawer</span><b>{money(cashierShift.expected_cash)}</b></div>
            </div>
          ) : (
            <p className="hint">No front-desk float is open. Count the drawer and open one to start the shift.</p>
          )}
          <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
            <label htmlFor="hotel-cashier-float">
              <span>{cashierShift ? 'Cash counted in the drawer' : 'Cash in the drawer now'}</span>
              <AmountField
                id="hotel-cashier-float"
                type="number"
                min={0}
                step="0.01"
                aria-label="Hotel cashier float"
                value={cashierFloat}
                onChange={(e) => setCashierFloat(e.target.value)}
              />
            </label>
            {cashierShift ? (
              <label htmlFor="hotel-cashier-notes">
                <span>Note (optional)</span>
                <input
                  id="hotel-cashier-notes"
                  aria-label="Hotel cashier notes"
                  value={cashierNotes}
                  onChange={(e) => setCashierNotes(e.target.value)}
                />
              </label>
            ) : null}
            <div style={{ alignSelf: 'end' }}>
              {cashierShift ? (
                <button
                  type="button"
                  className="btn-ok"
                  disabled={busy}
                  aria-label="Close front-desk float"
                  onClick={async () => {
                    const ok = await act('/hotel/cashier/shift/close', 'Front-desk float closed', {
                      closing_float: Number(cashierFloat) || 0,
                      notes: cashierNotes.trim() || null,
                    });
                    if (ok) {
                      setCashierNotes('');
                      setCashierFloat('0');
                    }
                  }}
                >
                  Close front-desk float
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-ok"
                  disabled={busy}
                  aria-label="Open front-desk float"
                  onClick={async () => {
                    if (await act('/hotel/cashier/shift/open', 'Front-desk float opened', { opening_float: Number(cashierFloat) || 0 })) setCashierFloat('0');
                  }}
                >
                  Open front-desk float
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h2 id="night-audit">Night audit</h2>
          <p className="muted">Saves today’s numbers at the end of the day. It does not charge anyone and does not post room nights again.</p>
          {nightAudits.some((n) => String(n.business_date).slice(0, 10) === dashDate) ? (
            <p className="hint">Today’s night audit is already saved.</p>
          ) : null}
          <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
            <label htmlFor="hotel-night-audit-note">
              <span>Note (optional)</span>
              <input
                id="hotel-night-audit-note"
                aria-label="Hotel night audit note"
                value={auditNote}
                onChange={(e) => setAuditNote(e.target.value)}
              />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button
                type="button"
                className="btn-ok"
                disabled={busy}
                aria-label="Run night audit"
                onClick={() => {
                  const note = auditNote.trim();
                  void act('/hotel/night-audits', 'Night audit posted', note ? { notes: note } : {}).then((ok) => {
                    if (ok) setAuditNote('');
                  });
                }}
              >
                Run night audit
              </button>
            </div>
          </div>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Closed floats</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Closed</th><th>Counted</th><th>Expected</th><th>Over or short</th></tr></thead>
              <tbody>
                {closedShifts.map((c) => (
                  <tr key={c.id}>
                    <td>
                      {stayClock(c.closed_at, formatPrefs)}
                      {c.notes ? <div className="muted">{c.notes}</div> : null}
                    </td>
                    <td>{money(c.closing_float)}</td>
                    <td>{c.expected_cash != null ? money(c.expected_cash) : '—'}</td>
                    <td>
                      {c.over_short == null
                        ? '—'
                        : Math.abs(Number(c.over_short)) < 0.005
                          ? 'Exact'
                          : Number(c.over_short) < 0
                            ? `Short ${money(Math.abs(Number(c.over_short)))}`
                            : `Over ${money(c.over_short)}`}
                    </td>
                  </tr>
                ))}
                {!closedShifts.length && <tr><td colSpan={4} className="muted">{emptyOr('No closed front-desk floats.')}</td></tr>}
              </tbody>
            </table>
          </div>
          <h3 style={{ marginTop: 16 }}>Night audits</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Date</th><th>Occupancy</th><th>Note</th></tr></thead>
              <tbody>
                {nightAudits.map((n) => (
                  <tr key={n.id}>
                    <td>{stayWhen(n.business_date, formatPrefs)}</td>
                    <td>{n.snapshot?.occupancy_rate ?? '—'}%</td>
                    <td>{n.snapshot?.note || '—'}</td>
                  </tr>
                ))}
                {!nightAudits.length && <tr><td colSpan={3} className="muted">{emptyOr('No night audits posted yet.')}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        </>
      )}

      {show('supplies') && (
        <div className="card" style={{ marginBottom: 16 }}>
                    <p className="muted">
            Linen, toiletries, food and drink, and cleaning supplies are kept with purchasing.
          </p>
          <div className="hdesk-links">
            {([
              ['/inventory?tab=products', 'Supplies', 'Everything you keep in the store room'],
              ['/inventory?tab=lowstock', 'Low supplies', 'What is running out'],
              ['/purchasing?tab=orders', 'Purchase orders', 'Order from a supplier'],
              ['/purchasing?tab=grn', 'Receive supplies', 'Goods have arrived'],
              ['/purchasing?tab=invoices', 'Supplier bills', 'What you owe suppliers'],
              ['/purchasing?tab=suppliers', 'Suppliers', 'Who you buy from'],
              ['/inventory?tab=adjust', 'Stock adjustments', 'Correct a count'],
              ['/inventory?tab=batches', 'Lots', 'Items with expiry dates'],
              ['/purchasing?tab=returns', 'Purchase returns', 'Send goods back'],
            ] as [string, string, string][]).map(([href, title, note]) => (
              <Link key={href} href={href}>{title}<small>{note}</small></Link>
            ))}
          </div>
        </div>
      )}

      {show('reports') && !report && !listsReady && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p className="muted">Loading hotel reports…</p>
        </div>
      )}
      {show('reports') && !report && listsReady && (
        <div className="card" style={{ marginBottom: 16 }}>
          <EmptyState
            title="Reports unavailable"
            detail="Hotel reports are not available right now. Occupancy on the dashboard still uses rooms and reservations."
          />
        </div>
      )}
      {show('reports') && report && (() => {
        const prev = report.previous || {};
        const days: { date: string; sold: number; occupancy_rate: number; room_revenue: number }[] = report.days || [];
        const shortDay = (iso: string) => stayWhen(iso, formatPrefs).slice(0, 5);
        const extras = Object.entries((report.service_sales || {}) as Record<string, number>).filter(([k]) => k !== 'room');
        const extrasTotal = extras.reduce((sum, [, v]) => sum + Number(v), 0);
        const sources = Object.entries((report.source_detail || {}) as Record<string, { stays: number; nights: number; revenue: number }>)
          .map(([k, v]) => ({ key: k, ...v }))
          .sort((x, y) => y.revenue - x.revenue);
        const types = Object.entries((report.room_type_detail || {}) as Record<string, { nights: number; revenue: number }>)
          .map(([k, v]) => ({ key: k, ...v }))
          .sort((x, y) => y.revenue - x.revenue);
        const methods = Object.entries((report.payments_by_method || {}) as Record<string, number>).sort((x, y) => Number(y[1]) - Number(x[1]));
        const roomRows: { code: string; nights: number; revenue: number; occupancy_rate: number }[] = report.rooms || [];
        const owing: { folio_number: string; guest_name?: string; room_code?: string; check_out_date?: string; balance: number }[] = report.owing || [];
        const next7 = report.on_the_books?.next_7 || {};
        const next30 = report.on_the_books?.next_30 || {};
        const period = `${stayWhen(report.start_date, formatPrefs)} – ${stayWhen(report.end_date, formatPrefs)}`;
        const tables: [string, string[], (string | number)[][]][] = [
          ['Summary', ['Measure', 'This period', 'Previous period'], [
            ['Occupancy %', report.occupancy_rate, prev.occupancy_rate ?? ''],
            ['Average room price', report.adr, prev.adr ?? ''],
            ['Income per room', report.revpar, prev.revpar ?? ''],
            ['Room revenue', report.room_revenue, prev.room_revenue ?? ''],
            ['Payments', report.payments_total, prev.payments_total ?? ''],
            ['Tax charged', report.tax_charged ?? 0, ''],
            ['Stays', report.stays ?? 0, ''],
            ['Cancellations', report.cancellations ?? 0, ''],
            ['No-shows', report.no_shows ?? 0, ''],
          ]],
          ['By day', ['Date', 'Rooms sold', 'Occupancy %', 'Room revenue'], days.map((d) => [d.date, d.sold, d.occupancy_rate, d.room_revenue])],
          ['By booking source', ['Source', 'Stays', 'Nights', 'Room revenue'], sources.map((x) => [bookingSourceWord(x.key), x.stays, x.nights, x.revenue])],
          ['By room type', ['Room type', 'Nights', 'Room revenue'], types.map((x) => [hotelWord(x.key), x.nights, x.revenue])],
          ['By room', ['Room', 'Nights', 'Occupancy %', 'Room revenue'], roomRows.map((x) => [x.code, x.nights, x.occupancy_rate, x.revenue])],
          ['Payments', ['Method', 'Amount'], methods.map(([k, v]) => [tenderWord(k), v])],
          ['Extras', ['Charge', 'Amount'], extras.map(([k, v]) => [folioChargeWord(k), v])],
          ['Guests owing', ['Bill', 'Guest', 'Room', 'Amount'], owing.map((x) => [x.folio_number, x.guest_name || '', x.room_code || '', x.balance])],
        ];
        const downloadReport = () => {
          const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
          const text = [`Hotel report,${cell(period)}`, ...tables.flatMap(([title, head, rows]) => ['', cell(title), head.map(cell).join(','), ...rows.map((r) => r.map(cell).join(','))])].join('\r\n');
          const link = document.createElement('a');
          link.href = URL.createObjectURL(new Blob([`﻿${text}`], { type: 'text/csv;charset=utf-8' }));
          link.download = `hotel-report-${report.start_date}-to-${report.end_date}.csv`;
          link.click();
          URL.revokeObjectURL(link.href);
        };
        const printReport = () => {
          const body = `<p>${escapeSlip(period)}</p>` + tables.map(([title, head, rows]) => (
            `<h2>${escapeSlip(title)}</h2><table><thead><tr>${head.map((x) => `<th>${escapeSlip(x)}</th>`).join('')}</tr></thead><tbody>` +
            (rows.map((r) => `<tr>${r.map((x) => `<td>${escapeSlip(String(x))}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="${head.length}">Nothing in this period.</td></tr>`) +
            '</tbody></table>'
          )).join('');
          if (!printDocumentHtml(hotelSlipHtml('Hotel report', body))) setError('Could not open the report for printing.');
        };
        return (
        <>
        <div className="card" style={{ marginBottom: 16 }}>
          <form
            className="hotel-report-range"
            onSubmit={(e) => {
              e.preventDefault();
              void refresh();
            }}
            style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}
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
            {([
              ['Today', localIso(), localIso()],
              ['Last 7 days', shiftIso(localIso(), -6), localIso()],
              ['This month', `${localIso().slice(0, 7)}-01`, localIso()],
              ['Last month', `${shiftIso(`${localIso().slice(0, 7)}-01`, -1).slice(0, 7)}-01`, shiftIso(`${localIso().slice(0, 7)}-01`, -1)],
            ] as [string, string, string][]).map(([label, from, to]) => (
              <button
                key={label}
                type="button"
                className={reportStart === from && reportEnd === to ? 'btn-ok' : undefined}
                disabled={busy}
                onClick={() => {
                  setReportStart(from);
                  setReportEnd(to);
                }}
              >
                {label}
              </button>
            ))}
            <span className="hreport-out">
              <button type="button" onClick={downloadReport} aria-label="Download hotel report CSV">Download CSV</button>
              <button type="button" onClick={printReport} aria-label="Print hotel report">Print</button>
            </span>
          </form>
        </div>
        <HotelViews
          label="Report views"
          value={reportView}
          onPick={setReportView}
          items={[['overview', 'Overview'], ['rooms', 'Rooms'], ['income', 'Income'], ['owing', 'Money owed', owing.length], ['supplies', 'Supplies']]}
        />
        {reportView === 'overview' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hotel-ops-kpis" style={{ marginBottom: 14 }}>
            <div className="hotel-kpi hotel-report-kpi">
              <div className="lbl">Occupancy</div>
              <div className="val">{Number(report.occupancy_rate || 0).toFixed(1)}%</div>
              <HotelDelta value={pctChange(Number(report.occupancy_rate || 0), prev.occupancy_rate)} />
              <div className="hint">{report.occupied_nights ?? 0} of {report.room_nights_available ?? 0} planned nights</div>
            </div>
            <div className="hotel-kpi hotel-report-kpi">
              <div className="lbl">Average room price (ADR)</div>
              <div className="val">{money(report.adr)}</div>
              <HotelDelta value={pctChange(Number(report.adr || 0), prev.adr)} />
              <div className="hint">Average nightly rate on planned nights</div>
            </div>
            <div className="hotel-kpi hotel-report-kpi">
              <div className="lbl">Income per room (RevPAR)</div>
              <div className="val">{money(report.revpar)}</div>
              <HotelDelta value={pctChange(Number(report.revpar || 0), prev.revpar)} />
              <div className="hint">Room revenue for every available night</div>
            </div>
            <div className="hotel-kpi hotel-report-kpi">
              <div className="lbl">Room revenue</div>
              <div className="val">{money(report.room_revenue)}</div>
              <HotelDelta value={pctChange(Number(report.room_revenue || 0), prev.room_revenue)} />
              <div className="hint">{report.rooms_total ?? 0} rooms in the house</div>
            </div>
          </div>
          <p className="muted">
            {Number(prev.room_revenue || 0) > 0
              ? `Arrows compare with ${stayWhen(prev.start_date, formatPrefs)} – ${stayWhen(prev.end_date, formatPrefs)}, the same number of days just before.`
              : `Nothing to compare yet: no room revenue in ${stayWhen(prev.start_date, formatPrefs)} – ${stayWhen(prev.end_date, formatPrefs)}.`}
          </p>
          <div className="hreport-charts">
            <DayBars
              title="Occupancy by day"
              summary={`Average ${Number(report.occupancy_rate || 0).toFixed(1)}%`}
              points={days.map((d) => ({ date: d.date, value: Number(d.occupancy_rate) }))}
              format={(v) => `${v.toFixed(0)}%`}
              dateLabel={shortDay}
            />
            <DayBars
              title="Room revenue by day"
              summary={`Total ${money(report.room_revenue)}`}
              points={days.map((d) => ({ date: d.date, value: Number(d.room_revenue) }))}
              format={(v) => money(v)}
              dateLabel={shortDay}
            />
          </div>
          <details className="hmore">
            <summary>See these numbers day by day</summary>
            <div className="list-table-wrap">
              <table className="table">
                <thead><tr><th>Date</th><th>Rooms sold</th><th>Occupancy</th><th>Room revenue</th></tr></thead>
                <tbody>
                  {days.map((d) => (
                    <tr key={d.date}><td>{stayWhen(d.date, formatPrefs)}</td><td>{d.sold}</td><td>{Number(d.occupancy_rate).toFixed(1)}%</td><td>{money(d.room_revenue)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <h3 style={{ marginTop: 16 }}>Already booked ahead</h3>
          <div className="hday-numbers">
            <div className="hbill-tile"><span>Next 7 days</span><b>{Number(next7.occupancy_rate || 0).toFixed(1)}%</b><small>{countWord(next7.occupied_nights ?? 0, 'night')} · {money(next7.room_revenue)}</small></div>
            <div className="hbill-tile"><span>Next 30 days</span><b>{Number(next30.occupancy_rate || 0).toFixed(1)}%</b><small>{countWord(next30.occupied_nights ?? 0, 'night')} · {money(next30.room_revenue)}</small></div>
            <div className="hbill-tile"><span>Stays starting in this period</span><b>{report.stays ?? 0}</b><small>Average {countWord(report.average_stay_nights ?? 0, 'night')}</small></div>
            <div className="hbill-tile"><span>Lost bookings</span><b>{(report.cancellations ?? 0) + (report.no_shows ?? 0)}</b><small>{report.cancellations ?? 0} cancelled · {report.no_shows ?? 0} no-show</small></div>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            Occupancy and room revenue count planned nights in the selected date range. An early leave still counts
            here. The dashboard counts only the nights the room is still held.
          </p>
        </div>
        )}
        {reportView === 'rooms' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Which room types earn most</h3>
          <RankBars format={(v) => money(v)} rows={types.map((x) => ({ label: hotelWord(x.key), value: x.revenue, note: `${countWord(x.nights, 'night')} · ${money(x.nights ? x.revenue / x.nights : 0)} a night` }))} />
          {!types.length && <p className="muted">No room revenue in this range.</p>}
          <h3 style={{ marginTop: 16 }}>Each room</h3>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Room</th><th>Nights sold</th><th>Occupancy</th><th>Room revenue</th></tr></thead>
              <tbody>
                {roomRows.map((x) => (
                  <tr key={x.code}><td><code>{x.code}</code></td><td>{x.nights}</td><td>{Number(x.occupancy_rate).toFixed(0)}%</td><td>{money(x.revenue)}</td></tr>
                ))}
                {!roomRows.length && <tr><td colSpan={4} className="muted">No room sold in this range.</td></tr>}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>Rooms that sold nothing in this period are not listed.</p>
        </div>
        )}
        {reportView === 'income' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hday-numbers" style={{ marginBottom: 14 }}>
            <div className="hbill-tile"><span>Room revenue</span><b>{money(report.room_revenue)}</b><small>Planned nights in this period</small></div>
            <div className="hbill-tile"><span>Extras</span><b>{money(extrasTotal)}</b><small>Meals, drinks, services, fees</small></div>
            <div className="hbill-tile"><span>Payments</span><b>{money(report.payments_total)}</b><small>Recorded on guest bills in this range</small></div>
            <div className="hbill-tile"><span>Tax charged</span><b>{money(report.tax_charged)}</b><small>On bills in this range</small></div>
          </div>
          <h3>Revenue by source</h3>
          <RankBars format={(v) => money(v)} rows={sources.map((x) => ({ label: bookingSourceWord(x.key), value: x.revenue, note: `${countWord(x.stays, 'stay')} · ${countWord(x.nights, 'night')}` }))} />
          {!sources.length && <p className="muted">No room revenue in this range.</p>}
          <h3 style={{ marginTop: 16 }}>How guests paid</h3>
          <RankBars format={(v) => money(v)} rows={methods.map(([k, v]) => ({ label: tenderWord(k), value: Number(v) }))} />
          {!methods.length && <p className="muted">No payments in this range.</p>}
          <h3 style={{ marginTop: 16 }}>Hotel-service sales</h3>
          <RankBars format={(v) => money(v)} rows={extras.sort((x, y) => Number(y[1]) - Number(x[1])).map(([k, v]) => ({ label: folioChargeWord(k), value: Number(v) }))} />
          {!extras.length && <p className="muted">No service sales in this period.</p>}
          <p className="muted" style={{ marginTop: 10 }}>
            Room revenue here includes tax when your rates include it. <Link href="/accounting">Accounting</Link> and the <Link href="/tax">tax report</Link> split it out.
          </p>
        </div>
        )}
        {reportView === 'owing' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="hday-numbers" style={{ marginBottom: 14 }}>
            <div className="hbill-tile is-due"><span>Guests still owe</span><b>{money(report.outstanding_guest_balances)}</b><small>On bills still open today</small></div>
          </div>
          <div className="list-table-wrap">
            <table className="table">
              <thead><tr><th>Guest</th><th>Room</th><th>Bill</th><th>Leaving</th><th>Owes</th></tr></thead>
              <tbody>
                {owing.map((x) => (
                  <tr key={x.folio_number}>
                    <td>{x.guest_name || '—'}</td>
                    <td>{x.room_code || '—'}</td>
                    <td><code>{x.folio_number}</code></td>
                    <td>{stayWhen(x.check_out_date, formatPrefs)}</td>
                    <td>{money(x.balance)}</td>
                  </tr>
                ))}
                {!owing.length && <tr><td colSpan={5} className="muted">No open bill has money owing.</td></tr>}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>
            This shows today, not the dates above. Take payment under <Link href="/hotel?tab=billing">Guest bills</Link>. Guests who already left are under <Link href="/hotel/invoices">Guest invoices</Link>.
          </p>
        </div>
        )}
        {reportView === 'supplies' && (
        <div className="card" style={{ marginBottom: 16 }}>
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
        </>
        );
      })()}

      {(show('restaurant') || show('bar')) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p className="muted">
            {foodTogether
              ? ''
              : foodKind === 'bar'
                ? 'The bar runs on its own desk.'
                : 'The restaurant runs on its own desk. It does not print a kitchen ticket.'}
            {' '}A catalog {foodNoun} uses that service’s tax. A one-off {foodNoun} has no tax.
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
                setMealForm((f) => ({ ...f, service_id: '', quantity: '1' }));
                setMessage(`${picked?.name || (postedDrink ? 'Drink' : 'Meal')} is on the bill.`);
                await refresh();
              } catch (err: unknown) {
                setError(hotelErr(err, foodCharge === 'bar' ? 'Could not post the bar drink' : 'Could not post the restaurant meal'));
              } finally {
                setBusy(false);
              }
            }}
            style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginBottom: 16 }}
          >
            <label style={{ gridColumn: '1 / -1' }}>
              <span>Guest bill</span>
              <select value={mealForm.folio_id} onChange={(e) => setMealForm((f) => ({ ...f, folio_id: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar folio' : 'Hotel restaurant folio'}>
                <option value="">Select the guest</option>
                {folioRows.filter((f) => f.status === 'open').map((f) => (
                  <option key={f.id} value={f.id}>{f.room_code ? `Room ${f.room_code} · ` : ''}{f.guest_name || 'Guest'}</option>
                ))}
              </select>
            </label>
            {tabReady && !folioRows.some((f) => f.status === 'open') ? (
              <p className="hint" style={{ gridColumn: '1 / -1' }}>No guest is checked in, so no bill is open.</p>
            ) : null}
            <div className="hmenu" role="group" aria-label={foodKind === 'bar' ? 'Hotel bar service' : 'Hotel restaurant service'} style={{ gridColumn: '1 / -1' }}>
              {services.filter((v) => v.is_active && foodCategories.includes(v.category)).map((v) => (
                <button key={v.id} type="button" aria-pressed={mealForm.service_id === v.id} onClick={() => setMealForm((f) => ({ ...f, service_id: f.service_id === v.id ? '' : v.id }))}>
                  <span>{v.name}</span>
                  <b>{money(v.unit_amount)}</b>
                </button>
              ))}
              {tabReady && !services.some((v) => v.is_active && foodCategories.includes(v.category)) ? (
                <p className="hint">No menu yet. Add meals and drinks under <Link href="/hotel?tab=services">Hotel services</Link>.</p>
              ) : null}
            </div>
            <label>
              <span>How many</span>
              <input type="number" min={1} step="1" value={mealForm.quantity} onChange={(e) => setMealForm((f) => ({ ...f, quantity: e.target.value }))} aria-label={foodKind === 'bar' ? 'Hotel bar quantity' : 'Hotel restaurant quantity'} />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" className="btn-ok" disabled={busy} aria-label={foodTogether ? 'Post outlet service' : foodKind === 'bar' ? 'Post bar service' : 'Post restaurant service'}>
                Post to bill
              </button>
            </div>
          </form>
          <details className="hmore">
            <summary>One-off item, not on the menu</summary>
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
          </details>
        </div>
      )}

      {show('events') && (
        <div className="card" style={{ marginBottom: 16 }}>
          {addShown('events') && (
          <div className="hdesk-form">
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
                setAddOpen(false);
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
              <span>Event name</span>
              <input placeholder="Mensah wedding" value={eventForm.title} onChange={(e) => setEventForm((f) => ({ ...f, title: e.target.value }))} required aria-label="Event title" />
            </label>
            <label>
              <span>Hall or room</span>
              <input placeholder="Main hall" value={eventForm.space_name} onChange={(e) => setEventForm((f) => ({ ...f, space_name: e.target.value }))} required aria-label="Event space name" />
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
              <button type="submit" className="btn-ok" disabled={busy}>Book event</button>
            </div>
          </form>
          </div>
          )}
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
                      <button type="button" className="btn-ok" disabled={busy} onClick={() => act(`/hotel/events/${evRow.id}/confirm`, 'Event confirmed')}>Confirm</button>
                    )}
                    {evRow.status !== 'cancelled' && evRow.status !== 'completed' && (
                      <button
                        type="button"
                        className="btn-danger"
                        disabled={busy}
                        onClick={() => {
                          if (!window.confirm(`Cancel ${evRow.title}? This cannot be undone.`)) return;
                          void act(`/hotel/events/${evRow.id}/cancel`, 'Event cancelled');
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!events.length && (
                <tr><td colSpan={5} className="muted">{emptyOr('No events booked yet.')}</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {show('settings') && (
        <div className="card" style={{ marginBottom: 16 }}>
                    <p className="muted">
            A room charge is nights × nightly rate. Tax % applies to rooms and to the early, late and no-show fees, and shows on the bill, the invoice and your tax report.
            Add the service charge from a guest bill when it applies.
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
                    room_rates_include_tax: settingsForm.room_rates_include_tax,
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
            <h3 className="hform-head">Your hotel</h3>
            <label>
              <span>Hotel name</span>
              <input value={settingsForm.property_name} onChange={(e) => setSettingsForm((f) => ({ ...f, property_name: e.target.value }))} aria-label="Hotel property name" placeholder="Your hotel name" />
            </label>
            <label>
              <span>Check-in time</span>
              <input type="time" value={settingsForm.check_in_time} onChange={(e) => setSettingsForm((f) => ({ ...f, check_in_time: e.target.value }))} aria-label="Hotel check-in time" />
            </label>
            <label>
              <span>Check-out time</span>
              <input type="time" value={settingsForm.check_out_time} onChange={(e) => setSettingsForm((f) => ({ ...f, check_out_time: e.target.value }))} aria-label="Hotel check-out time" />
            </label>
            <label>
              <span>Free cancellation until (hours before arrival)</span>
              <input type="number" min={0} value={settingsForm.cancellation_hours} onChange={(e) => setSettingsForm((f) => ({ ...f, cancellation_hours: e.target.value }))} aria-label="Hotel cancellation hours" />
            </label>
            <h3 className="hform-head">Tax</h3>
            <label>
              <span>Tax %</span>
              <input type="number" min={0} step="0.01" value={settingsForm.tax_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, tax_percent: e.target.value }))} aria-label="Hotel tax percent" />
            </label>
            <label style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={settingsForm.room_rates_include_tax}
                onChange={(e) => setSettingsForm((f) => ({ ...f, room_rates_include_tax: e.target.checked }))}
                aria-label="Room rates include tax"
              />
              <span>My room rates already include tax. Untick to add tax on top of the rate.</span>
            </label>
            {!(Number(settingsForm.tax_percent) > 0) ? (
              <p className="hint" style={{ gridColumn: '1 / -1' }}>Tax is 0, so no tax is charged on rooms. Set your rate if you charge tax.</p>
            ) : null}
            <h3 className="hform-head">Fees</h3>
            <label>
              <span>Early check-in fee</span>
              <AmountField type="number" min={0} step="0.01" value={settingsForm.early_checkin_fee} onChange={(e) => setSettingsForm((f) => ({ ...f, early_checkin_fee: e.target.value }))} aria-label="Early check-in fee" />
            </label>
            <label>
              <span>Late check-out fee</span>
              <AmountField type="number" min={0} step="0.01" value={settingsForm.late_checkout_fee} onChange={(e) => setSettingsForm((f) => ({ ...f, late_checkout_fee: e.target.value }))} aria-label="Late checkout fee" />
            </label>
            <label>
              <span>No-show fee (% of the stay)</span>
              <input type="number" min={0} step="0.01" value={settingsForm.no_show_fee_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, no_show_fee_percent: e.target.value }))} aria-label="Hotel no-show fee percent" />
            </label>
            <label>
              <span>Service charge %</span>
              <input type="number" min={0} max={100} step="0.01" value={settingsForm.service_charge_percent} onChange={(e) => setSettingsForm((f) => ({ ...f, service_charge_percent: e.target.value }))} aria-label="Hotel service charge percent" />
            </label>
            <h3 className="hform-head">Restaurant and bar</h3>
            <label style={{ gridColumn: '1 / -1' }}>
              <span>How they run</span>
              <select
                value={settingsForm.food_outlet_mode === 'separate' ? 'separate' : 'together'}
                onChange={(e) => setSettingsForm((f) => ({ ...f, food_outlet_mode: e.target.value }))}
                aria-label="Hotel food outlet mode"
              >
                <option value="together">Together — one desk for meals and drinks</option>
                <option value="separate">Separate — restaurant and bar each have a desk</option>
              </select>
            </label>
            <label style={{ gridColumn: '1 / -1' }}>
              <span>Note</span>
              <input value={settingsForm.notes} onChange={(e) => setSettingsForm((f) => ({ ...f, notes: e.target.value }))} aria-label="Hotel settings notes" />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" className="btn-ok" disabled={busy}>Save settings</button>
            </div>
          </form>
        </div>
      )}

      {dialog?.kind === 'arrival' && (
        <FormModal
          title={`${dialog.stay.guest_name || dialog.stay.reservation_number} · Room ${dialog.stay.room_code || ''}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <div className="hdesk-actions">
              {dialog.stay.can_check_in ? (
                <button
                  type="button"
                  className="btn-ok"
                  disabled={busy}
                  onClick={() => {
                    const { stay } = dialog;
                    setDialog(null);
                    checkInStay(stay);
                  }}
                >
                  Check in
                </button>
              ) : null}
              <button type="button" onClick={() => setDialog(null)}>Not now</button>
            </div>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p>{hotelWord(dialog.stay.status)} · {stayWhen(dialog.stay.check_in_date, formatPrefs)} – {stayWhen(dialog.stay.check_out_date, formatPrefs)}</p>
          {dialog.stay.guest_phone ? <p className="muted">{dialog.stay.guest_phone}</p> : null}
          {dialog.stay.special_requests ? <p className="muted">{dialog.stay.special_requests}</p> : null}
          <p className="muted">The bill opens when the guest checks in.</p>
        </FormModal>
      )}

      {dialog?.kind === 'balance' && (
        <FormModal
          title={`${dialog.name} still owes ${money(dialog.balance)}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <div className="hdesk-actions">
              <button
                type="button"
                className="btn-ok"
                disabled={busy}
                onClick={() => {
                  const id = dialog.stayId;
                  setDialog(null);
                  void showStayBill(id);
                }}
              >
                Take payment first
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  const { stayId, name } = dialog;
                  setDialog(null);
                  if (await act(`/hotel/reservations/${stayId}/check-out`, `${name} is checked out. The balance stays on Guest invoices.`, { allow_balance: true })) setFolio(null);
                }}
              >
                Check out and leave the balance
              </button>
            </div>
          }
        >
          <p>If you leave the balance, it stays owed under Guest invoices and you can collect it later.</p>
        </FormModal>
      )}

      {dialog?.kind === 'care' && (
        <FormModal
          title={`Room ${dialog.roomCode} ${dialog.closed ? 'is out of service' : 'needs cleaning'}`}
          onClose={() => setDialog(null)}
          footer={
            <div className="hdesk-actions">
              <button
                type="button"
                className="btn-ok"
                onClick={() => {
                  setDialog(null);
                  router.push(dialog.closed ? '/hotel?tab=maintenance' : '/hotel?tab=housekeeping');
                }}
              >
                {dialog.closed ? 'Open Maintenance' : 'Open Housekeeping'}
              </button>
              {!dialog.closed ? (
                <button
                  type="button"
                  onClick={() => {
                    const { roomId, roomCode } = dialog;
                    setDialog(null);
                    prefillStay(roomId, shiftIso(dashDate, 1), roomCode);
                  }}
                >
                  Book it from tomorrow
                </button>
              ) : null}
            </div>
          }
        >
          <p>{dialog.closed ? 'It cannot be sold until the fault is marked fixed.' : 'It cannot take a guest today until it is marked clean. You can still book it for a later date.'}</p>
        </FormModal>
      )}

      {dialog?.kind === 'extend' && (
        <FormModal
          title={`Extend ${dialog.stay.guest_name || dialog.stay.reservation_number}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={<button type="button" className="btn-ok" disabled={busy || !dlg.date} onClick={() => dialogSave(`/hotel/reservations/${dialog.stay.id}/extend`, { new_check_out_date: dlg.date }, 'Stay extended')}>Extend stay</button>}
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">Now leaving {stayWhen(dialog.stay.check_out_date, formatPrefs)}. The extra nights go on the bill.</p>
          <label>
            <span>New check-out date</span>
            <HotelDateInput value={dlg.date || ''} onChange={(date) => setDlg((d) => ({ ...d, date }))} ariaLabel="Extend stay date" required prefs={formatPrefs} />
          </label>
        </FormModal>
      )}

      {dialog?.kind === 'duplicate' && (
        <FormModal
          title={`Book ${dialog.stay.guest_name || 'this guest'} again`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <button
              type="button"
              className="btn-ok"
              disabled={busy || !dlg.date}
              onClick={() =>
                dialogSave(`/hotel/reservations/${dialog.stay.id}/duplicate`, {
                  check_in_date: dlg.date,
                  check_out_date: shiftIso(dlg.date, Math.max(1, dialog.stay.nights || 1)),
                }, 'Stay duplicated')
              }
            >
              Book same stay
            </button>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">Same room and same number of nights ({dialog.stay.nights || 1}).</p>
          <label>
            <span>New check-in date</span>
            <HotelDateInput value={dlg.date || ''} onChange={(date) => setDlg((d) => ({ ...d, date }))} ariaLabel="Duplicate stay date" required prefs={formatPrefs} />
          </label>
        </FormModal>
      )}

      {dialog?.kind === 'move' && (
        <FormModal
          title={`Change room for ${dialog.stay.guest_name || dialog.stay.reservation_number}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={<button type="button" className="btn-ok" disabled={busy || !dlg.room_id} onClick={() => dialogSave(`/hotel/reservations/${dialog.stay.id}/move`, { new_room_id: dlg.room_id }, 'Guest moved')}>Change room</button>}
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">Now in room {dialog.stay.room_code}. Only rooms free for the rest of this stay are listed.</p>
          <label>
            <span>Move to room</span>
            <select value={dlg.room_id || ''} onChange={(e) => setDlg((d) => ({ ...d, room_id: e.target.value }))} aria-label="Move to room">
              <option value="">{dlgRooms ? (dlgRooms.length ? 'Select' : 'No room is free') : 'Checking free rooms…'}</option>
              {(dlgRooms || []).map((r) => (
                <option key={r.id} value={r.id}>{r.code} · {roomPlainName(r.code, r.name)} · {money(r.rate_amount)}</option>
              ))}
            </select>
          </label>
        </FormModal>
      )}

      {dialog?.kind === 'edit' && (
        <FormModal
          title={`Edit ${dialog.stay.reservation_number}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <button
              type="button"
              className="btn-ok"
              disabled={busy}
              onClick={() => {
                const body: Record<string, unknown> = {
                  check_in_date: dlg.check_in_date,
                  check_out_date: dlg.check_out_date,
                  adults: Number(dlg.adults) || 1,
                  children: Number(dlg.children) || 0,
                  nightly_rate: Number(dlg.nightly_rate) || 0,
                };
                if (dlg.special_requests.trim()) body.special_requests = dlg.special_requests.trim();
                if (dlg.notes.trim()) body.notes = dlg.notes.trim();
                void dialogSave(`/hotel/reservations/${dialog.stay.id}`, body, 'Stay updated', 'PATCH');
              }}
            >
              Save stay
            </button>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <div className="hstay-grid">
            <label>
              <span>Check-in</span>
              <HotelDateInput value={dlg.check_in_date || ''} onChange={(v) => setDlg((d) => ({ ...d, check_in_date: v }))} ariaLabel="Edit check-in date" required prefs={formatPrefs} />
            </label>
            <label>
              <span>Check-out</span>
              <HotelDateInput value={dlg.check_out_date || ''} onChange={(v) => setDlg((d) => ({ ...d, check_out_date: v }))} ariaLabel="Edit check-out date" required prefs={formatPrefs} />
            </label>
            <label>
              <span>Adults</span>
              <input type="number" min={1} max={20} value={dlg.adults || ''} onChange={(e) => setDlg((d) => ({ ...d, adults: e.target.value }))} aria-label="Edit adults" />
            </label>
            <label>
              <span>Children</span>
              <input type="number" min={0} max={20} value={dlg.children || ''} onChange={(e) => setDlg((d) => ({ ...d, children: e.target.value }))} aria-label="Edit children" />
            </label>
            <label>
              <span>Price per night</span>
              <AmountField type="number" min={0} step="0.01" value={dlg.nightly_rate || ''} onChange={(e) => setDlg((d) => ({ ...d, nightly_rate: e.target.value }))} aria-label="Edit nightly rate" />
            </label>
            <label>
              <span>Special requests</span>
              <input value={dlg.special_requests || ''} onChange={(e) => setDlg((d) => ({ ...d, special_requests: e.target.value }))} aria-label="Edit special requests" />
            </label>
            <label>
              <span>Desk note</span>
              <input value={dlg.notes || ''} onChange={(e) => setDlg((d) => ({ ...d, notes: e.target.value }))} aria-label="Edit desk note" />
            </label>
          </div>
          <p className="muted">The price per night stays as shown unless you change it, even if the dates or people change.</p>
        </FormModal>
      )}

      {dialog?.kind === 'void' && (
        <FormModal
          title="Void this charge"
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <button
              type="button"
              className="btn-danger"
              disabled={busy || !dlg.reason?.trim() || !folio}
              onClick={() => dialogSave(`/hotel/folios/${folio?.id}/charges/${dialog.chargeId}/void`, { void_reason: dlg.reason.trim() }, 'Charge voided')}
            >
              Void charge
            </button>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">{dialog.label}. It comes off the bill and the books.</p>
          <label>
            <span>Why are you voiding it?</span>
            <input value={dlg.reason || ''} onChange={(e) => setDlg((d) => ({ ...d, reason: e.target.value }))} aria-label="Void reason" />
          </label>
        </FormModal>
      )}

      {dialog?.kind === 'refund' && (
        <FormModal
          title="Give money back"
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <button
              type="button"
              className="btn-danger"
              disabled={busy || !(Number(dlg.amount) > 0) || !dlg.reason?.trim() || !folio}
              onClick={() => dialogSave(`/hotel/folios/${folio?.id}/payments/${dialog.paymentId}/refund`, { amount: Number(dlg.amount), reason: dlg.reason.trim() }, 'Payment refunded')}
            >
              Refund
            </button>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">From the {dialog.label} payment.</p>
          <label>
            <span>Amount to give back</span>
            <AmountField type="number" min={0} step="0.01" value={dlg.amount || ''} onChange={(e) => setDlg((d) => ({ ...d, amount: e.target.value }))} aria-label="Refund amount" />
          </label>
          <label>
            <span>Why are you refunding this?</span>
            <input value={dlg.reason || ''} onChange={(e) => setDlg((d) => ({ ...d, reason: e.target.value }))} aria-label="Refund reason" />
          </label>
        </FormModal>
      )}

      {dialog?.kind === 'room' && (
        <FormModal
          title={`Room ${dialog.room.code}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <div className="hdesk-actions">
              <button
                type="button"
                className="btn-ok"
                disabled={busy || !dlg.name?.trim()}
                onClick={() => {
                  const body: Record<string, unknown> = {
                    name: dlg.name.trim(),
                    room_type: dlg.room_type,
                    max_occupancy: Number(dlg.max_occupancy) || 1,
                    rate_amount: Number(dlg.rate_amount) || 0,
                    extra_person_charge: Number(dlg.extra_person_charge) || 0,
                    amenities: dlgAmenities,
                  };
                  if (dlg.weekend_rate.trim()) body.weekend_rate = Number(dlg.weekend_rate) || 0;
                  for (const key of ['floor', 'bed_type', 'description', 'notes']) {
                    if (dlg[key].trim()) body[key] = dlg[key].trim();
                  }
                  void dialogSave(`/hotel/rooms/${dialog.room.id}`, body, `Room ${dialog.room.code} saved`, 'PATCH');
                }}
              >
                Save room
              </button>
              <button
                type="button"
                className={dialog.room.is_active ? 'btn-danger' : 'btn-ok'}
                disabled={busy}
                onClick={() => {
                  if (dialog.room.is_active && !window.confirm(`Stop selling room ${dialog.room.code}? It leaves the room board and booking lists. Past stays stay on record.`)) return;
                  void dialogSave(`/hotel/rooms/${dialog.room.id}`, { is_active: !dialog.room.is_active }, dialog.room.is_active ? `Room ${dialog.room.code} is no longer for sale` : `Room ${dialog.room.code} is for sale again`, 'PATCH');
                }}
              >
                {dialog.room.is_active ? 'Stop selling this room' : 'Sell this room again'}
              </button>
            </div>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <div className="hstay-grid">
            <label><span>Name</span><input value={dlg.name || ''} onChange={(e) => setDlg((d) => ({ ...d, name: e.target.value }))} aria-label="Edit room name" /></label>
            <label>
              <span>Type</span>
              <select value={dlg.room_type || 'standard'} onChange={(e) => setDlg((d) => ({ ...d, room_type: e.target.value }))} aria-label="Edit room type">
                {ROOM_TYPES.map((t) => <option key={t} value={t}>{hotelWord(t)}</option>)}
              </select>
            </label>
            <label><span>Nightly rate</span><AmountField type="number" min={0} step="0.01" value={dlg.rate_amount || ''} onChange={(e) => setDlg((d) => ({ ...d, rate_amount: e.target.value }))} aria-label="Edit room rate" /></label>
            <label><span>Weekend rate</span><AmountField type="number" min={0} step="0.01" value={dlg.weekend_rate || ''} onChange={(e) => setDlg((d) => ({ ...d, weekend_rate: e.target.value }))} aria-label="Edit weekend rate" /></label>
            <label><span>Charge per extra guest</span><AmountField type="number" min={0} step="0.01" value={dlg.extra_person_charge || ''} onChange={(e) => setDlg((d) => ({ ...d, extra_person_charge: e.target.value }))} aria-label="Edit extra guest charge" /></label>
            <label><span>Most guests</span><input type="number" min={1} max={20} value={dlg.max_occupancy || ''} onChange={(e) => setDlg((d) => ({ ...d, max_occupancy: e.target.value }))} aria-label="Edit max guests" /></label>
            <label><span>Floor</span><input value={dlg.floor || ''} onChange={(e) => setDlg((d) => ({ ...d, floor: e.target.value }))} aria-label="Edit floor" /></label>
            <label><span>Bed</span><input value={dlg.bed_type || ''} onChange={(e) => setDlg((d) => ({ ...d, bed_type: e.target.value }))} aria-label="Edit bed" /></label>
            <label><span>Description</span><input value={dlg.description || ''} onChange={(e) => setDlg((d) => ({ ...d, description: e.target.value }))} aria-label="Edit description" /></label>
            <label><span>Note</span><input value={dlg.notes || ''} onChange={(e) => setDlg((d) => ({ ...d, notes: e.target.value }))} aria-label="Edit room note" /></label>
          </div>
          <fieldset style={{ border: 'none', padding: 0, margin: '10px 0 0', display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <legend>Amenities</legend>
            {ROOM_AMENITIES.map((key) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" checked={Boolean(dlgAmenities[key])} onChange={(e) => setDlgAmenities((a) => ({ ...a, [key]: e.target.checked }))} aria-label={`Edit amenity ${hotelWord(key)}`} />
                <span>{hotelWord(key)}</span>
              </label>
            ))}
          </fieldset>
          <p className="muted">A new price applies to new bookings. Stays already booked keep theirs.</p>
        </FormModal>
      )}

      {dialog?.kind === 'guest' && (
        <FormModal
          title={`Edit ${dialog.guest.full_name}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <button
              type="button"
              className="btn-ok"
              disabled={busy || !dlg.full_name?.trim()}
              onClick={() => {
                const was = dialog.guest as Record<string, any>;
                const body: Record<string, string> = {};
                for (const [key] of GUEST_EDIT_FIELDS) {
                  const next = key === 'phone' ? dlg[key].replace(/[\s()-]/g, '') : dlg[key].trim();
                  if (next && next !== String(was[key] ?? '')) body[key] = next;
                }
                void dialogSave(`/hotel/guests/${dialog.guest.id}`, body, 'Guest saved', 'PATCH');
              }}
            >
              Save guest
            </button>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <div className="hstay-grid">
            {GUEST_EDIT_FIELDS.map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <input value={dlg[key] || ''} onChange={(e) => setDlg((d) => ({ ...d, [key]: e.target.value }))} aria-label={`Edit guest ${label}`} />
              </label>
            ))}
          </div>
        </FormModal>
      )}

      {dialog?.kind === 'history' && guestHistory && (
        <FormModal title={guestHistory.guest?.full_name || 'Guest'} onClose={() => setDialog(null)} busy={busy}>
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <p className="muted">
            {[guestHistory.guest?.phone, guestHistory.guest?.email].filter(Boolean).join(' · ')}
          </p>
          <div className="hbill-tiles">
            <div className="hbill-tile"><span>Stays</span><b>{(guestHistory.reservations || []).length}</b></div>
            <div className="hbill-tile"><span>Still owes</span><b>{money(guestHistory.outstanding_balance)}</b></div>
          </div>
          <ul>
            {(guestHistory.reservations || []).map((r: Reservation) => (
              <li key={r.id}>
                {r.reservation_number} · {hotelWord(r.status)} · {stayWhen(r.check_in_date, formatPrefs)} – {stayWhen(r.check_out_date, formatPrefs)}
                {leftEarlyWhen(r) ? <span> · Left {stayWhen(leftEarlyWhen(r), formatPrefs)}</span> : null}
              </li>
            ))}
            {!(guestHistory.reservations || []).length && <li className="muted">No stays yet.</li>}
          </ul>
          <h3>Merge a duplicate</h3>
          <p className="muted">Keeps this guest, moves stays and bills from the duplicate, then deactivates the duplicate.</p>
          <label>
            <span>Duplicate of {guestHistory.guest?.full_name}</span>
            <select value={mergeSource} onChange={(e) => setMergeSource(e.target.value)} aria-label="Duplicate guest to merge">
              <option value="">Select duplicate profile</option>
              {guests
                .filter((g) => g.id !== guestHistory?.guest?.id)
                .map((g) => (
                  <option key={g.id} value={g.id}>{g.full_name}{g.phone ? ` · ${g.phone}` : ''}</option>
                ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !mergeSource}
            style={{ marginTop: 8 }}
            onClick={() => {
              if (!window.confirm('Merge the duplicate into this guest? This cannot be undone.')) return;
              void dialogSave(`/hotel/guests/${guestHistory.guest.id}/merge`, { source_guest_id: mergeSource }, 'Guest profiles merged');
            }}
          >
            Merge duplicate
          </button>
        </FormModal>
      )}

      {dialog?.kind === 'service' && (
        <FormModal
          title={`Edit ${dialog.service.name}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <div className="hdesk-actions">
              <button
                type="button"
                className="btn-ok"
                disabled={busy || !dlg.name?.trim()}
                onClick={() => {
                  const body: Record<string, unknown> = {
                    name: dlg.name.trim(),
                    category: dlg.category,
                    unit_amount: Number(dlg.unit_amount) || 0,
                    tax_percent: Number(dlg.tax_percent) || 0,
                  };
                  if (dlg.notes.trim()) body.notes = dlg.notes.trim();
                  void dialogSave(`/hotel/services/${dialog.service.id}`, body, 'Service saved', 'PATCH');
                }}
              >
                Save service
              </button>
              <button
                type="button"
                className={dialog.service.is_active ? 'btn-danger' : 'btn-ok'}
                disabled={busy}
                onClick={() => dialogSave(`/hotel/services/${dialog.service.id}`, { is_active: !dialog.service.is_active }, dialog.service.is_active ? 'Service turned off' : 'Service turned on', 'PATCH')}
              >
                {dialog.service.is_active ? 'Turn off' : 'Turn on'}
              </button>
            </div>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <div className="hstay-grid">
            <label><span>Name</span><input value={dlg.name || ''} onChange={(e) => setDlg((d) => ({ ...d, name: e.target.value }))} aria-label="Edit service name" /></label>
            <label>
              <span>Category</span>
              <select value={dlg.category || 'service'} onChange={(e) => setDlg((d) => ({ ...d, category: e.target.value }))} aria-label="Edit service category">
                {['restaurant', 'bar', 'laundry', 'transport', 'spa', 'extra', 'service'].map((c) => <option key={c} value={c}>{hotelWord(c)}</option>)}
              </select>
            </label>
            <label><span>Price</span><AmountField type="number" min={0} step="0.01" value={dlg.unit_amount || ''} onChange={(e) => setDlg((d) => ({ ...d, unit_amount: e.target.value }))} aria-label="Edit service price" /></label>
            <label><span>Tax %</span><input type="number" min={0} step="0.01" value={dlg.tax_percent || ''} onChange={(e) => setDlg((d) => ({ ...d, tax_percent: e.target.value }))} aria-label="Edit service tax" /></label>
            <label><span>Notes</span><input value={dlg.notes || ''} onChange={(e) => setDlg((d) => ({ ...d, notes: e.target.value }))} aria-label="Edit service notes" /></label>
          </div>
        </FormModal>
      )}

      {dialog?.kind === 'plan' && (
        <FormModal
          title={`Edit ${dialog.plan.name}`}
          onClose={() => setDialog(null)}
          busy={busy}
          footer={
            <div className="hdesk-actions">
              <button
                type="button"
                className="btn-ok"
                disabled={busy || !dlg.name?.trim()}
                onClick={() => dialogSave(`/hotel/rate-plans/${dialog.plan.id}`, { name: dlg.name.trim(), amount: Number(dlg.amount) || 0, min_nights: Number(dlg.min_nights) || 1 }, 'Rate plan saved', 'PATCH')}
              >
                Save plan
              </button>
              <button
                type="button"
                className={dialog.plan.is_active === false ? 'btn-ok' : 'btn-danger'}
                disabled={busy}
                onClick={() => dialogSave(`/hotel/rate-plans/${dialog.plan.id}`, { is_active: dialog.plan.is_active === false }, dialog.plan.is_active === false ? 'Rate plan turned on' : 'Rate plan turned off', 'PATCH')}
              >
                {dialog.plan.is_active === false ? 'Turn on' : 'Turn off'}
              </button>
            </div>
          }
        >
          {dlgError ? <p className="hotel-banner warn" role="alert">{dlgError}</p> : null}
          <div className="hstay-grid">
            <label><span>Name</span><input value={dlg.name || ''} onChange={(e) => setDlg((d) => ({ ...d, name: e.target.value }))} aria-label="Edit plan name" /></label>
            <label><span>Price per night</span><AmountField type="number" min={0} step="0.01" value={dlg.amount || ''} onChange={(e) => setDlg((d) => ({ ...d, amount: e.target.value }))} aria-label="Edit plan price" /></label>
            <label><span>Minimum nights</span><input type="number" min={1} value={dlg.min_nights || ''} onChange={(e) => setDlg((d) => ({ ...d, min_nights: e.target.value }))} aria-label="Edit plan minimum nights" /></label>
          </div>
          <p className="muted">Stays already booked keep their price.</p>
        </FormModal>
      )}
    </>
  );
}
