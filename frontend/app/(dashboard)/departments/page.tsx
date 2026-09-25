'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';

type Dept = {
  id: string;
  code: string;
  name: string;
  branch_id?: string | null;
  is_active?: boolean;
};

function canWriteUsers(role: string, perms: Record<string, string[]>) {
  if (role === 'company_admin' || role === 'super_admin' || perms['*']?.includes('*')) return true;
  const u = perms.users || [];
  return u.includes('write') || u.includes('create') || u.includes('*');
}

export default function Page() {
  const [rows, setRows] = useState<Dept[]>([]);
  const [q, setQ] = useState('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  async function refresh(search = q) {
    const me = await getMe();
    const perms = (me.data?.permissions || {}) as Record<string, string[]>;
    setCanWrite(canWriteUsers(me.data?.role || '', perms));
    const params = new URLSearchParams();
    if (search.trim()) params.set('q', search.trim());
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await api(`/departments${qs}`);
    setRows(res.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  const visible = rows.filter((r) => {
    if (statusFilter === 'all') return true;
    const active = r.is_active !== false;
    return statusFilter === 'inactive' ? !active : active;
  });

  async function createDept(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    const nameTrim = name.trim();
    const codeTrim = (code.trim() || nameTrim).toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40);
    if (!nameTrim || !codeTrim) {
      setError('Department name is required.');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    setSubmitting(true);
    try {
      const created = await api('/departments', {
        method: 'POST',
        body: JSON.stringify({
          code: codeTrim,
          name: nameTrim,
        }),
      });
      setCode('');
      setName('');
      setMessage('Department created');
      if (created?.data?.id) {
        setRows((prev) => {
          const next = prev.filter((r) => r.id !== created.data.id);
          return [created.data, ...next];
        });
      }
      setBusy(false);
      setSubmitting(false);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Department was not created');
      setBusy(false);
      setSubmitting(false);
    }
  }

  async function toggleActive(row: Dept) {
    setError('');
    try {
      await api(`/departments/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: row.is_active === false }),
      });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function rename(row: Dept, nextName: string) {
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === row.name) return;
    setError('');
    try {
      await api(`/departments/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: trimmed }),
      });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Departments</h1>
      <p className="muted">
        Tenant-scoped departments. Names must be unique in this company. Assign users on User
        Management.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '12px 0' }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search departments"
          aria-label="Search departments"
        />
        <button
          type="button"
          onClick={() => refresh(q).catch((err) => setError(err.message))}
          aria-label="Search department list"
        >
          Search
        </button>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
          aria-label="Department status filter"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {canWrite && (
        <form className="card" onSubmit={createDept} style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Create department</h2>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Code (e.g. SALES)"
            aria-label="Department code"
            required
          />
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name (e.g. Sales)"
            aria-label="Department name"
            required
          />
          <button type="submit" disabled={busy || submitting} aria-label="Create department">
            {busy ? 'Saving…' : 'Create department'}
          </button>
          {message ? <p className="form-flash ok" role="status">{message}</p> : null}
          {error ? <p className="form-flash err" role="alert">{error}</p> : null}
        </form>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Active</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 ? (
            <tr>
              <td colSpan={canWrite ? 4 : 3} className="muted">
                No departments match this filter.
              </td>
            </tr>
          ) : (
            visible.map((r) => (
              <tr key={r.id}>
                <td>{r.code}</td>
                <td>
                  {canWrite ? (
                    <input
                      defaultValue={r.name}
                      aria-label={`Edit department name ${r.code}`}
                      onBlur={(e) => rename(r, e.target.value)}
                    />
                  ) : (
                    r.name
                  )}
                </td>
                <td>{r.is_active === false ? 'Inactive' : 'Active'}</td>
                {canWrite && (
                  <td>
                    <button
                      type="button"
                      onClick={() => toggleActive(r)}
                      aria-label={
                        r.is_active === false
                          ? `Activate department ${r.code}`
                          : `Deactivate department ${r.code}`
                      }
                    >
                      {r.is_active === false ? 'Activate' : 'Deactivate'}
                    </button>
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </>
  );
}
