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
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [planCode, setPlanCode] = useState('trial');
  const [notes, setNotes] = useState('');

  async function load() {
    setError('');
    try {
      const r = await api(`/platform/tenants/${id}`);
      setRow(r.data);
      setPlanCode(r.data?.plan_code || 'trial');
      setNotes(r.data?.platform_notes || '');
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

  async function savePlan() {
    setBusy(true);
    setError('');
    try {
      await api(`/platform/tenants/${id}/plan`, {
        method: 'PATCH',
        body: JSON.stringify({ plan_code: planCode }),
      });
      await load();
    } catch (err: any) {
      setError(err.message || 'Failed to update plan');
    } finally {
      setBusy(false);
    }
  }

  async function saveNotes() {
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await api(`/platform/tenants/${id}/notes`, {
        method: 'PATCH',
        body: JSON.stringify({ platform_notes: notes }),
      });
      setMsg('Operator notes saved');
      await load();
    } catch (err: any) {
      setError(err.message || 'Failed to save notes');
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
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}
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
            <div className="card">
              <div className="muted">Last activity</div>
              <div className="kpi" style={{ fontSize: 16 }}>
                {row.last_activity_at || '—'}
              </div>
            </div>
          </div>
          <div className="card" style={{ marginTop: 16, maxWidth: 420 }}>
            <div className="muted">Plan code (metadata — billing deferred)</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <select
                value={planCode}
                onChange={(e) => setPlanCode(e.target.value)}
                style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
              >
                {(row.plan_codes || ['trial', 'starter', 'growth', 'enterprise']).map((c: string) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <button type="button" disabled={busy} onClick={savePlan}>
                Save plan
              </button>
            </div>
          </div>
          <div className="card" style={{ marginTop: 16, maxWidth: 640 }}>
            <div className="muted">House operator notes (not visible on tenant Company profile)</div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              style={{ width: '100%', marginTop: 8, padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
              placeholder="Internal notes for Ribdigi House operators"
            />
            <button type="button" disabled={busy} onClick={saveNotes} style={{ marginTop: 8 }}>
              Save notes
            </button>
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            Suspension changes status only — no data wipe. Active sessions are revoked.
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
