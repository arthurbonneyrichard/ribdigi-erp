'use client';

/**
 * Shows what this device is holding for the FMCG screens: how many items wait to be sent, which were
 * refused and why. Sends on its own when the connection returns, and on demand. A screen calls
 * `bump()` (via the `refresh` prop) after queueing something.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { discard, listQueue, retry, syncQueue, type QueuedAction } from '../lib/fmcgOffline';

const KIND_WORDS: Record<string, string> = { shelf_audit: 'Shelf audit', competitor_price: 'Competitor price', complaint: 'Complaint', pod: 'Proof of delivery' };

export default function FmcgOfflineBar({ tenant, tick, onSynced }: { tenant: string; tick: number; onSynced?: () => void }) {
  const [items, setItems] = useState<QueuedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(true);
  const [note, setNote] = useState('');

  const reload = useCallback(async () => {
    if (tenant) setItems(await listQueue(tenant));
  }, [tenant]);

  const send = useCallback(async () => {
    if (!tenant || busy) return;
    setBusy(true);
    setNote('');
    try {
      const s = await syncQueue(tenant);
      if (s.saved) setNote(`${s.saved} sent.`);
      if (s.saved || s.duplicates) onSynced?.();
    } finally {
      setBusy(false);
      await reload();
    }
  }, [tenant, busy, reload, onSynced]);

  useEffect(() => {
    reload();
  }, [reload, tick]);

  useEffect(() => {
    setOnline(typeof navigator === 'undefined' ? true : navigator.onLine !== false);
    const up = () => { setOnline(true); send(); };
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    const timer = window.setInterval(() => { if (navigator.onLine !== false) send(); }, 60000);
    return () => { window.removeEventListener('online', up); window.removeEventListener('offline', down); window.clearInterval(timer); };
  }, [send]);

  const waiting = items.filter((i) => !i.error);
  const failed = items.filter((i) => i.error);
  if (online && !items.length && !note) return null;

  return (
    <section className="fs-box" aria-label="Offline work">
      {!online ? <div className="fs-banner" role="status">You are offline. What you save is kept on this device and sent when you are back online.</div> : null}
      {waiting.length ? (
        <p>
          <strong>{waiting.length}</strong> waiting to be sent, saved on this device only.{' '}
          <button type="button" disabled={busy || !online} onClick={send} aria-label="Send saved work now">{busy ? 'Sending...' : 'Send now'}</button>
        </p>
      ) : null}
      {note ? <p role="status">{note}</p> : null}
      {failed.length ? (
        <>
          <div className="fs-banner bad" role="alert">{failed.length} could not be saved by the server. Fix or discard them.</div>
          <table>
            <thead><tr><th>What</th><th>Taken</th><th>Why not</th><th /></tr></thead>
            <tbody>
              {failed.map((f) => (
                <tr key={f.ref}>
                  <td>{KIND_WORDS[f.kind]}: {f.label}</td><td>{f.captured_at.slice(0, 16).replace('T', ' ')}</td><td>{f.error}</td>
                  <td>
                    <button type="button" onClick={async () => { await retry(f); await reload(); send(); }} aria-label={`Send ${f.label} again`}>Try again</button>{' '}
                    <button type="button" className="fs-danger" onClick={async () => { if (window.confirm('Discard this? It will be lost.')) { await discard(f.ref); await reload(); } }} aria-label={`Discard ${f.label}`}>Discard</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
      <p className="fs-muted">Saved work lives only in this browser. Clearing browser data or using another browser or device loses anything not yet sent.</p>
    </section>
  );
}
