'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Category = { id: string; code: string; name: string; budget_amount: number };
type Expense = {
  id: string;
  category: string;
  description: string;
  amount: number;
  payment_method: string;
  payee?: string;
  reference?: string;
  status: string;
  rejection_reason?: string;
  has_attachment?: boolean;
  attachment_url?: string | null;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
};

export default function Page() {
  const [rows, setRows] = useState<Expense[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [threshold, setThreshold] = useState(100);
  const [l2Threshold, setL2Threshold] = useState(1000);
  const [levels, setLevels] = useState<
    { min_amount: number; roles: string[]; label: string; step?: number }[]
  >([]);
  const [categoryId, setCategoryId] = useState('');
  const [amount, setAmount] = useState('50');
  const [description, setDescription] = useState('');
  const [payee, setPayee] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [liquidAccountId, setLiquidAccountId] = useState('');
  const [liquidAccounts, setLiquidAccounts] = useState<any[]>([]);
  const [reference, setReference] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [ocrFor, setOcrFor] = useState<string | null>(null);
  const [ocrDraft, setOcrDraft] = useState<{
    amount: string;
    payee: string;
    description: string;
    reference: string;
    expense_date: string;
  } | null>(null);
  const [ocrMeta, setOcrMeta] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    const [exp, cats, settings, liquid] = await Promise.all([
      api('/expenses'),
      api('/expenses/categories'),
      api('/expenses/settings'),
      api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
    ]);
    setRows(exp.data || []);
    setCategories(cats.data || []);
    setLiquidAccounts(liquid.data || []);
    setThreshold(settings.data?.expense_approval_threshold ?? 100);
    setL2Threshold(settings.data?.expense_l2_threshold ?? 1000);
    setLevels(settings.data?.levels || []);
    if (!categoryId && cats.data?.length) setCategoryId(cats.data[0].id);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createExpense() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses', {
        method: 'POST',
        body: JSON.stringify({
          category_id: categoryId || undefined,
          amount: Number(amount),
          description,
          payee: payee || undefined,
          payment_method: paymentMethod,
          liquid_account_id: liquidAccountId || null,
          reference: reference || undefined,
        }),
      });
      setMessage(`Expense ${r.data.status}: ${r.data.amount}`);
      setDescription('');
      setPayee('');
      setReference('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function approve(id: string) {
    setError('');
    try {
      const r = await api(`/expenses/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ comment: 'Approved' }),
      });
      setMessage(r.message || (r.data?.status === 'approved' ? 'Expense approved' : 'Level approved'));
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function reject(id: string) {
    setError('');
    try {
      await api(`/expenses/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: rejectReason || 'Rejected' }),
      });
      setMessage('Expense rejected');
      setRejectReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function uploadAttachment(id: string, file: File) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/expenses/${id}/attachment`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail?.message || body.detail || body.message || 'Upload failed');
      setMessage('Receipt uploaded');
      await refresh();
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Upload failed');
    }
  }

  async function downloadAttachment(id: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/expenses/${id}/attachment`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Download failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = match?.[1] || 'expense-attachment';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeAttachment(id: string) {
    setError('');
    try {
      await api(`/expenses/${id}/attachment`, { method: 'DELETE' });
      setMessage('Attachment removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function suggestOcr(id: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/expenses/${id}/ocr-suggest`, { method: 'POST', body: '{}' });
      const s = r.data?.suggestions || {};
      setOcrFor(id);
      setOcrMeta(r.data);
      setOcrDraft({
        amount: s.amount != null ? String(s.amount) : '',
        payee: s.payee || '',
        description: s.description || '',
        reference: s.reference || '',
        expense_date: s.expense_date || '',
      });
      setMessage(
        r.data?.warnings?.length
          ? `OCR ready (${r.data.engine}) — ${r.data.warnings[0]}`
          : `OCR suggestions ready (${r.data?.engine || 'ocr'}, confidence ${r.data?.confidence ?? 0})`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function applyOcr() {
    if (!ocrFor || !ocrDraft) return;
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {};
      if (ocrDraft.amount !== '') body.amount = Number(ocrDraft.amount);
      if (ocrDraft.payee !== '') body.payee = ocrDraft.payee;
      if (ocrDraft.description !== '') body.description = ocrDraft.description;
      if (ocrDraft.reference !== '') body.reference = ocrDraft.reference;
      if (ocrDraft.expense_date !== '') body.expense_date = ocrDraft.expense_date;
      await api(`/expenses/${ocrFor}`, { method: 'PATCH', body: JSON.stringify(body) });
      setMessage('OCR suggestions applied (pending expense updated)');
      setOcrFor(null);
      setOcrDraft(null);
      setOcrMeta(null);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveApprovalMatrix() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          levels: levels.map((l) => ({
            min_amount: Number(l.min_amount),
            roles: l.roles,
            label: l.label || undefined,
          })),
        }),
      });
      setThreshold(r.data?.expense_approval_threshold ?? threshold);
      setL2Threshold(r.data?.expense_l2_threshold ?? l2Threshold);
      setLevels(r.data?.levels || []);
      setMessage('Approval matrix saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  function updateLevel(idx: number, patch: Partial<(typeof levels)[0]>) {
    setLevels((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  function addLevel() {
    setLevels((prev) => {
      const last = prev[prev.length - 1];
      const min = last ? Number(last.min_amount) * 2 || 1000 : 100;
      return [
        ...prev,
        {
          min_amount: min,
          roles: ['company_admin', 'super_admin'],
          label: `Level ${prev.length + 1}`,
        },
      ];
    });
  }

  function removeLevel(idx: number) {
    setLevels((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));
  }

  return (
    <Shell>
      <h1>Expenses</h1>
      <p className="muted">
        Auto-approve ≤ {threshold}
        {levels.length > 1 ? `; ${levels.length} approval levels above that` : ''}. Receipts supported.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Approval matrix</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Amount must exceed a level&apos;s min to require that step. Roles are comma-separated.
        </p>
        {levels.map((lvl, idx) => (
          <div
            key={idx}
            style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}
          >
            <span className="muted">L{idx + 1}</span>
            <input
              value={lvl.min_amount}
              onChange={(e) => updateLevel(idx, { min_amount: Number(e.target.value) || 0 })}
              placeholder="Min amount"
              style={{ width: 100 }}
            />
            <input
              value={lvl.label || ''}
              onChange={(e) => updateLevel(idx, { label: e.target.value })}
              placeholder="Label"
              style={{ width: 140 }}
            />
            <input
              value={(lvl.roles || []).join(', ')}
              onChange={(e) =>
                updateLevel(idx, {
                  roles: e.target.value
                    .split(',')
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              placeholder="roles"
              style={{ minWidth: 220, flex: 1 }}
            />
            <button type="button" onClick={() => removeLevel(idx)} disabled={levels.length <= 1}>
              Remove
            </button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={addLevel} disabled={levels.length >= 5}>
            Add level
          </button>
          <button type="button" onClick={saveApprovalMatrix}>
            Save matrix
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>New expense</h3>
        <div style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" />
          <input value={payee} onChange={(e) => setPayee(e.target.value)} placeholder="Payee" />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description"
          />
          <input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="Reference"
          />
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="cheque">Cheque</option>
          </select>
          <select
            value={liquidAccountId}
            onChange={(e) => setLiquidAccountId(e.target.value)}
            title="Optional GL override"
          >
            <option value="">GL: method default</option>
            {liquidAccounts.map((a: any) => (
              <option key={a.id} value={a.id}>
                {a.code} {a.name}
              </option>
            ))}
          </select>
          <button onClick={createExpense}>Submit expense</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <label>
          Reject reason{' '}
          <input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
        </label>
      </div>

      {ocrDraft && ocrFor && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>OCR suggestions</h3>
          <p className="muted">
            Engine: {ocrMeta?.engine || '—'} · Confidence: {ocrMeta?.confidence ?? '—'}
            {ocrMeta?.tesseract_available === false ? ' · Tesseract not on server (PDF text still works)' : ''}
          </p>
          <div style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
            <input
              value={ocrDraft.amount}
              onChange={(e) => setOcrDraft({ ...ocrDraft, amount: e.target.value })}
              placeholder="Amount"
            />
            <input
              value={ocrDraft.payee}
              onChange={(e) => setOcrDraft({ ...ocrDraft, payee: e.target.value })}
              placeholder="Payee"
            />
            <input
              value={ocrDraft.description}
              onChange={(e) => setOcrDraft({ ...ocrDraft, description: e.target.value })}
              placeholder="Description"
            />
            <input
              value={ocrDraft.reference}
              onChange={(e) => setOcrDraft({ ...ocrDraft, reference: e.target.value })}
              placeholder="Reference"
            />
            <input
              value={ocrDraft.expense_date}
              onChange={(e) => setOcrDraft({ ...ocrDraft, expense_date: e.target.value })}
              placeholder="Date YYYY-MM-DD"
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" onClick={applyOcr}>
                Apply to expense
              </button>
              <button
                type="button"
                onClick={() => {
                  setOcrFor(null);
                  setOcrDraft(null);
                  setOcrMeta(null);
                }}
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Payee</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Approval</th>
            <th>Receipt</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.category}</td>
              <td>{r.payee || '—'}</td>
              <td>{r.description}</td>
              <td>{r.amount}</td>
              <td>{r.status}</td>
              <td>
                {r.status === 'pending'
                  ? `L${r.awaiting_level || r.approval_step || 1}/${r.approval_steps_required || 1}`
                  : r.approval_steps_required
                    ? `${r.approval_steps_required} level(s)`
                    : 'auto'}
              </td>
              <td>
                {r.has_attachment ? (
                  <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
                    <button onClick={() => downloadAttachment(r.id)}>Download</button>
                    <button onClick={() => suggestOcr(r.id)}>OCR</button>
                    <button onClick={() => removeAttachment(r.id)}>Remove</button>
                  </span>
                ) : (
                  <label style={{ cursor: 'pointer' }}>
                    <span className="muted">Upload</span>
                    <input
                      type="file"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) uploadAttachment(r.id, f);
                        e.target.value = '';
                      }}
                    />
                  </label>
                )}
              </td>
              <td>
                {r.status === 'pending' && (
                  <>
                    <button onClick={() => approve(r.id)} style={{ marginRight: 8 }}>
                      Approve
                    </button>
                    <button onClick={() => reject(r.id)}>Reject</button>
                  </>
                )}
                {r.status === 'rejected' && (
                  <span className="muted">{r.rejection_reason}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
