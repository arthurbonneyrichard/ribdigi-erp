'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

type Check = { status?: string; latency_ms?: number; reason?: string; mode?: string; required?: boolean };

export default function PlatformHealthPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/platform/health')
      .then((r) => setData(r.data))
      .catch((err) => setError(err.message || 'Failed to load health'));
  }, []);

  const checks: Record<string, Check> = data?.checks || {};

  return (
    <PlatformShell>
      <h1>Platform health</h1>
      <p className="muted">Deep readiness checks for Ribdigi House operators.</p>
      {error && <p>{error}</p>}
      {data && (
        <>
          <p style={{ marginTop: 12 }}>
            Overall: <strong>{data.status}</strong>
          </p>
          <div className="grid" style={{ marginTop: 16 }}>
            {Object.entries(checks).map(([name, check]) => (
              <div className="card" key={name}>
                <div className="muted">{name}</div>
                <div className="kpi" style={{ fontSize: 18 }}>
                  {check.status || '—'}
                </div>
                <p className="muted" style={{ marginTop: 8 }}>
                  {check.latency_ms != null ? `${check.latency_ms} ms` : null}
                  {check.mode ? ` · ${check.mode}` : null}
                  {check.reason ? ` · ${check.reason}` : null}
                </p>
              </div>
            ))}
          </div>
          <details style={{ marginTop: 20 }}>
            <summary className="muted">Raw payload</summary>
            <pre style={{ overflow: 'auto', fontSize: 13 }}>{JSON.stringify(data, null, 2)}</pre>
          </details>
        </>
      )}
    </PlatformShell>
  );
}
