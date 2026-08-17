'use client';

import { useCallback, useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const ARCHIVE_ROLES = new Set(['company_admin', 'super_admin']);

const AUDIT_MODULES = [
  '',
  'accounting',
  'ai',
  'audit',
  'auth',
  'backup',
  'company',
  'credit',
  'dashboard',
  'expenses',
  'inventory',
  'notifications',
  'onboarding',
  'platform_staff',
  'pos',
  'purchasing',
  'reports',
  'sales',
  'security',
  'settings',
  'stores',
  'system',
  'tax',
  'tenants',
  'users',
  'webhooks',
] as const;

export default function Page() {
  const [rows, setRows] = useState<any[]>([]);
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [verify, setVerify] = useState<any>(null);
  const [retention, setRetention] = useState<any>(null);
  const [archives, setArchives] = useState<any[]>([]);
  const [canArchive, setCanArchive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const refreshLogs = useCallback(async () => {
    const params = new URLSearchParams();
    if (module) params.set('module', module);
    if (action) params.set('action', action);
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    const q = params.toString() ? `?${params}` : '';
    const r = await api(`/audit-logs${q}`);
    setRows(r.data || []);
  }, [module, action, fromDate, toDate]);

  const refreshPolicy = useCallback(async () => {
    const [policy, me] = await Promise.all([api('/audit-logs/retention'), api('/me')]);
    setRetention(policy.data || null);
    const role = me.data?.role || '';
    const admin = ARCHIVE_ROLES.has(role);
    setCanArchive(admin);
    if (admin) {
      try {
        const listed = await api('/audit-logs/archives');
        setArchives(listed.data || []);
      } catch {
        setArchives([]);
      }
    } else {
      setArchives([]);
    }
  }, []);

  useEffect(() => {
    Promise.all([refreshLogs(), refreshPolicy()]).catch((err) => setError(err.message));
  }, [refreshLogs, refreshPolicy]);

  async function runVerify() {
    setError('');
    try {
      const r = await api('/audit-logs/verify');
      setVerify(r.data);
      setMessage(r.data?.valid ? 'Integrity chain valid' : 'Integrity chain broken');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function exportCsv() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (module) params.set('module', module);
      if (action) params.set('action', action);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      const res = await fetch(`${base}/audit-logs/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit-logs.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('CSV downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function archiveCold() {
    if (
      !window.confirm(
        'Cold-archive aged audit events now? Hot rows are marked archived_at and never deleted.',
      )
    ) {
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const days = retention?.cold_archive_after_days;
      const q =
        typeof days === 'number' && days > 0 ? `?older_than_days=${days}` : '';
      const r = await api(`/audit-logs/archive-cold${q}`, { method: 'POST', body: '{}' });
      setMessage(r.message || 'Cold archive complete');
      await Promise.all([refreshLogs(), refreshPolicy()]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <h1>Audit Logs</h1>
      <p className="muted">
        Append-only activity trail with integrity verification and 7-year retention (BR-17.2).
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {retention && (
        <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }} data-testid="audit-retention">
          <h3 style={{ margin: 0 }}>Retention & cold archive</h3>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            {retention.notes}
          </p>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 14 }}>
            <span>
              Retention: <strong>{retention.retention_years} years</strong>
            </span>
            <span>
              Cold after: <strong>{retention.cold_archive_after_days} days</strong>
            </span>
            <span>
              Purge: <strong>{retention.purge_allowed ? 'allowed' : 'never'}</strong>
            </span>
          </div>
          {canArchive && (
            <div>
              <button type="button" onClick={archiveCold} disabled={busy}>
                {busy ? 'Archiving…' : 'Archive cold now'}
              </button>
            </div>
          )}
          {canArchive && (
            <table className="table" data-testid="audit-archives">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Events</th>
                  <th>Range</th>
                  <th>Size</th>
                  <th>SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {archives.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      No cold archives yet
                    </td>
                  </tr>
                )}
                {archives.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontSize: 12 }}>
                      {a.created_at ? String(a.created_at).replace('T', ' ').slice(0, 19) : '—'}
                    </td>
                    <td>{a.event_count ?? '—'}</td>
                    <td className="muted" style={{ fontSize: 12 }}>
                      {a.from_created_at
                        ? String(a.from_created_at).replace('T', ' ').slice(0, 10)
                        : '—'}
                      {' → '}
                      {a.to_created_at
                        ? String(a.to_created_at).replace('T', ' ').slice(0, 10)
                        : '—'}
                    </td>
                    <td className="muted" style={{ fontSize: 12 }}>
                      {typeof a.byte_size === 'number'
                        ? `${Math.max(1, Math.round(a.byte_size / 1024))} KB`
                        : '—'}
                    </td>
                    <td className="muted" style={{ fontSize: 12 }} title={a.sha256 || ''}>
                      {a.sha256 ? String(a.sha256).slice(0, 12) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <select
          value={module}
          onChange={(e) => setModule(e.target.value)}
          aria-label="Audit module filter"
          title="Filter audit logs by module"
        >
          {AUDIT_MODULES.map((m) => (
            <option key={m || 'all'} value={m}>
              {m ? `Module: ${m}` : 'All modules'}
            </option>
          ))}
        </select>
        <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Action" />
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          title="From date (YYYY-MM-DD)"
          aria-label="Audit from date"
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          title="To date (YYYY-MM-DD)"
          aria-label="Audit to date"
        />
        <button type="button" onClick={() => refreshLogs().catch((e) => setError(e.message))}>
          Filter
        </button>
        <button type="button" onClick={runVerify}>
          Verify chain
        </button>
        <button type="button" onClick={exportCsv}>
          Export CSV
        </button>
      </div>

      {verify && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p>Valid: {String(verify.valid)}</p>
          <p>Checked: {verify.checked}</p>
          {verify.broken_at && <p>Broken at: {verify.broken_at}</p>}
        </div>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>When</th>
            <th>Module</th>
            <th>Action</th>
            <th>Entity</th>
            <th>User</th>
            <th>IP</th>
            <th>Archived</th>
            <th>Hash</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{String(r.created_at)}</td>
              <td>{r.module}</td>
              <td>{r.action}</td>
              <td>
                {r.entity}
                {r.entity_id ? `:${String(r.entity_id).slice(0, 8)}` : ''}
              </td>
              <td>{r.user_id ? String(r.user_id).slice(0, 8) : '—'}</td>
              <td>{r.ip_address || '—'}</td>
              <td className="muted" style={{ fontSize: 12 }}>
                {r.archived_at
                  ? String(r.archived_at).replace('T', ' ').slice(0, 10)
                  : '—'}
              </td>
              <td>{r.integrity_hash ? String(r.integrity_hash).slice(0, 10) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
