'use client';

import { useEffect, useState } from 'react';
import { api, getAccessToken } from '../../../lib/api';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type BackupJob = {
  id: string;
  filename?: string;
  status?: string;
  size_bytes?: number;
  checksum_sha256?: string;
  created_at?: string;
  record_counts?: Record<string, number>;
  error_message?: string;
};

export default function Page() {
  const [rows, setRows] = useState<BackupJob[]>([]);
  const [backupManageFilter, setBackupManageFilter] = useState<
    'all' | 'pending' | 'completed' | 'failed' | 'restoring'
  >('all');
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [dryReport, setDryReport] = useState<any>(null);
  const [backupNotes, setBackupNotes] = useState('');
  const [restoreJob, setRestoreJob] = useState<BackupJob | null>(null);
  const [confirmText, setConfirmText] = useState('');

  async function refresh() {
    const [list, cfg] = await Promise.all([api('/backup'), api('/backup/settings')]);
    setRows(list.data || []);
    setSettings(cfg.data);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, []);

  const managedBackups = rows.filter((r) => {
    if (backupManageFilter === 'all') return true;
    return (r.status || 'pending') === backupManageFilter;
  });

  function startWork(action: string) {
    setError('');
    setMessage('');
    setBusy(true);
    setBusyAction(action);
  }

  function endWork() {
    setBusy(false);
    setBusyAction('');
  }

  async function createBackup() {
    startWork('create');
    try {
      const r = await api('/backup', {
        method: 'POST',
        body: JSON.stringify({ notes: backupNotes.trim() || null }),
      });
      setMessage(
        r.data?.status === 'completed'
          ? (r.message || 'Backup completed')
          : (r.message || `Backup ${r.data?.status || 'recorded'}; not complete yet`)
      );
      setBackupNotes('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      endWork();
    }
  }

  async function saveSettings() {
    setError('');
    try {
      const r = await api('/backup/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          enabled: !!settings.enabled,
          frequency: settings.frequency,
          retention_count: Number(settings.retention_count),
          hour_utc: Number(settings.hour_utc),
        }),
      });
      setSettings(r.data);
      setMessage('Settings saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadBackup(id: string, filename: string) {
    setError('');
    try {
      const token = getAccessToken();
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${base}/backup/${id}/download`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'backup.ribbak';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Backup downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function dryRun(id: string) {
    startWork('dry-run');
    try {
      const r = await api(`/backup/${id}/restore`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: true, confirm: false }),
      });
      setDryReport(r.data);
      setMessage(r.message || 'Dry-run validation complete');
    } catch (err: any) {
      setError(err.message);
      setDryReport(null);
    } finally {
      endWork();
    }
  }

  async function verifyBackup(id: string) {
    startWork('verify');
    try {
      const r = await api(`/backup/${id}/verify`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setDryReport(r.data);
      setMessage(r.message || 'Verify complete');
    } catch (err: any) {
      setError(err.message);
    } finally {
      endWork();
    }
  }

  function openRestore(job: BackupJob) {
    setError('');
    setMessage('');
    setConfirmText('');
    setRestoreJob(job);
    if (typeof window !== 'undefined') {
      window.location.hash = 'restore';
      window.setTimeout(() => {
        document.getElementById('restore')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    }
  }

  function cancelRestore() {
    setRestoreJob(null);
    setConfirmText('');
  }

  async function applyRestore() {
    if (!restoreJob) return;
    if (confirmText !== 'RESTORE') {
      setError('Type RESTORE to confirm. Restore is not applied until that exact word is submitted.');
      return;
    }
    startWork('restore');
    try {
      const r = await api(`/backup/${restoreJob.id}/restore`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: false, confirm: true, confirm_text: 'RESTORE' }),
      });
      setDryReport(r.data);
      const proof = r.data?.proof;
      if (proof && proof.ok === false) {
        setError(
          `Restore wrote this company's matching rows, but integrity proof found ${proof.mismatch_count || 0} mismatch(es).`
        );
        setMessage(r.message || 'Restore applied with proof mismatches');
      } else {
        setMessage(r.message || 'Restore applied');
      }
      setRestoreJob(null);
      setConfirmText('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      endWork();
    }
  }

  const restoreReady = confirmText === 'RESTORE' && !busy && restoreJob?.status === 'completed';
  const proof = dryReport?.proof;

  return (
    <>
      <h1>Backups</h1>
      <p className="muted">
        Encrypted company exports (<code>.ribbak</code>) for this workspace only — not a
        platform-wide Postgres restore and not Docker volumes. Restore upserts this company&apos;s
        matching records; it does not delete rows created after the backup, and it cannot restore
        another company&apos;s data. Last/next run and retention come from the server. Failed jobs
        stay failed — starting a job is not success.
      </p>
      {error && (
        <p role="alert" style={{ color: '#b91c1c' }}>
          {error}
        </p>
      )}
      {message && (
        <p role="status" style={{ color: 'var(--brand, #4AB012)' }}>
          {message}
        </p>
      )}
      {busy && (
        <p className="muted" role="status" aria-live="polite">
          {busyAction === 'restore'
            ? 'Applying restore… this can take a while on large companies.'
            : busyAction === 'dry-run'
              ? 'Validating backup…'
              : busyAction === 'verify'
                ? 'Verifying backup against live data…'
                : busyAction === 'create'
                  ? 'Creating backup…'
                  : 'Working…'}
        </p>
      )}

      <div className="card" style={{ marginBottom: 16 }} id="schedule">
        <h2>Schedule</h2>
        {settings && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label>
              <input
                type="checkbox"
                aria-label="Backup schedule enabled"
                checked={!!settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              />{' '}
              Enabled
            </label>
            <select
              value={settings.frequency || 'daily'}
              onChange={(e) => setSettings({ ...settings, frequency: e.target.value })}
              aria-label="Backup frequency"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
            <input
              type="number"
              min={1}
              max={365}
              value={settings.retention_count ?? 30}
              onChange={(e) => setSettings({ ...settings, retention_count: e.target.value })}
              placeholder="Retention"
              aria-label="Backup retention count"
              style={{ width: 100 }}
            />
            <input
              type="number"
              min={0}
              max={23}
              value={settings.hour_utc ?? 2}
              onChange={(e) => setSettings({ ...settings, hour_utc: e.target.value })}
              placeholder="Hour UTC"
              aria-label="Backup hour UTC"
              style={{ width: 100 }}
            />
            <button aria-label="Save backup settings" onClick={saveSettings}>Save settings</button>
            <input
              value={backupNotes}
              onChange={(e) => setBackupNotes(e.target.value)}
              placeholder="Backup notes (optional)"
              aria-label="Backup notes"
              title="Optional notes (1–500 chars; letters/digits required)"
              style={{ minWidth: 180 }}
            />
            <button disabled={busy} onClick={createBackup} aria-label="Create backup now">
              {busy && busyAction === 'create' ? 'Working…' : 'Create backup now'}
            </button>
          </div>
        )}
        {settings?.last_run_at && <p className="muted">Last run: {String(settings.last_run_at)}</p>}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="restore">
        <h2>Restore</h2>
        <p className="muted">
          Company admin only. Pick a completed backup below, dry-run it, then type{' '}
          <strong>RESTORE</strong> to apply. Cross-tenant archives are rejected. This overwrites
          matching product, sales, purchase, stock, and ledger rows in <em>this</em> company.
        </p>
        {restoreJob ? (
          <div>
            <p>
              Apply <code>{restoreJob.filename || restoreJob.id}</code> into this company?
            </p>
            <label style={{ display: 'block', marginBottom: 8 }}>
              Type RESTORE to confirm
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="RESTORE"
                aria-label="Restore confirmation text"
                autoComplete="off"
                disabled={busy}
                style={{ display: 'block', marginTop: 4, minWidth: 220 }}
              />
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                disabled={!restoreReady}
                onClick={applyRestore}
                aria-label="Apply backup restore"
              >
                {busy && busyAction === 'restore' ? 'Restoring…' : 'Apply restore'}
              </button>
              <button type="button" disabled={busy} onClick={cancelRestore} aria-label="Cancel restore">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="muted">No restore selected. Use Restore on a completed job in history.</p>
        )}
      </div>

      {dryReport && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Restore report</h2>
          <p>
            Valid: {String(dryReport.valid)} · Applied: {String(dryReport.applied ?? false)}
            {dryReport.dry_run != null ? ` · Dry-run: ${String(dryReport.dry_run)}` : ''}
            {proof ? ` · Proof ok: ${String(proof.ok)}` : ''}
          </p>
          {proof?.mismatch_count ? (
            <p role="alert" style={{ color: '#b91c1c' }}>
              {proof.mismatch_count} proof mismatch(es). Restore is upsert-only; newer live rows may
              remain.
            </p>
          ) : null}
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(
              {
                record_counts: dryReport.record_counts || dryReport.restored || {},
                restored: dryReport.restored,
                unknown_datasets: dryReport.unknown_datasets,
                company_name: dryReport.company_name,
                proof: proof
                  ? {
                      ok: proof.ok,
                      checked: proof.checked,
                      mismatch_count: proof.mismatch_count,
                      mismatches: (proof.mismatches || []).slice(0, 10),
                    }
                  : undefined,
              },
              null,
              2
            )}
          </pre>
        </div>
      )}

      <div id="history">
      <select
        value={backupManageFilter}
        onChange={(e) =>
          setBackupManageFilter(
            e.target.value as 'all' | 'pending' | 'completed' | 'failed' | 'restoring'
          )
        }
        title="Filter backup job list by status"
        aria-label="Backup job status filter"
        style={{ marginBottom: 12 }}
      >
        <option value="all">All statuses</option>
        <option value="pending">Pending only</option>
        <option value="completed">Completed only</option>
        <option value="failed">Failed only</option>
        <option value="restoring">Restoring only</option>
      </select>
      <table className="table">
        <thead>
          <tr>
            <th>When</th>
            <th>File</th>
            <th>Size</th>
            <th>Status</th>
            <th>Checksum</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {managedBackups.map((r) => {
            const completed = r.status === 'completed';
            return (
            <tr key={r.id}>
              <td>{String(r.created_at)}</td>
              <td>{r.filename}</td>
              <td>{r.size_bytes}</td>
              <td>{r.status}</td>
              <td>{r.checksum_sha256 ? String(r.checksum_sha256).slice(0, 12) : '—'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button
                  disabled={!completed || busy}
                  onClick={() => downloadBackup(r.id, r.filename || 'backup.ribbak')}
                  aria-label="Download backup"
                >
                  Download
                </button>
                <button
                  disabled={!completed || busy}
                  onClick={() => dryRun(r.id)}
                  aria-label="Backup dry-run restore"
                >
                  Dry-run
                </button>
                <button
                  disabled={!completed || busy}
                  onClick={() => verifyBackup(r.id)}
                  aria-label="Verify backup"
                >
                  Verify
                </button>
                <button
                  disabled={!completed || busy}
                  onClick={() => openRestore(r)}
                  aria-label="Select backup for restore"
                >
                  Restore
                </button>
              </td>
            </tr>
            );
          })}
          {!managedBackups.length && (
            <tr>
              <td colSpan={6} className="muted">
                No backups for this filter
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
    </>
  );
}
