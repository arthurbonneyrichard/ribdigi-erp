'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import Shell from '../../../components/Shell';
import { api } from '../../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type RoleRow = {
  role: string;
  label: string;
  org_chart_label?: string;
  system?: boolean;
  permissions?: Record<string, string[]>;
  record_scope?: string;
  is_active?: boolean;
};

const emptyRoleForm = {
  slug: '',
  label: '',
  base_role: 'cashier',
  record_scope: 'own',
};

export default function AdminRolesPage() {
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [roleForm, setRoleForm] = useState(emptyRoleForm);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  // Stage 124 R1 — role_active → GET /roles?is_active=
  const [roleActiveFilter, setRoleActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('role_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });

  async function refresh(opts?: { roleActive?: string }) {
    const roleActive = opts?.roleActive !== undefined ? opts.roleActive : roleActiveFilter;
    const roleQs =
      roleActive === 'true'
        ? '?is_active=true'
        : roleActive === 'false'
          ? '?is_active=false'
          : roleActive === 'all'
            ? '?active_only=false'
            : '';
    const [rolesRes, meRes] = await Promise.all([api(`/roles${roleQs}`), api('/me')]);
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

  // Stage 104 R1 / Stage 110 A1 — honor Shell #create / #custom / #system
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

  async function createRole(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/roles', {
        method: 'POST',
        body: JSON.stringify({
          slug: roleForm.slug.trim().toLowerCase(),
          label: roleForm.label.trim(),
          base_role: roleForm.base_role,
          record_scope: roleForm.record_scope,
        }),
      });
      setRoleForm(emptyRoleForm);
      setMessage('Custom role created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteRole(slug: string) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${slug}`, { method: 'DELETE' });
      setMessage('Custom role deleted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRoleActive(slug: string, next: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${slug}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: next }),
      });
      setMessage(next ? 'Custom role reactivated' : 'Custom role deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const systemBases = roles.filter(
    (r) => r.system && r.role !== 'super_admin' && r.role !== 'company_admin'
  );
  const customRoles = roles.filter((r) => !r.system);

  return (
    <Shell>
      <h1>Roles</h1>
      <p className="muted">
        System and custom tenant roles. Assign users on{' '}
        <Link href="/users">Users</Link>. Filter custom roles via <code>role_active</code> →{' '}
        <code>GET /roles?is_active=</code> (Stage 124 R1).
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
        <label className="muted">
          Custom role status{' '}
          <select
            value={roleActiveFilter}
            onChange={(e) => {
              const v = e.target.value;
              setRoleActiveFilter(v);
              const url = new URL(window.location.href);
              if (v === 'true' || v === 'false') url.searchParams.set('role_active', v);
              else url.searchParams.delete('role_active');
              const qs = url.searchParams.toString();
              window.history.replaceState(
                {},
                '',
                `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`
              );
              refresh({ roleActive: v }).catch((err) => setError(err.message));
            }}
            aria-label="Custom role active filter"
          >
            <option value="">Active customs (default)</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
            <option value="all">All customs</option>
          </select>
        </label>
        <button
          type="button"
          onClick={async () => {
            // Stage 124 X1 — custom roles CSV export
            setError('');
            setMessage('');
            try {
              const token = localStorage.getItem('token');
              const tenant = localStorage.getItem('tenant');
              const qs =
                roleActiveFilter === 'true'
                  ? '?is_active=true'
                  : roleActiveFilter === 'false'
                    ? '?is_active=false'
                    : roleActiveFilter === 'all'
                      ? '?active_only=false'
                      : '';
              const res = await fetch(`${apiBase}/roles/export${qs}`, {
                headers: {
                  ...(token ? { Authorization: `Bearer ${token}` } : {}),
                  ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
                },
              });
              if (!res.ok) throw new Error('Roles export failed');
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'custom_roles_export.csv';
              a.click();
              URL.revokeObjectURL(url);
              setMessage('Custom roles CSV exported');
            } catch (err: any) {
              setError(err.message || 'Roles export failed');
            }
          }}
        >
          Export custom roles CSV
        </button>
      </div>

      {canWrite && (
        <form
          id="create"
          onSubmit={createRole}
          style={{ display: 'grid', gap: 8, maxWidth: 420, marginBottom: 24 }}
        >
          <h2 style={{ fontSize: 18, margin: 0 }}>Create custom role</h2>
          <input
            value={roleForm.slug}
            onChange={(e) => setRoleForm({ ...roleForm, slug: e.target.value })}
            placeholder="Slug (e.g. store_lead)"
            required
          />
          <input
            value={roleForm.label}
            onChange={(e) => setRoleForm({ ...roleForm, label: e.target.value })}
            placeholder="Label"
            required
          />
          <select
            value={roleForm.base_role}
            onChange={(e) => setRoleForm({ ...roleForm, base_role: e.target.value })}
          >
            {systemBases.map((r) => (
              <option key={r.role} value={r.role}>
                Base: {r.label}
              </option>
            ))}
          </select>
          <select
            value={roleForm.record_scope}
            onChange={(e) => setRoleForm({ ...roleForm, record_scope: e.target.value })}
          >
            <option value="own">Record scope: own</option>
            <option value="store">Record scope: store</option>
            <option value="branch">Record scope: branch</option>
            <option value="all">Record scope: all</option>
          </select>
          <button type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
            {busy ? 'Saving…' : 'Create role'}
          </button>
        </form>
      )}

      <h2 style={{ fontSize: 18 }} id="custom">
        Custom roles
      </h2>
      {customRoles.length === 0 ? (
        <p className="muted">No custom roles yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Label</th>
              <th>Scope</th>
              <th>Active</th>
              {canWrite && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {customRoles.map((r) => (
              <tr key={r.role}>
                <td>{r.role}</td>
                <td>{r.label}</td>
                <td>{r.record_scope || 'own'}</td>
                <td>{r.is_active === false ? 'no' : 'yes'}</td>
                {canWrite && (
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Link href={`/admin/permissions?role=${encodeURIComponent(r.role)}`}>
                      Permissions
                    </Link>
                    {r.is_active === false ? (
                      <button type="button" onClick={() => setRoleActive(r.role, true)}>
                        Reactivate
                      </button>
                    ) : (
                      <button type="button" onClick={() => setRoleActive(r.role, false)}>
                        Deactivate
                      </button>
                    )}
                    <button type="button" onClick={() => deleteRole(r.role)}>
                      Delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 18, marginTop: 24 }} id="system">
        System roles (org chart)
      </h2>
      <p className="muted">
        Tenant Admin · Manager · Cashier · Accountant · Inventory Officer · Sales Officer (+ Super
        Admin). View permission matrices on{' '}
        <Link href="/admin/permissions">Permissions</Link>.
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Slug</th>
            <th>Label</th>
            <th>Org chart</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {roles
            .filter((r) => r.system)
            .map((r) => (
              <tr key={r.role}>
                <td>{r.role}</td>
                <td>{r.label}</td>
                <td>{r.org_chart_label || r.label}</td>
                <td>
                  <Link href={`/admin/permissions`}>View matrix</Link>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </Shell>
  );
}
