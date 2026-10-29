'use client';

type GridRoom = {
  id: string;
  code: string;
  name: string;
  room_type?: string;
  floor?: string | null;
  status: string;
};

type GridReservation = {
  id: string;
  room_id: string;
  guest_name?: string | null;
  check_in_date: string;
  check_out_date: string;
  status: string;
  reservation_number?: string;
  checked_out_at?: string | null;
};

type CalendarCell = {
  reservation_id: string;
  reservation_number?: string;
  status: string;
  guest_name?: string | null;
};

type CalendarPayload = {
  days?: string[];
  rooms?: { room: GridRoom; days?: Record<string, CalendarCell> }[];
} | null;

type MaintRow = {
  room_id: string;
  status: string;
  ooo_starts_on?: string | null;
  ooo_ends_on?: string | null;
};

export type NightKind = 'available' | 'booked' | 'checked_in' | 'ooo' | 'dirty';

function shiftIso(iso: string, days: number) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function localIso(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function enumerateDays(start: string, count: number): string[] {
  const out: string[] = [];
  if (!start || count < 1) return out;
  for (let i = 0; i < count; i++) out.push(shiftIso(start, i));
  return out;
}

function weekday(iso: string) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' });
}

function dayNum(iso: string) {
  return iso.slice(8);
}

function monthShort(iso: string) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { month: 'short' });
}

function rangeCaption(days: string[]) {
  if (!days.length) return '';
  const fmt = (iso: string) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  return `${fmt(days[0])} – ${fmt(days[days.length - 1])} ${days[days.length - 1].slice(0, 4)}`;
}

function isWeekend(iso: string) {
  const day = new Date(`${iso}T12:00:00`).getDay();
  return day === 0 || day === 6;
}

function isOpenMaint(status: string) {
  return !['completed', 'closed', 'cancelled', 'done'].includes((status || '').toLowerCase());
}

function nightOoo(room: GridRoom, day: string, maint: MaintRow[]): boolean {
  const dated = maint.filter((t) => t.room_id === room.id && isOpenMaint(t.status) && t.ooo_starts_on);
  if (dated.length) {
    return dated.some((t) => {
      const start = t.ooo_starts_on as string;
      const end = t.ooo_ends_on || t.ooo_starts_on;
      return day >= start && day <= (end as string);
    });
  }
  return ['out_of_order', 'maintenance', 'blocked'].includes(room.status);
}

function stayCheckout(r: GridReservation): string {
  if (r.status === 'checked_out' && r.checked_out_at) {
    const left = r.checked_out_at.slice(0, 10);
    if (left && left < r.check_out_date) return left;
  }
  return r.check_out_date;
}

function stayFromReservations(reservations: GridReservation[], roomId: string, day: string): CalendarCell | null {
  for (const r of reservations) {
    if (r.room_id !== roomId) continue;
    if (['cancelled', 'no_show', 'waitlisted'].includes(r.status)) continue;
    if (day >= r.check_in_date && day < stayCheckout(r)) {
      return {
        reservation_id: r.id,
        reservation_number: r.reservation_number,
        status: r.status,
        guest_name: r.guest_name,
      };
    }
  }
  return null;
}

function kindFor(cell: CalendarCell | null, room: GridRoom, day: string, maint: MaintRow[]): NightKind {
  if (cell) {
    if (cell.status === 'checked_in') return 'checked_in';
    return 'booked';
  }
  if (nightOoo(room, day, maint)) return 'ooo';
  if (room.status === 'dirty' && day === localIso()) return 'dirty';
  return 'available';
}

function stayEdge(
  prev: CalendarCell | null,
  cell: CalendarCell | null,
  next: CalendarCell | null
): 'none' | 'only' | 'start' | 'mid' | 'end' {
  if (!cell) return 'none';
  const samePrev = prev && prev.reservation_id === cell.reservation_id;
  const sameNext = next && next.reservation_id === cell.reservation_id;
  if (!samePrev && !sameNext) return 'only';
  if (!samePrev && sameNext) return 'start';
  if (samePrev && sameNext) return 'mid';
  return 'end';
}

export function HotelRoomNightGrid({
  rooms,
  reservations,
  calendar,
  maint,
  availableRoomIds,
  startDate,
  dayCount,
  compact,
  showNav,
  onStartChange,
  onDayCountChange,
  onEmptyNight,
}: {
  rooms: GridRoom[];
  reservations: GridReservation[];
  calendar: CalendarPayload;
  maint: MaintRow[];
  availableRoomIds?: string[];
  startDate: string;
  dayCount: number;
  compact?: boolean;
  showNav?: boolean;
  onStartChange?: (iso: string) => void;
  onDayCountChange?: (n: number) => void;
  onEmptyNight: (roomId: string, dateIso: string, roomCode: string) => void;
}) {
  const days =
    calendar?.days && calendar.days.length && !showNav
      ? calendar.days.slice(0, dayCount)
      : enumerateDays(startDate, dayCount);
  const calRows = calendar?.rooms || [];
  const roomList: GridRoom[] =
    calRows.length > 0
      ? calRows.map((row) => row.room)
      : rooms.filter((r) => r.id);
  const availSet = new Set(availableRoomIds || []);
  const visibleRooms = compact ? roomList.slice(0, 8) : roomList;

  return (
    <div className={`hotel-rng${compact ? ' compact' : ''}`}>
      <div className="hotel-rng-head">
        <div>
          <h3>{compact ? 'Room nights' : 'Booking calendar'}</h3>
          <p className="hint">
            Each bar is a stay. Click an open night to start a booking.
          </p>
          <p className="hotel-rng-range">{rangeCaption(days)}</p>
        </div>
        {showNav && (
          <div className="hotel-rng-nav">
            <button type="button" onClick={() => onStartChange?.(shiftIso(startDate, -7))} aria-label="Previous week">
              Previous week
            </button>
            <button type="button" onClick={() => onStartChange?.(localIso())} aria-label="Jump to today">
              Today
            </button>
            <button type="button" onClick={() => onStartChange?.(shiftIso(startDate, 7))} aria-label="Next week">
              Next week
            </button>
            {[14, 21, 30].map((n) => (
              <button
                key={n}
                type="button"
                className={dayCount === n ? 'is-on' : ''}
                onClick={() => onDayCountChange?.(n)}
                aria-label={`Show ${n} days`}
                aria-pressed={dayCount === n}
              >
                {n}d
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="hotel-rng-legend" aria-hidden="true">
        <span><i className="k available" />Available</span>
        <span><i className="k booked" />Booked</span>
        <span><i className="k checked_in" />Checked in</span>
        <span><i className="k ooo" />Out of order</span>
        <span><i className="k dirty" />Dirty</span>
      </div>
      <div className="hotel-rng-scroll">
        <div
          className="hotel-rng-table"
          style={{ minWidth: `calc(156px + ${Math.max(days.length, 1)} * 40px)` }}
          role="grid"
          aria-label="Hotel room-night calendar"
        >
          <div
            className="hotel-rng-row head"
            role="row"
            style={{ gridTemplateColumns: `156px repeat(${days.length || 1}, minmax(40px, 1fr))` }}
          >
            <div className="hotel-rng-room" role="columnheader">
              Room
            </div>
            {days.map((d, i) => {
              const today = d === localIso();
              const showMonth = i === 0 || dayNum(d) === '01';
              return (
                <div
                  key={d}
                  className={`hotel-rng-dayhead${today ? ' is-today' : ''}${isWeekend(d) ? ' is-weekend' : ''}`}
                  role="columnheader"
                  aria-current={today ? 'date' : undefined}
                >
                  <span className="mo">{showMonth ? monthShort(d) : '\u00a0'}</span>
                  <span className="wd">{weekday(d)}</span>
                  <span className="dn">{dayNum(d)}</span>
                </div>
              );
            })}
          </div>
          {visibleRooms.map((room) => {
            const calMap = calRows.find((row) => row.room.id === room.id)?.days || {};
            const cells = days.map((d) => calMap[d] || stayFromReservations(reservations, room.id, d));
            const captions = cells.flatMap((cell, i) => {
              if (!cell) return [];
              const edge = stayEdge(cells[i - 1] || null, cell, cells[i + 1] || null);
              if (edge !== 'start' && edge !== 'only') return [];
              return [{
                id: `${cell.reservation_id}-${days[i]}`,
                name: cell.guest_name || 'Stay',
                when: `${monthShort(days[i])} ${dayNum(days[i])}`,
              }];
            });
            const lastDay = days[days.length - 1] || '';
            const later = reservations
              .filter((r) => r.room_id === room.id && !['cancelled', 'no_show', 'waitlisted', 'checked_out'].includes(r.status))
              .filter((r) => String(r.check_in_date || '').slice(0, 10) > lastDay)
              .sort((a, b) => String(a.check_in_date).localeCompare(String(b.check_in_date)))[0];
            const laterWhen = later ? String(later.check_in_date || '').slice(0, 10) : '';
            return (
              <div
                className="hotel-rng-row"
                role="row"
                key={room.id}
                style={{ gridTemplateColumns: `156px repeat(${days.length || 1}, minmax(40px, 1fr))` }}
              >
                <div className="hotel-rng-room" role="rowheader">
                  <code>{room.code}</code>
                  <span className="rt">{room.room_type || room.name}</span>
                  {captions.slice(0, 2).map((cap) => (
                    <span className="stay-name" key={cap.id} title={`${cap.name} · ${cap.when}`}>{cap.name}</span>
                  ))}
                  {captions.length > 2 ? <span className="stay-name">+{captions.length - 2} more</span> : null}
                  {later && laterWhen ? (
                    <span className="stay-name" title={`Next stay ${later.guest_name || 'Stay'} ${laterWhen}`}>
                      Next stay {later.guest_name || 'Stay'} {monthShort(laterWhen)} {dayNum(laterWhen)}
                    </span>
                  ) : null}
                </div>
                {days.map((d, i) => {
                  const cell = cells[i];
                  const kind = kindFor(cell, room, d, maint);
                  const edge = stayEdge(cells[i - 1] || null, cell, cells[i + 1] || null);
                  const vacantHint = kind === 'available' && availSet.has(room.id) && d === days[0];
                  const today = d === localIso();
                  const label = cell
                    ? `${cell.guest_name || 'Guest'} · ${cell.status.replace(/_/g, ' ')}${cell.reservation_number ? ` · ${cell.reservation_number}` : ''}`
                    : kind === 'ooo'
                      ? `${room.code} out of order`
                      : kind === 'dirty'
                        ? `${room.code} dirty`
                        : `${room.code} available ${d}`;
                  const clickable = kind === 'available';
                  return (
                    <button
                      key={`${room.id}-${d}`}
                      type="button"
                      role="gridcell"
                      className={`hotel-rng-cell ${kind} stay-${edge}${vacantHint ? ' vacant-api' : ''}${today ? ' is-today' : ''}${isWeekend(d) ? ' is-weekend' : ''}`}
                      title={label}
                      aria-label={label}
                      disabled={!clickable}
                      onClick={() => {
                        if (clickable) onEmptyNight(room.id, d, room.code);
                      }}
                    />
                  );
                })}
              </div>
            );
          })}
          {!visibleRooms.length && (
            <p className="empty" style={{ padding: 12 }}>
              No rooms yet. Add rooms on the Rooms tab.
            </p>
          )}
        </div>
      </div>
      {compact && roomList.length > visibleRooms.length && (
        <p className="hint" style={{ marginTop: 10 }}>
          Showing {visibleRooms.length} of {roomList.length} rooms.
        </p>
      )}
    </div>
  );
}
