'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import PlatformShell from '../../../../components/PlatformShell';
import { api } from '../../../../lib/api';

export default function PlatformTenantDetailPage() {
  const params = useParams();
  const id = String(params?.id || '');
  const [row, setRow] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setError('');
    try {
      const r = await api(`/platform/tenants/${id}`);
      setRow(r.data);
    } catch (err: any) {
      setError(err.message || 'Not found');
    }
  }

  useEffect(() => {
    if (id) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function setLifecycle(action: 'suspend' | 'activate') {
    setBusy(true);
    try {
      await api(`/platform/tenants/${id}/${action}`, { method: 'POST', body: '{}' });
      await load();
    } catch (err: any) {
      setError(err.message || `Failed to ${action}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PlatformShell>
      <p>
        <Link href="/platform/tenants">← Tenants</Link>
      </p>
      <h1>{row?.company_name || 'Tenant'}</h1>
      {error && <p>{error}</p>}
      {row && (
        <>
          <div className="grid" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="muted">Slug</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {row.slug}
              </div>
            </div>
            <div className="card">
              <div className="muted">Status</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {row.status}
              </div>
            </div>
            <div className="card">
              <div className="muted">Users</div>
              <div className="kpi">{row.user_count ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Stores</div>
              <div className="kpi">{row.store_count ?? 0}</div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            Suspension changes status only — no data wipe.
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            {row.status !== 'suspended' ? (
              <button type="button" disabled={busy} onClick={() => setLifecycle('suspend')}>
                Suspend
              </button>
            ) : (
              <button type="button" disabled={busy} onClick={() => setLifecycle('activate')}>
                Activate
              </button>
            )}
          </div>
        </>
      )}
    </PlatformShell>
  );
}
