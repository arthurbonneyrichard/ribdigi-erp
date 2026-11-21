'use client';

/**
 * FMCG live staff map: where each rep and driver was last seen, and the day's path and stops for one
 * person. Admins and HR see everyone; a manager sees the people who report to them in HR. HR or an admin
 * switches sharing on per person. Refreshes every 20 seconds. This is not real-time GPS: a position
 * arrives only while the person has the ERP open on their phone and is clocked in.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../lib/api';
import TileMap, { type MapMarker } from '../../../components/TileMap';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const LIVE_TABS = ['livemap'];

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const ROLE_WORDS: Record<string, string> = {
  fmcg_rep: 'Sales rep', fmcg_driver: 'Driver', fmcg_manager: 'Distribution manager', fmcg_storekeeper: 'Storekeeper',
  fmcg_quality: 'Quality', fmcg_fleet: 'Fleet', company_admin: 'Admin', hrm_manager: 'HR manager',
};

function ago(minutes: number | null | undefined) {
  if (minutes == null) return 'never';
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const h = Math.floor(minutes / 60);
  return h < 24 ? `${h} h ${minutes % 60} min ago` : `${Math.floor(h / 24)} d ago`;
}
function words(p: Row): { text: string; tone: 'live' | 'stale' | 'none' } {
  if (!p.enabled) return { text: 'Sharing is off', tone: 'none' };
  if (!p.notice_accepted) return { text: 'Has not accepted the notice yet', tone: 'none' };
  if (!p.has_hr_record) return { text: 'No HR record with this email', tone: 'none' };
  if (!p.on_duty) return { text: p.last_at ? `Off duty · last seen ${ago(p.minutes_ago)}` : 'Not clocked in', tone: 'none' };
  if (p.stale) return { text: `Last seen ${ago(p.minutes_ago)} (phone may be asleep)`, tone: 'stale' };
  return { text: `Live · ${ago(p.minutes_ago)}`, tone: 'live' };
}
const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export default function FmcgLive({ tab }: { tab: string }) {
  const [people, setPeople] = useState<Row[]>([]);
  const [canSwitch, setCanSwitch] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState('');
  const [day, setDay] = useState(today());
  const [trail, setTrail] = useState<Row | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api('/fmcg/tracking/people');
      setPeople(res?.data?.people || []);
      setCanSwitch(Boolean(res?.data?.can_switch));
      setLoadedAt(new Date());
      setError('');
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    if (tab !== 'livemap') return;
    void load();
    const timer = window.setInterval(() => void load(), 20_000);
    return () => window.clearInterval(timer);
  }, [tab, load]);

  useEffect(() => {
    if (!selected) {
      setTrail(null);
      return;
    }
    let live = true;
    api(`/fmcg/tracking/people/${encodeURIComponent(selected)}/trail?day=${encodeURIComponent(day)}`)
      .then((res) => live && setTrail(res?.data || null))
      .catch((err) => live && setError(problem(err)));
    return () => {
      live = false;
    };
  }, [selected, day]);

  async function toggle(p: Row) {
    setError('');
    setNotice('');
    try {
      await api(`/fmcg/tracking/people/${encodeURIComponent(p.user_id)}`, { method: 'PUT', body: JSON.stringify({ enabled: !p.enabled }) });
      setNotice(p.enabled ? `${p.name}: location sharing switched off.` : `${p.name}: switched on. They see a notice and must accept it, and it only runs while they are clocked in.`);
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  const markers: MapMarker[] = useMemo(() => {
    const base: MapMarker[] = people
      .filter((p) => p.latitude != null && p.longitude != null && (!selected || p.user_id === selected || !trail))
      .map((p) => ({
        id: p.user_id, lat: p.latitude, lon: p.longitude, label: p.name,
        tone: words(p).tone, selected: p.user_id === selected,
      }));
    const stops: MapMarker[] = (trail?.stops || []).map((s: Row, i: number) => ({
      id: `stop-${i}`, lat: s.latitude, lon: s.longitude, label: `${s.minutes} min stop`, tone: 'stop' as const,
    }));
    return [...base, ...stops];
  }, [people, selected, trail]);
  const path = useMemo(() => (trail?.points || []).map((p: Row) => ({ lat: p.latitude, lon: p.longitude })), [trail]);
  const shown = people.filter((p) => p.enabled || p.last_at || canSwitch);

  if (tab !== 'livemap') return null;
  return (
    <section className="fs-wrap" aria-label="Live staff map">
      <header className="fs-head">
        <div className="fs-head-text">
          <h1>Live staff map</h1>
          <p>
            Where your field staff were last seen. A position arrives only while the person has the ERP open on their phone and is
            clocked in, so this is not live tracking of a locked or closed phone. Refreshes every 20 seconds
            {loadedAt ? ` (updated ${loadedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })})` : ''}.
          </p>
        </div>
      </header>
      {error ? <p className="fs-error" role="alert">{error}</p> : null}
      {notice ? <p className="fs-ok" role="status">{notice}</p> : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, alignItems: 'start' }}>
        <div>
          <TileMap markers={markers} path={path} height={460} label="Staff locations map" onSelect={(id) => !id.startsWith('stop-') && setSelected(id === selected ? '' : id)} />
          <p className="fs-hint" style={{ marginTop: 6 }}>Green = live now. Amber = last seen a while ago. Grey = sharing off or off duty. Red = a stop of 10 minutes or more.</p>
        </div>

        <div>
          <ul className="fs-list" aria-label="People" style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
            {shown.map((p) => {
              const w = words(p);
              return (
                <li key={p.user_id} style={{ padding: '10px 12px', border: `1px solid ${p.user_id === selected ? '#1a7f37' : 'var(--line, #d4e5c4)'}`, borderRadius: 10, background: 'var(--card, #fff)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <div>
                      <strong>{p.name}</strong> <small>· {ROLE_WORDS[p.role] || p.role}</small>
                      <div><small>{w.text}</small></div>
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button type="button" aria-label={`Show ${p.name}'s day`} disabled={!p.enabled && !p.last_at} onClick={() => setSelected(p.user_id === selected ? '' : p.user_id)}>
                        {p.user_id === selected ? 'Hide day' : 'Show day'}
                      </button>
                      {canSwitch ? (
                        <button type="button" aria-label={`${p.enabled ? 'Switch off' : 'Switch on'} location sharing for ${p.name}`} onClick={() => toggle(p)}>
                          {p.enabled ? 'Switch off' : 'Switch on'}
                        </button>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
            {!shown.length ? <li className="fs-hint">No one is sharing yet. {canSwitch ? 'Switch sharing on for a rep or driver.' : 'Ask HR to switch sharing on for your team.'}</li> : null}
          </ul>
        </div>
      </div>

      {selected && trail ? (
        <section aria-label="Day path" style={{ marginTop: 16 }}>
          <h2 style={{ fontSize: 18 }}>
            {trail.name}: {trail.day}
          </h2>
          <label>
            <span style={{ marginRight: 8 }}>Day</span>
            <input type="date" aria-label="Day to show" value={day} max={today()} onChange={(e) => setDay(e.target.value || today())} />
          </label>
          <p>
            <strong>{trail.distance_km} km</strong> covered · {trail.points.length} {trail.points.length === 1 ? 'position' : 'positions'} · {trail.stops.length} {trail.stops.length === 1 ? 'stop' : 'stops'}
          </p>
          {trail.stops.length ? (
            <ul aria-label="Stops">
              {trail.stops.map((s: Row, i: number) => (
                <li key={i}>
                  {clock(s.from)} to {clock(s.to)}: {s.minutes} min at {s.latitude.toFixed(5)}, {s.longitude.toFixed(5)}
                </li>
              ))}
            </ul>
          ) : null}
          {!trail.points.length ? <p className="fs-hint">No positions on this day. Opening someone&apos;s day is recorded in the audit log.</p> : <p className="fs-hint">Opening someone&apos;s day is recorded in the audit log.</p>}
        </section>
      ) : null}
    </section>
  );
}
