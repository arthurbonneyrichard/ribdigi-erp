'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  flushOfflineQueue,
  formatCacheAge,
  formatTimeLeft,
  getCachedCatalogMeta,
  getLastSyncAt,
  getOfflineAuthEnvelope,
  downloadRecoveryPackage,
  importRecoveryPackage,
  isOfflineAuthValid,
  isUnsynced,
  listQueueSnapshots,
  listQueuedSales,
  queueSummary,
  refreshOfflineStatus,
  resendSyncedAfterRestore,
  resolveRecordOnServer,
  restoreQueueSnapshot,
  retryRecord,
  revalidateOfflineAccess,
  type ApiFn,
  type OfflineAuthEnvelope,
  type QueueSummary,
  type QueuedSale,
} from '../lib/posOffline';
import { formatWhen, plainLabel } from '../lib/format';
import { useCompanyFormat } from '../lib/useCompanyFormat';

type ManagerConflict = {
  id: string;
  device_id?: string | null;
  client_request_id?: string | null;
  conflict_code?: string | null;
  message?: string | null;
  offline_total?: number | null;
  local_receipt_number?: string | null;
  allowed_resolutions?: string[];
  created_at?: string | null;
};

const RESOLUTION_LABELS: Record<string, string> = {
  approve_server_price: 'Approve server price',
  approve_outside_window: 'Approve (outside offline window)',
  approve_allocation_override: 'Approve over allocation',
  approve_credit_override: 'Approve over credit limit',
  dismiss: 'Dismiss (keep record)',
};

const STATE_LABELS: Record<string, string> = {
  pending: 'Pending',
  syncing: 'Syncing',
  synced: 'Synced',
  needs_attention: 'Needs attention',
  dismissed: 'Dismissed',
};

export type OfflineStatus = {
  envelope: OfflineAuthEnvelope | null;
  summary: QueueSummary;
  lastSyncAt: string | null;
  provisional: boolean;
};

export default function PosOfflinePanel({
  api,
  online,
  tenantId,
  userId,
  storeId,
  storeLabel,
  canApprove,
  refreshToken,
  onStatus,
  onMessage,
  onError,
}: {
  api: ApiFn;
  online: boolean;
  tenantId: string;
  userId: string;
  storeId: string | null;
  storeLabel?: string;
  canApprove: boolean;
  refreshToken: number;
  onStatus: (status: OfflineStatus) => void;
  onMessage: (text: string) => void;
  onError: (text: string) => void;
}) {
  useCompanyFormat();
  const [envelope, setEnvelope] = useState<OfflineAuthEnvelope | null>(null);
  const [summary, setSummary] = useState<QueueSummary | null>(null);
  const [records, setRecords] = useState<QueuedSale[]>([]);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [catalogAt, setCatalogAt] = useState<string | null>(null);
  const [provisional, setProvisional] = useState(false);
  const [otherDevices, setOtherDevices] = useState(0);
  const [busy, setBusy] = useState<'' | 'sync' | 'revalidate' | 'restore' | 'backup' | 'resend'>('');
  const [open, setOpen] = useState(false);
  const [managerConflicts, setManagerConflicts] = useState<ManagerConflict[]>([]);
  const [snapshots, setSnapshots] = useState<Array<{ id: string; reason: string; created_at: string; count: number }>>(
    []
  );
  const syncLock = useRef(false);

  const reload = useCallback(async () => {
    try {
      const [env, sum, recs, last, meta] = await Promise.all([
        getOfflineAuthEnvelope(),
        queueSummary(userId),
        listQueuedSales(),
        getLastSyncAt(),
        getCachedCatalogMeta(),
      ]);
      setEnvelope(env);
      setSummary(sum);
      setRecords(recs.slice().reverse());
      setLastSyncAt(last);
      setCatalogAt(meta?.cached_at || null);
      onStatus({ envelope: env, summary: sum, lastSyncAt: last, provisional });
    } catch {
      /* IndexedDB unavailable: panel shows nothing queued */
    }
  }, [userId, provisional, onStatus]);

  useEffect(() => {
    void reload();
  }, [reload, refreshToken]);

  const loadManagerConflicts = useCallback(async () => {
    if (!online || !canApprove) {
      setManagerConflicts([]);
      return;
    }
    try {
      const r = (await api('/pos/offline/conflicts')) as { data?: ManagerConflict[] };
      setManagerConflicts(Array.isArray(r?.data) ? r.data : []);
    } catch {
      setManagerConflicts([]);
    }
  }, [api, online, canApprove]);

  const syncNow = useCallback(
    async (opts?: { force?: boolean; quiet?: boolean }) => {
      if (syncLock.current || !tenantId || !userId) return;
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        if (!opts?.quiet) onError('You are offline. Queued sales are kept and will sync when the connection returns.');
        return;
      }
      syncLock.current = true;
      setBusy('sync');
      try {
        let res = await flushOfflineQueue(api, { tenant_id: tenantId, user_id: userId, force: opts?.force });
        if (res.authRequired) {
          onError('Sign in again to sync. Your queued sales are kept on this device.');
          return;
        }
        const status = await refreshOfflineStatus(api, { tenant_id: tenantId, user_id: userId }).catch(() => null);
        if (status) {
          setProvisional(status.provisional);
          setOtherDevices(status.other_devices_pending);
        }
        const after = await queueSummary(userId);
        if (after.pending > 0 && !res.authRequired) {
          const second = await flushOfflineQueue(api, { tenant_id: tenantId, user_id: userId });
          res = {
            ...second,
            synced: res.synced + second.synced,
            needsAttention: second.needsAttention + res.needsAttention,
          };
        }
        const parts: string[] = [];
        if (res.synced) parts.push(`${res.synced} synced`);
        if (res.needsAttention) parts.push(`${res.needsAttention} need attention`);
        if (res.retrying) parts.push(`${res.retrying} will retry`);
        if (res.otherUsers) parts.push(`${res.otherUsers} waiting for another cashier to sign in`);
        if (parts.length && !opts?.quiet) onMessage(`Offline queue: ${parts.join(' · ')}.`);
        else if (res.synced) onMessage(`Synced ${res.synced} offline record(s).`);
        if (res.needsAttention) {
          onError(`${res.needsAttention} offline record(s) need review. Nothing was deleted; see Offline queue.`);
        }
      } catch (err: unknown) {
        onError((err as Error)?.message || 'Sync failed. Queued sales are kept for retry.');
      } finally {
        syncLock.current = false;
        setBusy('');
        await reload();
        await loadManagerConflicts();
      }
    },
    [api, tenantId, userId, onError, onMessage, reload, loadManagerConflicts]
  );

  useEffect(() => {
    if (!online || !tenantId || !userId) return;
    void syncNow({ quiet: true });
    const t = window.setInterval(() => {
      if (navigator.onLine) void syncNow({ quiet: true });
    }, 60000);
    return () => window.clearInterval(t);
  }, [online, tenantId, userId, syncNow]);

  async function revalidate() {
    if (!online) {
      onError('Refreshing offline selling needs a connection.');
      return;
    }
    setBusy('revalidate');
    try {
      await syncNow({ quiet: true });
      const r = await revalidateOfflineAccess(api, {
        tenant_id: tenantId,
        user_id: userId,
        store_id: storeId,
        label: storeLabel,
      });
      onMessage(
        `Offline selling is ready until ${formatWhen(r.envelope.offline_valid_until) || 'the next online check'} · ` +
          `${r.products} products and ${r.customers} customers saved on this device.`
      );
    } catch (err: unknown) {
      onError((err as Error)?.message || 'Could not refresh offline selling');
    } finally {
      setBusy('');
      await reload();
    }
  }

  async function saveBackup() {
    const passphrase = window.prompt('Choose a passphrase for this backup file (8+ characters). You need it to restore.');
    if (!passphrase) return;
    setBusy('backup');
    try {
      const pkg = await downloadRecoveryPackage(passphrase);
      onMessage(`Backup file saved (${pkg.record_count} sale${pkg.record_count === 1 ? '' : 's'}, encrypted). It holds no passwords.`);
    } catch (err: unknown) {
      onError((err as Error)?.message || 'Backup failed');
    } finally {
      setBusy('');
    }
  }

  async function restoreFromFile(file: File | null) {
    if (!file) return;
    setBusy('restore');
    try {
      const raw = JSON.parse(await file.text());
      const passphrase =
        raw?.version === 2 ? window.prompt('Enter the passphrase for this backup file') || '' : undefined;
      const r = await importRecoveryPackage(raw, { tenant_id: tenantId, passphrase });
      onMessage(
        `Restored ${r.imported} record(s), ${r.skipped} already here. A safety copy of the previous queue was kept. ` +
          'Use Sync now to send them.'
      );
    } catch (err: unknown) {
      onError((err as Error)?.message || 'Restore failed. Your current queue was not changed.');
    } finally {
      setBusy('');
      await reload();
    }
  }

  async function resendAfterServerRestore() {
    if (!window.confirm('Re-send synced sales kept on this device? Use this after the server was restored from a backup. Duplicates are prevented by request id.')) {
      return;
    }
    setBusy('resend');
    try {
      const n = await resendSyncedAfterRestore(tenantId);
      onMessage(`${n} synced record(s) queued to re-send.`);
    } finally {
      setBusy('');
      await syncNow();
    }
  }

  async function resolve(rec: { sync_event_id?: string | null } & Partial<QueuedSale>, action: string) {
    const note = window.prompt(`${RESOLUTION_LABELS[action] || action}: reason (required)`);
    if (!note || note.trim().length < 3) return;
    try {
      if (rec.id && rec.client_request_id && rec.payload) {
        await resolveRecordOnServer(api, rec as QueuedSale, action, note.trim());
      } else if (rec.sync_event_id) {
        await api(`/pos/offline/conflicts/${rec.sync_event_id}/resolve`, {
          method: 'POST',
          body: JSON.stringify({ action, note: note.trim() }),
        });
      }
      onMessage(action === 'dismiss' ? 'Dismissed. The record is kept and was not posted.' : 'Approved. Syncing…');
    } catch (err: unknown) {
      onError((err as Error)?.message || 'Could not record the resolution');
    }
    await syncNow({ force: false, quiet: true });
  }

  async function loadSnapshots() {
    setSnapshots(await listQueueSnapshots().catch(() => []));
  }

  async function restoreSnapshot(id: string) {
    try {
      const r = await restoreQueueSnapshot(id);
      onMessage(`Copy restored: ${r.imported} sale${r.imported === 1 ? '' : 's'} added, ${r.skipped} already here.`);
    } catch (err: unknown) {
      onError((err as Error)?.message || 'Could not restore the safety copy');
    }
    await reload();
  }

  const valid = isOfflineAuthValid(envelope);
  const unsynced = summary ? summary.pending + summary.syncing + summary.needs_attention : 0;
  const authText = !envelope?.grant_id
    ? 'This device is not ready for offline selling.'
    : valid
      ? `Offline selling is ready · ${formatTimeLeft(envelope.offline_valid_until)}`
      : envelope.revoked_at
        ? 'Offline selling was turned off on this device.'
        : 'Offline selling on this device has expired.';
  const quiet = online && unsynced === 0 && !provisional && otherDevices === 0 && (!envelope?.grant_id || valid);
  const summaryLabel = !online
    ? 'You are offline'
    : unsynced > 0
      ? `${unsynced} saved sale${unsynced === 1 ? '' : 's'} to send`
      : 'Offline selling';

  return (
    <details className="tpos-more tpos-offline-tools" open={!quiet || undefined}>
      <summary>{summaryLabel}</summary>
      <div className="tpos-more-body" aria-live="polite">
      <p className="muted" style={{ margin: 0, flexBasis: '100%' }}>
        {authText}
        {lastSyncAt ? ` Last sent ${formatWhen(lastSyncAt) || formatCacheAge(lastSyncAt)}.` : ' Nothing has been sent from this device yet.'}
        {summary?.needs_attention ? ` ${summary.needs_attention} need a manager.` : ''}
        {provisional || otherDevices > 0
          ? ` ${otherDevices} sale${otherDevices === 1 ? '' : 's'} on other devices are not here yet.`
          : ''}
      </p>
      {!online ? (
        <p className="muted" style={{ margin: 0, flexBasis: '100%' }}>
          Prices and stock are from the last time this device was online
          {catalogAt ? ` (${formatCacheAge(catalogAt)})` : ''}.
        </p>
      ) : null}
      {online && envelope?.grant_id && !valid && unsynced > 0 ? (
        <p className="muted" style={{ margin: 0, flexBasis: '100%' }}>
          Saved sales can be sent now. Refresh offline selling only if you need to sell while offline again.
        </p>
      ) : null}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="tpos-btn" onClick={revalidate} disabled={!online || !!busy}>
          {busy === 'revalidate' ? 'Refreshing…' : 'Refresh offline selling'}
        </button>
        <button type="button" className="tpos-btn" onClick={() => syncNow({ force: true })} disabled={!online || !!busy}>
          {busy === 'sync' ? 'Sending…' : 'Send saved sales'}
        </button>
        <button type="button" className="tpos-btn tpos-btn-quiet" onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide saved sales' : 'Saved sales'}
        </button>
      </div>
      {open ? (
        <div className="tpos-recovery" style={{ display: 'grid', gap: 8, marginTop: 8 }}>
          {records.length === 0 ? <p className="muted">No saved sales on this device.</p> : null}
          {records.slice(0, 50).map((rec) => (
            <div key={rec.id} style={{ borderTop: '1px solid var(--border, #ddd)', paddingTop: 6 }}>
              <div>
                <strong>{rec.local_receipt_number || rec.client_request_id}</strong>
                {rec.kind === 'quote' ? ' · quote' : ''} · {STATE_LABELS[rec.state] || plainLabel(rec.state)}
                {rec.server_reference ? ` → ${rec.server_reference}` : ''}
                {typeof rec.payload?.total === 'number' ? ` · ${Number(rec.payload.total).toFixed(2)}` : ''}
                {' · '}
                {formatWhen(rec.created_at) || '—'}
                {rec.user_id && rec.user_id !== userId ? ' · another cashier' : ''}
              </div>
              {rec.last_error_message ? <div className="muted">{rec.last_error_message}</div> : null}
              {isUnsynced(rec.state) && rec.user_id === userId ? (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  <button
                    type="button"
                    className="tpos-btn tpos-btn-quiet"
                    disabled={!online}
                    onClick={async () => {
                      await retryRecord(rec.id);
                      await syncNow({ force: true });
                    }}
                  >
                    Retry
                  </button>
                  {rec.state === 'needs_attention' && canApprove
                    ? (rec.allowed_resolutions && rec.allowed_resolutions.length
                        ? rec.allowed_resolutions
                        : rec.sync_event_id
                          ? ['dismiss']
                          : []
                      ).map((action) => (
                        <button
                          key={action}
                          type="button"
                          className="tpos-btn tpos-btn-quiet"
                          disabled={!online}
                          onClick={() => resolve(rec, action)}
                        >
                          {RESOLUTION_LABELS[action] || action}
                        </button>
                      ))
                    : null}
                  {rec.state === 'needs_attention' && !canApprove ? (
                    <span className="muted">A manager can approve or dismiss this from their POS.</span>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
          {canApprove && managerConflicts.length ? (
            <div>
              <strong>Needs a manager (all devices in your stores)</strong>
              {managerConflicts.map((c) => (
                <div key={c.id} style={{ marginTop: 4 }}>
                  {c.local_receipt_number || c.client_request_id}
                  {c.created_at ? ` · ${formatWhen(c.created_at)}` : ''}
                  {typeof c.offline_total === 'number' ? ` · ${Number(c.offline_total).toFixed(2)}` : ''}
                  <div className="muted">{c.message}</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(c.allowed_resolutions || ['dismiss']).map((action) => (
                      <button
                        key={action}
                        type="button"
                        className="tpos-btn tpos-btn-quiet"
                        disabled={!online}
                        onClick={() => resolve({ sync_event_id: c.id }, action)}
                      >
                        {RESOLUTION_LABELS[action] || action}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" className="tpos-btn" onClick={saveBackup} disabled={!!busy}>
              Save backup file
            </button>
            <label className="tpos-btn">
              Restore from backup
              <input
                type="file"
                accept="application/json,.json"
                aria-label="Restore offline queue from a backup file"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  restoreFromFile(f).finally(() => {
                    e.target.value = '';
                  });
                }}
              />
            </label>
            <button type="button" className="tpos-btn tpos-btn-quiet" onClick={resendAfterServerRestore} disabled={!online || !!busy}>
              Send sales again after a restore
            </button>
            <button type="button" className="tpos-btn tpos-btn-quiet" onClick={loadSnapshots}>
              Saved copies
            </button>
          </div>
          <p className="muted" style={{ margin: 0 }}>
            Restoring a backup only adds sales that are missing here. Sending sales does not need a restore.
          </p>
          {snapshots.map((s) => (
            <div key={s.id}>
              {formatWhen(s.created_at) || '—'} · {plainLabel(s.reason) || s.reason} · {s.count} sale{s.count === 1 ? '' : 's'}{' '}
              <button type="button" className="tpos-btn tpos-btn-quiet" onClick={() => restoreSnapshot(s.id)}>
                Merge back
              </button>
            </div>
          ))}
        </div>
      ) : null}
      </div>
    </details>
  );
}
