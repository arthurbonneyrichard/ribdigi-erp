'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { formatDateTime, type RegionalFormats } from '../../lib/format';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [rows, setRows] = useState<any[]>([]);
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [verify, setVerify] = useState<any>(null);
  const [formats, setFormats] = useState<RegionalFormats>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function refresh() {
    const params = new URLSearchParams();
    if (module) params.set('module', module);
    if (action) params.set('action', action);
    const q = params.toString() ? `?${params}` : '';
    const r = await api(`/audit-logs${q}`);
    setRows(r.data || []);
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
    refresh().catch((err) => setError(err.message));
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
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      if (module) params.set('module', module);
      if (action) params.set('action', action);
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
      <p className="muted">Append-only activity trail with integrity verification</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <input value={module} onChange={(e) => setModule(e.target.value)} placeholder="Module (auth, users…)" />
        <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Action" />
        <button onClick={() => refresh().catch((e) => setError(e.message))}>Filter</button>
        <button onClick={runVerify}>Verify chain</button>
        <button onClick={exportCsv}>Export CSV</button>
        <button onClick={exportPdf}>Export PDF</button>
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
            <th>Hash</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
