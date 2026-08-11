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

const MODULES = [
  'dashboard',
  'inventory',
  'sales',
  'pos',
  'purchasing',
  'expenses',
  'accounting',
  'credit',
  'tax',
  'stores',
  'reports',
  'notifications',
  'audit',
  'ai',
  'security',
  'users',
  'customers',
  'suppliers',
];

export default function AdminPermissionsPage() {
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [editRole, setEditRole] = useState('');
  const [matrix, setMatrix] = useState<Record<string, string[]>>({});
  const [matrixScope, setMatrixScope] = useState('own');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
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
    refresh()
      .then(() => {
        if (typeof window === 'undefined') return;
        const q = new URLSearchParams(window.location.search).get('role');
        if (q) setEditRole(q);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!editRole) return;
    const role = roles.find((r) => r.role === editRole);
    if (!role || role.system) return;
    setMatrix({ ...(role.permissions || {}) });
    setMatrixScope(role.record_scope || 'own');
  }, [editRole, roles]);

  async function saveMatrix() {
    if (!editRole) return;
    setError('');
    setMessage('');
    try {
      await api(`/roles/${editRole}/permissions`, {
        method: 'PUT',
        body: JSON.stringify({ permissions: matrix, record_scope: matrixScope }),
      });
      setMessage('Role permissions updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function toggleAction(module: string, action: string) {
    setMatrix((prev) => {
      const current = new Set(prev[module] || []);
      if (current.has(action)) current.delete(action);
      else current.add(action);
      const next = { ...prev };
      if (current.size) next[module] = Array.from(current);
      else delete next[module];
      return next;
    });
  }

  const customRoles = roles.filter((r) => !r.system);

  return (
    <Shell>
      <h1>Permissions</h1>
      <p className="muted">
        Module/action matrix for custom tenant roles. Create roles on{' '}
        <Link href="/admin/roles">Roles</Link>; assign on <Link href="/users">Users</Link>.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <label className="muted">
        Custom role{' '}
        <select
          value={editRole}
          onChange={(e) => setEditRole(e.target.value)}
          style={{ padding: 8, marginLeft: 8 }}
        >
          <option value="">Select…</option>
          {customRoles.map((r) => (
            <option key={r.role} value={r.role}>
              {r.label} ({r.role})
            </option>
          ))}
        </select>
      </label>

      {!editRole && <p className="muted" style={{ marginTop: 16 }}>Select a custom role to edit permissions.</p>}

      {canWrite && editRole && (
        <div className="card" style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 18 }}>Permission matrix · {editRole}</h2>
          <select
            value={matrixScope}
            onChange={(e) => setMatrixScope(e.target.value)}
            style={{ marginBottom: 12, padding: 8 }}
          >
            <option value="own">own</option>
            <option value="department">department</option>
            <option value="branch">branch</option>
            <option value="all">all</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Module</th>
                <th>read</th>
                <th>write</th>
                <th>approve</th>
              </tr>
            </thead>
            <tbody>
              {MODULES.map((mod) => (
                <tr key={mod}>
                  <td>{mod}</td>
                  {(['read', 'write', 'approve'] as const).map((action) => (
                    <td key={action}>
                      <input
                        type="checkbox"
                        checked={(matrix[mod] || []).includes(action)}
                        onChange={() => toggleAction(mod, action)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button type="button" onClick={saveMatrix}>
              Save permissions
            </button>
            <button type="button" onClick={() => setEditRole('')}>
              Close
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}
