'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';
import { formatDateTime } from '../../../lib/format';
import { fetchHouseFormats, HOUSE_FORMAT_DEFAULTS } from '../../../lib/houseFormats';

type AuditRow = {
  id?: string;
  action?: string;
  module?: string;
  entity?: string;
  entity_id?: string;
  created_at?: string;
  user_id?: string;
  details?: Record<string, any>;
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function activityDefaultFromDate() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

export default function PlatformAuditPage() {
  const pathname = usePathname();
  const isActivity = Boolean(pathname?.includes('/activity'));
  const listPath = isActivity ? '/platform/activity' : '/platform/audit';
  const [items, setItems] = useState<AuditRow[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [deliveryOnly, setDeliveryOnly] = useState(false);
  const [verify, setVerify] = useState<any>(null);
  const [formats, setFormats] = useState(HOUSE_FORMAT_DEFAULTS);

  async function load() {
    setError('');
    try {
      const params = new URLSearchParams();
      if (module.trim()) params.set('module', module.trim());
      if (action.trim()) params.set('action', action.trim());
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      if (deliveryOnly) params.set('delivery_only', 'true');
      const r = await api(`${listPath}?${params.toString()}`);
      setItems(r.data?.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit');
    }
  }

  useEffect(() => {
    fetchHouseFormats().then(setFormats);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listPath]);

  async function runVerify() {
    setError('');
    setMessage('');
    try {
      const r = await api('/platform/audit/verify');
      setVerify(r.data);
      const when = r.data?.verified_at
        ? formatDateTime(r.data.verified_at, formats.date_format, formats.time_format)
        : '';
      setMessage(
        r.data?.valid
          ? `Integrity chain valid${when ? ` · verified ${when}` : ''}`
          : `Integrity chain broken${when ? ` · verified ${when}` : ''}`,
      );
    } catch (err: any) {
      setError(err.message || 'Verify failed');
    }
  }

  async function exportFmt(fmt: 'csv' | 'pdf') {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (module.trim()) params.set('module', module.trim());
      if (action.trim()) params.set('action', action.trim());
      const exportFrom =
        fromDate || (isActivity ? activityDefaultFromDate() : '');
      if (exportFrom) params.set('from_date', exportFrom);
      if (toDate) params.set('to_date', toDate);
      if (deliveryOnly) params.set('delivery_only', 'true');
      params.set('format', fmt);
      const res = await fetch(`${apiBase}/platform/audit/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error(`${fmt.toUpperCase()} export failed`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `platform-audit-logs.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${fmt.toUpperCase()} downloaded`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function deliverySummary(row: AuditRow) {
    const d = row.details || {};
    if (row.action !== 'platform.email.delivery' && d.sent == null && !d.mode) return null;
    return `sent=${String(d.sent)} · mode=${d.mode || '—'} · to=${d.recipient || '—'}${
      d.error ? ` · error=${d.error}` : ''
    }`;
  }

  return (
    <PlatformShell>
      <h1>{isActivity ? 'Platform activity' : 'Platform audit'}</h1>
      <p className="muted">
        Events recorded against the Ribdigi House platform tenant.
        {isActivity
          ? ' Activity defaults to the last 7 days when from_date is omitted.'
          : ' Activity is an alias of this surface.'}{' '}
        Email delivery outcomes appear as platform.email.delivery (no fabricated success).
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0', alignItems: 'center' }}
      >
        <input
          value={module}
          onChange={(e) => setModule(e.target.value)}
          placeholder="Module (e.g. platform_tenants)"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 200 }}
        />
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="Action (e.g. platform.tenant.create)"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 220 }}
        />
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          aria-label="From date"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          aria-label="To date"
          style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <label className="muted" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={deliveryOnly}
            onChange={(e) => setDeliveryOnly(e.target.checked)}
          />
          Delivery only
        </label>
        <button
          type="submit"
          style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}
        >
          Filter
        </button>
        <button type="button" onClick={() => exportFmt('csv')}>
          Export CSV
        </button>
        <button type="button" onClick={() => exportFmt('pdf')}>
          Export PDF
        </button>
        <button type="button" onClick={runVerify}>
          Verify chain
        </button>
      </form>
      {error && <p>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}
      {verify && (
        <div className="card" style={{ marginBottom: 16, maxWidth: 480 }}>
          <p>Valid: {String(verify.valid)}</p>
          <p>Checked: {verify.checked}</p>
          {verify.verified_at && (
            <p>
              Verified:{' '}
              {formatDateTime(verify.verified_at, formats.date_format, formats.time_format)}
            </p>
          )}
          {verify.broken_at && <p>Broken at id: {verify.broken_at}</p>}
          {verify.broken_created_at && (
            <p>
              Broken event:{' '}
              {formatDateTime(verify.broken_created_at, formats.date_format, formats.time_format)}
            </p>
          )}
        </div>
      )}
      <table className="table" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>When</th>
            <th>Action</th>
            <th>Module</th>
            <th>Entity</th>
            <th>User</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id || `${row.action}-${row.created_at}`}>
              <td>
                {formatDateTime(row.created_at, formats.date_format, formats.time_format)}
              </td>
              <td>{row.action}</td>
              <td>{row.module}</td>
              <td>
                {row.entity}
                {row.entity_id ? ` · ${row.entity_id}` : ''}
              </td>
              <td>{row.user_id || '—'}</td>
              <td className="muted" style={{ maxWidth: 320, fontSize: 13 }}>
                {deliverySummary(row) ||
                  (row.details && Object.keys(row.details).length
                    ? JSON.stringify(row.details)
                    : '—')}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">
                {isActivity
                  ? 'No platform activity in this window. Activity defaults to the last 7 days when from_date is omitted.'
                  : 'No platform audit events yet.'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </PlatformShell>
  );
}
