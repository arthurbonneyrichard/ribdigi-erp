'use client';

import { useEffect } from 'react';

/** Stage 163 P1 — register static-only service worker (never caches /api/v1/*). */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Registration failure must not block the app.
    });
  }, []);
  return null;
}
