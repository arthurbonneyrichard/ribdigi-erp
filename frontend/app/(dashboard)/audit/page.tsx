'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api, apiFetch } from '../../../lib/api';
import { formatWhen, plainLabel } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import './audit-ui.css';

const ARCHIVE_ROLES = new Set(['company_admin', 'super_admin']);

/** Known areas from backend AUDIT_MODULES. Blank is omitted (all areas). */
const AUDIT_MODULES = [
  '',
  'accounting',
  'ai',
  'audit',
  'auth',
  'backup',
  'billing',
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
  'printers',
  'purchasing',
  'reports',
  'restaurant',
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

const USER_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function areaLabel(value: string | null | undefined): string {
  const key = String(value || '').trim().toLowerCase();
  if (!key) return 'All modules';
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

/** Dates are YYYY-MM-DD or omitted. A partial value is not sent. */
function isoDayOrBlank(raw: string): string {
  const v = raw.trim();
  if (!v) return '';
  return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : '';
}

function auditListParams(input: {
  module: string;
  appliedAction: string;
  appliedEntity: string;
  fromDate: string;
  toDate: string;
  userId: string;
}): URLSearchParams {
  const params = new URLSearchParams();
  if (input.module) params.set('module', input.module);
  const actionQ = auditActionQueryValue(input.appliedAction);
  if (actionQ) params.set('action', actionQ);
  const entityQ = auditEntityQueryValue(input.appliedEntity);
  if (entityQ) params.set('entity', entityQ);
  const from = isoDayOrBlank(input.fromDate);
  if (from) params.set('from_date', from);
  const to = isoDayOrBlank(input.toDate);
  if (to) params.set('to_date', to);
  const userTrim = input.userId.trim();
  if (userTrim) params.set('user_id', userTrim);
  return params;
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
  const [userDraft, setUserDraft] = useState('');
  const [userId, setUserId] = useState('');
  const [verify, setVerify] = useState<any>(null);
  const [retention, setRetention] = useState<any>(null);
  const [archives, setArchives] = useState<any[]>([]);
  const [canArchive, setCanArchive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [staffNames, setStaffNames] = useState<Record<string, string>>({});

  const people = useMemo(
    () =>
      Object.entries(staffNames).sort((a, b) =>
        a[1].localeCompare(b[1], undefined, { sensitivity: 'base' }),
      ),
    [staffNames],
  );

  const refreshLogs = useCallback(async () => {
    const params = auditListParams({
      module,
      appliedAction,
      appliedEntity,
      fromDate,
      toDate,
      userId,
    });
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

  function applyFilters() {
    if (action.trim() && !auditActionQueryValue(action)) {
      setError('Use a short code such as invoice_posted.');
      return;
    }
    if (entity.trim() && !auditEntityQueryValue(entity)) {
      setError('Use a short code such as sales_invoice.');
      return;
    }
    const nextUser = userDraft.trim();
    if (nextUser && !USER_ID_RE.test(nextUser)) {
      setError('Enter a staff id, or leave it blank.');
      return;
    }
    setError('');
    setAppliedAction(auditActionQueryValue(action) || '');
    setAppliedEntity(auditEntityQueryValue(entity) || '');
    setUserId(nextUser);
  }

  async function runVerify() {
    setError('');
    setMessage('');
    try {
      const r = await api('/audit-logs/verify');
      const data = r.data ?? null;
      setVerify(data);
      if (data?.valid !== true) setMessage('');
    } catch (err: any) {
      setVerify(null);
      setError(err.message || 'The record check could not be completed.');
    }
  }

  async function exportCsv() {
    setError('');
    try {
      const params = auditListParams({
        module,
        appliedAction,
        appliedEntity,
        fromDate,
        toDate,
        userId,
      });
      const res = await apiFetch(`/audit-logs/export?${params}`);
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

  const chainOk = verify?.valid === true;

  return (
    <div className="audit-ui">
      <PageHeader
        title="Audit"
        subtitle="Who did what, and when. Open a record when a link is shown. These entries cannot be edited or deleted."
      />
      {error && <p className="audit-ui-alert">{error}</p>}
      {message && <p className="audit-ui-ok">{message}</p>}

      <section className="card audit-ui-keep" aria-labelledby="audit-log-heading">
        <h2 id="audit-log-heading">Activity log</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            applyFilters();
          }}
        >
          <div className="audit-ui-filters">
            <label className="audit-ui-field">
              <span className="audit-ui-label">Area</span>
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
              <span className="audit-ui-hint">Leave this as All modules to include every area.</span>
            </label>
            <label className="audit-ui-field">
              <span className="audit-ui-label">What happened</span>
              <input
                value={action}
                onChange={(e) => setAction(e.target.value)}
                placeholder="invoice_posted"
                title="For example invoice_posted"
                aria-label="Audit action filter"
                autoComplete="off"
                spellCheck={false}
              />
              <span className="audit-ui-hint">
                Code such as invoice_posted. It is sent only when you choose Apply filters.
              </span>
            </label>
            <label className="audit-ui-field">
              <span className="audit-ui-label">Record type</span>
              <input
                value={entity}
                onChange={(e) => setEntity(e.target.value)}
                placeholder="sales_invoice"
                title="For example sales_invoice"
                aria-label="Audit entity filter"
                autoComplete="off"
                spellCheck={false}
              />
              <span className="audit-ui-hint">
                Code such as sales_invoice. It is sent only when you choose Apply filters.
              </span>
            </label>
            <label className="audit-ui-field">
              <span className="audit-ui-label">From</span>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                title="From date"
                aria-label="Audit from date"
              />
              <span className="audit-ui-hint">Leave blank for any start date.</span>
            </label>
            <label className="audit-ui-field">
              <span className="audit-ui-label">To</span>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                title="To date"
                aria-label="Audit to date"
              />
              <span className="audit-ui-hint">Leave blank for any end date.</span>
            </label>
            <label className="audit-ui-field">
              <span className="audit-ui-label">Person</span>
              <select
                value={userDraft}
                onChange={(e) => setUserDraft(e.target.value)}
                title="Staff id. Leave blank for everyone."
                aria-label="Audit user filter"
              >
                <option value="">Everyone</option>
                {people.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
              <span className="audit-ui-hint">
                Everyone leaves the person blank, so it is not sent. Choose Apply filters to use a person.
              </span>
            </label>
          </div>
          <div className="audit-ui-actions">
            <button type="submit" aria-label="Apply audit filters">
              Apply filters
            </button>
            <button type="button" aria-label="Verify audit chain" onClick={runVerify}>
              Check the record chain
            </button>
            <button type="button" onClick={exportCsv} aria-label="Export audit CSV">
              Export CSV
            </button>
          </div>
        </form>

        {verify && (
          <div
            className={chainOk ? 'audit-ui-verify audit-ui-verify-ok' : 'audit-ui-verify audit-ui-verify-bad'}
            role={chainOk ? 'status' : 'alert'}
          >
            <p>{chainOk ? 'Records check out.' : 'A record failed the check.'}</p>
            {!chainOk && verify.action ? <p>Failed on {plainLabel(String(verify.action))}.</p> : null}
            <p>Checked: {verify.checked ?? 0}</p>
          </div>
        )}

        <p className="muted audit-ui-note">
          This list shows up to 200 records. Export CSV uses the same filters.
        </p>

        <div className="audit-ui-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Area</th>
                <th>What happened</th>
                <th>Record type</th>
                <th>Person</th>
                <th>Network address</th>
                <th>Record</th>
                <th>Stored away</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="muted audit-ui-empty">
                    No records match these filters. Clear a code or widen the dates, then choose Apply filters.
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
                      <a href={recordHref(r.entity, r.entity_id) || '#'}>Open record</a>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="muted">
                    {formatWhen(r.archived_at) || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {retention && (
        <section className="card audit-ui-keep" data-testid="audit-retention" aria-labelledby="audit-keep-heading">
          <h2 id="audit-keep-heading">How long records are kept</h2>
          <p className="muted audit-ui-note">
            Records stay for at least {retention.retention_years} years. Older records can be stored
            away, and they are never deleted.
          </p>
          <div className="audit-ui-facts">
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
            <div className="audit-ui-actions">
              <button type="button" onClick={archiveCold} disabled={busy} aria-label="Archive cold audit logs">
                {busy ? 'Storing…' : 'Archive cold now'}
              </button>
            </div>
          )}
          {canArchive && (
            <div className="audit-ui-scroll">
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
                      <td colSpan={4} className="muted audit-ui-empty">
                        No older records are stored yet. Choose Archive cold now to store records past the policy. They stay on this list and are never deleted.
                      </td>
                    </tr>
                  )}
                  {archives.map((a) => (
                    <tr key={a.id}>
                      <td>{formatWhen(a.created_at) || '—'}</td>
                      <td>{a.event_count ?? '—'}</td>
                      <td className="muted">
                        {formatWhen(a.from_created_at) || '—'}
                        {' to '}
                        {formatWhen(a.to_created_at) || '—'}
                      </td>
                      <td className="muted">
                        {typeof a.byte_size === 'number'
                          ? `${Math.max(1, Math.round(a.byte_size / 1024))} KB`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
