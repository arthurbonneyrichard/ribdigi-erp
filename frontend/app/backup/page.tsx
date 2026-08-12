'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [rows, setRows] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [dryReport, setDryReport] = useState<any>(null);
  // Stage 129 B1 — backup_status → GET /backup?status=
  const [backupStatusFilter, setBackupStatusFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('backup_status') || '')
      .trim()
      .toLowerCase();
    return v || '';
  });

  async function refresh(opts?: { backupStatus?: string }) {
    const backupStatus =
      opts?.backupStatus !== undefined ? opts.backupStatus : backupStatusFilter;
    const qs = backupStatus ? `?status=${encodeURIComponent(backupStatus)}` : '';
    const [list, cfg] = await Promise.all([api(`/backup${qs}`), api('/backup/settings')]);
    setRows(list.data || []);
    setSettings(cfg.data);
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const bs = (params.get('backup_status') || '').trim().toLowerCase();
    if (bs) setBackupStatusFilter(bs);
    refresh({ backupStatus: bs || backupStatusFilter }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stage 103 B1 / Stage 107 O1 — honor Shell #schedule / #restore / #history
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

  async function createBackup() {
    setError('');
    setBusy(true);
    try {
      const r = await api('/backup', { method: 'POST', body: JSON.stringify({ notes: 'manual' }) });
      setMessage(r.message || 'Backup created');
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
      <p className="muted">Encrypted tenant logical backups with checksum verification</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }} id="schedule">
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
            <button disabled={busy} onClick={createBackup}>
              {busy ? 'Working…' : 'Create backup now'}
            </button>
            <button
              type="button"
              onClick={async () => {
                // Stage 140 B1 — backup schedule settings CSV
                setError('');
                try {
                  const token = localStorage.getItem('token');
                  const res = await fetch(`${base}/backup/settings/export`, {
                    headers: {
                      ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    },
                  });
                  if (!res.ok) throw new Error('Backup settings export failed');
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'backup_settings_export.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                  setMessage('Backup settings CSV exported (Stage 140 B1)');
                } catch (err: any) {
                  setError(err.message || 'Backup settings export failed');
                }
              }}
            >
              Export backup settings CSV
            </button>
          </div>
        )}
        {settings?.last_run_at && <p className="muted">Last run: {String(settings.last_run_at)}</p>}
        <p className="muted" style={{ marginTop: 8 }}>
          Schedule CSV via <code>GET /backup/settings/export</code> (Stage 140 B1) — distinct from job
          history <code>/backup/export</code>.
        </p>
      </div>

      <div id="restore">
      {dryReport && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Restore report</h2>
          <p>Valid: {String(dryReport.valid)} · Applied: {String(dryReport.applied)}</p>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(dryReport.record_counts || dryReport.restored || {}, null, 2)}
          </pre>
        </div>
      )}

      <div id="history">
      <h2 style={{ fontSize: 18, marginTop: 8 }}>Backup history</h2>
      <p className="muted">
        Filter via <code>backup_status</code> → <code>GET /backup?status=</code>; export metadata via{' '}
        <code>GET /backup/export</code> (Stage 129 B1 — archive bytes not included).
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select
          value={backupStatusFilter || 'default'}
          onChange={(e) => {
            const v = e.target.value === 'default' ? '' : e.target.value;
            setBackupStatusFilter(v);
            const url = new URL(window.location.href);
            if (v) url.searchParams.set('backup_status', v);
            else url.searchParams.delete('backup_status');
            window.history.replaceState({}, '', url.toString());
            refresh({ backupStatus: v }).catch((err) => setError(err.message));
          }}
        >
          <option value="default">Status filter (all)</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
          <option value="restoring">Restoring</option>
        </select>
        <button
          type="button"
          onClick={async () => {
            const token = localStorage.getItem('token') || '';
            const tenant = localStorage.getItem('tenant') || '';
            const qs = backupStatusFilter ? `?status=${encodeURIComponent(backupStatusFilter)}` : '';
            const res = await fetch(`${base}/backup/export${qs}`, {
              headers: {
                Authorization: `Bearer ${token}`,
                'X-Tenant-ID': tenant,
              },
            });
            if (!res.ok) {
              setError(await res.text());
              return;
            }
            const blob = await res.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'backup_jobs_export.csv';
            a.click();
            URL.revokeObjectURL(a.href);
            setMessage('Backup jobs CSV downloaded');
          }}
        >
          Export backup jobs CSV
        </button>
      </div>
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
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{String(r.created_at)}</td>
              <td>{r.filename}</td>
              <td>{r.size_bytes}</td>
              <td>{r.status}</td>
              <td>{r.checksum_sha256 ? String(r.checksum_sha256).slice(0, 12) : '—'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button onClick={() => downloadBackup(r.id, r.filename)}>Download</button>
                <button onClick={() => dryRun(r.id)}>Dry-run</button>
                <button disabled={busy} onClick={() => applyRestore(r.id)}>
                  Restore
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      </div>
    </Shell>
  );
}
