'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [alerts, setAlerts] = useState<any[]>([]);
  const [digestBusy, setDigestBusy] = useState(false);
  const [predBusy, setPredBusy] = useState(false);
  const [draftPrBusy, setDraftPrBusy] = useState(false);
  const [lastAtRisk, setLastAtRisk] = useState<any[]>([]);
  const [includeOpenPr, setIncludeOpenPr] = useState(false);
  const [predictionNotes, setPredictionNotes] = useState('');
  const [predictionRiskReason, setPredictionRiskReason] = useState('');
  const [minConfidence, setMinConfidence] = useState('');
  const [lastDocExtract, setLastDocExtract] = useState<any | null>(null);
  const [documentType, setDocumentType] = useState<'auto' | 'receipt' | 'invoice' | 'purchase_order'>('auto');
  const [expectedAmount, setExpectedAmount] = useState('');
  const [draftExpenseBusy, setDraftExpenseBusy] = useState(false);
  const [draftPiBusy, setDraftPiBusy] = useState(false);
  const [tmplName, setTmplName] = useState('');
  const [reportPeriod, setReportPeriod] = useState('');
  const [analysisFromDate, setAnalysisFromDate] = useState('');
  const [analysisToDate, setAnalysisToDate] = useState('');
  const [draftDocDate, setDraftDocDate] = useState('');
  const [draftDocDescription, setDraftDocDescription] = useState('');
  const [draftDocCategoryId, setDraftDocCategoryId] = useState('');
  const [draftDocStoreId, setDraftDocStoreId] = useState('');
  const [draftDocBranchId, setDraftDocBranchId] = useState('');
  const [draftDocDepartmentId, setDraftDocDepartmentId] = useState('');
  const [draftDocPurchaseOrderId, setDraftDocPurchaseOrderId] = useState('');
  const [draftDocSupplierId, setDraftDocSupplierId] = useState('');
  const [expenseCategories, setExpenseCategories] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [assistCustomerId, setAssistCustomerId] = useState('');

  useEffect(() => {
    api('/expenses/categories')
      .then((r) => setExpenseCategories(r.data || []))
      .catch(() => setExpenseCategories([]));
    api('/stores')
      .then((r) => setStores(r.data || []))
      .catch(() => setStores([]));
    api('/branches')
      .then((r) => setBranches(r.data || []))
      .catch(() => setBranches([]));
    api('/departments')
      .then((r) => setDepartments(r.data || []))
      .catch(() => setDepartments([]));
    api('/suppliers')
      .then((r) => setSuppliers(r.data || []))
      .catch(() => setSuppliers([]));
    api('/customers')
      .then((r) => setCustomers(r.data || []))
      .catch(() => setCustomers([]));
  }, []);

  async function go() {
    const message = q.trim();
    if (!message) {
      setError('AI chat message is required.');
      setMessage('');
      setA('');
      return;
    }
    setError('');
    setMessage('');
    setA('');
    try {
      const r = await api('/ai/chat', { method: 'POST', body: JSON.stringify({ message }) });
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
      const signals = r.data?.signals || [];
      if (signals.length) {
        setA(
          signals
            .map((s: any) => {
              const detail = s.detail ? ` — ${s.detail}` : '';
              return `[${s.kind || 'insight'}] ${s.headline || ''}${detail}`;
            })
            .join('\n')
        );
      } else {
        setA((r.data?.insights || []).join('\n'));
      }
      setMessage(
        signals.some((s: any) => s.kind === 'action' || s.kind === 'sales_spike' || s.kind === 'sales_drop' || s.kind === 'expense_anomaly')
          ? 'Loaded composed rule-based insights (sales, expenses, restock actions).'
          : 'Loaded rule-based insights.'
      );
    } catch (err: any) {
      setError(err.message || 'Unable to load insights');
    }
  }

  async function emailInsightDigest() {
    setError('');
    setMessage('');
    setDigestBusy(true);
    try {
      const r = await api('/ai/insights/digest', { method: 'POST', body: '{}' });
      const data = r.data || {};
      setA((data.insights || []).join('\n'));
      setMessage(
        data.sent
          ? 'Weekly AI insight digest emailed to your account.'
          : 'Digest generated, but email delivery is disabled or unavailable.'
      );
    } catch (err: any) {
      setError(err.message || 'Unable to email the insight digest');
    } finally {
      setDigestBusy(false);
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
        notes: predictionNotes.trim() || null,
        include_open: includeOpenPr,
      };
      const mc = minConfidence.trim() === '' ? null : Number(minConfidence);
      if (mc != null && Number.isFinite(mc)) {
        body.min_confidence = mc;
      } else if (minConfidence.trim() !== '') {
        setError('Min confidence must be a number from 0 to 1');
        return;
      }
      // Prefer lines already loaded so the UI matches what the user saw.
      // Slim to AiLowStockPredictionLine allow-list (extra=forbid on API).
      if (lastAtRisk.length) {
        body.lines = lastAtRisk.map((x: any) => ({
          product_id: String(x.product_id || '').trim(),
          confidence: x.confidence,
          suggested_order_qty: x.suggested_order_qty,
          recommended_order_qty: x.recommended_order_qty,
          warehouse_id: x.warehouse_id ? String(x.warehouse_id).trim() : null,
          preferred_supplier_id: x.preferred_supplier_id
            ? String(x.preferred_supplier_id).trim()
            : null,
          notes: String(x.notes || '').trim() || null,
          // Optional UI override; else prediction risk_reason; blank → null (omit).
          risk_reason:
            predictionRiskReason.trim() ||
            (typeof x.risk_reason === 'string' ? x.risk_reason.trim() : '') ||
            null,
        }));
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
        setPredictionNotes('');
        setPredictionRiskReason('');
        setA(
          [
            `Draft purchase request(s) created: ${nums || created.length}`,
            skipped.length ? `Skipped ${skipped.length} line(s)` : '',
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
      const params = new URLSearchParams();
      if (analysisFromDate) params.set('from_date', analysisFromDate);
      if (analysisToDate) params.set('to_date', analysisToDate);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const r = await api(`/ai/sales/analysis${qs}`);
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
      const params = new URLSearchParams();
      if (analysisFromDate) params.set('from_date', analysisFromDate);
      if (analysisToDate) params.set('to_date', analysisToDate);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const r = await api(`/ai/expenses/analysis${qs}`);
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
      const period = reportPeriod.trim() ? reportPeriod.trim() : null;
      const r = await api('/ai/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt, format: 'csv', period }),
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

  async function exportReport() {
    setError('');
    setMessage('');
    try {
      const prompt = q.trim() || 'monthly sales for this month';
      const period = reportPeriod.trim() ? reportPeriod.trim() : null;
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const res = await fetch(`${base}/ai/reports/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
        body: JSON.stringify({ prompt, format: 'csv', period }),
        cache: 'no-store',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body.detail;
        throw new Error(
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
              : body.message || 'Export failed'
        );
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || 'ai-report.csv';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`AI report CSV downloaded (${filename})`);
      setA(`exported=${filename} prompt=${prompt}`);
    } catch (err: any) {
      setError(err.message || 'Unable to export AI report');
    }
  }

  async function saveReportTemplate() {
    const name = tmplName.trim();
    if (!name) {
      setError('AI report template name is required.');
      setMessage('');
      return;
    }
    const prompt = q.trim();
    if (!prompt) {
      setError('AI report prompt is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    try {
      const r = await api('/ai/reports/templates', {
        method: 'POST',
        body: JSON.stringify({ name, prompt, format: 'csv' }),
      });
      const d = r.data || {};
      setMessage(`Template saved: ${d.name} (${d.report_type})`);
      setA(
        [
          `template_id=${d.id}`,
          `name=${d.name}`,
          `report_type=${d.report_type}`,
          `format=${d.format}`,
          `prompt=${d.prompt}`,
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to save report template');
    }
  }

  async function customerAssist() {
    setError('');
    setMessage('');
    try {
      const prompt = q.trim() || 'overview of best customers and churn';
      const r = await api('/ai/customer/assist', {
        method: 'POST',
        body: JSON.stringify({
          query: prompt,
          customer_id: assistCustomerId.trim() || null,
        }),
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
    setLastDocExtract(null);
    setDraftDocPurchaseOrderId('');
    setDraftDocSupplierId('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('document_type', documentType);
      const amt = expectedAmount.trim();
      if (amt !== '') {
        const n = Number(amt);
        if (!Number.isFinite(n)) {
          setError('Expected amount must be a finite number');
          return;
        }
        fd.append('expected_amount', String(n));
      }
      const r = await api('/ai/documents/analyze', { method: 'POST', body: fd });
      const d = r.data || {};
      setLastDocExtract(d);
      const rawDate = String(d.extracted?.expense_date || '').trim();
      setDraftDocDate(rawDate.length >= 10 ? rawDate.slice(0, 10) : '');
      setDraftDocDescription(String(d.extracted?.description || '').trim());
      setDraftDocCategoryId(
        String(d.extracted?.category_id || d.category_suggestion?.category_id || '').trim(),
      );
      setDraftDocPurchaseOrderId(
        String(d.matches?.purchase_orders?.[0]?.purchase_order_id || '').trim(),
      );
      setDraftDocSupplierId(
        String(d.matches?.purchase_orders?.[0]?.supplier_id || '').trim(),
      );
      setA(
        [
          `type=${d.document_type} engine=${d.engine} conf=${d.confidence}`,
          `amount=${d.extracted?.amount} date=${d.extracted?.expense_date} payee=${d.extracted?.payee} ref=${d.extracted?.reference}`,
          `category=${d.extracted?.category || d.category_suggestion?.category || '—'}`,
          `party_matches=${(d.matches?.parties || []).length} po_matches=${(d.matches?.purchase_orders || []).length}`,
          `discrepancies=${(d.discrepancies || []).map((x: any) => x.code).join(',') || 'none'}`,
          d.apply_hint || '',
        ].join('\n')
      );
    } catch (err: any) {
      setError(err.message || 'Unable to analyze document');
    }
  }

  async function createDraftExpenseFromDoc() {
    if (!lastDocExtract?.extracted) {
      setError('Analyze a receipt/invoice first');
      return;
    }
    const ex = lastDocExtract.extracted;
    if (ex.amount == null || Number(ex.amount) <= 0) {
      setError('Extracted amount is missing — cannot create draft expense');
      return;
    }
    setError('');
    setMessage('');
    setDraftExpenseBusy(true);
    try {
      const expenseDate = draftDocDate.trim() || String(ex.expense_date || '').trim() || null;
      const r = await api('/ai/documents/create-expense', {
        method: 'POST',
        body: JSON.stringify({
          amount: Number(ex.amount),
          payee: String(ex.payee || '').trim() || null,
          description: draftDocDescription.trim() || null,
          reference: String(ex.reference || '').trim() || null,
          expense_date: expenseDate,
          category_id: draftDocCategoryId.trim() || null,
          category:
            String(ex.category || lastDocExtract.category_suggestion?.category || '').trim() ||
            null,
          payment_method: 'cash',
          store_id: draftDocStoreId.trim() || null,
          branch_id: draftDocBranchId.trim() || null,
          department_id: draftDocDepartmentId.trim() || null,
        }),
      });
      const exp = r.data?.expense || r.data;
      setMessage(
        `Draft expense ${exp?.reference || exp?.id || ''} created (${exp?.status || 'pending'}) — open Expenses to review/approve.`
      );
    } catch (err: any) {
      setError(err.message || 'Unable to create draft expense');
    } finally {
      setDraftExpenseBusy(false);
    }
  }

  async function createDraftPurchaseInvoiceFromDoc() {
    const poId = draftDocPurchaseOrderId.trim();
    if (!poId) {
      setError('No matched purchase order — analyze an invoice that references a PO number first');
      return;
    }
    const poMatch =
      (lastDocExtract?.matches?.purchase_orders || []).find(
        (m: any) => String(m.purchase_order_id) === poId,
      ) || lastDocExtract?.matches?.purchase_orders?.[0];
    const ex = lastDocExtract?.extracted || {};
    setError('');
    setMessage('');
    setDraftPiBusy(true);
    try {
      const invoiceDate = draftDocDate.trim() || String(ex.expense_date || '').trim() || null;
      const r = await api('/ai/documents/create-purchase-invoice', {
        method: 'POST',
        body: JSON.stringify({
          purchase_order_id: poId,
          supplier_id: draftDocSupplierId.trim() || null,
          supplier_invoice_number: String(ex.reference || '').trim() || null,
          notes: String(ex.description || '').trim() || null,
          invoice_date: invoiceDate,
          is_reverse_charge: false,
        }),
      });
      const inv = r.data?.purchase_invoice || r.data;
      const poNum = r.data?.po_number || poMatch?.po_number || '';
      setMessage(
        `Draft purchase invoice ${inv?.invoice_number || inv?.id || ''} created from ${poNum} (${inv?.status || 'draft'}) — open Purchasing → Invoices to review/approve.`
      );
    } catch (err: any) {
      setError(err.message || 'Unable to create draft purchase invoice');
    } finally {
      setDraftPiBusy(false);
    }
  }

  const hasPoMatch = Boolean(draftDocPurchaseOrderId.trim());

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
          aria-label="AI chat message"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={go} aria-label="Ask AI chat">
            Ask
          </button>
          <button onClick={generateReport} aria-label="Generate AI report">
            Generate report
          </button>
          <button onClick={exportReport} aria-label="Export AI report">
            Export CSV
          </button>
          <input
            value={reportPeriod}
            onChange={(e) => setReportPeriod(e.target.value)}
            placeholder="Period (e.g. this_month)"
            aria-label="AI report period"
            style={{ minWidth: 160 }}
          />
          <input
            value={tmplName}
            onChange={(e) => setTmplName(e.target.value)}
            placeholder="Template name"
            aria-label="AI report template name"
            style={{ minWidth: 140 }}
          />
          <button
            onClick={saveReportTemplate}
            aria-label="Save AI report template"
            disabled={!tmplName.trim()}
          >
            Save template
          </button>
          <select
            value={assistCustomerId}
            onChange={(e) => setAssistCustomerId(e.target.value)}
            aria-label="AI customer assist customer"
            title="Optional customer (UuidIdValue); blank → overview / all customers"
          >
            <option value="">All customers / overview</option>
            {customers
              .filter((c) => c.is_active !== false)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code ? `${c.code} — ${c.name}` : c.name || c.id}
                </option>
              ))}
          </select>
          <button onClick={customerAssist} aria-label="Customer assist">
            Customer assist
          </button>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            Document type
            <select
              aria-label="Document type"
              value={documentType}
              onChange={(e) =>
                setDocumentType(e.target.value as 'auto' | 'receipt' | 'invoice' | 'purchase_order')
              }
            >
              <option value="auto">auto</option>
              <option value="receipt">receipt</option>
              <option value="invoice">invoice</option>
              <option value="purchase_order">purchase_order</option>
            </select>
          </label>
          <input
            type="number"
            step="any"
            value={expectedAmount}
            onChange={(e) => setExpectedAmount(e.target.value)}
            placeholder="Expected amount (optional)"
            title="Optional expected amount for discrepancy checks (finite money)"
            aria-label="AI document expected amount"
            style={{ width: 180 }}
          />
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
          <input
            type="date"
            value={draftDocDate}
            onChange={(e) => setDraftDocDate(e.target.value)}
            title="Draft expense / purchase invoice date (YYYY-MM-DD)"
            aria-label="AI document draft date"
          />
          <input
            value={draftDocDescription}
            onChange={(e) => setDraftDocDescription(e.target.value)}
            placeholder="Expense description (optional)"
            title="Optional AI draft expense description (1–500 chars; letters/digits required)"
            aria-label="AI document expense description"
            style={{ minWidth: 200 }}
          />
          <select
            value={draftDocCategoryId}
            onChange={(e) => setDraftDocCategoryId(e.target.value)}
            aria-label="AI document expense category"
            title="Optional spend category (UuidIdValue); blank → MISC / label path"
          >
            <option value="">No category / MISC</option>
            {expenseCategories
              .filter((c) => c.is_active !== false)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
          </select>
          <select
            value={draftDocStoreId}
            onChange={(e) => setDraftDocStoreId(e.target.value)}
            aria-label="AI document expense store"
            title="Optional store (UuidIdValue); blank → no store"
          >
            <option value="">No store</option>
            {stores
              .filter((s) => s.is_active !== false)
              .filter((s) => !draftDocBranchId || s.branch_id === draftDocBranchId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
          </select>
          <select
            value={draftDocBranchId}
            onChange={(e) => {
              setDraftDocBranchId(e.target.value);
              setDraftDocStoreId('');
              setDraftDocDepartmentId('');
            }}
            aria-label="AI document expense branch"
            title="Optional branch (UuidIdValue); blank → no branch"
          >
            <option value="">No branch</option>
            {branches
              .filter((b) => b.is_active !== false)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
          </select>
          <select
            value={draftDocDepartmentId}
            onChange={(e) => setDraftDocDepartmentId(e.target.value)}
            aria-label="AI document expense department"
            title="Optional department (UuidIdValue); blank → no department"
          >
            <option value="">No department</option>
            {departments
              .filter((d) => d.is_active !== false)
              .filter((d) => !draftDocBranchId || !d.branch_id || d.branch_id === draftDocBranchId)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} — {d.name}
                </option>
              ))}
          </select>
          <button
            type="button"
            onClick={createDraftExpenseFromDoc}
            disabled={draftExpenseBusy || !lastDocExtract?.extracted?.amount}
            title="Creates a pending expense from the last Analyze document result (requires expenses:write)"
            aria-label="Create draft expense"
          >
            {draftExpenseBusy ? 'Creating draft expense…' : 'Create draft expense'}
          </button>
          <select
            value={draftDocPurchaseOrderId}
            onChange={(e) => {
              const next = e.target.value;
              setDraftDocPurchaseOrderId(next);
              const match = (lastDocExtract?.matches?.purchase_orders || []).find(
                (m: any) => String(m.purchase_order_id) === next,
              );
              setDraftDocSupplierId(String(match?.supplier_id || '').trim());
            }}
            aria-label="AI document purchase order"
            title="Matched purchase order (UuidIdValue); required for draft PI"
          >
            <option value="">Select matched PO</option>
            {(lastDocExtract?.matches?.purchase_orders || []).map((m: any) => (
              <option key={m.purchase_order_id} value={m.purchase_order_id}>
                {m.po_number || m.purchase_order_id}
              </option>
            ))}
          </select>
          <select
            value={draftDocSupplierId}
            onChange={(e) => setDraftDocSupplierId(e.target.value)}
            aria-label="AI document supplier"
            title="Optional supplier (UuidIdValue); omit → PO supplier; must match PO"
          >
            <option value="">PO default supplier</option>
            {suppliers
              .filter((s) => s.is_active !== false)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code ? `${s.code} — ${s.name}` : s.name}
                </option>
              ))}
          </select>
          <button
            type="button"
            onClick={createDraftPurchaseInvoiceFromDoc}
            disabled={draftPiBusy || !hasPoMatch}
            title="Creates a draft purchase invoice by copying lines from the selected matched PO (requires purchasing:write)"
            aria-label="Create draft purchase invoice"
          >
            {draftPiBusy ? 'Creating draft PI…' : 'Create draft purchase invoice'}
          </button>
          <button onClick={loadInsights}>Load insights</button>
          <button onClick={emailInsightDigest} disabled={digestBusy}>
            {digestBusy ? 'Emailing digest…' : 'Email digest to me'}
          </button>
          <button
            onClick={loadInventoryPredictions}
            disabled={predBusy}
            aria-label="Inventory predictions"
          >
            {predBusy ? 'Loading predictions…' : 'Inventory predictions'}
          </button>
          <button
            onClick={createDraftPrsFromPredictions}
            disabled={draftPrBusy}
            title="Creates draft purchase requests from at-risk prediction lines (requires purchasing:write)"
            aria-label="Create draft purchase requests from predictions"
          >
            {draftPrBusy ? 'Creating draft PR(s)…' : 'Create draft PR(s)'}
          </button>
          <input
            value={minConfidence}
            onChange={(e) => setMinConfidence(e.target.value)}
            placeholder="Min confidence 0–1"
            aria-label="AI prediction min confidence"
            title="Optional confidence floor for draft PRs (0–1 finite; blank → 0)"
            style={{ width: 140 }}
          />
          <input
            value={predictionNotes}
            onChange={(e) => setPredictionNotes(e.target.value)}
            placeholder="Prediction notes (optional)"
            aria-label="AI low-stock prediction notes"
            title="Optional notes for draft PRs (1–500 chars; letters/digits required)"
            style={{ minWidth: 200 }}
          />
          <input
            value={predictionRiskReason}
            onChange={(e) => setPredictionRiskReason(e.target.value)}
            placeholder="Risk reason override (optional)"
            aria-label="AI prediction risk reason"
            title="Optional risk_reason override for prediction lines (1–500 chars; letters/digits required)"
            style={{ minWidth: 200 }}
          />
          <label
            style={{ display: 'inline-flex', gap: 4, alignItems: 'center', fontSize: 13 }}
            title="Allow creating another draft PR even if the product is already on an open request"
          >
            <input
              type="checkbox"
              checked={includeOpenPr}
              onChange={(e) => setIncludeOpenPr(e.target.checked)}
              aria-label="Include open purchase requests"
            />
            Include open PRs
          </label>
          <input
            type="date"
            value={analysisFromDate}
            onChange={(e) => setAnalysisFromDate(e.target.value)}
            title="Analysis from date (YYYY-MM-DD)"
            aria-label="AI analysis from date"
          />
          <input
            type="date"
            value={analysisToDate}
            onChange={(e) => setAnalysisToDate(e.target.value)}
            title="Analysis to date (YYYY-MM-DD)"
            aria-label="AI analysis to date"
          />
          <button onClick={loadSalesAnalysis} aria-label="Sales analysis">
            Sales analysis
          </button>
          <button onClick={loadExpenseAnalysis} aria-label="Expense analysis">
            Expense analysis
          </button>
          <button onClick={loadSecurityAlerts}>Security alerts</button>
        </div>
        <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          Weekly AI insight digests are sent to active company and super admins every Monday at 07:00 UTC.
          Use <strong>Email digest to me</strong> to preview the tenant-scoped email with your account.
          {' '}
          Inventory predictions lists at-risk SKUs (14-day window). <strong>Create draft PR(s)</strong> turns
          those lines into draft purchase requests — open{' '}
          <Link href="/purchasing">Purchasing → Requests</Link> to submit. Requires purchasing write
          permission. After <strong>Analyze document</strong>, <strong>Create draft expense</strong> turns
          the extracted amount/payee/category into a pending expense — open{' '}
          <Link href="/expenses">Expenses</Link> to review (requires expenses write).
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
