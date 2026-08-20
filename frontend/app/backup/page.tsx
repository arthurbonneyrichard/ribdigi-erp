'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [rows, setRows] = useState<any[]>([]);
  const [backupManageFilter, setBackupManageFilter] = useState<
    'all' | 'pending' | 'completed' | 'failed' | 'restoring'
  >('all');
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [dryReport, setDryReport] = useState<any>(null);
  const [backupNotes, setBackupNotes] = useState('');

  async function refresh() {
    const [list, cfg] = await Promise.all([api('/backup'), api('/backup/settings')]);
    setRows(list.data || []);
    setSettings(cfg.data);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  const managedBackups = rows.filter((r) => {
    if (backupManageFilter === 'all') return true;
    return (r.status || 'pending') === backupManageFilter;
  });

  async function createBackup() {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const r = await api('/backup', {
        method: 'POST',
        body: JSON.stringify({ notes: backupNotes.trim() || null }),
      });
      setMessage(r.message || 'Backup created');
      setBackupNotes('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
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
      const token = localStorage.getItem('token');
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
    setError('');
    try {
      const r = await api(`/backup/${id}/restore`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: true, confirm: false }),
      });
      setDryReport(r.data);
      setMessage('Dry-run validation complete');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function applyRestore(id: string) {
    if (!window.confirm('Apply restore? This upserts tenant business data from the backup.')) return;
    setError('');
    setBusy(true);
    try {
      const r = await api(`/backup/${id}/restore`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: false, confirm: true, confirm_text: 'RESTORE' }),
      });
      setDryReport(r.data);
      setMessage(r.message || 'Restore applied');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <h1>Backup &amp; Recovery</h1>
      <p className="muted">
        Encrypted tenant logical backups with checksum verification. Schedule failures raise an in-app
        Backup failed alert for admins (see Notifications).
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Schedule</h2>
        {settings && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label>
              <input
                type="checkbox"
                checked={!!settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              />{' '}
              Enabled
            </label>
            <select
              value={settings.frequency || 'daily'}
              onChange={(e) => setSettings({ ...settings, frequency: e.target.value })}
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
              style={{ width: 100 }}
            />
            <input
              type="number"
              min={0}
              max={23}
              value={settings.hour_utc ?? 2}
              onChange={(e) => setSettings({ ...settings, hour_utc: e.target.value })}
              placeholder="Hour UTC"
              style={{ width: 100 }}
            />
            <button onClick={saveSettings}>Save settings</button>
            <input
              value={backupNotes}
              onChange={(e) => setBackupNotes(e.target.value)}
              placeholder="Backup notes (optional)"
              aria-label="Backup notes"
              title="Optional notes (1–500 chars; letters/digits required)"
              style={{ minWidth: 180 }}
            />
            <button disabled={busy} onClick={createBackup} aria-label="Create backup now">
              {busy ? 'Working…' : 'Create backup now'}
            </button>
          </div>
        )}
        {settings?.last_run_at && <p className="muted">Last run: {String(settings.last_run_at)}</p>}
      </div>

      {dryReport && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Restore report</h2>
          <p>Valid: {String(dryReport.valid)} · Applied: {String(dryReport.applied)}</p>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(dryReport.record_counts || dryReport.restored || {}, null, 2)}
          </pre>
        </div>
      )}

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
          {managedBackups.map((r) => (
            <tr key={r.id}>
              <td>{String(r.created_at)}</td>
              <td>{r.filename}</td>
              <td>{r.size_bytes}</td>
              <td>{r.status}</td>
              <td>{r.checksum_sha256 ? String(r.checksum_sha256).slice(0, 12) : '—'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button onClick={() => downloadBackup(r.id, r.filename)}>Download</button>
                <button onClick={() => dryRun(r.id)} aria-label="Backup dry-run restore">
                  Dry-run
                </button>
                <button
                  disabled={busy}
                  onClick={() => applyRestore(r.id)}
                  aria-label="Apply backup restore"
                >
                  Restore
                </button>
              </td>
            </tr>
          ))}
          {!managedBackups.length && (
            <tr>
              <td colSpan={6} className="muted">
                No backups for this filter
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Shell>
  );
}
