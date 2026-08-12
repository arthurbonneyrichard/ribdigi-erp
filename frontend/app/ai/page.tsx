'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
    {
      id: string;
      kind: string;
      severity: string;
      title: string;
      summary: string;
      action?: string;
      domains?: string[];
    }[]
  >([]);
  const [insightActuals, setInsightActuals] = useState<string[]>([]);
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
  const [purchaseSummary, setPurchaseSummary] = useState<{
    total_spend: number;
    purchase_order_count: number;
    open_po_count: number;
    overdue_invoice_count: number;
    trend_direction: string;
    top_supplier_spend_share?: number;
  } | null>(null);
  const [purchaseSuggestions, setPurchaseSuggestions] = useState<
    { kind: string; summary: string }[]
  >([]);
  const [purchaseOverdue, setPurchaseOverdue] = useState<
    { invoice_number?: string; supplier_name?: string; balance: number }[]
  >([]);
  const [crossSummary, setCrossSummary] = useState<{
    total_sales: number;
    total_purchase_spend: number;
    total_approved_expenses: number;
    at_risk_sku_count: number;
    cross_signal_count: number;
  } | null>(null);
  const [crossSignals, setCrossSignals] = useState<
    { kind: string; severity: string; title: string; summary: string; domains?: string[] }[]
  >([]);
  const [docType, setDocType] = useState('receipt');
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docResult, setDocResult] = useState<any>(null);
  const [securityAlerts, setSecurityAlerts] = useState<
    { id: string; kind: string; title: string; detail: string; severity: string; score: number }[]
  >([]);
  const [reportPrompt, setReportPrompt] = useState('Show me monthly sales for Q2');
  const [reportResult, setReportResult] = useState<any>(null);
  const [reportTemplates, setReportTemplates] = useState<any[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [customerInsights, setCustomerInsights] = useState<any>(null);
  const [customerQuery, setCustomerQuery] = useState('Who are my best customers?');
  const [customerAnswer, setCustomerAnswer] = useState('');

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

  async function loadPurchasesAnalysis() {
    try {
      const r = await api('/ai/purchases/analysis');
      setPurchaseSummary(r.data?.summary || null);
      setPurchaseSuggestions(r.data?.suggestions || []);
      setPurchaseOverdue(r.data?.purchase_invoices?.overdue || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load purchases analysis');
    }
  }

  async function loadCrossDomainAnalysis() {
    try {
      const r = await api('/ai/cross-domain/analysis');
      setCrossSummary(r.data?.summary || null);
      setCrossSignals(r.data?.cross_signals || []);
    } catch (err: any) {
      setError(err.message || 'Unable to load cross-domain analysis');
    }
  }

  async function analyzeDocument() {
    setError('');
    setMessage('');
    if (!docFile) {
      setError('Choose a document file to analyze');
      return;
    }
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', docFile);
      const res = await fetch(
        `${apiBase}/ai/documents/analyze?document_type=${encodeURIComponent(docType)}`,
        {
          method: 'POST',
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
          body: form,
        },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail?.message || body.detail || body.message || 'Analyze failed');
      }
      setDocResult(body.data || body);
      setMessage('Document analyzed (suggest-only — apply via expense/PI OCR confirm paths)');
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Unable to analyze document');
    }
  }

  async function loadCustomerInsights() {
    try {
      const r = await api('/ai/customers/insights');
      setCustomerInsights(r.data);
    } catch (err: any) {
      setError(err.message || 'Unable to load customer insights');
    }
  }

  async function askCustomerAssist() {
    setError('');
    try {
      const r = await api('/ai/customer/assist', {
        method: 'POST',
        body: JSON.stringify({ query: customerQuery }),
      });
      setCustomerAnswer(r.data?.answer || '');
      if (r.data?.best_customers) {
        setCustomerInsights((prev: any) => ({
          ...(prev || {}),
          best_customers: r.data.best_customers,
          churn_risks: r.data.churn_risks,
          promotion_suggestions: r.data.promotion_suggestions,
        }));
      }
    } catch (err: any) {
      setError(err.message || 'Unable to assist');
    }
  }

  async function loadReportTemplates() {
    try {
      const r = await api('/ai/reports/templates');
      setReportTemplates(r.data || []);
    } catch {
      setReportTemplates([]);
    }
  }

  async function generateReport() {
    setError('');
    try {
      const r = await api('/ai/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt: reportPrompt }),
      });
      setReportResult(r.data);
    } catch (err: any) {
      setError(err.message || 'Unable to generate report');
    }
  }

  async function saveReportTemplate() {
    setError('');
    try {
      await api('/ai/reports/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: templateName || reportResult?.title || 'Saved report',
          prompt: reportPrompt,
          format: reportResult?.format || 'xlsx',
        }),
      });
      setTemplateName('');
      await loadReportTemplates();
      setMessage('Report template saved');
    } catch (err: any) {
      setError(err.message || 'Unable to save template');
    }
  }

  async function runTemplate(t: any) {
    setReportPrompt(t.prompt);
    setError('');
    try {
      const r = await api('/ai/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ template_id: t.id }),
      });
      setReportResult(r.data);
    } catch (err: any) {
      setError(err.message || 'Unable to run template');
    }
  }

  async function loadSecurityAlerts() {
    try {
      const r = await api('/ai/security/alerts?lookback_hours=72');
      setSecurityAlerts(r.data?.alerts || []);
    } catch (err: any) {
      // security:read may be missing for some roles
      setSecurityAlerts([]);
    }
  }

  async function downloadAiCsv(path: string, filename: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || `${filename} export failed`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${filename} exported`);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  async function loadInsightCards() {
    try {
      const r = await api('/ai/insights');
      setInsightCards(r.data?.cards || []);
      setInsightActuals(r.data?.actuals_covered || r.data?.actuals || []);
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
    loadPurchasesAnalysis().catch(() => undefined);
    loadCrossDomainAnalysis().catch(() => undefined);
    loadCustomerInsights().catch(() => undefined);
    loadReportTemplates().catch(() => undefined);
    loadSecurityAlerts().catch(() => undefined);
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

  // Stage 102 A1 / Stage 108 A1 — honor Shell AI section hashes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <Shell>
      <h1>AI Business Assistant</h1>
      <p className="muted">
        Rule-based chat, NL reports, customer intelligence, sales/purchases/expense analysis, security
        monitoring, demand forecasts, dead stock, business insights, and stockout predictions — from
        actual Inventory, Sales, Purchases, and Expenses.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {/* Stage 102 A1 — section anchors for Shell deep-links */}
      <div className="card" style={{ marginBottom: 16 }} id="chat">
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

      <div className="card" style={{ marginBottom: 16 }} id="forecast">
        <h3>Demand forecast</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          7 / 30 / 90-day unit demand from sales velocity with short-window seasonality and optimal
          reorder quantity. Export via <code>GET /ai/inventory/demand-forecast/export</code> (Stage
          146 F1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button type="button" onClick={loadForecasts}>
            Refresh forecast
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv(
                '/ai/inventory/demand-forecast/export',
                'ai_demand_forecast_export.csv'
              )
            }
          >
            Export forecast CSV
          </button>
        </div>
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

      <div className="card" style={{ marginBottom: 16 }} id="dead-stock">
        <h3>Dead stock</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          On-hand inventory with no posted sales in the last 90 days. Export via{' '}
          <code>GET /ai/inventory/dead-stock/export</code> (Stage 146 K1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button type="button" onClick={loadDeadStock}>
            Refresh dead stock
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv(
                '/ai/inventory/dead-stock/export?lookback_days=90',
                'ai_dead_stock_export.csv'
              )
            }
          >
            Export dead stock CSV
          </button>
        </div>
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

      <div className="card" style={{ marginBottom: 16 }} id="sales-analysis">
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

      <div className="card" style={{ marginBottom: 16 }} id="expense-analysis">
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

      <div className="card" style={{ marginBottom: 16 }} id="purchases-analysis">
        <h3>Purchases analysis</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Spend trend, supplier concentration, PO fill/open backlog, and overdue bills from live PO /
          GRN / purchase invoices.
        </p>
        <button type="button" onClick={loadPurchasesAnalysis} style={{ marginBottom: 12 }}>
          Refresh purchases analysis
        </button>
        {purchaseSummary && (
          <p>
            Spend: {purchaseSummary.total_spend} · POs: {purchaseSummary.purchase_order_count} · Open
            POs: {purchaseSummary.open_po_count} · Overdue PIs:{' '}
            {purchaseSummary.overdue_invoice_count} · Trend: {purchaseSummary.trend_direction}
            {purchaseSummary.top_supplier_spend_share != null
              ? ` · Top supplier share: ${Math.round(purchaseSummary.top_supplier_spend_share * 100)}%`
              : ''}
          </p>
        )}
        {purchaseSuggestions.length > 0 && (
          <ul>
            {purchaseSuggestions.slice(0, 8).map((s, i) => (
              <li key={i}>
                <strong>{s.kind}</strong>: {s.summary}
              </li>
            ))}
          </ul>
        )}
        {purchaseOverdue.slice(0, 5).map((row) => (
          <p key={row.invoice_number || String(row.balance)} className="muted">
            {row.invoice_number || 'Invoice'} · {row.supplier_name || 'Supplier'} · balance{' '}
            {row.balance}
          </p>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="cross-domain">
        <h3>Cross-domain analysis</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Orchestrates Inventory, Sales, Purchases, and Expenses analyzers into synthesis signals.
        </p>
        <button type="button" onClick={loadCrossDomainAnalysis} style={{ marginBottom: 12 }}>
          Refresh cross-domain analysis
        </button>
        {crossSummary && (
          <p>
            Sales: {crossSummary.total_sales} · Purchases: {crossSummary.total_purchase_spend} ·
            Expenses: {crossSummary.total_approved_expenses} · At-risk SKUs:{' '}
            {crossSummary.at_risk_sku_count} · Signals: {crossSummary.cross_signal_count}
          </p>
        )}
        {crossSignals.length === 0 && crossSummary && (
          <p className="muted">No cross-domain alerts for the current window.</p>
        )}
        {crossSignals.slice(0, 8).map((s) => (
          <div key={s.kind + s.title} style={{ marginBottom: 10, borderTop: '1px solid #e5e7eb', paddingTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{s.title}</strong>
              <span className="muted">
                {s.kind} · {s.severity}
              </span>
            </div>
            <p>{s.summary}</p>
            {Array.isArray(s.domains) && s.domains.length > 0 && (
              <p className="muted">Actuals: {s.domains.join(' · ')}</p>
            )}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="document">
        <h3>Document analyze</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          OCR extract / match / discrepancy flags via <code>POST /ai/documents/analyze</code>. Suggest
          only — apply reviewed fields on expense or purchase-invoice OCR paths with confirm.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="receipt">receipt</option>
            <option value="invoice">invoice</option>
            <option value="purchase_order">purchase_order</option>
            <option value="purchase_invoice">purchase_invoice</option>
          </select>
          <input
            type="file"
            accept="image/*,.pdf,.txt"
            onChange={(e) => setDocFile(e.target.files?.[0] || null)}
          />
          <button type="button" onClick={analyzeDocument}>
            Analyze document
          </button>
        </div>
        {docResult && (
          <div>
            <p className="muted">
              Type: {docResult.document_type || docType}
              {docResult.method ? ` · Method: ${docResult.method}` : ''}
            </p>
            {docResult.extracted_fields && (
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 180, overflow: 'auto' }}>
                {JSON.stringify(docResult.extracted_fields, null, 2)}
              </pre>
            )}
            {docResult.matches && (
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 140, overflow: 'auto' }}>
                {JSON.stringify(docResult.matches, null, 2)}
              </pre>
            )}
            {Array.isArray(docResult.discrepancies) && docResult.discrepancies.length > 0 && (
              <ul>
                {docResult.discrepancies.slice(0, 8).map((d: any, i: number) => (
                  <li key={i}>
                    {typeof d === 'string' ? d : d.detail || d.message || JSON.stringify(d)}
                  </li>
                ))}
              </ul>
            )}
            {docResult.apply_hint && <p className="muted">{docResult.apply_hint}</p>}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="customer">
        <h3>Customer assistant</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Churn risk, best customers, and promotion suggestions from sales history.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <input
            value={customerQuery}
            onChange={(e) => setCustomerQuery(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
            placeholder="Ask about customers"
          />
          <button type="button" onClick={askCustomerAssist}>
            Ask
          </button>
          <button type="button" onClick={loadCustomerInsights}>
            Refresh insights
          </button>
        </div>
        {customerAnswer && <p>{customerAnswer}</p>}
        {customerInsights?.best_customers?.length > 0 && (
          <p className="muted">
            Best:{' '}
            {customerInsights.best_customers
              .slice(0, 5)
              .map((c: any) => `${c.name} (${c.monetary})`)
              .join(' · ')}
          </p>
        )}
        {customerInsights?.churn_risks?.length > 0 && (
          <p className="muted">
            Churn risk:{' '}
            {customerInsights.churn_risks
              .slice(0, 5)
              .map((c: any) => `${c.name} (${c.churn?.band})`)
              .join(' · ')}
          </p>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="report-generator">
        <h3>Report generator</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Ask in plain language, e.g. &quot;Show me monthly sales for Q2&quot; or &quot;low stock as pdf&quot;.
        </p>
        <textarea
          value={reportPrompt}
          onChange={(e) => setReportPrompt(e.target.value)}
          style={{ width: '100%', minHeight: 72 }}
          placeholder="Describe the report you need"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={generateReport} disabled={!reportPrompt.trim()}>
            Generate
          </button>
          <input
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            placeholder="Template name"
            style={{ minWidth: 160 }}
          />
          <button type="button" onClick={saveReportTemplate} disabled={!reportPrompt.trim()}>
            Save template
          </button>
          <button type="button" onClick={loadReportTemplates}>
            Refresh templates
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv('/ai/reports/templates/export', 'ai_report_templates_export.csv')
            }
          >
            Export templates CSV
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Templates CSV via <code>GET /ai/reports/templates/export</code> (Stage 145 T1).
        </p>
        {reportResult && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>{reportResult.title}</strong> · {reportResult.report_type} ·{' '}
              {reportResult.period_label} · {reportResult.row_count} rows · {reportResult.format}
            </p>
            <pre style={{ whiteSpace: 'pre-wrap', background: '#f8fafc', padding: 12, maxHeight: 220, overflow: 'auto' }}>
              {(reportResult.preview_lines || []).slice(0, 20).join('\n') ||
                JSON.stringify(reportResult.preview_rows?.slice(0, 5) || [], null, 2)}
            </pre>
          </div>
        )}
        {reportTemplates.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <h4>Saved templates</h4>
            {reportTemplates.map((t) => (
              <div key={t.id} style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8, marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{t.name}</strong>
                  <button type="button" onClick={() => runTemplate(t)}>
                    Run
                  </button>
                </div>
                <p className="muted">{t.prompt}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="security">
        <h3>Security monitor</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Unusual logins and suspicious transaction bursts from audit history. Export via{' '}
          <code>GET /ai/security/alerts/export</code> (Stage 145 S1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button type="button" onClick={loadSecurityAlerts}>
            Refresh security alerts
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv(
                '/ai/security/alerts/export?lookback_hours=72',
                'ai_security_alerts_export.csv'
              )
            }
          >
            Export security alerts CSV
          </button>
        </div>
        {securityAlerts.length === 0 && <p className="muted">No security alerts in the lookback window</p>}
        {securityAlerts.slice(0, 12).map((a) => (
          <div key={a.id} style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8, marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{a.title}</strong>
              <span className="muted">
                {a.severity} · score {a.score}
              </span>
            </div>
            <p>{a.detail}</p>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="insights">
        <h3>Business insights</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Sales spikes/drops, purchase spend and overdue bills, expense anomalies, and restock
          suggestions — cited to Inventory, Sales, Purchases, and Expenses actuals.
          {insightActuals.length > 0 ? ` Covered: ${insightActuals.join(', ')}.` : null} Export via{' '}
          <code>GET /ai/insights/export</code> (Stage 145 I1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button type="button" onClick={loadInsights}>
            Refresh insights
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv('/ai/insights/export', 'ai_business_insights_export.csv')
            }
          >
            Export insights CSV
          </button>
        </div>
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
            {Array.isArray(c.domains) && c.domains.length > 0 && (
              <p className="muted">Actuals: {c.domains.join(' · ')}</p>
            )}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="low-stock">
        <h3>Low stock prediction</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Sales velocity over ~30 days with a short seasonality factor. Horizon 7–14 days.
          {method ? ` Method: ${method}.` : ''} At risk: {atRiskCount}. Export via{' '}
          <code>GET /ai/inventory/low-stock-prediction/export</code> (Stage 146 L1).
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <button type="button" onClick={loadPredictions}>
            Refresh predictions
          </button>
          <button
            type="button"
            onClick={() =>
              downloadAiCsv(
                '/ai/inventory/low-stock-prediction/export?horizon_days=14',
                'ai_low_stock_prediction_export.csv'
              )
            }
          >
            Export low-stock CSV
          </button>
        </div>
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
