'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import StatusChip from '../../../../components/StatusChip';

const OWNER_ROLES = ['super_admin', 'platform_owner'];

type PlatformSettings = {
  trial_days: number;
  grace_days: number;
  billing_grace_days: number;
  billing_reminder_days: number[];
  billing_max_attempts: number;
  live_charges: boolean;
  source?: string;
  editable?: boolean;
  billing?: {
    provider?: string | null;
    configured?: boolean;
    live_charges?: boolean;
    gateway_mode?: string | null;
    gateway_enabled?: boolean;
    gateway_tested?: boolean;
  };
  auth?: {
    login_2fa_enabled?: boolean;
    totp_enforced_roles?: string[];
    webauthn_rp_id?: string | null;
    access_ttl_minutes?: number;
    refresh_ttl_days?: number;
  };
  services?: {
    rate_limit_enabled?: boolean;
    rate_limit_backend?: string;
    rate_limit_per_minute?: number;
    rate_limit_read_per_minute?: number;
    rate_limit_auth_per_minute?: number;
    metrics_enabled?: boolean;
    request_log_enabled?: boolean;
    celery_enabled?: boolean;
    email_enabled?: boolean;
    sms_enabled?: boolean;
    ai_enabled?: boolean;
    ai_provider?: string;
    ai_security_monitor_enabled?: boolean;
    bank_feed_sync_enabled?: boolean;
    storage_backend?: string;
  };
  backup?: {
    retention_count?: number;
    interval_minutes?: number;
    encryption_configured?: boolean;
  };
  audit?: {
    retention_years?: number;
    cold_archive_after_days?: number;
    http_middleware_enabled?: boolean;
  };
  deploy?: {
    app_env?: string;
    release_channel?: string;
    build_id?: string;
    frontend_url?: string | null;
  };
};

function Flag({ on, onLabel = 'On', offLabel = 'Off' }: { on?: boolean; onLabel?: string; offLabel?: string }) {
  return <StatusChip value={on ? 'yes' : 'no'} label={on ? onLabel : offLabel} />;
}

function SettingRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{children}</td>
    </tr>
  );
}

export default function PlatformSettingsPage() {
  const router = useRouter();
  const [data, setData] = useState<PlatformSettings | null>(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await getMe();
        if (!OWNER_ROLES.includes(me.data?.role || '')) {
          router.replace('/platform');
          return;
        }
        const res = await api('/platform/settings');
        if (cancelled) return;
        setData(res.data || null);
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load platform settings');
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready && !error) return <p className="muted">Loading platform settings…</p>;

  const billing = data?.billing || {};
  const auth = data?.auth || {};
  const services = data?.services || {};
  const backup = data?.backup || {};
  const audit = data?.audit || {};
  const deploy = data?.deploy || {};
  const reminders = (data?.billing_reminder_days || []).join(', ');
  const totpRoles = (auth.totp_enforced_roles || []).join(', ') || '—';

  return (
    <div className="plat">
      <header className="plat-hero">
        <div>
          <p className="plat-kicker">Software owner</p>
          <h1>Platform settings</h1>
          <p className="plat-sub">
            Read-only operations posture from the server environment. No keys or secrets are shown.
            Change values in deploy env, then restart API workers.
          </p>
        </div>
        {data ? (
          <div className="plat-filters" aria-label="Settings source">
            <span className="plat-chip active">{data.source || 'environment'}</span>
            <span className="plat-chip">{data.editable ? 'Editable' : 'Read-only'}</span>
          </div>
        ) : null}
      </header>

      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="plat-stats" aria-label="Subscription lifecycle">
            <div className="plat-stat">
              <span>Trial days</span>
              <strong>{data.trial_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Trial grace</span>
              <strong>{data.grace_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Billing grace</span>
              <strong>{data.billing_grace_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Max attempts</span>
              <strong>{data.billing_max_attempts}</strong>
            </div>
            <div className="plat-stat">
              <span>Reminder days</span>
              <strong style={{ fontSize: 18 }}>{reminders || '—'}</strong>
              <p className="muted">Before renewal</p>
            </div>
          </div>

          <div className="plat-panel">
            <h2>Billing gateway</h2>
            <div className="list-table-wrap">
              <table className="table" aria-label="Billing gateway status">
                <tbody>
                  <SettingRow label="Provider">{billing.provider || 'Not set'}</SettingRow>
                  <SettingRow label="Configured">
                    <Flag on={billing.configured} onLabel="Yes" offLabel="No" />
                  </SettingRow>
                  <SettingRow label="Mode">{billing.gateway_mode || '—'}</SettingRow>
                  <SettingRow label="Enabled">
                    <Flag on={billing.gateway_enabled} />
                  </SettingRow>
                  <SettingRow label="Tested">
                    <Flag on={billing.gateway_tested} onLabel="Yes" offLabel="No" />
                  </SettingRow>
                  <SettingRow label="Live charges">
                    <Flag on={data.live_charges} onLabel="On" offLabel="Off" />
                  </SettingRow>
                </tbody>
              </table>
            </div>
            {!data.live_charges ? (
              <p className="muted" style={{ marginTop: 12 }}>
                Live charges are off. Paid self-serve checkout is not live until a tested live gateway
                is configured on Billing.
              </p>
            ) : null}
          </div>

          <div className="plat-panel">
            <h2>Security & access</h2>
            <div className="list-table-wrap">
              <table className="table" aria-label="Security and access settings">
                <tbody>
                  <SettingRow label="Login 2FA">
                    <Flag on={auth.login_2fa_enabled} onLabel="Required" offLabel="Optional" />
                  </SettingRow>
                  <SettingRow label="TOTP enforced roles">{totpRoles}</SettingRow>
                  <SettingRow label="Passkey RP ID">{auth.webauthn_rp_id || '—'}</SettingRow>
                  <SettingRow label="Access session TTL">
                    {auth.access_ttl_minutes != null ? `${auth.access_ttl_minutes} min` : '—'}
                  </SettingRow>
                  <SettingRow label="Refresh session TTL">
                    {auth.refresh_ttl_days != null ? `${auth.refresh_ttl_days} days` : '—'}
                  </SettingRow>
                </tbody>
              </table>
            </div>
          </div>

          <div className="plat-panel">
            <h2>System services</h2>
            <div className="list-table-wrap">
              <table className="table" aria-label="System service settings">
                <tbody>
                  <SettingRow label="Rate limiting">
                    <Flag on={services.rate_limit_enabled} />
                  </SettingRow>
                  <SettingRow label="Rate limit backend">{services.rate_limit_backend || '—'}</SettingRow>
                  <SettingRow label="Rate limits / min">
                    {[
                      services.rate_limit_per_minute != null ? `all ${services.rate_limit_per_minute}` : null,
                      services.rate_limit_read_per_minute != null
                        ? `read ${services.rate_limit_read_per_minute}`
                        : null,
                      services.rate_limit_auth_per_minute != null
                        ? `auth ${services.rate_limit_auth_per_minute}`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </SettingRow>
                  <SettingRow label="Metrics">
                    <Flag on={services.metrics_enabled} />
                  </SettingRow>
                  <SettingRow label="Request log">
                    <Flag on={services.request_log_enabled} />
                  </SettingRow>
                  <SettingRow label="Celery">
                    <Flag on={services.celery_enabled} />
                  </SettingRow>
                  <SettingRow label="Platform email">
                    <Flag on={services.email_enabled} />
                  </SettingRow>
                  <SettingRow label="Platform SMS">
                    <Flag on={services.sms_enabled} />
                  </SettingRow>
                  <SettingRow label="AI assistant">
                    <Flag on={services.ai_enabled} />
                  </SettingRow>
                  <SettingRow label="AI provider">{services.ai_provider || 'none'}</SettingRow>
                  <SettingRow label="AI security monitor">
                    <Flag on={services.ai_security_monitor_enabled} />
                  </SettingRow>
                  <SettingRow label="Bank feed sync">
                    <Flag on={services.bank_feed_sync_enabled} />
                  </SettingRow>
                  <SettingRow label="Storage backend">{services.storage_backend || '—'}</SettingRow>
                </tbody>
              </table>
            </div>
          </div>

          <div className="plat-panel">
            <h2>Backup & audit</h2>
            <div className="list-table-wrap">
              <table className="table" aria-label="Backup and audit settings">
                <tbody>
                  <SettingRow label="Backup retention">{backup.retention_count ?? '—'}</SettingRow>
                  <SettingRow label="Backup interval">
                    {backup.interval_minutes != null ? `${backup.interval_minutes} min` : '—'}
                  </SettingRow>
                  <SettingRow label="Backup encryption">
                    <Flag on={backup.encryption_configured} onLabel="Configured" offLabel="Not set" />
                  </SettingRow>
                  <SettingRow label="Audit retention">
                    {audit.retention_years != null ? `${audit.retention_years} years` : '—'}
                  </SettingRow>
                  <SettingRow label="Cold archive after">
                    {audit.cold_archive_after_days != null
                      ? `${audit.cold_archive_after_days} days`
                      : '—'}
                  </SettingRow>
                  <SettingRow label="HTTP audit middleware">
                    <Flag on={audit.http_middleware_enabled} />
                  </SettingRow>
                </tbody>
              </table>
            </div>
          </div>

          <div className="plat-panel">
            <h2>Deploy identity</h2>
            <div className="list-table-wrap">
              <table className="table" aria-label="Deploy identity">
                <tbody>
                  <SettingRow label="App environment">{deploy.app_env || '—'}</SettingRow>
                  <SettingRow label="Release channel">{deploy.release_channel || '—'}</SettingRow>
                  <SettingRow label="Build ID">{deploy.build_id || '—'}</SettingRow>
                  <SettingRow label="Frontend URL">{deploy.frontend_url || '—'}</SettingRow>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <div className="plat-panel">
        <h2>Related</h2>
        <ul className="plat-tools">
          <li>
            <Link href="/platform/billing" aria-label="Open billing gateway">
              Billing gateway
            </Link>
            <p className="muted">Change the gateway, plans, and subscriptions.</p>
          </li>
          <li>
            <Link href="/jobs" aria-label="Open scheduled jobs">
              Jobs
            </Link>
            <p className="muted">Run sync jobs and Celery workers.</p>
          </li>
          <li>
            <Link href="/security" aria-label="Open security settings">
              Security
            </Link>
            <p className="muted">Two-factor and passkeys for this account.</p>
          </li>
          <li>
            <Link href="/platform" aria-label="Open platform health console">
              Platform console
            </Link>
            <p className="muted">Tenant health, revenue, and attention queue.</p>
          </li>
          <li>
            <Link href="/platform/reports" aria-label="Open platform reports">
              Platform reports
            </Link>
            <p className="muted">Export summary, subscriptions, packages, and trials.</p>
          </li>
        </ul>
      </div>
    </div>
  );
}
