'use client';

import { useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');
  const [alerts, setAlerts] = useState<any[]>([]);

  async function go() {
    setError('');
    setA('');
    try {
      const r = await api('/ai/chat', { method: 'POST', body: JSON.stringify({ message: q }) });
      setA(r.data?.answer || r.data?.reply || JSON.stringify(r.data));
    } catch (err: any) {
      setError(err.message || 'AI assistant unavailable');
    }
  }

  async function loadInsights() {
    setError('');
    try {
      const r = await api('/ai/insights');
      setA((r.data?.insights || []).join('\n'));
    } catch (err: any) {
      setError(err.message || 'Unable to load insights');
    }
  }

  async function loadSecurityAlerts() {
    setError('');
    try {
      const r = await api('/ai/security/alerts?scan=true');
      setAlerts(r.data?.alerts || []);
      setA(
        (r.data?.alerts || [])
          .map((x: any) => `[${x.risk_score}] ${x.kind}: ${x.title}`)
          .join('\n') || 'No security alerts'
      );
    } catch (err: any) {
      setError(err.message || 'Unable to load security alerts');
    }
  }

  return (
    <Shell>
      <h1>AI Business Assistant</h1>
      <p className="muted">
        Chat requires a configured AI provider. Rule-based insights and the AI Security Monitor are available now.
      </p>
      <div className="card">
        <textarea value={q} onChange={(e) => setQ(e.target.value)} style={{ width: '100%', minHeight: 100 }} placeholder="Ask a business question" />
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
          <button onClick={go}>Ask</button>
          <button onClick={loadInsights}>Load insights</button>
          <button onClick={loadSecurityAlerts}>Security alerts</button>
        </div>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        {a && <pre style={{ whiteSpace: 'pre-wrap' }}>{a}</pre>}
        {alerts.length > 0 && (
          <ul>
            {alerts.map((x) => (
              <li key={x.id}>
                <strong>{x.risk_score}</strong> {x.kind} — {x.title}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Shell>
  );
}
