'use client';

/**
 * FMCG staff location, phone side. Shows nothing unless HR switched sharing on for this person.
 * Then: a notice to accept once, and a permanent banner while sharing. Positions are read only while
 * this page is open and the person is clocked in (the server refuses them otherwise).
 *
 * Honest limit: a web page cannot read the location when the screen is locked or the app is closed.
 * The screen is kept awake while sharing; if the phone still sleeps, the manager sees "last seen".
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { normalizeIndustry } from '../lib/industries';

type Status = {
  enabled: boolean;
  notice: string;
  notice_accepted: boolean;
  clocked_in: boolean;
  sharing: boolean;
  has_hr_record: boolean;
  last_at: string | null;
};
type Point = { latitude: number; longitude: number; accuracy_m: number; speed_kmh?: number; captured_at: string };

const QUEUE_KEY = 'ribdigi.fmcg.track.queue.v1';
const SEND_EVERY_MS = 30_000;
const MOVE_M = 50;
const MIN_GAP_MS = 10_000;

function metres(a: { latitude: number; longitude: number }, b: { latitude: number; longitude: number }) {
  const r = 6371000;
  const p1 = (a.latitude * Math.PI) / 180;
  const p2 = (b.latitude * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((b.longitude - a.longitude) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

function readQueue(): Point[] {
  try {
    const raw = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}
function writeQueue(list: Point[]) {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(list.slice(-300)));
  } catch {
    /* a private window keeps nothing; points just go out live */
  }
}

export default function StaffLocationSharer({ industry }: { industry?: string | null }) {
  const isFmcg = normalizeIndustry(industry) === 'fmcg';
  const [status, setStatus] = useState<Status | null>(null);
  const [note, setNote] = useState('');
  const [sentAt, setSentAt] = useState<number | null>(null);
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);
  const lastSent = useRef<{ at: number; point: Point | null }>({ at: 0, point: null });
  const flushing = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const res = await api('/fmcg/tracking/me');
      setStatus((res?.data as Status) || null);
    } catch {
      /* offline or not allowed: keep what we know */
    }
  }, []);

  useEffect(() => {
    if (!isFmcg) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(timer);
  }, [isFmcg, refresh]);

  const flush = useCallback(async () => {
    if (flushing.current) return;
    const queue = readQueue();
    if (!queue.length) return;
    flushing.current = true;
    try {
      const batch = queue.slice(0, 100);
      await api('/fmcg/tracking/pings', { method: 'POST', body: JSON.stringify({ points: batch }) });
      writeQueue(readQueue().slice(batch.length));
      setSentAt(Date.now());
      setNote('');
    } catch (err) {
      const message = String((err as Error)?.message || '');
      if (/clock|switched on|accept|notice/i.test(message)) {
        writeQueue([]);
        void refresh();
      } else {
        setNote('No signal. Your positions are kept and sent when you are back online.');
      }
    } finally {
      flushing.current = false;
    }
  }, [refresh]);

  const sharing = Boolean(status?.sharing);

  useEffect(() => {
    if (!isFmcg) return;
    if (!sharing) {
      writeQueue([]);
      return;
    }
    if (!('geolocation' in navigator)) {
      setNote('This phone or browser cannot share its location.');
      return;
    }
    let wake: { release: () => Promise<void> } | null = null;
    const keepAwake = async () => {
      try {
        const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> } };
        if (nav.wakeLock && document.visibilityState === 'visible') wake = await nav.wakeLock.request('screen');
      } catch {
        /* the phone may refuse; sharing still works while the screen is on */
      }
    };
    void keepAwake();
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void keepAwake();
        void flush();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('online', onVisible);

    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        setDenied(false);
        const point: Point = {
          latitude: Number(pos.coords.latitude.toFixed(6)),
          longitude: Number(pos.coords.longitude.toFixed(6)),
          accuracy_m: Math.round(pos.coords.accuracy || 0),
          ...(pos.coords.speed != null && pos.coords.speed >= 0 ? { speed_kmh: Math.round(pos.coords.speed * 3.6 * 10) / 10 } : {}),
          captured_at: new Date(pos.timestamp || Date.now()).toISOString(),
        };
        const now = Date.now();
        const prev = lastSent.current;
        const moved = prev.point ? metres(prev.point, point) : Infinity;
        const due = now - prev.at >= SEND_EVERY_MS || (moved >= MOVE_M && now - prev.at >= MIN_GAP_MS);
        if (!due) return;
        lastSent.current = { at: now, point };
        writeQueue([...readQueue(), point]);
        void flush();
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) setDenied(true);
        else setNote('Waiting for a location signal…');
      },
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 30_000 },
    );
    const retry = window.setInterval(() => void flush(), 45_000);
    return () => {
      navigator.geolocation.clearWatch(watch);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('online', onVisible);
      window.clearInterval(retry);
      void wake?.release().catch(() => undefined);
    };
  }, [isFmcg, sharing, flush]);

  async function accept() {
    setBusy(true);
    try {
      const res = await api('/fmcg/tracking/me/notice', { method: 'POST' });
      setStatus((res?.data as Status) || null);
    } catch (err) {
      setNote(String((err as Error)?.message || 'Could not save that. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  if (!isFmcg || !status?.enabled) return null;

  const box: React.CSSProperties = {
    margin: '8px 16px', padding: '10px 14px', borderRadius: 10, border: '1px solid #c9d9b6', background: '#f2f7ec',
    color: '#10211B', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
  };

  if (!status.notice_accepted) {
    return (
      <div role="region" aria-label="Location sharing notice" style={box}>
        <span style={{ flex: '1 1 260px' }}>
          <strong>Your manager can see where you are while you work.</strong> {status.notice}
        </span>
        <button type="button" aria-label="Accept location sharing notice" disabled={busy} onClick={accept} className="btn-primary">
          I understand
        </button>
      </div>
    );
  }
  if (!status.has_hr_record) {
    return (
      <div role="status" style={box}>
        Location sharing is on for you, but HR has no staff record with your login email, so you cannot clock in. Ask HR to add it.
      </div>
    );
  }
  if (!status.clocked_in) {
    return (
      <div role="status" aria-label="Location sharing waiting" style={box}>
        📍 Location sharing starts when you clock in. It stops when you clock out.
      </div>
    );
  }
  return (
    <div role="status" aria-label="Location is being shared" style={box}>
      <span style={{ flex: '1 1 260px' }}>
        📍 <strong>Your location is shared with your manager.</strong> Keep this page open. It stops when you clock out.
        {sentAt ? ` Last sent ${new Date(sentAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.` : ' Waiting for your first position…'}
      </span>
      {denied ? <strong role="alert">Allow location for this site in your browser settings.</strong> : null}
      {note ? <small>{note}</small> : null}
    </div>
  );
}
