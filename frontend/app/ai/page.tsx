'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Prediction = {
  product_id: string;
  sku: string;
  name: string;
  stock_qty: number;
  available_qty: number;
  velocity_per_day: number;
  adjusted_velocity_per_day: number;
  days_to_stockout: number | null;
  confidence: number;
  status: string;
  at_risk: boolean;
  suggested_order_qty: number;
  seasonality_factor: number;
};

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [atRiskCount, setAtRiskCount] = useState(0);
  const [method, setMethod] = useState('');

  async function loadPredictions() {
    setError('');
    setMessage('');
    try {
      const r = await api('/ai/inventory/low-stock-prediction?horizon_days=14');
      setPredictions(r.data?.predictions || []);
      setAtRiskCount(r.data?.at_risk_count || 0);
      setMethod(r.data?.method || '');
      setMessage(
        `Loaded ${r.data?.predictions?.length || 0} products · ${r.data?.at_risk_count || 0} at risk`
      );
    } catch (err: any) {
      setError(err.message || 'Unable to load predictions');
    }
  }

  useEffect(() => {
    loadPredictions().catch(() => undefined);
  }, []);

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
      <p className="muted">
        Chat requires a configured AI provider. Rule-based insights and velocity stockout
        predictions are available now.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Low stock prediction</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Sales velocity over ~30 days with a short seasonality factor. Horizon 7–14 days.
          {method ? ` Method: ${method}.` : ''} At risk: {atRiskCount}.
        </p>
        <button type="button" onClick={loadPredictions} style={{ marginBottom: 12 }}>
          Refresh predictions
        </button>
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Stock</th>
              <th>Velocity/day</th>
              <th>Days to stockout</th>
              <th>Confidence</th>
              <th>Suggested qty</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {predictions
              .filter((p) => p.at_risk || p.status !== 'insufficient_data')
              .slice(0, 50)
              .map((p) => (
                <tr key={p.product_id}>
                  <td>
                    {p.name} <span className="muted">({p.sku})</span>
                  </td>
                  <td>{p.available_qty}</td>
                  <td>{p.adjusted_velocity_per_day}</td>
                  <td>{p.days_to_stockout ?? '—'}</td>
                  <td>{Math.round((p.confidence || 0) * 100)}%</td>
                  <td>{p.suggested_order_qty}</td>
                  <td style={{ color: p.at_risk ? '#b91c1c' : undefined }}>{p.status}</td>
                </tr>
              ))}
            {!predictions.length && (
              <tr>
                <td colSpan={7} className="muted">
                  No prediction data yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Chat &amp; insights</h3>
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: '100%', minHeight: 100 }}
          placeholder="Ask a business question"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button onClick={go}>Ask</button>
          <button onClick={loadInsights}>Load insights</button>
        </div>
        {a && <pre style={{ whiteSpace: 'pre-wrap' }}>{a}</pre>}
      </div>
    </Shell>
  );
}
