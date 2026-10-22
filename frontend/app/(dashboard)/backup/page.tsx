'use client';

import { useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api, getAccessToken } from '../../../lib/api';
import './backup-ui.css';

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
  const [messageTone, setMessageTone] = useState<'ok' | 'pending'>('ok');
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
      const status = String(r.data?.status || '');
      if (status === 'failed') {
        setMessage('');
        setError(r.data?.error_message || r.message || 'This backup failed. It was not completed.');
      } else if (status === 'completed') {
        setMessageTone('ok');
        setMessage(r.message || 'Backup completed');
      } else {
        setMessageTone('pending');
        setMessage(r.message || `Backup ${status || 'recorded'}. It is not complete yet.`);
      }
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
      setMessageTone('ok');
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
      setMessageTone('ok');
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
      setMessageTone('ok');
      setMessage(r.message || 'Dry-run validation complete. Nothing was written.');
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
      const proofOk = r.data?.proof?.ok;
      if (r.data?.valid === false || proofOk === false) {
        setMessage('');
        setError('This backup file did not match the check. It was not marked successful.');
      } else {
        setMessageTone('ok');
        setMessage(r.message || 'Check finished for this backup file.');
      }
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
        setMessage('');
        setError(
          `Restore wrote this company's matching rows, but the check found ${proof.mismatch_count || 0} mismatch(es).`
        );
      } else {
        setMessageTone('ok');
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

  const historyEmpty = rows.length
    ? 'No backups for this filter. Choose All statuses, or create a backup above.'
    : 'No backups yet. Add a note if you want one, then choose Create backup now.';

  return (
    <div className="backup-ui">
      <PageHeader
        title="Create a backup"
        subtitle="This saves an encrypted copy for this company only. A failed job stays failed. Starting the job is not the same as a finished backup."
      />
      {error && (
        <p role="alert" className="backup-ui-alert">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className={messageTone === 'pending' ? 'backup-ui-pending' : 'backup-ui-ok'}>
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
                ? 'Checking this backup file…'
                : busyAction === 'create'
                  ? 'Creating backup…'
                  : 'Working…'}
        </p>
      )}

      <div className="card backup-ui-form">
        <label>
          Note (optional)
          <input
            value={backupNotes}
            onChange={(e) => setBackupNotes(e.target.value)}
            placeholder="Backup notes (optional)"
            aria-label="Backup notes"
            title="Optional notes (1–500 chars; letters/digits required)"
          />
        </label>
        <button disabled={busy} onClick={createBackup} aria-label="Create backup now">
          {busy && busyAction === 'create' ? 'Working…' : 'Create backup now'}
        </button>
      </div>

      <h2 className="backup-ui-section">Saved backups</h2>
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
      <div className="backup-ui-scroll">
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
            const statusLabel =
              r.status === 'completed'
                ? 'Completed'
                : r.status === 'failed'
                  ? 'Failed'
                  : r.status === 'pending'
                    ? 'Pending'
                    : r.status === 'restoring'
                      ? 'Restoring'
                      : String(r.status || '');
            return (
            <tr key={r.id}>
              <td>{String(r.created_at)}</td>
              <td>{r.filename}</td>
              <td>{r.size_bytes}</td>
              <td>
                {statusLabel}
                {r.status === 'failed' && r.error_message ? (
                  <div className="backup-ui-alert">{String(r.error_message)}</div>
                ) : null}
              </td>
              <td>{r.checksum_sha256 ? String(r.checksum_sha256).slice(0, 12) : '—'}</td>
              <td>
                <div className="backup-ui-row-actions">
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
                </div>
              </td>
            </tr>
            );
          })}
          {!managedBackups.length && (
            <tr>
              <td colSpan={6} className="muted">
                {historyEmpty}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
      </div>

      <div className="card" id="restore">
        <h2>Restore a completed backup</h2>
        <p className="muted">
          Choose Restore on a completed row above. Dry-run first if you want a preview. Type{' '}
          <strong>RESTORE</strong> before Apply. This overwrites matching product, sales, purchase,
          stock, and ledger rows in this company. It does not delete rows created after the backup.
        </p>
        {restoreJob ? (
          <div className="backup-ui-form">
            <p>
              Apply <code>{restoreJob.filename || restoreJob.id}</code> into this company?
            </p>
            <label>
              Type RESTORE to confirm
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="RESTORE"
                aria-label="Restore confirmation text"
                autoComplete="off"
                disabled={busy}
              />
            </label>
            <div className="backup-ui-row-actions">
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
          <p className="muted">No restore selected. Choose Restore on a completed backup in the list above.</p>
        )}
      </div>

      {dryReport && (
        <div className="card">
          <h2>Check result</h2>
          <p>
            File accepted: {dryReport.valid ? 'yes' : 'no'} · Written: {dryReport.applied ? 'yes' : 'no'}
            {dryReport.dry_run != null ? ` · Preview only: ${dryReport.dry_run ? 'yes' : 'no'}` : ''}
            {proof ? ` · Check matched: ${proof.ok ? 'yes' : 'no'}` : ''}
          </p>
          {proof?.mismatch_count ? (
            <p role="alert" className="backup-ui-alert">
              {proof.mismatch_count} mismatch(es). This check did not pass. Newer live rows may remain.
            </p>
          ) : null}
          <pre className="backup-ui-report">
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

      <details className="card backup-ui-advanced" id="schedule">
        <summary>Schedule</summary>
        <p className="muted backup-ui-note">
          Daily or weekly runs keep the newest copies and drop older ones after the retention count.
        </p>
        {settings ? (
          <div className="backup-ui-settings">
            <label>
              <input
                type="checkbox"
                aria-label="Backup schedule enabled"
                checked={!!settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              />{' '}
              Run on a schedule
            </label>
            <label>
              Frequency
              <select
                value={settings.frequency || 'daily'}
                onChange={(e) => setSettings({ ...settings, frequency: e.target.value })}
                aria-label="Backup frequency"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </label>
            <label>
              Keep this many
              <input
                type="number"
                min={1}
                max={365}
                value={settings.retention_count ?? 30}
                onChange={(e) => setSettings({ ...settings, retention_count: e.target.value })}
                placeholder="Retention"
                aria-label="Backup retention count"
              />
            </label>
            <label>
              Hour UTC
              <input
                type="number"
                min={0}
                max={23}
                value={settings.hour_utc ?? 2}
                onChange={(e) => setSettings({ ...settings, hour_utc: e.target.value })}
                placeholder="Hour UTC"
                aria-label="Backup hour UTC"
              />
            </label>
            <button aria-label="Save backup settings" onClick={saveSettings}>Save settings</button>
          </div>
        ) : (
          <p className="muted backup-ui-note">Schedule settings load with this page. Refresh if the switches are missing.</p>
        )}
        {settings?.last_run_at && <p className="muted">Last scheduled run: {String(settings.last_run_at)}</p>}
      </details>
    </div>
  );
}
