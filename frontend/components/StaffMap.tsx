'use client';

/** Google Maps when the company has set its API key; otherwise (or if Google fails to load) OpenStreetMap. */

import { useCallback, useState } from 'react';
import GoogleMap, { mapsKey } from './GoogleMap';
import TileMap, { type MapMarker, type MapPoint } from './TileMap';

export default function StaffMap(props: {
  markers: MapMarker[];
  path?: MapPoint[];
  height?: number;
  onSelect?: (id: string) => void;
  label?: string;
}) {
  const [failed, setFailed] = useState(false);
  const onFail = useCallback(() => setFailed(true), []);
  if (mapsKey() && !failed) return <GoogleMap {...props} onFail={onFail} />;
  return <TileMap {...props} />;
}
