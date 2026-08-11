'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

export default function PlatformHealthPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/platform/health')
      .then((r) => setData(r.data))
      .catch((err) => setError(err.message || 'Failed to load health'));
  }, []);

  return (
    <PlatformShell>
      <h1>Platform health</h1>
      <p className="muted">Deep readiness checks for Ribdigi House operators.</p>
      {error && <p>{error}</p>}
      {data && (
        <div className="card" style={{ marginTop: 16 }}>
          <p>
            Status: <strong>{data.status}</strong>
          </p>
          <pre style={{ overflow: 'auto', fontSize: 13 }}>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </PlatformShell>
  );
}
