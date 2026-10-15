'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  flushOfflineQueue,
  formatCacheAge,
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
  restoreQueuedSalesFromTill,
  revalidateOfflineAccess,
  type ApiFn,
  type OfflineAuthEnvelope,
  type QueueSummary,
  type QueuedSale,
} from '../lib/posOffline';
import {
  describePrepareFailure,
  noteQueue,
  noteSyncEnd,
  noteSyncStart,
  offlineSellingStatus,
} from '../lib/connectivity';
import { formatMoney, formatWhen, plainLabel } from '../lib/format';
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
  preparing = false,
  prepareFailure = '',
  embedded = false,
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
  preparing?: boolean;
  prepareFailure?: string;
  /** Render the panel body only, for the Online status button. */
  embedded?: boolean;
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
  const [localFailure, setLocalFailure] = useState('');
  const [open, setOpen] = useState(false);
  const [managerConflicts, setManagerConflicts] = useState<ManagerConflict[]>([]);
  const [snapshots, setSnapshots] = useState<Array<{ id: string; reason: string; created_at: string; count: number }>>(
    []
  );
  const syncLock = useRef(false);

  const reload = useCallback(async () => {
    try {
      if (tenantId && userId) {
        await restoreQueuedSalesFromTill(tenantId, userId).catch(() => 0);
      }
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
      noteQueue(sum.pending + sum.syncing + sum.needs_attention, last);
      onStatus({ envelope: env, summary: sum, lastSyncAt: last, provisional });
    } catch {
      /* IndexedDB unavailable: panel shows nothing queued */
    }
  }, [userId, tenantId, provisional, onStatus]);

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
      syncLock.current = true;
      setBusy('sync');
      noteSyncStart();
      let problem = '';
      let reportFailure = false;
      try {
        const { probeApi } = await import('../lib/connectivity');
        const phase = await probeApi();
        if (phase !== 'online') {
          if (!opts?.quiet) {
            problem =
              phase === 'offline'
                ? 'No internet connection. Queued sales stay on this device.'
                : 'The server did not respond. Queued sales stay on this device.';
            reportFailure = true;
            onError(problem);
          }
          return;
        }
        let res = await flushOfflineQueue(api, { tenant_id: tenantId, user_id: userId, force: opts?.force });
        if (res.authRequired) {
          problem = 'Sign in again to sync. Your queued sales are kept on this device.';
          reportFailure = true;
          onError(problem);
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
        if (res.needsAttention) {
          problem =
            res.needsAttention === 1
              ? '1 saved sale needs a manager. It stays on this device.'
              : `${res.needsAttention} saved sales need a manager. They stay on this device.`;
          reportFailure = true;
          if (!opts?.quiet) onError(problem);
        }
        if (!opts?.quiet) {
          const parts: string[] = [];
          if (res.synced) parts.push(`${res.synced} synced`);
          if (res.needsAttention) parts.push(`${res.needsAttention} need attention`);
          if (res.retrying) parts.push(`${res.retrying} will retry`);
          if (res.otherUsers) parts.push(`${res.otherUsers} waiting for another cashier to sign in`);
          if (parts.length) onMessage(`Offline queue: ${parts.join(' · ')}.`);
        } else if (res.synced) {
          onMessage(res.synced === 1 ? '1 saved sale was sent.' : `${res.synced} saved sales were sent.`);
        }
      } catch (err: unknown) {
        if (!opts?.quiet) {
          problem = (err as Error)?.message || 'Sync failed. Queued sales are kept for retry.';
          reportFailure = true;
          onError(problem);
        }
      } finally {
        noteSyncEnd(reportFailure ? problem || undefined : undefined);
        syncLock.current = false;
        setBusy('');
        await reload();
        await loadManagerConflicts();
      }
    },
    [api, tenantId, userId, onError, onMessage, reload, loadManagerConflicts]
  );

  async function revalidate() {
    if (!online) {
      onError('Refreshing offline selling needs a connection.');
      return;
    }
    setBusy('revalidate');
    setLocalFailure('');
    try {
      await syncNow({ quiet: true });
      const r = await revalidateOfflineAccess(api, {
        tenant_id: tenantId,
        user_id: userId,
        store_id: storeId,
        label: storeLabel,
      });
      setLocalFailure('');
      onMessage(
        `Offline selling is ready until ${formatWhen(r.envelope.offline_valid_until) || 'the next online check'} · ` +
          `${r.products} products and ${r.customers} customers saved on this device.`
      );
    } catch (err: unknown) {
      const env = await getOfflineAuthEnvelope().catch(() => null);
      const text = describePrepareFailure(err, Boolean(env?.grant_id));
      setLocalFailure(text);
      onError(text);
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
          'They will be sent automatically.'
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
  const authText = offlineSellingStatus({
    grantId: envelope?.grant_id,
    catalogSaved: Boolean(catalogAt),
    valid,
    revoked: Boolean(envelope?.revoked_at),
    online,
    preparing: preparing || busy === 'revalidate',
    failure: prepareFailure || localFailure,
  });
  const needsManager = (summary?.needs_attention || 0) > 0 || managerConflicts.length > 0;
  const quiet = online && !needsManager && !provisional && otherDevices === 0 && (!envelope?.grant_id || valid);
  const waiting =
    unsynced > 0 ? `${unsynced} saved sale${unsynced === 1 ? '' : 's'} waiting` : '';
  const summaryLabel = !online
    ? waiting
      ? `You are offline · ${waiting}`
      : 'You are offline'
    : needsManager
      ? 'A saved sale needs a manager'
      : unsynced > 0
        ? `Sending ${unsynced === 1 ? '1 saved sale' : `${unsynced} saved sales`}`
        : 'Offline selling';
  const [userOpen, setUserOpen] = useState(false);
  const queuedRef = useRef(0);
  const wasOnline = useRef(online);
  useEffect(() => {
    const cameOnline = online && !wasOnline.current;
    wasOnline.current = online;
    const grew = unsynced > queuedRef.current;
    queuedRef.current = unsynced;
    if (!online || !tenantId || !userId || unsynced <= 0) return;
    if (cameOnline || grew) void syncNow({ quiet: true });
  }, [online, unsynced, tenantId, userId, syncNow]);

  useEffect(() => {
    if (!online || !tenantId || !userId || unsynced <= 0) return;
    const t = window.setInterval(() => {
      void syncNow({ quiet: true });
    }, 15000);
    return () => window.clearInterval(t);
  }, [online, tenantId, userId, unsynced, syncNow]);

  const body = (
      <div className="tpos-more-body tpos-offline-body" aria-live="polite">
      <p className="muted tpos-offline-status">
        {authText}
        {unsynced > 0
          ? ` · ${unsynced} saved sale${unsynced === 1 ? ' is' : 's are'} still on this device.`
          : lastSyncAt
            ? ` · Last sent ${formatWhen(lastSyncAt) || formatCacheAge(lastSyncAt)}.`
            : ' · Nothing has been sent from this device yet.'}
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
          Saved sales are sent automatically. Refresh offline selling only if you need to sell while offline again.
        </p>
      ) : null}
      <div className="tpos-offline-actions">
        <button type="button" className="tpos-btn" onClick={revalidate} disabled={!online || !!busy}>
          {busy === 'revalidate' ? 'Refreshing…' : 'Refresh offline selling'}
        </button>
        <button type="button" className="tpos-btn tpos-btn-quiet" onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide saved sales' : waiting ? `Saved sales (${unsynced})` : 'Saved sales'}
        </button>
      </div>
      {online && unsynced > 0 ? (
        <p className="muted" style={{ margin: '6px 0 0' }}>
          Saved sales are sent automatically when the server answers. You do not need to press anything.
        </p>
      ) : null}
      {open ? (
        <div className="tpos-recovery tpos-offline-list">
          {records.length === 0 ? <p className="muted">No saved sales are waiting on this device, so charge the next cart when you are ready.</p> : null}
          {records.slice(0, 50).map((rec) => (
            <div className="tpos-offline-sale" key={rec.id}>
              <div>
                <strong>{rec.local_receipt_number || rec.client_request_id}</strong>
                {rec.kind === 'quote' ? ' · quote' : ''} · {STATE_LABELS[rec.state] || plainLabel(rec.state)}
                {rec.server_reference ? ` → ${rec.server_reference}` : ''}
                {rec.user_id && rec.user_id !== userId ? ' · another cashier' : ''}
              </div>
              <div className="tpos-offline-sale-meta">
                {typeof rec.payload?.total === 'number' ? formatMoney(rec.payload.total) : ''}
              </div>
              <div className="tpos-offline-sale-meta">{formatWhen(rec.created_at) || '—'}</div>
              {rec.last_error_message ? <div className="muted tpos-offline-sale-span">{rec.last_error_message}</div> : null}
              {isUnsynced(rec.state) && rec.user_id === userId ? (
                <div className="tpos-offline-sale-span" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
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
                  {typeof c.offline_total === 'number' ? ` · ${formatMoney(c.offline_total)}` : ''}
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
  );

  if (embedded) return body;

  return (
    <details
      className={`tpos-more tpos-offline-tools${!online ? ' is-offline' : ''}${unsynced > 0 ? ' has-queue' : ''}`}
      open={!quiet || userOpen}
      onToggle={(event) => {
        if (quiet) setUserOpen(event.currentTarget.open);
      }}
    >
      <summary>{summaryLabel}</summary>
      {body}
    </details>
  );
}
