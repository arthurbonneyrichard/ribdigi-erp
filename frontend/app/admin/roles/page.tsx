'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import Shell from '../../../components/Shell';
import { api } from '../../../lib/api';

type RoleRow = {
  role: string;
  label: string;
  system?: boolean;
  permissions?: Record<string, string[]>;
  record_scope?: string;
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

  async function refresh() {
    const [rolesRes, meRes] = await Promise.all([api('/roles'), api('/me')]);
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

  const systemBases = roles.filter(
    (r) => r.system && r.role !== 'super_admin' && r.role !== 'company_admin'
  );
  const customRoles = roles.filter((r) => !r.system);

  return (
    <Shell>
      <h1>Roles</h1>
      <p className="muted">
        System and custom tenant roles. Assign users on{' '}
        <Link href="/users">Users</Link>; edit module actions on{' '}
        <Link href="/admin/permissions">Permissions</Link>.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {canWrite && (
        <form onSubmit={createRole} style={{ margin: '20px 0', maxWidth: 520 }}>
          <h2 style={{ fontSize: 18 }}>Create custom role</h2>
          <input
            value={roleForm.slug}
            onChange={(e) => setRoleForm({ ...roleForm, slug: e.target.value })}
            placeholder="Slug (e.g. senior_cashier)"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <input
            value={roleForm.label}
            onChange={(e) => setRoleForm({ ...roleForm, label: e.target.value })}
            placeholder="Label"
            required
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          />
          <select
            value={roleForm.base_role}
            onChange={(e) => setRoleForm({ ...roleForm, base_role: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            {systemBases.map((r) => (
              <option key={r.role} value={r.role}>
                Copy permissions from {r.label}
              </option>
            ))}
          </select>
          <select
            value={roleForm.record_scope}
            onChange={(e) => setRoleForm({ ...roleForm, record_scope: e.target.value })}
            style={{ width: '100%', padding: 10, marginBottom: 8 }}
          >
            <option value="own">Record scope: own</option>
            <option value="department">Record scope: department</option>
            <option value="branch">Record scope: branch</option>
            <option value="all">Record scope: all</option>
          </select>
          <button type="submit" disabled={busy} style={{ padding: '10px 16px' }}>
            {busy ? 'Saving…' : 'Create role'}
          </button>
        </form>
      )}

      <h2 style={{ fontSize: 18 }}>Custom roles</h2>
      {customRoles.length === 0 ? (
        <p className="muted">No custom roles yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Label</th>
              <th>Scope</th>
              {canWrite && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {customRoles.map((r) => (
              <tr key={r.role}>
                <td>{r.role}</td>
                <td>{r.label}</td>
                <td>{r.record_scope || 'own'}</td>
                {canWrite && (
                  <td style={{ display: 'flex', gap: 8 }}>
                    <Link href={`/admin/permissions?role=${encodeURIComponent(r.role)}`}>
                      Permissions
                    </Link>
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

      <h2 style={{ fontSize: 18, marginTop: 24 }}>System roles</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Role</th>
            <th>Label</th>
          </tr>
        </thead>
        <tbody>
          {roles
            .filter((r) => r.system)
            .map((r) => (
              <tr key={r.role}>
                <td>{r.role}</td>
                <td>{r.label}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </Shell>
  );
}
