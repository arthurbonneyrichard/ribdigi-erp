'use client';

import { useCallback, useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { Metric } from '../../../components/PlatformUi';
import '../platform/platform-ui.css';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';

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
  process_subscription_renewals: 'Subscription renewals',
};

const PLATFORM_VIEW_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

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
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<any>(null);

  const allowed = PLATFORM_VIEW_ROLES.has(role);
  const canRun = RUN_ROLES.has(role);

  const refresh = useCallback(async () => {
    const meRes = await getMe();
    const nextRole = meRes.data?.role || '';
    setRole(nextRole);
    setReady(true);
    if (!PLATFORM_VIEW_ROLES.has(nextRole)) {
      setInfo(null);
      return;
    }
    const jobsRes = await api('/jobs');
    setInfo(jobsRes.data || null);
  }, []);

  useEffect(() => {
    refresh().catch((err) => {
      setError(err.message || 'Failed to load jobs');
      setReady(true);
    });
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

  if (ready && !allowed) {
    return (
      <>
        <PageHeader title="Jobs" subtitle="This area is only available to Ribdigi House operators." />
      </>
    );
  }

  const jobs: string[] = info?.jobs || [];
  const beat = info?.beat || {};

  return (
    <div className="plat">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Jobs"
        subtitle="Background job handlers and schedules for Ribdigi House operators. Platform staff can view; platform owner can run or enqueue."
        subtitleClassName="plat-sub"
        actions={
          <button
            type="button"
            onClick={() => refresh().catch((e) => setError(e.message))}
            disabled={!!busy}
            aria-label="Refresh jobs list"
          >
            Refresh
          </button>
        }
      />

      <div className="plat-metrics" aria-label="Broker">
        <Metric
          label="Celery enabled"
          value={info?.celery_enabled ? 'Yes' : 'No'}
          note={info?.task_always_eager ? 'Always eager' : undefined}
        />
        <Metric label="Broker" value={info?.broker_configured ? 'Configured' : 'Not configured'} />
        <Metric label="Results" value={info?.result_backend_configured ? 'Configured' : 'Not configured'} />
      </div>

      <div className="plat-panel">
        <div className="plat-panel-head">
          <h2>Handlers</h2>
        </div>
        {jobs.length === 0 ? (
          <p className="muted">No jobs loaded</p>
        ) : (
          <div className="plat-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Schedule</th>
                  <th className="col-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((name) => (
                  <tr key={name}>
                    <td>
                      <div className="plat-co">{JOB_LABELS[name] || name}</div>
                      <span className="plat-small">{name}</span>
                    </td>
                    <td>{beatForJob(beat, name)}</td>
                    <td className="plat-actions-cell col-right">
                      {canRun ? (
                        <span className="plat-row-actions">
                          <button
                            type="button"
                            disabled={!!busy}
                            onClick={() => runJob(name, false)}
                            aria-label={`Run sync ${name}`}
                          >
                            {busy === `${name}:run` ? 'Running…' : 'Run sync'}
                          </button>
                          <button
                            type="button"
                            disabled={!!busy || !info?.celery_enabled}
                            title={!info?.celery_enabled ? 'Background processing is not available' : undefined}
                            onClick={() => runJob(name, true)}
                            aria-label={`Enqueue ${name}`}
                          >
                            {busy === `${name}:enqueue` ? 'Enqueue…' : 'Enqueue'}
                          </button>
                        </span>
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
        )}
      </div>

      {lastResult && (
        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Last result</h2>
          </div>
          <pre className="plat-code">{JSON.stringify(lastResult, null, 2)}</pre>
        </div>
      )}

      {(error || message) && (
        <div className="plat-feedback-dock" aria-live="polite">
          {error ? (
            <div className="plat-toast is-bad" role="alert">
              <p>{error}</p>
              <button type="button" aria-label="Dismiss error" onClick={() => setError('')}>
                ×
              </button>
            </div>
          ) : null}
          {message ? (
            <div className="plat-toast" role="status">
              <p>{message}</p>
              <button type="button" aria-label="Dismiss message" onClick={() => setMessage('')}>
                ×
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
