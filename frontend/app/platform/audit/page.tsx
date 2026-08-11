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

  useEffect(() => {
    api('/platform/audit')
      .then((r) => setItems(r.data?.items || []))
      .catch((err) => setError(err.message || 'Failed to load audit'));
  }, []);

  return (
    <PlatformShell>
      <h1>Platform audit</h1>
      <p className="muted">Events recorded against the Ribdigi House platform tenant.</p>
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
