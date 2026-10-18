'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';

const OWNER_ROLES = ['super_admin', 'platform_owner'];

type PlatformSettings = {
  trial_days: number;
  grace_days: number;
  billing_grace_days: number;
  billing_reminder_days: number[];
  billing_max_attempts: number;
  live_charges: boolean;
  source?: string;
  billing?: {
    provider?: string | null;
    configured?: boolean;
    live_charges?: boolean;
    gateway_mode?: string | null;
    gateway_enabled?: boolean;
    gateway_tested?: boolean;
  };
};

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
  const reminders = (data?.billing_reminder_days || []).join(', ');

  return (
    <div className="plat">
      <header className="plat-hero">
        <div>
          <p className="plat-kicker">Software owner</p>
          <h1>Platform settings</h1>
          <p className="plat-sub">
            Read-only. These values are set in the server environment. No keys or secrets are shown
            here.
          </p>
        </div>
      </header>

      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="plat-stats" aria-label="Platform settings">
            <div className="plat-stat">
              <span>Trial days</span>
              <strong>{data.trial_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Trial grace days</span>
              <strong>{data.grace_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Billing grace days</span>
              <strong>{data.billing_grace_days}</strong>
            </div>
            <div className="plat-stat">
              <span>Billing max attempts</span>
              <strong>{data.billing_max_attempts}</strong>
            </div>
            <div className="plat-stat">
              <span>Billing reminder days</span>
              <strong>{reminders || '—'}</strong>
              <p className="muted">Days before renewal.</p>
            </div>
          </div>

          <div className="plat-panel">
            <h2>Billing gateway</h2>
            <table className="table">
              <tbody>
                <tr>
                  <th>Provider</th>
                  <td>{billing.provider || 'Not set'}</td>
                </tr>
                <tr>
                  <th>Configured</th>
                  <td>{billing.configured ? 'Yes' : 'No'}</td>
                </tr>
                <tr>
                  <th>Mode</th>
                  <td>{billing.gateway_mode || '—'}</td>
                </tr>
                <tr>
                  <th>Enabled</th>
                  <td>{billing.gateway_enabled ? 'Yes' : 'No'}</td>
                </tr>
                <tr>
                  <th>Tested</th>
                  <td>{billing.gateway_tested ? 'Yes' : 'No'}</td>
                </tr>
                <tr>
                  <th>Live charges</th>
                  <td>{data.live_charges ? 'On' : 'Off'}</td>
                </tr>
              </tbody>
            </table>
            {!data.live_charges ? (
              <p className="muted">Live charges are off. Paid self-serve checkout is not live.</p>
            ) : null}
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
            <Link href="/security" aria-label="Open security settings">
              Security
            </Link>
            <p className="muted">Two-factor and passkeys for this account.</p>
          </li>
        </ul>
      </div>
    </div>
  );
}
