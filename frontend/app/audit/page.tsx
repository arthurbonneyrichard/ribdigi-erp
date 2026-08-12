'use client';

import { Suspense, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { formatDateTime, type RegionalFormats } from '../../lib/format';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function PageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [rows, setRows] = useState<any[]>([]);
  const [module, setModule] = useState(() => searchParams.get('module') || '');
  // Stage 110 A1 / Stage 114 O1 / Stage 116 A1 / Stage 117 S1 — Shell Audit module leaves honor ?module=
  const [action, setAction] = useState(() => searchParams.get('action') || '');
  const [fromDate, setFromDate] = useState(() => searchParams.get('from_date') || '');
  const [toDate, setToDate] = useState(() => searchParams.get('to_date') || '');
  const [verify, setVerify] = useState<any>(null);
  const [retention, setRetention] = useState<any>(null);
  const [archives, setArchives] = useState<any[]>([]);
  const [formats, setFormats] = useState<RegionalFormats>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  function syncUrl(next: {
    module?: string;
    action?: string;
    fromDate?: string;
    toDate?: string;
  }) {
    const params = new URLSearchParams();
    const nm = next.module !== undefined ? next.module : module;
    const na = next.action !== undefined ? next.action : action;
    const nf = next.fromDate !== undefined ? next.fromDate : fromDate;
    const nt = next.toDate !== undefined ? next.toDate : toDate;
    if (nm.trim()) params.set('module', nm.trim());
    if (na.trim()) params.set('action', na.trim());
    if (nf.trim()) params.set('from_date', nf.trim());
    if (nt.trim()) params.set('to_date', nt.trim());
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  async function refresh(overrides?: {
    module?: string;
    action?: string;
    fromDate?: string;
    toDate?: string;
  }) {
    const mod = overrides?.module !== undefined ? overrides.module : module;
    const act = overrides?.action !== undefined ? overrides.action : action;
    const fd = overrides?.fromDate !== undefined ? overrides.fromDate : fromDate;
    const td = overrides?.toDate !== undefined ? overrides.toDate : toDate;
    const params = new URLSearchParams();
    if (mod.trim()) params.set('module', mod.trim());
    if (act.trim()) params.set('action', act.trim());
    if (fd.trim()) params.set('from_date', fd.trim());
    if (td.trim()) params.set('to_date', td.trim());
    const q = params.toString() ? `?${params}` : '';
    const [logs, policy, archiveList] = await Promise.all([
      api(`/audit-logs${q}`),
      api('/audit-logs/retention').catch(() => ({ data: null })),
      api('/audit-logs/archives').catch(() => ({ data: [] })),
    ]);
    setRows(logs.data || []);
    setRetention(policy.data || null);
    setArchives(archiveList.data || []);
  }

  useEffect(() => {
    api('/me')
      .then((r) =>
        setFormats({
          date_format: r.data?.date_format,
          number_format: r.data?.number_format,
          time_format: r.data?.time_format,
        }),
      )
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const fromModule = searchParams.get('module') || '';
    const fromAction = searchParams.get('action') || '';
    const fromFrom = searchParams.get('from_date') || '';
    const fromTo = searchParams.get('to_date') || '';
    setModule(fromModule);
    setAction(fromAction);
    setFromDate(fromFrom);
    setToDate(fromTo);
    refresh({
      module: fromModule,
      action: fromAction,
      fromDate: fromFrom,
      toDate: fromTo,
    }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

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

  async function runColdArchive() {
    setError('');
    setMessage('');
    try {
      const r = await api('/audit-logs/archive-cold', { method: 'POST', body: '{}' });
      setMessage(
        r.data?.archived
          ? `Cold-archived ${r.data.archived} event(s)`
          : r.message || 'Nothing to archive',
      );
      await refresh();
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
      params.set('format', 'csv');
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

  async function exportPdf() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (module) params.set('module', module);
      if (action) params.set('action', action);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      params.set('format', 'pdf');
      const res = await fetch(`${base}/audit-logs/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error('PDF export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit-logs.pdf';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('PDF downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Audit Logs</h1>
      <p className="muted">
        Append-only activity trail with integrity verification
        {retention
          ? ` · ${retention.retention_years}-year retention · cold archive after ${retention.cold_archive_after_days}d`
          : ''}
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <input
          value={module}
          onChange={(e) => setModule(e.target.value)}
          placeholder="Module (auth, users…)"
        />
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="Action"
        />
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          aria-label="From date"
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          aria-label="To date"
        />
        <button
          onClick={() => {
            syncUrl({ module, action, fromDate, toDate });
            refresh().catch((e) => setError(e.message));
          }}
        >
          Filter
        </button>
        <button onClick={runVerify}>Verify chain</button>
        <button onClick={exportCsv}>Export CSV</button>
        <button onClick={exportPdf}>Export PDF</button>
        <button onClick={runColdArchive}>Run cold archive</button>
      </div>

      {verify && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p>Valid: {String(verify.valid)}</p>
          <p>Checked: {verify.checked}</p>
          {verify.broken_at && <p>Broken at: {verify.broken_at}</p>}
        </div>
      )}

      {retention && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Retention policy</h3>
          <p className="muted">{retention.notes}</p>
          <p>
            Purge allowed: {String(retention.purge_allowed)} · Archives on file: {archives.length}
          </p>
          {archives.slice(0, 5).map((a) => (
            <p key={a.id} className="muted">
              {a.event_count} events · {a.sha256?.slice(0, 12)}… · {a.storage_key}
            </p>
          ))}
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
            <th>Hash</th>
            <th>Cold</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                {formatDateTime(r.created_at, formats.date_format, formats.time_format)}
              </td>
              <td>{r.module}</td>
              <td>{r.action}</td>
              <td>
                {r.entity}
                {r.entity_id ? `:${String(r.entity_id).slice(0, 8)}` : ''}
              </td>
              <td>{r.user_id ? String(r.user_id).slice(0, 8) : '—'}</td>
              <td>{r.ip_address || '—'}</td>
              <td>{r.integrity_hash ? String(r.integrity_hash).slice(0, 10) : '—'}</td>
              <td>{r.archived_at ? 'yes' : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<main className="main"><p className="muted">Loading…</p></main>}>
      <PageInner />
    </Suspense>
  );
}
