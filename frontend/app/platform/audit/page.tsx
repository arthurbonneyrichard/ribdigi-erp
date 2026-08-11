'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type AuditRow = {
  id?: string;
  action?: string;
  module?: string;
  entity?: string;
  entity_id?: string;
  created_at?: string;
  user_id?: string;
};

export default function PlatformAuditPage() {
  const [items, setItems] = useState<AuditRow[]>([]);
  const [error, setError] = useState('');
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');

  async function load() {
    setError('');
    try {
      const params = new URLSearchParams();
      if (module.trim()) params.set('module', module.trim());
      if (action.trim()) params.set('action', action.trim());
      const r = await api(`/platform/audit?${params.toString()}`);
      setItems(r.data?.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PlatformShell>
      <h1>Platform audit</h1>
      <p className="muted">
        Events recorded against the Ribdigi House platform tenant. Activity is an alias of this
        surface.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0' }}
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
        <button
          type="submit"
          style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}
        >
          Filter
        </button>
      </form>
      {error && <p>{error}</p>}
      <table className="table" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>When</th>
            <th>Action</th>
            <th>Module</th>
            <th>Entity</th>
            <th>User</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id || `${row.action}-${row.created_at}`}>
              <td>{row.created_at || '—'}</td>
              <td>{row.action}</td>
              <td>{row.module}</td>
              <td>
                {row.entity}
                {row.entity_id ? ` · ${row.entity_id}` : ''}
              </td>
              <td>{row.user_id || '—'}</td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                No platform audit events yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </PlatformShell>
  );
}
