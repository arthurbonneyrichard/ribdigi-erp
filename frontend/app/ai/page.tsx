'use client';

import { useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');

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

  return (
    <Shell>
      <h1>AI Business Assistant</h1>
      <p className="muted">Chat requires a configured AI provider. Rule-based insights are available now.</p>
      <div className="card">
        <textarea value={q} onChange={(e) => setQ(e.target.value)} style={{ width: '100%', minHeight: 100 }} placeholder="Ask a business question" />
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button onClick={go}>Ask</button>
          <button onClick={loadInsights}>Load insights</button>
        </div>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        {a && <pre style={{ whiteSpace: 'pre-wrap' }}>{a}</pre>}
      </div>
    </Shell>
  );
}
