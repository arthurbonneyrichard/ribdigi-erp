'use client';

/**
 * A small street map with no map library: OpenStreetMap tiles as images, with markers and a path drawn
 * over them. Fits itself to what you give it; zoom with + and -. The tiles are OpenStreetMap's public
 * servers, which are fine for a manager looking at a handful of people. A busy company should point
 * `tileUrl` at its own tile provider.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

export type MapPoint = { lat: number; lon: number };
export type MapMarker = MapPoint & { id: string; label: string; tone?: 'live' | 'stale' | 'none' | 'stop'; selected?: boolean };

const TILE = 256;
const DEFAULT_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

function worldX(lon: number, z: number) {
  return ((lon + 180) / 360) * TILE * 2 ** z;
}
function worldY(lat: number, z: number) {
  const r = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * TILE * 2 ** z;
}

const TONES: Record<string, string> = { live: '#1a7f37', stale: '#8a6d00', none: '#6b7280', stop: '#b42318' };

export default function TileMap({
  markers,
  path,
  height = 420,
  onSelect,
  tileUrl = DEFAULT_TILES,
  label = 'Map',
}: {
  markers: MapMarker[];
  path?: MapPoint[];
  height?: number;
  onSelect?: (id: string) => void;
  tileUrl?: string;
  label?: string;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(640);
  const [zoomShift, setZoomShift] = useState(0);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => setWidth(Math.max(280, Math.round(el.clientWidth || 640)));
    read();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const all: MapPoint[] = useMemo(() => [...markers, ...(path || [])], [markers, path]);
  const fitKey = all.map((p) => `${p.lat.toFixed(4)},${p.lon.toFixed(4)}`).join('|');
  useEffect(() => setZoomShift(0), [fitKey]);

  const view = useMemo(() => {
    if (!all.length) return { z: 3, cx: worldX(-0.2, 3), cy: worldY(5.6, 3) };
    const lats = all.map((p) => p.lat);
    const lons = all.map((p) => p.lon);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
    let fit = 16;
    for (let z = 17; z >= 3; z--) {
      const w = worldX(maxLon, z) - worldX(minLon, z);
      const h = worldY(minLat, z) - worldY(maxLat, z);
      if (w <= width - 90 && h <= height - 90) {
        fit = z;
        break;
      }
      fit = 3;
    }
    const z = Math.max(3, Math.min(18, fit + zoomShift));
    return { z, cx: (worldX(minLon, z) + worldX(maxLon, z)) / 2, cy: (worldY(minLat, z) + worldY(maxLat, z)) / 2 };
  }, [all, width, height, zoomShift]);

  const left = view.cx - width / 2;
  const top = view.cy - height / 2;
  const n = 2 ** view.z;
  const tiles: { key: string; src: string; x: number; y: number }[] = [];
  for (let tx = Math.floor(left / TILE); tx <= Math.floor((left + width) / TILE); tx++) {
    for (let ty = Math.floor(top / TILE); ty <= Math.floor((top + height) / TILE); ty++) {
      if (ty < 0 || ty >= n) continue;
      const wrapped = ((tx % n) + n) % n;
      tiles.push({
        key: `${view.z}/${tx}/${ty}`,
        src: tileUrl.replace('{z}', String(view.z)).replace('{x}', String(wrapped)).replace('{y}', String(ty)),
        x: tx * TILE - left,
        y: ty * TILE - top,
      });
    }
  }
  const px = (p: MapPoint) => ({ x: worldX(p.lon, view.z) - left, y: worldY(p.lat, view.z) - top });
  const line = (path || []).map((p) => {
    const q = px(p);
    return `${q.x.toFixed(1)},${q.y.toFixed(1)}`;
  }).join(' ');

  return (
    <div ref={box} role="img" aria-label={label} style={{ position: 'relative', width: '100%', height, overflow: 'hidden', borderRadius: 10, background: '#e5e3df', border: '1px solid var(--line, #d4e5c4)' }}>
      {tiles.map((t) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={t.key} src={t.src} alt="" width={TILE} height={TILE} draggable={false} style={{ position: 'absolute', left: t.x, top: t.y, userSelect: 'none' }} />
      ))}
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }} aria-hidden={false}>
        {line && (path || []).length > 1 ? <polyline points={line} fill="none" stroke="#1d4ed8" strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" opacity={0.85} /> : null}
        {markers.map((mk) => {
          const q = px(mk);
          const color = TONES[mk.tone || 'live'];
          return (
            <g key={mk.id} transform={`translate(${q.x},${q.y})`} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={() => onSelect?.(mk.id)} role={onSelect ? 'button' : undefined} aria-label={mk.label}>
              <circle r={mk.selected ? 11 : 8} fill={color} stroke="#fff" strokeWidth={3} />
              <text y={-14} textAnchor="middle" fontSize={12} fontWeight={600} stroke="#fff" strokeWidth={3} paintOrder="stroke" fill="#10211B">
                {mk.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ position: 'absolute', top: 8, right: 8, display: 'grid', gap: 4 }}>
        <button type="button" aria-label="Zoom in" onClick={() => setZoomShift((s) => Math.min(s + 1, 6))} style={{ width: 32, height: 32 }}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => setZoomShift((s) => Math.max(s - 1, -6))} style={{ width: 32, height: 32 }}>−</button>
        <button type="button" aria-label="Fit everyone on the map" onClick={() => setZoomShift(0)} style={{ width: 32, height: 32 }}>⤢</button>
      </div>
      <small style={{ position: 'absolute', bottom: 2, right: 6, background: 'rgba(255,255,255,.8)', padding: '0 4px', borderRadius: 3 }}>
        © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors
      </small>
    </div>
  );
}
