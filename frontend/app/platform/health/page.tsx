'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';
import { downloadPlatformEvidence } from '../../../lib/platformEvidence';

type Check = { status?: string; latency_ms?: number; reason?: string; mode?: string; required?: boolean };

export default function PlatformHealthPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    api('/platform/health')
      .then((r) => setData(r.data))
      .catch((err) => setError(err.message || 'Failed to load health'));
  }, []);

  async function downloadEvidence() {
    setError('');
    setMessage('');
    try {
      setMessage(await downloadPlatformEvidence());
    } catch (err: any) {
      setError(err.message || 'Evidence download failed');
    }
  }

  const checks: Record<string, Check> = data?.checks || {};
  const security = data?.security || {};
  const contacts = data?.operator_contacts || {};
  const runtime = data?.house_runtime || {};

  return (
    <PlatformShell>
      <h1>Platform health</h1>
      <p className="muted">Deep readiness checks for Ribdigi House operators.</p>
      {error && <p>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}
      {data && (
        <>
          <p style={{ marginTop: 12 }}>
            Overall: <strong>{data.status}</strong>
          </p>
          <p style={{ marginTop: 8 }}>
            <button type="button" onClick={downloadEvidence}>
              Download evidence JSON
            </button>
          </p>
          <div className="grid" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="muted">Operator support</div>
              <p style={{ marginTop: 8 }}>{contacts.company_name || 'Ribdigi House'}</p>
              <p className="muted">{contacts.support_email || 'No support email set'}</p>
              <p className="muted">{contacts.support_phone || 'No support phone set'}</p>
              <p className="muted" style={{ marginTop: 8 }}>
                Edit contacts under Platform settings.
              </p>
            </div>
            <div className="card">
              <div className="muted">Rate limit</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {security.rate_limit_enabled ? 'Enabled' : 'Disabled'}
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                Backend: {security.rate_limit_backend || '—'} · API/min:{' '}
                {security.rate_limit_api_per_minute ?? '—'} · Auth/min:{' '}
                {security.rate_limit_auth_per_minute ?? '—'}
              </p>
              <p className="muted">
                Redis required: {String(security.rate_limit_require_redis ?? false)}
              </p>
            </div>
            <div className="card">
              <div className="muted">Celery</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {security.celery_enabled ? 'Enabled' : 'Disabled'}
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                Runtime flag from House security posture (packaging honesty).
              </p>
            </div>
            <div className="card">
              <div className="muted">House idle timeout</div>
              <div className="kpi" style={{ fontSize: 18 }}>
                {runtime.inactivity_timeout_minutes ?? '—'} min
              </div>
              <p className="muted" style={{ marginTop: 8 }}>
                TZ: {runtime.timezone || '—'} · date: {runtime.date_format || '—'} · time:{' '}
                {runtime.time_format || '—'} · numbers: {runtime.number_format || '—'}
              </p>
            </div>
            <div className="card">
              <div className="muted">Security posture</div>
              <p className="muted" style={{ marginTop: 8 }}>
                Env: {data.env || '—'} · OpenAPI: {String(security.openapi_enabled)} · Debug:{' '}
                {String(security.debug)}
              </p>
              <p className="muted">
                CORS origins: {security.cors_origins_count ?? '—'}
                {security.cors_allows_wildcard ? ' (includes *)' : ''}
              </p>
              {security.cors_allows_wildcard && (
                <p role="alert" style={{ color: '#b45309', marginTop: 8 }}>
                  Warning: CORS allowlist includes wildcard '*'. Tighten origins before production.
                </p>
              )}
              {Array.isArray(security.cors_origins) && (
                <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
                  Allowlist: {security.cors_origins.join(', ') || '—'}
                </p>
              )}
            </div>
            {Object.entries(checks).map(([name, check]) => (
              <div className="card" key={name}>
                <div className="muted">{name}</div>
                <div className="kpi" style={{ fontSize: 18 }}>
                  {check.status || '—'}
                </div>
                <p className="muted" style={{ marginTop: 8 }}>
                  {check.required === true
                    ? 'Required'
                    : check.required === false
                      ? 'Optional'
                      : null}
                  {check.required != null &&
                  (check.latency_ms != null || check.mode || check.reason)
                    ? ' · '
                    : null}
                  {check.latency_ms != null ? `${check.latency_ms} ms` : null}
                  {check.mode ? ` · ${check.mode}` : null}
                  {check.reason ? ` · ${check.reason}` : null}
                </p>
              </div>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 16 }}>
            Operator evidence pack via Download evidence JSON /{' '}
            <code>GET /platform/evidence</code> (packaging honesty — not go-live Complete).
          </p>
          <details style={{ marginTop: 20 }}>
            <summary className="muted">Raw payload</summary>
            <pre style={{ overflow: 'auto', fontSize: 13 }}>{JSON.stringify(data, null, 2)}</pre>
          </details>
        </>
      )}
    </PlatformShell>
  );
}
