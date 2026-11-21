'use client';

/**
 * The same map as TileMap, drawn by Google Maps (the Maps JavaScript API). It needs the company's own
 * API key in NEXT_PUBLIC_GOOGLE_MAPS_API_KEY at build time. Google bills the key, and its terms allow
 * their maps only through this API (never by pulling their tile images directly), so this is the way to
 * use Google. StaffMap falls back to TileMap when there is no key or Google cannot load.
 */

import { useEffect, useRef, useState } from 'react';
import type { MapMarker, MapPoint } from './TileMap';

type G = any; // the Google Maps API ships its own loader; we only use a handful of calls

const TONES: Record<string, string> = { live: '#1a7f37', stale: '#b7791f', none: '#6b7280', stop: '#b42318' };

let loader: Promise<G> | null = null;

export function mapsKey(): string {
  return (process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || '').trim();
}

function loadGoogle(key: string): Promise<G> {
  const w = window as unknown as { google?: G };
  if (w.google?.maps) return Promise.resolve(w.google);
  if (loader) return loader;
  loader = new Promise<G>((resolve, reject) => {
    const cb = `__ribdigiMapsReady${Date.now()}`;
    (window as unknown as Record<string, unknown>)[cb] = () => resolve((window as unknown as { google: G }).google);
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&loading=async&callback=${cb}`;
    script.async = true;
    script.onerror = () => {
      loader = null;
      reject(new Error('Google Maps could not load'));
    };
    document.head.appendChild(script);
  });
  return loader;
}

export default function GoogleMap({
  markers,
  path,
  height = 420,
  onSelect,
  label = 'Map',
  onFail,
}: {
  markers: MapMarker[];
  path?: MapPoint[];
  height?: number;
  onSelect?: (id: string) => void;
  label?: string;
  onFail?: () => void;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<G>(null);
  const drawn = useRef<G[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let live = true;
    loadGoogle(mapsKey())
      .then((google) => {
        if (!live || !box.current) return;
        map.current = new google.maps.Map(box.current, {
          center: { lat: 5.6, lng: -0.19 },
          zoom: 11,
          streetViewControl: false,
          mapTypeControl: true,
          fullscreenControl: true,
        });
        setReady(true);
      })
      .catch(() => onFail?.());
    // Google reports a bad or restricted key here; show the fallback map instead of a grey box.
    (window as unknown as { gm_authFailure?: () => void }).gm_authFailure = () => onFail?.();
    return () => {
      live = false;
    };
  }, [onFail]);

  useEffect(() => {
    const google = (window as unknown as { google?: G }).google;
    if (!ready || !google || !map.current) return;
    drawn.current.forEach((item) => item.setMap(null));
    drawn.current = [];
    const bounds = new google.maps.LatLngBounds();
    if (path && path.length > 1) {
      const line = new google.maps.Polyline({
        path: path.map((p) => ({ lat: p.lat, lng: p.lon })),
        strokeColor: '#1d4ed8', strokeOpacity: 0.85, strokeWeight: 4, map: map.current,
      });
      drawn.current.push(line);
      path.forEach((p) => bounds.extend({ lat: p.lat, lng: p.lon }));
    }
    markers.forEach((mk) => {
      const marker = new google.maps.Marker({
        position: { lat: mk.lat, lng: mk.lon },
        map: map.current,
        title: mk.label,
        label: { text: mk.label, className: 'ribdigi-gm-label', fontSize: '12px', fontWeight: '600', color: '#10211B' },
        zIndex: mk.selected ? 10 : 1,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: mk.selected ? 11 : 8,
          fillColor: TONES[mk.tone || 'live'],
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 3,
          labelOrigin: new google.maps.Point(0, -2.2),
        },
      });
      if (onSelect) marker.addListener('click', () => onSelect(mk.id));
      drawn.current.push(marker);
      bounds.extend({ lat: mk.lat, lng: mk.lon });
    });
    if (!bounds.isEmpty()) {
      map.current.fitBounds(bounds, 60);
      // One point (or several on top of each other) must not zoom to rooftop level.
      google.maps.event.addListenerOnce(map.current, 'idle', () => {
        if ((map.current.getZoom() || 0) > 17) map.current.setZoom(16);
      });
    }
  }, [ready, markers, path, onSelect]);

  return <div ref={box} role="img" aria-label={label} style={{ width: '100%', height, borderRadius: 10, overflow: 'hidden', background: '#e5e3df', border: '1px solid var(--line, #d4e5c4)' }} />;
}
