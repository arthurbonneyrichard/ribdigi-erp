'use client';

import { useEffect } from 'react';

/** Stage 163 P1 / Stage 168 W1 — register static-only SW (never caches /api/v1/*). */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Registration failure must not block the app.
    });
    // Remote wipe push messages (PARTIAL) — listen after SW register.
    let unlisten: (() => void) | undefined;
    void import('../lib/offlinePush')
      .then(({ listenForRemoteWipePushMessages, registerOfflinePushSubscription }) => {
        unlisten = listenForRemoteWipePushMessages();
        void registerOfflinePushSubscription();
      })
      .catch(() => {
        /* push optional */
      });
    return () => {
      if (unlisten) unlisten();
    };
  }, []);
  return null;
}
