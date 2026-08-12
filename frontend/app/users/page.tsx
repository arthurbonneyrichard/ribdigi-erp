'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type RoleRow = { role: string; label: string };
type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  phone?: string | null;
};

const emptyForm = {
  email: '',
  full_name: '',
  password: '',
  role: 'cashier',
  phone: '',
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type ImportReportRow = {
  line: number;
  email: string;
  full_name: string;
  role: string;
  ok: boolean;
  errors: string[];
};

type ImportReport = {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  can_commit: boolean;
  imported?: number;
  rows: ImportReportRow[];
};

export default function Page() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);

  async function refresh() {
    const [usersRes, rolesRes, meRes] = await Promise.all([
      api('/users'),
      api('/roles'),
      api('/me'),
    ]);
    setRows(usersRes.data || []);
    setRoles(rolesRes.data || []);
    const perms = meRes.data?.permissions || {};
    const role = meRes.data?.role || '';
    setCanWrite(
      role === 'super_admin' ||
        role === 'company_admin' ||
        perms?.['*']?.includes('*') ||
        (perms.users || []).includes('write') ||
        (perms.users || []).includes('*')
    );
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email,
          full_name: form.full_name,
          password: form.password,
          role: form.role,
          phone: form.phone || null,
        }),
      });
      setForm(emptyForm);
      setMessage('User created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function setRole(userId: string, role: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      setMessage('Role updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setActive(userId: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      if (is_active) {
        await api(`/users/${userId}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage('User activated');
      } else {
        await api(`/users/${userId}`, { method: 'DELETE' });
        setMessage('User deactivated');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadImportTemplate() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/users/import/template`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Template download failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'users-import-template.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('CSV template downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runUserImport(dryRun: boolean) {
    if (!importFile) {
      setError('Choose a CSV file first');
      return;
    }
    setError('');
    setMessage('');
    setImportBusy(true);
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const formData = new FormData();
      formData.append('file', importFile);
      const res = await fetch(`${apiBase}/users/import?dry_run=${dryRun ? 'true' : 'false'}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: formData,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = body.detail;
        if (detail && typeof detail === 'object' && detail.report) {
          setImportReport(detail.report);
          throw new Error(detail.message || 'Import validation failed');
        }
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.message || body.message || 'Import failed'
        );
      }
      setImportReport(body.data as ImportReport);
      if (dryRun) {
        setMessage(
          body.data?.can_commit
            ? `Validation OK — ${body.data.valid_rows} user(s) ready to import`
            : `Validation found ${body.data?.error_rows || 0} error row(s)`
        );
      } else {
        setMessage(`Imported ${body.data?.imported || 0} user(s)`);
        setImportFile(null);
        await refresh();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <Shell>
      <h1>User Management</h1>
      <p className="muted">Create users, assign system roles, and activate or deactivate accounts.</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {canWrite && (
        <div className="card" style={{ margin: '20px 0', display: 'grid', gap: 12 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Bulk import users</h2>
          <p className="muted" style={{ margin: 0 }}>
            Download the CSV template, fill rows (role must be a system role; temporary password must
            meet policy), validate, then import. Import is all-or-nothing.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={downloadImportTemplate}>
              Download CSV template
            </button>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              setImportFile(e.target.files?.[0] || null);
              setImportReport(null);
            }}
          />
          {importFile && <p className="muted">Selected: {importFile.name}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => runUserImport(true)}
              disabled={!importFile || importBusy}
            >
              {importBusy ? 'Working…' : 'Validate'}
            </button>
            <button
              type="button"
              onClick={() => runUserImport(false)}
              disabled={!importFile || importBusy || !importReport?.can_commit}
            >
              Import valid rows
            </button>
          </div>
          {importReport && (
            <div>
              <p className="muted">
                {importReport.total_rows} rows · {importReport.valid_rows} valid ·{' '}
                {importReport.error_rows} errors
                {importReport.imported != null ? ` · imported ${importReport.imported}` : ''}
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Email</th>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {importReport.rows.map((r) => (
                    <tr key={`${r.line}-${r.email}`}>
                      <td>{r.line}</td>
                      <td>{r.email || '—'}</td>
                      <td>{r.full_name || '—'}</td>
                      <td>{r.role || '—'}</td>
                      <td style={{ color: r.ok ? '#047857' : '#b91c1c' }}>{r.ok ? 'OK' : 'Error'}</td>
                      <td>{r.errors?.length ? r.errors.join('; ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {canWrite && (
        <form onSubmit={createUser} style={{ margin: '20px 0' }}>
          <h2 style={{ fontSize: 18 }}>Create user</h2>
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Temporary password"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Phone (optional)"
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            {roles
              .filter((r) => r.role !== 'super_admin')
              .map((r) => (
                <option key={r.role} value={r.role}>
                  {r.label}
                </option>
              ))}
          </select>
          <button type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
            {busy ? 'Creating…' : 'Create user'}
          </button>
        </form>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Full Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.full_name}</td>
              <td>{r.email}</td>
              <td>
                {canWrite ? (
                  <select value={r.role} onChange={(e) => setRole(r.id, e.target.value)}>
                    {roles.map((role) => (
                      <option key={role.role} value={role.role}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.role
                )}
              </td>
              <td>{r.is_active ? 'Yes' : 'No'}</td>
              {canWrite && (
                <td>
                  {r.is_active ? (
                    <button type="button" onClick={() => setActive(r.id, false)}>
                      Deactivate
                    </button>
                  ) : (
                    <button type="button" onClick={() => setActive(r.id, true)}>
                      Activate
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
