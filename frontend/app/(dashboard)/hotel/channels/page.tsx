'use client';

/**
 * Booking sites (channel sync over iCal). Each room links to Booking.com, Expedia, Airbnb or any
 * site that shares a calendar: the site reads our calendar link to close nights we sold, and we
 * read the site's calendar every 30 minutes so its bookings close the room here.
 */

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { formatDateTime } from '../../../../lib/format';
import '../hotel-desk.css';
import '../invoices/hotel-invoices.css';

type Row = Record<string, any>;
const CHANNELS: [string, string][] = [
  ['booking_com', 'Booking.com'],
  ['expedia', 'Expedia'],
  ['airbnb', 'Airbnb'],
  ['other', 'Other site'],
];

function problem(err: unknown) {
  return err instanceof Error ? err.message : 'Something went wrong. Try again.';
}

export default function HotelChannelsPage() {
  const [feeds, setFeeds] = useState<Row[] | null>(null);
  const [rooms, setRooms] = useState<Row[]>([]);
  const [form, setForm] = useState({ room_id: '', channel: 'booking_com', import_url: '' });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const [f, r] = await Promise.all([api('/hotel/channels'), api('/hotel/rooms?is_active=true')]);
      setFeeds((f?.data || []) as Row[]);
      setRooms((r?.data || []) as Row[]);
      setError('');
    } catch (err) {
      setFeeds([]);
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(work: () => Promise<string>) {
    setBusy(true);
    setError('');
    try {
      setNotice(await work());
      await load();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice('Calendar link copied. Paste it into the booking site’s calendar import.');
    } catch {
      setError('Could not copy. Select the link and copy it by hand.');
    }
  }

  return (
    <div className="hinv">
      <header className="hi-head">
        <div>
          <h1>Booking sites</h1>
          <p>Link each room to Booking.com, Expedia or Airbnb so a room sold on one is closed on the others.</p>
        </div>
        <Link href="/hotel?tab=rooms" className="hi-link">Rooms and rates →</Link>
      </header>

      {notice ? <div className="hi-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="hi-error" role="alert" onClick={() => setError('')}>{error}</div> : null}

      <div className="hi-list" style={{ padding: 16 }}>
        <h2 style={{ margin: '0 0 8px' }}>Link a room</h2>
        <ol style={{ margin: '0 0 12px', paddingLeft: 20, lineHeight: 1.6 }}>
          <li>Pick the room and the site, and press Link.</li>
          <li>Copy <strong>our calendar link</strong> into the site’s calendar import (on Booking.com: Rates &amp; Availability → Sync calendars).</li>
          <li>Paste the site’s own calendar link (its export) below the room, and press Save. We read it every 30 minutes.</li>
        </ol>
        <div className="hi-tools">
          <select aria-label="Room to link" value={form.room_id} onChange={(e) => setForm((f) => ({ ...f, room_id: e.target.value }))}>
            <option value="">Pick a room</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>Room {r.code}{r.name ? ` · ${r.name}` : ''}</option>
            ))}
          </select>
          <select aria-label="Booking site" value={form.channel} onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}>
            {CHANNELS.map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
          <input aria-label="Site calendar link (optional)" placeholder="Site's calendar link (optional, https://…)" value={form.import_url} onChange={(e) => setForm((f) => ({ ...f, import_url: e.target.value }))} />
          <button
            type="button"
            className="hi-primary"
            disabled={busy || !form.room_id}
            aria-label="Link room to booking site"
            onClick={() =>
              void run(async () => {
                await api('/hotel/channels', {
                  method: 'POST',
                  body: JSON.stringify({ room_id: form.room_id, channel: form.channel, import_url: form.import_url.trim() || null }),
                });
                setForm((f) => ({ ...f, import_url: '' }));
                return 'Room linked. Now copy our calendar link into the site.';
              })
            }
          >
            Link
          </button>
        </div>
      </div>

      <div className="hi-list" aria-label="Linked rooms">
        {feeds === null ? <p className="hi-empty">Loading…</p> : null}
        {feeds && feeds.length === 0 ? <p className="hi-empty">No rooms are linked to a booking site yet.</p> : null}
        {(feeds || []).map((f) => (
          <div key={f.id} className="hi-row" style={{ gridTemplateColumns: 'minmax(0,1fr)', gap: 8 }}>
            <div className="who">
              <strong>Room {f.room_code} · {f.channel_label}{f.is_active ? '' : ' (paused)'}</strong>
              <small>
                {f.last_synced_at ? `Last read ${formatDateTime(f.last_synced_at)}: ${f.last_status || ''}` : f.import_url ? 'Not read yet' : 'Add the site’s calendar link to read its bookings'}
              </small>
            </div>
            <div className="hi-tools">
              <input aria-label={`Our calendar link for room ${f.room_code}`} readOnly value={f.export_url} onFocus={(e) => e.currentTarget.select()} />
              <button type="button" aria-label={`Copy our calendar link for room ${f.room_code}`} onClick={() => void copy(f.export_url)}>Copy our link</button>
            </div>
            <div className="hi-tools">
              <input
                aria-label={`Site calendar link for room ${f.room_code}`}
                placeholder="Site's calendar link (https://…)"
                value={drafts[f.id] ?? f.import_url ?? ''}
                onChange={(e) => setDrafts((d) => ({ ...d, [f.id]: e.target.value }))}
              />
              <button
                type="button"
                disabled={busy}
                aria-label={`Save site calendar link for room ${f.room_code}`}
                onClick={() =>
                  void run(async () => {
                    const url = (drafts[f.id] ?? f.import_url ?? '').trim();
                    await api(`/hotel/channels/${f.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify(url ? { import_url: url } : { clear_import_url: true }),
                    });
                    return url ? 'Site calendar link saved' : 'Site calendar link removed';
                  })
                }
              >
                Save
              </button>
              <button
                type="button"
                className="hi-primary"
                disabled={busy || !f.import_url}
                aria-label={`Read bookings now for room ${f.room_code}`}
                onClick={() =>
                  void run(async () => {
                    const res = await api(`/hotel/channels/${f.id}/sync`, { method: 'POST', body: '{}' });
                    return `Room ${f.room_code}: ${res?.data?.status || 'read'}`;
                  })
                }
              >
                Read now
              </button>
              <button
                type="button"
                disabled={busy}
                aria-label={`${f.is_active ? 'Pause' : 'Resume'} link for room ${f.room_code}`}
                onClick={() =>
                  void run(async () => {
                    await api(`/hotel/channels/${f.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !f.is_active }) });
                    return f.is_active ? 'Link paused' : 'Link resumed';
                  })
                }
              >
                {f.is_active ? 'Pause' : 'Resume'}
              </button>
              <button
                type="button"
                disabled={busy}
                aria-label={`Remove link for room ${f.room_code}`}
                onClick={() => {
                  if (!window.confirm(`Stop syncing room ${f.room_code} with ${f.channel_label}? Remove our link on the site too.`)) return;
                  void run(async () => {
                    await api(`/hotel/channels/${f.id}`, { method: 'DELETE' });
                    return 'Link removed';
                  });
                }}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
      <p style={{ color: 'var(--hi-muted)', fontWeight: 600, margin: 0 }}>
        Calendars share dates only. A booking from a site arrives as “Booking.com guest” at the room’s rate: open it to add the guest’s name and the price the site took.
        If a site’s booking lands on nights already sold, you get an alert to move one of the guests.
      </p>
    </div>
  );
}
