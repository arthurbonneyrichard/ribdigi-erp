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

type ChatTurn = {
  id: string;
  message: string;
  answer: string;
  intent?: string | null;
  created_at?: string;
};

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [atRiskCount, setAtRiskCount] = useState(0);
  const [method, setMethod] = useState('');
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [insightCards, setInsightCards] = useState<
    { id: string; kind: string; severity: string; title: string; summary: string; action?: string }[]
  >([]);

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

  async function loadInsightCards() {
    try {
      const r = await api('/ai/insights');
      setInsightCards(r.data?.cards || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load insights');
    }
  }

  async function loadHistory() {
    try {
      const r = await api('/ai/chat/history?limit=30');
      setHistory(r.data?.items || []);
    } catch {
      /* history is optional when chat is unavailable */
    }
  }

  useEffect(() => {
    loadPredictions().catch(() => undefined);
    loadInsightCards().catch(() => undefined);
    loadHistory().catch(() => undefined);
  }, []);

  async function go() {
    setError('');
    setA('');
    try {
      const r = await api('/ai/chat', { method: 'POST', body: JSON.stringify({ message: q }) });
      const answer = r.data?.answer || r.data?.reply || '';
      setA(answer);
      setQ('');
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'AI assistant unavailable');
    }
  }

  async function loadInsights() {
    setError('');
    try {
      await loadInsightCards();
    } catch (err: any) {
      setError(err.message || 'Unable to load insights');
    }
  }

  return (
    <Shell>
      <h1>AI Business Assistant</h1>
      <p className="muted">
        Rule-based chat answers sales, stock, expense, and customer questions from your tenant data.
        Draft purchase orders when you have purchasing write access. Insights and velocity stockout
        predictions are also available.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Chat</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Try: &quot;What is my top selling product this month?&quot; or &quot;Create a purchase order for 50
          units of Alpha Widget&quot;.
        </p>
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: '100%', minHeight: 100 }}
          placeholder="Ask a business question"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button type="button" onClick={go} disabled={!q.trim()}>
            Ask
          </button>
          <button type="button" onClick={loadHistory}>
            Refresh history
          </button>
        </div>
        {a && (
          <pre style={{ whiteSpace: 'pre-wrap', marginTop: 12, background: '#f8fafc', padding: 12 }}>
            {a}
          </pre>
        )}
        {history.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>Recent history</h4>
            {history.map((h) => (
              <div key={h.id} style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8, marginBottom: 10 }}>
                <p className="muted" style={{ marginBottom: 4 }}>
                  You: {h.message}
                  {h.intent ? ` · ${h.intent}` : ''}
                </p>
                <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{h.answer}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Dashboard insights</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Sales spikes/drops, expense anomalies, and restock suggestions.
        </p>
        <button type="button" onClick={loadInsights} style={{ marginBottom: 12 }}>
          Refresh insights
        </button>
        {insightCards.length === 0 && <p className="muted">No insight cards yet</p>}
        {insightCards.map((c) => (
          <div key={c.id} style={{ marginBottom: 12, borderTop: '1px solid #e5e7eb', paddingTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{c.title}</strong>
              <span className="muted">
                {c.kind} · {c.severity}
              </span>
            </div>
            <p>{c.summary}</p>
            {c.action && <p className="muted">{c.action}</p>}
          </div>
        ))}
      </div>

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
    </Shell>
  );
}
