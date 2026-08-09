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

type Forecast = {
  product_id: string;
  sku: string;
  name: string;
  available_qty: number;
  forecast_7d: number;
  forecast_30d: number;
  forecast_90d: number;
  optimal_reorder_qty: number;
  seasonality: string;
  confidence: number;
  status: string;
};

type DeadStock = {
  product_id: string;
  sku: string;
  name: string;
  stock_qty: number;
  days_without_sale: number | null;
  estimated_carrying_cost: number;
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
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [deadStock, setDeadStock] = useState<DeadStock[]>([]);
  const [atRiskCount, setAtRiskCount] = useState(0);
  const [method, setMethod] = useState('');
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [insightCards, setInsightCards] = useState<
    { id: string; kind: string; severity: string; title: string; summary: string; action?: string }[]
  >([]);
  const [salesSummary, setSalesSummary] = useState<{
    invoice_count: number;
    total_sales: number;
    trend_direction: string;
  } | null>(null);
  const [salesPeaks, setSalesPeaks] = useState<{
    peak_hour?: number | null;
    peak_weekday_label?: string | null;
  } | null>(null);
  const [salesSegments, setSalesSegments] = useState<[string, number][]>([]);
  const [salesAffinity, setSalesAffinity] = useState<
    {
      product_a_id: string;
      product_b_id: string;
      product_a_name: string;
      product_b_name: string;
      co_occurrence_count: number;
      support: number;
    }[]
  >([]);
  const [expenseSummary, setExpenseSummary] = useState<{
    total_approved: number;
    total_pending: number;
  } | null>(null);
  const [expenseAnomalies, setExpenseAnomalies] = useState<
    { expense_id?: string; category?: string; description: string; amount: number }[]
  >([]);
  const [expenseSuggestions, setExpenseSuggestions] = useState<
    { kind: string; summary: string }[]
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

  async function loadForecasts() {
    try {
      const r = await api('/ai/inventory/demand-forecast');
      setForecasts(r.data?.forecasts || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load demand forecast');
    }
  }

  async function loadDeadStock() {
    try {
      const r = await api('/ai/inventory/dead-stock?lookback_days=90');
      setDeadStock(r.data?.items || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load dead stock');
    }
  }

  async function loadSalesAnalysis() {
    try {
      const r = await api('/ai/sales/analysis');
      setSalesSummary(r.data?.summary || null);
      setSalesPeaks(r.data?.peaks || null);
      setSalesSegments(Object.entries(r.data?.rfm?.segment_counts || {}));
      setSalesAffinity(r.data?.product_affinity?.pairs || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load sales analysis');
    }
  }

  async function loadExpenseAnalysis() {
    try {
      const r = await api('/ai/expenses/analysis');
      setExpenseSummary(r.data?.summary || null);
      setExpenseAnomalies(r.data?.anomalies || []);
      setExpenseSuggestions(r.data?.optimization_suggestions || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load expense analysis');
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
      /* optional */
    }
  }

  useEffect(() => {
    loadPredictions().catch(() => undefined);
    loadForecasts().catch(() => undefined);
    loadDeadStock().catch(() => undefined);
    loadSalesAnalysis().catch(() => undefined);
    loadExpenseAnalysis().catch(() => undefined);
    loadInsightCards().catch(() => undefined);
    loadHistory().catch(() => undefined);
  }, []);

  async function go() {
    setError('');
    setA('');
    try {
      const r = await api('/ai/chat', { method: 'POST', body: JSON.stringify({ message: q }) });
      setA(r.data?.answer || r.data?.reply || '');
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
        Rule-based chat, sales/expense analysis, demand forecasts, dead-stock detection, insights,
        and velocity stockout predictions — all from your tenant data.
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
        <h3>Demand forecast</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          7 / 30 / 90-day unit demand from sales velocity with short-window seasonality and optimal
          reorder quantity.
        </p>
        <button type="button" onClick={loadForecasts} style={{ marginBottom: 12 }}>
          Refresh forecast
        </button>
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Avail</th>
              <th>7d</th>
              <th>30d</th>
              <th>90d</th>
              <th>Reorder qty</th>
              <th>Seasonality</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {forecasts
              .filter((f) => f.status === 'ok')
              .slice(0, 40)
              .map((f) => (
                <tr key={f.product_id}>
                  <td>
                    {f.name} <span className="muted">({f.sku})</span>
                  </td>
                  <td>{f.available_qty}</td>
                  <td>{f.forecast_7d}</td>
                  <td>{f.forecast_30d}</td>
                  <td>{f.forecast_90d}</td>
                  <td>{f.optimal_reorder_qty}</td>
                  <td>{f.seasonality}</td>
                  <td>{Math.round((f.confidence || 0) * 100)}%</td>
                </tr>
              ))}
            {!forecasts.filter((f) => f.status === 'ok').length && (
              <tr>
                <td colSpan={8} className="muted">
                  No forecastable products yet (need posted sales history)
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Dead stock</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          On-hand inventory with no posted sales in the last 90 days.
        </p>
        <button type="button" onClick={loadDeadStock} style={{ marginBottom: 12 }}>
          Refresh dead stock
        </button>
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Stock</th>
              <th>Days without sale</th>
              <th>Est. carrying cost</th>
            </tr>
          </thead>
          <tbody>
            {deadStock.slice(0, 40).map((d) => (
              <tr key={d.product_id}>
                <td>
                  {d.name} <span className="muted">({d.sku})</span>
                </td>
                <td>{d.stock_qty}</td>
                <td>{d.days_without_sale ?? '—'}</td>
                <td>{d.estimated_carrying_cost}</td>
              </tr>
            ))}
            {!deadStock.length && (
              <tr>
                <td colSpan={4} className="muted">
                  No dead stock detected
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Sales analysis</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Trends, RFM segments, product affinity, and peak hour/day from posted invoices.
        </p>
        <button type="button" onClick={loadSalesAnalysis} style={{ marginBottom: 12 }}>
          Refresh sales analysis
        </button>
        {salesSummary && (
          <p>
            Invoices: {salesSummary.invoice_count} · Sales: {salesSummary.total_sales} · Trend:{' '}
            {salesSummary.trend_direction}
            {salesPeaks?.peak_hour != null ? ` · Peak hour: ${salesPeaks.peak_hour}:00` : ''}
            {salesPeaks?.peak_weekday_label ? ` · Peak day: ${salesPeaks.peak_weekday_label}` : ''}
          </p>
        )}
        {salesSegments.length > 0 && (
          <p className="muted">
            RFM segments:{' '}
            {salesSegments.map(([k, v]) => `${k}: ${v}`).join(' · ')}
          </p>
        )}
        {salesAffinity.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Bought together</th>
                <th>Count</th>
                <th>Support</th>
              </tr>
            </thead>
            <tbody>
              {salesAffinity.slice(0, 10).map((p) => (
                <tr key={`${p.product_a_id}-${p.product_b_id}`}>
                  <td>
                    {p.product_a_name} + {p.product_b_name}
                  </td>
                  <td>{p.co_occurrence_count}</td>
                  <td>{Math.round((p.support || 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Expense analysis</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Budget variance, unusual spends, and cost optimization suggestions.
        </p>
        <button type="button" onClick={loadExpenseAnalysis} style={{ marginBottom: 12 }}>
          Refresh expense analysis
        </button>
        {expenseSummary && (
          <p>
            Approved: {expenseSummary.total_approved} · Pending: {expenseSummary.total_pending} ·
            Anomalies: {expenseAnomalies.length}
          </p>
        )}
        {expenseSuggestions.length > 0 && (
          <ul>
            {expenseSuggestions.slice(0, 8).map((s, i) => (
              <li key={i}>
                <strong>{s.kind}</strong>: {s.summary}
              </li>
            ))}
          </ul>
        )}
        {expenseAnomalies.slice(0, 5).map((a) => (
          <p key={a.expense_id || a.description} className="muted">
            {a.category || 'Pattern'}: {a.description} ({a.amount})
          </p>
        ))}
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
