'use client';

/**
 * Staff map drawn with Leaflet on OpenStreetMap tiles. No key, no billing. OpenStreetMap's public tile
 * servers are fine for a manager watching a handful of people; a busy company should set
 * NEXT_PUBLIC_MAP_TILE_URL to its own tile provider (same {z}/{x}/{y} format).
 */

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { MapMarker, MapPoint } from './TileMap';

const TONES: Record<string, string> = { live: '#1a7f37', stale: '#b7791f', none: '#6b7280', stop: '#b42318' };
const TILES = process.env.NEXT_PUBLIC_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

export default function StaffMap({
  markers,
  path,
  height = 420,
  onSelect,
  label = 'Map',
}: {
  markers: MapMarker[];
  path?: MapPoint[];
  height?: number;
  onSelect?: (id: string) => void;
  label?: string;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { center: [5.6, -0.19], zoom: 11 });
    L.tileLayer(TILES, { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      layer.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    const group = layer.current;
    if (!m || !group) return;
    group.clearLayers();
    const points: L.LatLngTuple[] = [];
    if (path && path.length > 1) {
      const line = path.map((p) => [p.lat, p.lon] as L.LatLngTuple);
      L.polyline(line, { color: '#1d4ed8', weight: 4, opacity: 0.85 }).addTo(group);
      points.push(...line);
    }
    markers.forEach((mk) => {
      const dot = L.circleMarker([mk.lat, mk.lon], {
        radius: mk.selected ? 11 : 8,
        color: '#ffffff',
        weight: 3,
        fillColor: TONES[mk.tone || 'live'],
        fillOpacity: 1,
      }).addTo(group);
      dot.bindTooltip(mk.label, { permanent: !mk.id.startsWith('stop-'), direction: 'top', offset: [0, -8] });
      dot.on('click', () => select.current?.(mk.id));
      points.push([mk.lat, mk.lon]);
    });
    if (points.length) m.fitBounds(L.latLngBounds(points), { padding: [50, 50], maxZoom: 16 });
  }, [markers, path]);

  return (
    <div
      ref={box}
      role="img"
      aria-label={label}
      style={{ width: '100%', height, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--line, #d4e5c4)', zIndex: 0 }}
    />
  );
}
