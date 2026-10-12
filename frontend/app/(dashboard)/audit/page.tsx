'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, getAccessToken } from '../../../lib/api';
import { formatWhen, plainLabel } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';

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
  'fmcg',
  'hotel',
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

function areaLabel(value: string | null | undefined): string {
  const key = String(value || '').trim().toLowerCase();
  if (!key) return 'All areas';
  const special: Record<string, string> = {
    ai: 'AI',
    auth: 'Sign-in',
    fmcg: 'FMCG',
    platform_staff: 'Platform',
    pos: 'Point of sale',
    tenants: 'Companies',
    webhooks: 'Connections',
  };
  return special[key] || plainLabel(key);
}

/** Keep aligned with backend AuditActionValue (strip/lower; digit-start OK for 2fa_*). */
function auditActionQueryValue(raw: string): string | null {
  const v = raw.trim().toLowerCase();
  if (!v) return null;
  if (!/^[a-z0-9][a-z0-9_]{1,62}$/.test(v)) return null;
  return v;
}

/** Keep aligned with backend AuditEntityValue (strip/lower; must start with a letter). */
function auditEntityQueryValue(raw: string): string | null {
  const v = raw.trim().toLowerCase();
  if (!v) return null;
  if (!/^[a-z][a-z0-9_]{0,62}$/.test(v)) return null;
  return v;
}

function recordHref(entity?: string, entityId?: string | null): string | null {
  if (!entityId) return null;
  const e = (entity || '').toLowerCase();
  const id = String(entityId);
  if (e === 'user') return `/users`;
  if (e === 'department') return `/departments`;
  if (e === 'backup' || e === 'backup_job') return `/backup`;
  if (e.includes('invoice') && e.includes('sales')) return `/sales`;
  if (e.includes('purchase')) return `/purchasing`;
  if (e.includes('expense')) return `/expenses`;
  if (e === 'product') return `/inventory`;
  return null;
}

export default function Page() {
  useCompanyFormat();
  const [rows, setRows] = useState<any[]>([]);
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [appliedAction, setAppliedAction] = useState('');
  const [entity, setEntity] = useState('');
  const [appliedEntity, setAppliedEntity] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [userId, setUserId] = useState('');
  const [verify, setVerify] = useState<any>(null);
  const [retention, setRetention] = useState<any>(null);
  const [archives, setArchives] = useState<any[]>([]);
  const [canArchive, setCanArchive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [staffNames, setStaffNames] = useState<Record<string, string>>({});

  const refreshLogs = useCallback(async () => {
    const params = new URLSearchParams();
    if (module) params.set('module', module);
    const actionQ = auditActionQueryValue(appliedAction);
    if (actionQ) params.set('action', actionQ);
    const entityQ = auditEntityQueryValue(appliedEntity);
    if (entityQ) params.set('entity', entityQ);
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    // trim/omit so UuidIdValue Query user_id does not 422
    const userTrim = userId.trim();
    if (userTrim) params.set('user_id', userTrim);
    const q = params.toString() ? `?${params}` : '';
    const r = await api(`/audit-logs${q}`);
    setRows(r.data || []);
    setError('');
  }, [module, appliedAction, appliedEntity, fromDate, toDate, userId]);

  const refreshPolicy = useCallback(async () => {
    const [policy, me] = await Promise.all([api('/audit-logs/retention'), getMe()]);
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

  useEffect(() => {
    api('/users')
      .then((r) => {
        const map: Record<string, string> = {};
        for (const person of r.data || []) {
          if (person?.id) map[String(person.id)] = person.full_name || person.email || 'Staff';
        }
        setStaffNames(map);
      })
      .catch(() => setStaffNames({}));
  }, []);

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
      if (action.trim() && !auditActionQueryValue(action)) {
              setError('Use a short code such as invoice_posted.');
        return;
      }
      if (entity.trim() && !auditEntityQueryValue(entity)) {
              setError('Use a short code such as sales_invoice.');
        return;
      }
      const token = getAccessToken();
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (module) params.set('module', module);
      const actionQ = auditActionQueryValue(action);
      if (actionQ) params.set('action', actionQ);
      const entityQ = auditEntityQueryValue(entity);
      if (entityQ) params.set('entity', entityQ);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      const userTrim = userId.trim();
      if (userTrim) params.set('user_id', userTrim);
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
        'Move older records into long-term storage? They stay on this list and are never deleted.',
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
    <>
      <h1>Audit</h1>
      <p className="muted">
        Who did what, and when. Open a record when a link is shown. These entries cannot be edited
        or deleted.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      {retention && (
        <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }} data-testid="audit-retention">
          <h3 style={{ margin: 0 }}>How long records are kept</h3>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Records stay for at least {retention.retention_years} years. Older records can be stored
            away, and they are never deleted.
          </p>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 14 }}>
            <span>
              Kept for: <strong>{retention.retention_years} years</strong>
            </span>
            <span>
              Store away after: <strong>{retention.cold_archive_after_days} days</strong>
            </span>
            <span>
              Removal: <strong>{retention.purge_allowed ? 'Allowed' : 'Never'}</strong>
            </span>
          </div>
          {canArchive && (
            <div>
              <button type="button" onClick={archiveCold} disabled={busy} aria-label="Archive cold audit logs">
                {busy ? 'Storing…' : 'Store older records'}
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
                </tr>
              </thead>
              <tbody>
                {archives.length === 0 && (
                  <tr>
                    <td colSpan={4} className="muted">
                      No older records stored yet
                    </td>
                  </tr>
                )}
                {archives.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontSize: 12 }}>
                      {formatWhen(a.created_at) || '—'}
                    </td>
                    <td>{a.event_count ?? '—'}</td>
                    <td className="muted" style={{ fontSize: 12 }}>
                      {formatWhen(a.from_created_at) || '—'}
                      {' to '}
                      {formatWhen(a.to_created_at) || '—'}
                    </td>
                    <td className="muted" style={{ fontSize: 12 }}>
                      {typeof a.byte_size === 'number'
                        ? `${Math.max(1, Math.round(a.byte_size / 1024))} KB`
                        : '—'}
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
              {areaLabel(m)}
            </option>
          ))}
        </select>
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="What happened"
          title="For example invoice_posted"
          aria-label="Audit action filter"
        />
        <input
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          placeholder="Record type"
          title="For example sales_invoice"
          aria-label="Audit entity filter"
        />
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          title="From date"
          aria-label="Audit from date"
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          title="To date"
          aria-label="Audit to date"
        />
        <button
          type="button"
          aria-label="Apply audit filters"
          onClick={() => {
            if (action.trim() && !auditActionQueryValue(action)) {
              setError('Use a short code such as invoice_posted.');
              return;
            }
            if (entity.trim() && !auditEntityQueryValue(entity)) {
              setError('Use a short code such as sales_invoice.');
              return;
            }
            setError('');
            setAppliedAction(auditActionQueryValue(action) || '');
            setAppliedEntity(auditEntityQueryValue(entity) || '');
          }}
        >
          Filter
        </button>
        <button type="button" aria-label="Verify audit chain" onClick={runVerify}>
          Check records
        </button>
        <button type="button" onClick={exportCsv} aria-label="Export audit CSV">
          Export CSV
        </button>
      </div>

      {verify && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p>{verify.valid ? 'Records check out.' : 'A record failed the check.'}</p>
          <p>Checked: {verify.checked}</p>
        </div>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>When</th>
            <th>Area</th>
            <th>Action</th>
            <th>Record type</th>
            <th>User</th>
            <th>IP</th>
            <th>Record</th>
            <th>Archived</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className="muted">
                No audit events for these filters.
              </td>
            </tr>
          ) : null}
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{formatWhen(r.created_at) || '—'}</td>
              <td>{areaLabel(r.module)}</td>
              <td>{plainLabel(r.action)}</td>
              <td>{plainLabel(r.entity)}</td>
              <td>{r.user_id ? staffNames[String(r.user_id)] || 'Staff' : '—'}</td>
              <td>{r.ip_address || '—'}</td>
              <td>
                {recordHref(r.entity, r.entity_id) ? (
                  <a href={recordHref(r.entity, r.entity_id) || '#'}>Open</a>
                ) : (
                  '—'
                )}
              </td>
              <td className="muted" style={{ fontSize: 12 }}>
                {formatWhen(r.archived_at) || '—'}
              </td>
              <td className="muted" style={{ fontSize: 12 }}>
                {r.archived_at
                  ? String(r.archived_at).replace('T', ' ').slice(0, 10)
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
