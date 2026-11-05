'use client';

type BoardRoom = {
  id: string;
  code: string;
  floor?: string | null;
  room_type: string;
  status: string;
  housekeeping_status?: string;
};

type BoardStay = {
  id: string;
  room_id: string;
  guest_name?: string | null;
  status: string;
  check_in_date: string;
  check_out_date: string;
  folio_balance?: number | null;
};

type Mark = { key: string; label: string };

const MARKS: Record<string, Mark> = {
  occupied: { key: 'occupied', label: 'In house' },
  leaving: { key: 'leaving', label: 'Leaving today' },
  arriving: { key: 'arriving', label: 'Arriving today' },
  ready: { key: 'ready', label: 'Ready' },
  dirty: { key: 'dirty', label: 'Needs cleaning' },
  closed: { key: 'closed', label: 'Out of service' },
};

const CLOSED = new Set(['maintenance', 'out_of_order', 'blocked', 'out_of_service']);

function markFor(room: BoardRoom, inHouse: BoardStay | undefined, arriving: BoardStay | undefined, today: string): Mark {
  if (inHouse) return inHouse.check_out_date === today ? MARKS.leaving : MARKS.occupied;
  if (CLOSED.has(room.status)) return MARKS.closed;
  if (arriving) return MARKS.arriving;
  if (room.status === 'dirty' || room.housekeeping_status === 'dirty') return MARKS.dirty;
  return MARKS.ready;
}

/** Every room at a glance, floor by floor. Hotel desk only. */
export default function HotelRoomBoard({
  rooms,
  stays,
  today,
  money,
  onStay,
  onEmptyRoom,
}: {
  rooms: BoardRoom[];
  stays: BoardStay[];
  today: string;
  money: (value: number) => string;
  onStay: (stayId: string) => void;
  onEmptyRoom: (roomId: string, roomCode: string) => void;
}) {
  const inHouse = new Map(stays.filter((s) => s.status === 'checked_in').map((s) => [s.room_id, s]));
  const arriving = new Map(
    stays.filter((s) => s.status === 'booked' && s.check_in_date === today).map((s) => [s.room_id, s]),
  );
  const floors = new Map<string, BoardRoom[]>();
  for (const room of rooms) {
    const floor = room.floor || 'Rooms';
    floors.set(floor, [...(floors.get(floor) || []), room]);
  }
  const counts: Record<string, number> = {};
  const tiles = new Map<string, Mark>();
  for (const room of rooms) {
    const mark = markFor(room, inHouse.get(room.id), arriving.get(room.id), today);
    tiles.set(room.id, mark);
    counts[mark.key] = (counts[mark.key] || 0) + 1;
  }

  return (
    <section className="hboard" aria-label="Room board">
      <div className="hboard-key">
        {Object.values(MARKS).map((mark) => (
          <span key={mark.key} className={`hboard-key-item is-${mark.key}`}>
            <i aria-hidden="true" />
            {mark.label} <b>{counts[mark.key] || 0}</b>
          </span>
        ))}
      </div>
      {Array.from(floors.entries()).map(([floor, list]) => (
        <div key={floor} className="hboard-floor">
          <h3>{floor}</h3>
          <div className="hboard-grid">
            {list.map((room) => {
              const stay = inHouse.get(room.id) || arriving.get(room.id);
              const mark = tiles.get(room.id) || MARKS.ready;
              const owes = Number(stay?.folio_balance || 0);
              return (
                <button
                  key={room.id}
                  type="button"
                  className={`hboard-room is-${mark.key}`}
                  aria-label={`Room ${room.code}, ${mark.label}${stay?.guest_name ? `, ${stay.guest_name}` : ''}`}
                  onClick={() => (stay ? onStay(stay.id) : onEmptyRoom(room.id, room.code))}
                >
                  <strong>{room.code}</strong>
                  <span className="hboard-who">{stay?.guest_name || mark.label}</span>
                  {stay?.status === 'checked_in' && owes > 0.004 ? (
                    <span className="hboard-owes">Owes {money(owes)}</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
