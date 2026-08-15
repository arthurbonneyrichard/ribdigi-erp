'use client';

import { useCallback, useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const JOB_LABELS: Record<string, string> = {
  scan_low_stock: 'Low stock alerts',
  scan_payment_due: 'Payment due alerts',
  scan_quotation_expiry: 'Quotation expiry alerts',
  scan_recurring_expense_due: 'Recurring expense due alerts',
  generate_recurring_expenses: 'Generate recurring expenses',
  run_due_backups: 'Due backups',
  scan_trial_lifecycle: 'Trial lifecycle',
  run_due_report_emails: 'Report emails',
  refresh_fx_rates: 'Refresh FX rates',
  sync_bank_feeds: 'Sync bank feeds',
  archive_cold_audit_logs: 'Archive cold audit logs',
  retry_due_webhooks: 'Retry webhooks',
  scan_ai_security_alerts: 'AI security alerts',
  send_weekly_ai_insight_digest: 'Weekly AI insight digest',
};

const RUN_ROLES = new Set(['super_admin', 'platform_owner']);

function beatForJob(beat: Record<string, number | string> | null | undefined, job: string): string {
  if (!beat) return '—';
  const minutesKey = `${job}_minutes`;
  const secondsKey = `${job}_seconds`;
  const scheduleKey = `${job}_schedule`;
  if (typeof beat[minutesKey] === 'number') return `every ${beat[minutesKey]} min`;
  if (typeof beat[secondsKey] === 'number') return `every ${beat[secondsKey]} sec`;
  if (typeof beat[scheduleKey] === 'string') return beat[scheduleKey];
  return '—';
}

export default function Page() {
  const [info, setInfo] = useState<any>(null);
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<any>(null);

  const canRun = RUN_ROLES.has(role);

  const refresh = useCallback(async () => {
    const [jobsRes, meRes] = await Promise.all([api('/jobs'), api('/me')]);
    setInfo(jobsRes.data || null);
    setRole(meRes.data?.role || '');
  }, []);

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Failed to load jobs'));
  }, [refresh]);

  async function runJob(name: string, enqueue: boolean) {
    setError('');
    setMessage('');
    setBusy(`${name}:${enqueue ? 'enqueue' : 'run'}`);
    try {
      const q = enqueue ? '?enqueue=true' : '';
      const r = await api(`/jobs/${name}/run${q}`, { method: 'POST', body: '{}' });
      setLastResult(r.data || null);
      setMessage(r.message || (enqueue ? `Enqueued ${name}` : `Ran ${name}`));
    } catch (err: any) {
      setError(err.message || 'Job failed');
    } finally {
      setBusy(null);
    }
  }

  const jobs: string[] = info?.jobs || [];
  const beat = info?.beat || {};

  return (
    <Shell>
      <h1>Jobs</h1>
      <p className="muted">
        Scheduled Celery handlers and beat intervals. Company admins can view;{' '}
        <strong>super_admin</strong> / <strong>platform_owner</strong> can run sync or enqueue.
        See <code>docs/CELERY_RELIABILITY_RUNBOOK.md</code>.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#0f766e' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 6 }}>
        <h3 style={{ margin: 0 }}>Broker</h3>
        <div className="muted" style={{ fontSize: 13 }}>
          Celery enabled: {info?.celery_enabled ? 'yes' : 'no'}
          {info?.task_always_eager ? ' · always eager' : ''}
        </div>
        <div className="muted" style={{ fontSize: 12, wordBreak: 'break-all' }}>
          Broker: {info?.broker || '—'}
        </div>
        <div className="muted" style={{ fontSize: 12, wordBreak: 'break-all' }}>
          Results: {info?.result_backend || '—'}
        </div>
        <div>
          <button type="button" onClick={() => refresh().catch((e) => setError(e.message))} disabled={!!busy}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Handlers</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Beat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">
                  No jobs loaded
                </td>
              </tr>
            )}
            {jobs.map((name) => (
              <tr key={name}>
                <td>
                  <div style={{ fontWeight: 600 }}>{JOB_LABELS[name] || name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {name}
                  </div>
                </td>
                <td className="muted" style={{ fontSize: 13 }}>
                  {beatForJob(beat, name)}
                </td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {canRun ? (
                    <>
                      <button
                        type="button"
                        disabled={!!busy}
                        onClick={() => runJob(name, false)}
                      >
                        {busy === `${name}:run` ? 'Running…' : 'Run sync'}
                      </button>
                      <button
                        type="button"
                        disabled={!!busy || !info?.celery_enabled}
                        title={!info?.celery_enabled ? 'CELERY_ENABLED is false' : undefined}
                        onClick={() => runJob(name, true)}
                      >
                        {busy === `${name}:enqueue` ? 'Enqueue…' : 'Enqueue'}
                      </button>
                    </>
                  ) : (
                    <span className="muted" style={{ fontSize: 12 }}>
                      View only
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lastResult && (
        <div className="card">
          <h3>Last result</h3>
          <pre
            style={{
              margin: 0,
              fontSize: 12,
              overflow: 'auto',
              maxHeight: 320,
              whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify(lastResult, null, 2)}
          </pre>
        </div>
      )}
    </Shell>
  );
}
