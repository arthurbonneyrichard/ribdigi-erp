'use client';

import { useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [alerts, setAlerts] = useState<any[]>([]);
  const [predBusy, setPredBusy] = useState(false);
  const [draftPrBusy, setDraftPrBusy] = useState(false);
  const [lastAtRisk, setLastAtRisk] = useState<any[]>([]);
  const [includeOpenPr, setIncludeOpenPr] = useState(false);

  async function go() {
    setError('');
    setMessage('');
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
    setMessage('');
    try {
      const r = await api('/ai/insights');
      setA((r.data?.insights || []).join('\n'));
    } catch (err: any) {
      setError(err.message || 'Unable to load insights');
    }
  }

  async function loadSecurityAlerts() {
    setError('');
    setMessage('');
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

  async function loadInventoryPredictions() {
    setError('');
    setMessage('');
    setPredBusy(true);
    try {
      const r = await api('/ai/inventory/low-stock-prediction?days_ahead=14');
      const lines = r.data?.at_risk || [];
      setLastAtRisk(lines);
      setA(
        lines.length
          ? lines
              .slice(0, 20)
              .map(
                (x: any) =>
                  `${x.sku || x.product_id}: days=${x.days_to_stockout} conf=${x.confidence} qty=${x.suggested_order_qty} (${x.risk_reason})`
              )
              .join('\n')
          : 'No at-risk products in the prediction window'
      );
      if (!lines.length) {
        setMessage('No at-risk lines — nothing to turn into draft PRs yet.');
      }
    } catch (err: any) {
      setError(err.message || 'Unable to load inventory predictions');
    } finally {
      setPredBusy(false);
    }
  }

  async function createDraftPrsFromPredictions() {
    setError('');
    setMessage('');
    setDraftPrBusy(true);
    try {
      const body: Record<string, unknown> = {
        days_ahead: 14,
        notes: 'Created from AI low-stock prediction',
        include_open: includeOpenPr,
      };
      // Prefer lines already loaded so the UI matches what the user saw
      if (lastAtRisk.length) {
        body.lines = lastAtRisk;
      }
      const r = await api('/ai/inventory/low-stock-prediction/requests', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const created = r.data?.created || [];
      const skipped = r.data?.skipped || [];
      const nums = created.map((p: any) => p.request_number).filter(Boolean).join(', ');
      if (created.length) {
        setMessage(
          `Created draft PR(s): ${nums || created.length}. Open Purchasing → Requests to submit.`
        );
        setA(
          [
            `created_count=${r.data?.created_count ?? created.length}`,
            nums ? `requests: ${nums}` : '',
            skipped.length ? `skipped=${skipped.length}` : '',
          ]
            .filter(Boolean)
            .join('\n')
        );
      } else {
        setMessage(r.message || 'No draft purchase requests created (nothing eligible).');
        setA(
          skipped.length
            ? `skipped=${JSON.stringify(skipped.slice(0, 10))}`
            : 'No at-risk lines eligible for draft PRs'
        );
      }
    } catch (err: any) {
      const detail = err.detail;
      const skipped = detail?.skipped || [];
      if (skipped.length) {
        setA(
          skipped
            .slice(0, 20)
            .map((s: any) => `${s.product_id}: ${s.reason}`)
            .join('\n')
        );
        setError(
          `${detail?.message || err.message || 'No lines eligible'}. Enable “Include open PRs” to allow duplicates, or cancel existing requests.`
        );
      } else {
        setError(err.message || 'Unable to create draft purchase requests');
      }
    } finally {
      setDraftPrBusy(false);
    }
  }

  async function loadSalesAnalysis() {
    setError('');
    setMessage('');
    try {
      const r = await api('/ai/sales/analysis');
      const d = r.data || {};
      setA(
        [
          `Trend next-month forecast: ${d.trend?.forecast_next_month}`,
          `RFM customers: ${d.rfm?.customer_count} segments=${JSON.stringify(d.rfm?.segment_counts || {})}`,
          `Affinity pairs: ${(d.affinity || []).length}`,
          `Peak hours: ${(d.peaks?.hours || []).map((h: any) => h.hour).join(',')}`,
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to load sales analysis');
    }
  }

  async function loadExpenseAnalysis() {
    setError('');
    setMessage('');
    try {
      const r = await api('/ai/expenses/analysis');
      const d = r.data || {};
      setA(
        [
          `Budget alerts: ${(d.budget_variance_alerts || []).length}`,
          `Unusual: ${(d.unusual_expenses || []).length}`,
          ...(d.cost_optimization_suggestions || []).slice(0, 5),
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to load expense analysis');
    }
  }

  async function generateReport() {
    setError('');
    setMessage('');
    try {
      const prompt = q.trim() || 'monthly sales for this month';
      const r = await api('/ai/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt, format: 'csv' }),
      });
      const d = r.data || {};
      setA(
        [
          `type=${d.report_type} period=${d.period_label || '-'} rows=${d.row_count}`,
          `method=${d.method}`,
          JSON.stringify(d.preview_rows?.slice?.(0, 3) || d.data || {}, null, 2).slice(0, 1200),
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to generate report');
    }
  }

  async function customerAssist() {
    setError('');
    setMessage('');
    try {
      const prompt = q.trim() || 'overview of best customers and churn';
      const r = await api('/ai/customer/assist', {
        method: 'POST',
        body: JSON.stringify({ query: prompt }),
      });
      const d = r.data || {};
      setA(
        [
          d.answer || '',
          `intent=${d.intent} method=${d.method}`,
          `best=${(d.best_customers || []).length} high_churn=${(d.churn_risks || []).filter((c: any) => c.risk_level === 'high').length}`,
          `promos=${(d.promotions || []).length}`,
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to run customer assistant');
    }
  }

  async function analyzeDocument(file: File) {
    setError('');
    setMessage('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('document_type', 'auto');
      const r = await api('/ai/documents/analyze', { method: 'POST', body: fd });
      const d = r.data || {};
      setA(
        [
          `type=${d.document_type} engine=${d.engine} conf=${d.confidence}`,
          `amount=${d.extracted?.amount} date=${d.extracted?.expense_date} payee=${d.extracted?.payee} ref=${d.extracted?.reference}`,
          `party_matches=${(d.matches?.parties || []).length} po_matches=${(d.matches?.purchase_orders || []).length}`,
          `discrepancies=${(d.discrepancies || []).map((x: any) => x.code).join(',') || 'none'}`,
          d.apply_hint || '',
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to analyze document');
    }
  }

  return (
    <Shell>
      <h1>AI Business Assistant</h1>
      <p className="muted">
        Chat requires a configured AI provider. Rule-based insights, inventory/sales/expense analysis, report generator, customer/document assistants, and the Security Monitor are available now.
      </p>
      <div className="card">
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: '100%', minHeight: 100 }}
          placeholder="Ask a business question, report prompt, or customer query e.g. best customers / outstanding balance"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={go}>Ask</button>
          <button onClick={generateReport}>Generate report</button>
          <button onClick={customerAssist}>Customer assist</button>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
            <span style={{ border: '1px solid #ccc', padding: '6px 10px', borderRadius: 4 }}>Analyze document</span>
            <input
              type="file"
              accept="application/pdf,image/*"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void analyzeDocument(f);
                e.target.value = '';
              }}
            />
          </label>
          <button onClick={loadInsights}>Load insights</button>
          <button onClick={loadInventoryPredictions} disabled={predBusy}>
            {predBusy ? 'Loading predictions…' : 'Inventory predictions'}
          </button>
          <button
            onClick={createDraftPrsFromPredictions}
            disabled={draftPrBusy}
            title="Creates draft purchase requests from at-risk prediction lines (requires purchasing:write)"
          >
            {draftPrBusy ? 'Creating draft PR(s)…' : 'Create draft PR(s)'}
          </button>
          <label
            style={{ display: 'inline-flex', gap: 4, alignItems: 'center', fontSize: 13 }}
            title="Allow creating another draft PR even if the product is already on an open request"
          >
            <input
              type="checkbox"
              checked={includeOpenPr}
              onChange={(e) => setIncludeOpenPr(e.target.checked)}
            />
            Include open PRs
          </label>
          <button onClick={loadSalesAnalysis}>Sales analysis</button>
          <button onClick={loadExpenseAnalysis}>Expense analysis</button>
          <button onClick={loadSecurityAlerts}>Security alerts</button>
        </div>
        <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          Inventory predictions lists at-risk SKUs (14-day window). <strong>Create draft PR(s)</strong> turns
          those lines into draft purchase requests — open{' '}
          <Link href="/purchasing">Purchasing → Requests</Link> to submit. Requires purchasing write
          permission.
        </p>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        {message && <p style={{ color: '#166534' }}>{message}</p>}
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
