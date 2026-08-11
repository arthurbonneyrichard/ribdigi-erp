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
  const [catalog, setCatalog] = useState<any[]>([]);
  const [notes, setNotes] = useState('');
  const [extendDays, setExtendDays] = useState(14);
  const [suspendReason, setSuspendReason] = useState('');

  async function load() {
    setError('');
    try {
      const [r, plans] = await Promise.all([
        api(`/platform/tenants/${id}`),
        api('/platform/plans'),
      ]);
      setRow(r.data);
      setPlanCode(r.data?.plan_code || 'trial');
      setNotes(r.data?.platform_notes || '');
      setCatalog(plans.data?.catalog || []);
    } catch (err: any) {
      setError(err.message || 'Not found');
    }
  }

  const selectedPlan = catalog.find((p) => p.code === planCode);

  useEffect(() => {
    if (id) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function setLifecycle(action: 'suspend' | 'activate') {
    setBusy(true);
    setError('');
    try {
      const body =
        action === 'suspend'
          ? JSON.stringify({ reason: suspendReason.trim() || undefined })
          : '{}';
      await api(`/platform/tenants/${id}/${action}`, { method: 'POST', body });
      setMsg(action === 'suspend' ? 'Tenant suspended' : 'Tenant activated (billing deferred)');
      await load();
    } catch (err: any) {
      setError(err.message || `Failed to ${action}`);
    } finally {
      setBusy(false);
    }
  }

  async function extendTrial() {
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await api(`/platform/tenants/${id}/lifecycle`, {
        method: 'PATCH',
        body: JSON.stringify({ extend_trial_days: extendDays }),
      });
      setMsg(`Trial extended by ${extendDays} day(s) — not paid billing`);
      await load();
    } catch (err: any) {
      setError(err.message || 'Failed to extend trial');
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

  async function assistAdmin(kind: 'password-reset-email' | 'resend-verification') {
    setBusy(true);
    setError('');
    setMsg('');
    try {
      const r = await api(`/platform/tenants/${id}/admin/${kind}`, {
        method: 'POST',
        body: '{}',
      });
      if (r.data?.already_verified) {
        setMsg('Tenant Admin email already verified');
      } else {
        const sent = r.data?.email_delivery?.sent;
        setMsg(
          sent
            ? `Assist email sent to ${r.data?.email || 'Tenant Admin'}`
            : `Assist token issued for ${r.data?.email || 'Tenant Admin'} (mode: ${r.data?.email_delivery?.mode || 'n/a'})`,
        );
      }
      await load();
    } catch (err: any) {
      setError(err.message || 'Assist action failed');
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
              <div className="muted">Days remaining</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {row.days_remaining ?? '—'}
              </div>
            </div>
            <div className="card">
              <div className="muted">Trial ends</div>
              <div className="kpi" style={{ fontSize: 14 }}>
                {row.trial_ends_at || '—'}
              </div>
            </div>
            <div className="card">
              <div className="muted">Grace ends</div>
              <div className="kpi" style={{ fontSize: 14 }}>
                {row.grace_ends_at || '—'}
              </div>
            </div>
            <div className="card">
              <div className="muted">Last activity</div>
              <div className="kpi" style={{ fontSize: 16 }}>
                {row.last_activity_at || '—'}
              </div>
            </div>
            <div className="card">
              <div className="muted">Last House email delivery</div>
              <div className="kpi" style={{ fontSize: 14 }}>
                {row.last_house_email_delivery?.created_at || '—'}
              </div>
              {row.last_house_email_delivery ? (
                <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
                  sent={String(row.last_house_email_delivery.sent)} · mode=
                  {row.last_house_email_delivery.mode || '—'} · to=
                  {row.last_house_email_delivery.recipient || '—'}
                  {row.last_house_email_delivery.purpose
                    ? ` · ${row.last_house_email_delivery.purpose}`
                    : ''}
                </p>
              ) : (
                <p className="muted" style={{ marginTop: 8 }}>
                  No House assist email recorded for this tenant yet.
                </p>
              )}
            </div>
          </div>

          <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
            <div className="muted">Lifecycle (metadata — not paid billing / checkout)</div>
            <p className="muted" style={{ marginTop: 8 }}>
              Extend trial or reopen from grace/suspended without claiming billing Complete.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
              <input
                type="number"
                min={1}
                max={365}
                value={extendDays}
                onChange={(e) => setExtendDays(Number(e.target.value) || 1)}
                style={{ width: 90, padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
              />
              <button type="button" disabled={busy} onClick={extendTrial}>
                Extend trial
              </button>
            </div>
            {row.suspended_reason && (
              <p className="muted" style={{ marginTop: 8 }}>
                Suspended reason: {row.suspended_reason}
              </p>
            )}
          </div>

          <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
            <div className="muted">Plan code (metadata — billing deferred)</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <select
                value={planCode}
                onChange={(e) => setPlanCode(e.target.value)}
                style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
              >
                {(catalog.length
                  ? catalog.map((p) => p.code)
                  : row.plan_codes || ['trial', 'starter', 'growth', 'enterprise']
                ).map((c: string) => {
                  const meta = catalog.find((p) => p.code === c);
                  return (
                    <option key={c} value={c}>
                      {meta?.label ? `${c} — ${meta.label}` : c}
                    </option>
                  );
                })}
              </select>
              <button type="button" disabled={busy} onClick={savePlan}>
                Save plan
              </button>
            </div>
            {selectedPlan && (
              <p className="muted" style={{ marginTop: 8 }}>
                {selectedPlan.blurb || '—'} · Soft limits — stores:{' '}
                {selectedPlan.soft_limits?.stores ?? 'n/a'}, users:{' '}
                {selectedPlan.soft_limits?.users ?? 'n/a'} (informational; not checkout entitlements)
              </p>
            )}
          </div>
          <div className="card" style={{ marginTop: 16, maxWidth: 640 }}>
            <div className="muted">House operator notes (not visible on tenant Company profile)</div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value.slice(0, 2000))}
              rows={4}
              maxLength={2000}
              style={{ width: '100%', marginTop: 8, padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}
              placeholder="Internal notes for Ribdigi House operators"
            />
            <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
              {notes.length}/2000 characters
            </p>
            <button
              type="button"
              disabled={busy || notes.length > 2000}
              onClick={saveNotes}
              style={{ marginTop: 8 }}
            >
              Save notes
            </button>
          </div>

          <div className="card" style={{ marginTop: 16, maxWidth: 640 }}>
            <div className="muted">Tenant Admin assist (no impersonation)</div>
            {row.tenant_admin ? (
              <>
                <p style={{ marginTop: 8 }}>
                  {row.tenant_admin.full_name} · {row.tenant_admin.email} · verified:{' '}
                  {row.tenant_admin.email_verified ? 'yes' : 'no'}
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => assistAdmin('password-reset-email')}
                  >
                    Email password reset
                  </button>
                  <button
                    type="button"
                    disabled={busy || row.tenant_admin.email_verified}
                    onClick={() => assistAdmin('resend-verification')}
                  >
                    Resend verification
                  </button>
                </div>
              </>
            ) : (
              <p className="muted" style={{ marginTop: 8 }}>
                No active company_admin found for this tenant.
              </p>
            )}
          </div>

          <p className="muted" style={{ marginTop: 16 }}>
            Suspension changes status only — no data wipe. Active sessions are revoked.
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            {row.status !== 'suspended' ? (
              <>
                <input
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                  placeholder="Suspend reason (optional)"
                  style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1', minWidth: 220 }}
                />
                <button type="button" disabled={busy} onClick={() => setLifecycle('suspend')}>
                  Suspend
                </button>
              </>
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
