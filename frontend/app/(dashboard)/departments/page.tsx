'use client';

import { useEffect, useState } from 'react';
import FormModal from '../../../components/FormModal';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { normalizeIndustry } from '../../../lib/industries';
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
  const [deptAddOpen, setDeptAddOpen] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [restaurantOps, setRestaurantOps] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  async function loadList(search = q) {
    const params = new URLSearchParams();
    if (search.trim()) params.set('q', search.trim());
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await api(`/departments${qs}`);
    setRows(res.data || []);
  }

  async function refresh(search = q) {
    const me = await getMe();
    const perms = (me.data?.permissions || {}) as Record<string, string[]>;
    setCanWrite(canWriteUsers(me.data?.role || '', perms));
    setRestaurantOps(normalizeIndustry(me.data?.industry) === 'restaurant');
    await loadList(search);
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
      setDeptAddOpen(false);
      if (created?.data?.id) {
        setRows((prev) => {
          const next = prev.filter((r) => r.id !== created.data.id);
          return [created.data, ...next];
        });
      }
      await loadList();
    } catch (err: any) {
      setError(err.message || 'Department was not created');
    } finally {
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
      <PageHeader
        title="Departments"
        subtitle={
          restaurantOps
            ? 'Departments in this restaurant. Each name must be unique. Assign staff to them in User Management.'
            : 'Departments in your company. Each name must be unique. Assign staff to them in User Management.'
        }
        actions={
          canWrite ? (
            <button
              type="button"
              className="list-btn-primary"
              onClick={() => setDeptAddOpen(true)}
              aria-label="Create department"
            >
              Create department
            </button>
          ) : undefined
        }
      />
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
          <option value="inactive">{restaurantOps ? 'Not in use' : 'Inactive'}</option>
        </select>
      </div>

      {canWrite && deptAddOpen ? (
        <FormModal
          title="Create department"
          busy={busy || submitting}
          dirty={Boolean(name.trim() || code.trim())}
          onClose={() => setDeptAddOpen(false)}
        >
        <form onSubmit={createDept} style={{ display: 'grid', gap: 8 }}>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Code (e.g. SALES)"
            aria-label="Department code"
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
        </FormModal>
      ) : null}

      <div className={restaurantOps ? 'list-table-wrap rest-dept-table' : undefined}>
      <table className="table">
        {restaurantOps && canWrite ? (
          <colgroup>
            <col style={{ width: '52%' }} />
            <col style={{ width: '18%' }} />
            <col style={{ width: '30%' }} />
          </colgroup>
        ) : null}
        <thead>
          <tr>
            {restaurantOps ? <th>Department</th> : <th>Code</th>}
            {restaurantOps ? null : <th>Name</th>}
            {restaurantOps ? <th>Status</th> : <th>Active</th>}
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 ? (
            <tr>
              <td colSpan={restaurantOps ? (canWrite ? 3 : 2) : (canWrite ? 4 : 3)} className="muted">
                {restaurantOps
                  ? (rows.length
                    ? 'No departments for this filter. Choose All statuses to see every department.'
                    : 'No departments yet. Create one when you are ready to group staff.')
                  : 'No departments match this filter.'}
              </td>
            </tr>
          ) : (
            visible.map((r) => (
              <tr key={r.id}>
                {restaurantOps ? (
                  <td data-label="Department">
                    {canWrite ? (
                      <input
                        defaultValue={r.name}
                        aria-label={`Edit department name ${r.code}`}
                        onBlur={(e) => rename(r, e.target.value)}
                      />
                    ) : (
                      r.name
                    )}
                    <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                      {r.code}
                    </span>
                  </td>
                ) : (
                  <td>{r.code}</td>
                )}
                {restaurantOps ? null : (
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
                )}
                <td data-label={restaurantOps ? 'Status' : undefined}>
                  {restaurantOps
                    ? (r.is_active === false ? 'Not in use' : 'Active')
                    : (r.is_active === false ? 'Inactive' : 'Active')}
                </td>
                {canWrite && (
                  <td data-label={restaurantOps ? 'Actions' : undefined}>
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
      </div>
    </>
  );
}
