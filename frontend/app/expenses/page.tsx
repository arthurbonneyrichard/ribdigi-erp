'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api, authHeaders } from '../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Category = {
  id: string;
  code: string;
  name: string;
  budget_amount: number;
  account_id?: string | null;
  account_code?: string | null;
  account_name?: string | null;
};
type CoaAccount = { id: string; code: string; name: string; account_type: string };
type Expense = {
  id: string;
  category: string;
  description: string;
  amount: number;
  payment_method: string;
  payee?: string;
  reference?: string;
  store_id?: string | null;
  department_id?: string | null;
  status: string;
  rejection_reason?: string;
  has_attachment?: boolean;
  attachment_url?: string | null;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
};
type OrgStore = { id: string; code?: string; name: string };
type OrgDepartment = { id: string; code?: string; name: string };

type Recurring = {
  id: string;
  category: string;
  category_id?: string;
  description: string;
  amount: number;
  frequency: string;
  payment_method: string;
  payee?: string;
  next_run_at?: string;
  is_active: boolean;
  skip_next?: boolean;
  next_amount?: number | null;
  next_description?: string | null;
};

export default function Page() {
  const [rows, setRows] = useState<Expense[]>([]);
  const [recurring, setRecurring] = useState<Recurring[]>([]);
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
  const [stores, setStores] = useState<OrgStore[]>([]);
  const [departments, setDepartments] = useState<OrgDepartment[]>([]);
  const [storeId, setStoreId] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [filterStoreId, setFilterStoreId] = useState('');
  const [filterDepartmentId, setFilterDepartmentId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [reference, setReference] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [recAmount, setRecAmount] = useState('100');
  const [recDescription, setRecDescription] = useState('');
  const [recPayee, setRecPayee] = useState('');
  const [recFrequency, setRecFrequency] = useState('monthly');
  const [recCategoryId, setRecCategoryId] = useState('');
  const [recPaymentMethod, setRecPaymentMethod] = useState('bank_transfer');
  const [recStoreId, setRecStoreId] = useState('');
  const [recDepartmentId, setRecDepartmentId] = useState('');
  const [modifyNextId, setModifyNextId] = useState<string | null>(null);
  const [modifyNextAmount, setModifyNextAmount] = useState('');
  const [modifyNextDescription, setModifyNextDescription] = useState('');
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
  const [budgets, setBudgets] = useState<any>(null);
  const [newCatCode, setNewCatCode] = useState('');
  const [newCatName, setNewCatName] = useState('');
  const [newCatBudget, setNewCatBudget] = useState('0');
  const [newCatAccountId, setNewCatAccountId] = useState('');
  const [expenseAccounts, setExpenseAccounts] = useState<CoaAccount[]>([]);
  const [editBudgetId, setEditBudgetId] = useState<string | null>(null);
  const [editBudgetAmount, setEditBudgetAmount] = useState('');
  const [editAccountId, setEditAccountId] = useState('');
  // Stage 123 F1 — expense_category_active → GET /expenses/categories?is_active=
  const [expenseCategoryActiveFilter, setExpenseCategoryActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('expense_category_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 125 R1 — recurring_active → GET /expenses/recurring?is_active=
  const [recurringActiveFilter, setRecurringActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('recurring_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });

  async function refresh(
    statusOverride?: string,
    opts?: {
      storeId?: string;
      departmentId?: string;
      categoryActive?: string;
      recurringActive?: string;
    },
  ) {
    const params = new URLSearchParams();
    const store = opts?.storeId !== undefined ? opts.storeId : filterStoreId;
    const dept = opts?.departmentId !== undefined ? opts.departmentId : filterDepartmentId;
    if (store) params.set('store_id', store);
    if (dept) params.set('department_id', dept);
    const status = statusOverride !== undefined ? statusOverride : filterStatus;
    if (status) params.set('status', status);
    const expQs = params.toString() ? `?${params.toString()}` : '';
    const categoryActive =
      opts?.categoryActive !== undefined ? opts.categoryActive : expenseCategoryActiveFilter;
    const catQs =
      categoryActive === 'true'
        ? '?is_active=true'
        : categoryActive === 'false'
          ? '?is_active=false'
          : '';
    const recurringActive =
      opts?.recurringActive !== undefined ? opts.recurringActive : recurringActiveFilter;
    const recQs =
      recurringActive === 'true'
        ? '?is_active=true'
        : recurringActive === 'false'
          ? '?is_active=false'
          : recurringActive === 'all'
            ? '?active_only=false'
            : '';
    const [exp, cats, settings, liquid, rec, bud, accounts, storeRows, deptRows] =
      await Promise.all([
        api(`/expenses${expQs}`),
        api(`/expenses/categories${catQs}`),
        api('/expenses/settings'),
        api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
        api(`/expenses/recurring${recQs}`).catch(() => ({ data: [] })),
        api('/expenses/budgets').catch(() => ({ data: null })),
        api('/accounting/accounts').catch(() => ({ data: [] })),
        api('/stores').catch(() => ({ data: [] })),
        api('/departments').catch(() => ({ data: [] })),
      ]);
    setRows(exp.data || []);
    setCategories(cats.data || []);
    setLiquidAccounts(liquid.data || []);
    setStores(storeRows.data || []);
    setDepartments(deptRows.data || []);
    setRecurring(rec.data || []);
    setBudgets(bud.data || null);
    const coa = (accounts.data || []) as CoaAccount[];
    setExpenseAccounts(coa.filter((a) => (a.account_type || '').toLowerCase() === 'expense'));
    setThreshold(settings.data?.expense_approval_threshold ?? 100);
    setL2Threshold(settings.data?.expense_l2_threshold ?? 1000);
    setLevels(settings.data?.levels || []);
    if (!categoryId && cats.data?.length) setCategoryId(cats.data[0].id);
    if (!recCategoryId && cats.data?.length) setRecCategoryId(cats.data[0].id);
  }

  // Stage 106 E1 / Stage 110 E1 — shareable status + store_id + department_id filters
  // (Pending/Approved/Rejected Shell leaves honor ?status=)
  function writeExpenseFilters(patch: {
    status?: string;
    storeId?: string;
    departmentId?: string;
  }) {
    const nextStatus = patch.status !== undefined ? patch.status : filterStatus;
    const nextStore = patch.storeId !== undefined ? patch.storeId : filterStoreId;
    const nextDept = patch.departmentId !== undefined ? patch.departmentId : filterDepartmentId;
    if (patch.status !== undefined) setFilterStatus(patch.status);
    if (patch.storeId !== undefined) setFilterStoreId(patch.storeId);
    if (patch.departmentId !== undefined) setFilterDepartmentId(patch.departmentId);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      if (!nextStatus) url.searchParams.delete('status');
      else url.searchParams.set('status', nextStatus);
      if (!nextStore) url.searchParams.delete('store_id');
      else url.searchParams.set('store_id', nextStore);
      if (!nextDept) url.searchParams.delete('department_id');
      else url.searchParams.set('department_id', nextDept);
      const qs = url.searchParams.toString();
      window.history.replaceState({}, '', qs ? `${url.pathname}?${qs}` : url.pathname);
    }
  }

  function setStatusFilter(next: string) {
    writeExpenseFilters({ status: next });
    refresh(next).catch((err) => setError(err.message));
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get('status')?.trim() || '';
    const store = params.get('store_id')?.trim() || '';
    const dept = params.get('department_id')?.trim() || '';
    const allowed = ['pending', 'approved', 'rejected'];
    const status = allowed.includes(raw) ? raw : '';
    if (status) setFilterStatus(status);
    if (store) setFilterStoreId(store);
    if (dept) setFilterDepartmentId(dept);
    let recActive = recurringActiveFilter;
    const ra = params.get('recurring_active')?.trim().toLowerCase() || '';
    if (ra === 'true' || ra === 'false') {
      recActive = ra;
      setRecurringActiveFilter(ra);
    }
    refresh(status, { storeId: store, departmentId: dept, recurringActive: recActive }).catch(
      (err) => setError(err.message),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stage 101 E1 — honor Shell #recurring / #budgets / #approval-matrix
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

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [filterStoreId, filterDepartmentId]);

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
          store_id: storeId || null,
          department_id: departmentId || null,
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
        headers: authHeaders(),
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
        headers: authHeaders(),
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
      const body: Record<string, unknown> = { confirm: true };
      if (ocrDraft.amount !== '') body.amount = Number(ocrDraft.amount);
      if (ocrDraft.payee !== '') body.payee = ocrDraft.payee;
      if (ocrDraft.description !== '') body.description = ocrDraft.description;
      if (ocrDraft.reference !== '') body.reference = ocrDraft.reference;
      if (ocrDraft.expense_date !== '') body.expense_date = ocrDraft.expense_date;
      await api(`/expenses/${ocrFor}/ocr-apply`, { method: 'POST', body: JSON.stringify(body) });
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

  async function createRecurring() {
    setError('');
    setMessage('');
    try {
      await api('/expenses/recurring', {
        method: 'POST',
        body: JSON.stringify({
          category_id: recCategoryId || undefined,
          amount: Number(recAmount),
          description: recDescription,
          payee: recPayee || undefined,
          frequency: recFrequency,
          payment_method: recPaymentMethod,
          store_id: recStoreId || null,
          department_id: recDepartmentId || null,
        }),
      });
      setMessage('Recurring expense created');
      setRecDescription('');
      setRecPayee('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateRecurring() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses/recurring/generate', { method: 'POST', body: '{}' });
      const n = (r.data || []).length;
      setMessage(`Generated ${n} expense(s)`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function skipNext(id: string) {
    setError('');
    setMessage('');
    try {
      await api(`/expenses/recurring/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ skip_next: true }),
      });
      setMessage('Next occurrence marked to skip');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRecurringActive(id: string, next: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/expenses/recurring/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: next }),
      });
      setMessage(next ? 'Recurring expense resumed' : 'Recurring expense paused');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveModifyNext() {
    if (!modifyNextId) return;
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {};
      if (modifyNextAmount) body.next_amount = Number(modifyNextAmount);
      if (modifyNextDescription !== '') body.next_description = modifyNextDescription;
      await api(`/expenses/recurring/${modifyNextId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage('Next occurrence updated');
      setModifyNextId(null);
      setModifyNextAmount('');
      setModifyNextDescription('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createCategory() {
    setError('');
    setMessage('');
    try {
      await api('/expenses/categories', {
        method: 'POST',
        body: JSON.stringify({
          code: newCatCode,
          name: newCatName,
          budget_amount: Number(newCatBudget) || 0,
          account_id: newCatAccountId || null,
        }),
      });
      setMessage('Category created');
      setNewCatCode('');
      setNewCatName('');
      setNewCatBudget('0');
      setNewCatAccountId('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveCategoryBudget() {
    if (!editBudgetId) return;
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        budget_amount: Number(editBudgetAmount) || 0,
      };
      if (editAccountId) body.account_id = editAccountId;
      else body.clear_account = true;
      await api(`/expenses/categories/${editBudgetId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage('Category budget / GL updated');
      setEditBudgetId(null);
      setEditBudgetAmount('');
      setEditAccountId('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Expenses</h1>
      <p className="muted">
        Auto-approve ≤ {threshold}
        {levels.length > 1 ? `; ${levels.length} approval levels above that` : ''}. Receipts supported.
      </p>
      <div style={{ marginBottom: 12 }}>
        <button
          type="button"
          onClick={async () => {
            // Stage 120 X1 — expenses CSV export (honors current status/store/department filters)
            setError('');
            setMessage('');
            try {
              const token = localStorage.getItem('token');
              const tenant = localStorage.getItem('tenant');
              const qs = new URLSearchParams();
              if (filterStatus) qs.set('status', filterStatus);
              if (filterStoreId) qs.set('store_id', filterStoreId);
              if (filterDepartmentId) qs.set('department_id', filterDepartmentId);
              const q = qs.toString();
              const res = await fetch(`${apiBase}/expenses/export${q ? `?${q}` : ''}`, {
                headers: authHeaders(),
              });
              if (!res.ok) throw new Error('Expenses export failed');
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'expenses_export.csv';
              a.click();
              URL.revokeObjectURL(url);
              setMessage('Expenses CSV exported');
            } catch (err: any) {
              setError(err.message || 'Expenses export failed');
            }
          }}
        >
          Export expenses CSV
        </button>
      </div>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }} id="budgets">
        <h3>Categories &amp; budgets</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Allocate monthly budgets and optional GL accounts per category; variance uses approved spend
          in the current period
          {budgets?.from_date
            ? ` (${new Date(budgets.from_date).toLocaleDateString()} – ${new Date(
                budgets.to_date
              ).toLocaleDateString()})`
            : ''}
          . Unmapped categories post to Operating Expenses (6000). Filter via{' '}
          <code>expense_category_active</code> → <code>GET /expenses/categories?is_active=</code>{' '}
          (Stage 123 F1). Budget variance CSV via <code>GET /expenses/budgets/export</code>{' '}
          (Stage 139 B1).
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
          <label className="muted">
            Active status{' '}
            <select
              value={expenseCategoryActiveFilter}
              onChange={(e) => {
                const v = e.target.value;
                setExpenseCategoryActiveFilter(v);
                const url = new URL(window.location.href);
                if (v === 'true' || v === 'false') url.searchParams.set('expense_category_active', v);
                else url.searchParams.delete('expense_category_active');
                const qs = url.searchParams.toString();
                window.history.replaceState(
                  {},
                  '',
                  `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`
                );
                refresh(undefined, { categoryActive: v }).catch((err) => setError(err.message));
              }}
              aria-label="Expense category active filter"
            >
              <option value="">All</option>
              <option value="true">Active only</option>
              <option value="false">Inactive only</option>
            </select>
          </label>
          <button
            type="button"
            onClick={async () => {
              // Stage 123 X1 — expense categories CSV export
              setError('');
              setMessage('');
              try {
                const token = localStorage.getItem('token');
                const tenant = localStorage.getItem('tenant');
                const qs =
                  expenseCategoryActiveFilter === 'true'
                    ? '?is_active=true'
                    : expenseCategoryActiveFilter === 'false'
                      ? '?is_active=false'
                      : '';
                const res = await fetch(`${apiBase}/expenses/categories/export${qs}`, {
                  headers: authHeaders(),
                });
                if (!res.ok) throw new Error('Expense categories export failed');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'expense_categories_export.csv';
                a.click();
                URL.revokeObjectURL(url);
                setMessage('Expense categories CSV exported');
              } catch (err: any) {
                setError(err.message || 'Expense categories export failed');
              }
            }}
          >
            Export expense categories CSV
          </button>
          <button
            type="button"
            onClick={async () => {
              // Stage 139 B1 — expense budgets variance CSV
              setError('');
              setMessage('');
              try {
                const token = localStorage.getItem('token');
                const tenant = localStorage.getItem('tenant');
                const res = await fetch(`${apiBase}/expenses/budgets/export`, {
                  headers: authHeaders(),
                });
                if (!res.ok) throw new Error('Expense budgets export failed');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'expense_budgets_export.csv';
                a.click();
                URL.revokeObjectURL(url);
                setMessage('Expense budgets CSV exported (Stage 139 B1)');
              } catch (err: any) {
                setError(err.message || 'Expense budgets export failed');
              }
            }}
          >
            Export budgets CSV
          </button>
        </div>
        <div style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 12 }}>
          <input
            value={newCatCode}
            onChange={(e) => setNewCatCode(e.target.value)}
            placeholder="Code (e.g. TRAVEL)"
          />
          <input
            value={newCatName}
            onChange={(e) => setNewCatName(e.target.value)}
            placeholder="Name"
          />
          <input
            value={newCatBudget}
            onChange={(e) => setNewCatBudget(e.target.value)}
            placeholder="Budget amount"
          />
          <select value={newCatAccountId} onChange={(e) => setNewCatAccountId(e.target.value)}>
            <option value="">GL account (default 6000)</option>
            {expenseAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={createCategory}>
            Add category
          </button>
        </div>
        {editBudgetId && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={editBudgetAmount}
              onChange={(e) => setEditBudgetAmount(e.target.value)}
              placeholder="Budget"
              style={{ width: 120 }}
            />
            <select value={editAccountId} onChange={(e) => setEditAccountId(e.target.value)}>
              <option value="">GL: default 6000</option>
              {expenseAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={saveCategoryBudget}>
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setEditBudgetId(null);
                setEditBudgetAmount('');
                setEditAccountId('');
              }}
            >
              Cancel
            </button>
          </div>
        )}
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>GL</th>
              <th>Budget</th>
              <th>Spent</th>
              <th>Pending</th>
              <th>Variance</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(budgets?.categories || categories.map((c) => ({ ...c, spent: 0, pending: 0, variance: c.budget_amount }))).map(
              (c: any) => {
                const meta = categories.find((x) => x.id === c.id);
                const gl =
                  meta?.account_code ||
                  (meta?.account_id ? meta.account_id.slice(0, 8) : null) ||
                  '6000';
                return (
                <tr key={c.id}>
                  <td>
                    {c.name} <span className="muted">({c.code})</span>
                  </td>
                  <td className="muted">{gl}</td>
                  <td>{c.budget_amount}</td>
                  <td>{c.spent ?? '—'}</td>
                  <td>{c.pending ?? '—'}</td>
                  <td style={{ color: c.over_budget ? '#b91c1c' : undefined }}>
                    {c.variance ?? '—'}
                    {c.utilization_pct != null ? ` (${c.utilization_pct}%)` : ''}
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => {
                        setEditBudgetId(c.id);
                        setEditBudgetAmount(String(c.budget_amount ?? 0));
                        setEditAccountId(meta?.account_id || '');
                      }}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              );
              }
            )}
          </tbody>
        </table>
        {budgets?.totals && (
          <p className="muted" style={{ marginTop: 8 }}>
            Totals — budget {budgets.totals.budget_amount}, spent {budgets.totals.spent}, variance{' '}
            {budgets.totals.variance}
          </p>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="recurring">
        <h3>Recurring expenses</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Notify before auto-generate; skip or modify the next occurrence. Filter via{' '}
          <code>recurring_active</code> → <code>GET /expenses/recurring?is_active=</code> (Stage
          125 R1).
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <select
            value={recurringActiveFilter || 'default'}
            onChange={(e) => {
              const v = e.target.value === 'default' ? '' : e.target.value;
              setRecurringActiveFilter(v);
              const url = new URL(window.location.href);
              if (v === 'true' || v === 'false') url.searchParams.set('recurring_active', v);
              else url.searchParams.delete('recurring_active');
              window.history.replaceState({}, '', url.toString());
              refresh(undefined, { recurringActive: v }).catch((err) => setError(err.message));
            }}
          >
            <option value="default">Active filter (default / all)</option>
            <option value="true">Active only</option>
            <option value="false">Paused only</option>
            <option value="all">All (active_only=false)</option>
          </select>
          <button
            type="button"
            onClick={async () => {
              const token = localStorage.getItem('access_token') || '';
              const qs =
                recurringActiveFilter === 'true'
                  ? '?is_active=true'
                  : recurringActiveFilter === 'false'
                    ? '?is_active=false'
                    : recurringActiveFilter === 'all'
                      ? '?active_only=false'
                      : '';
              const res = await fetch(`${apiBase}/expenses/recurring/export${qs}`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (!res.ok) {
                setError(await res.text());
                return;
              }
              const blob = await res.blob();
              const a = document.createElement('a');
              a.href = URL.createObjectURL(blob);
              a.download = 'recurring_expenses_export.csv';
              a.click();
              URL.revokeObjectURL(a.href);
              setMessage('Recurring expenses CSV downloaded');
            }}
          >
            Export recurring CSV
          </button>
        </div>
        <div style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 12 }}>
          <select value={recCategoryId} onChange={(e) => setRecCategoryId(e.target.value)}>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input
            value={recAmount}
            onChange={(e) => setRecAmount(e.target.value)}
            placeholder="Amount"
          />
          <input
            value={recDescription}
            onChange={(e) => setRecDescription(e.target.value)}
            placeholder="Description"
          />
          <input
            value={recPayee}
            onChange={(e) => setRecPayee(e.target.value)}
            placeholder="Payee"
          />
          <select value={recFrequency} onChange={(e) => setRecFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
          <select
            value={recPaymentMethod}
            onChange={(e) => setRecPaymentMethod(e.target.value)}
          >
            <option value="bank_transfer">Bank transfer</option>
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="cheque">Cheque</option>
          </select>
          <select value={recStoreId} onChange={(e) => setRecStoreId(e.target.value)}>
            <option value="">Store (optional)</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ` : ''}
                {s.name}
              </option>
            ))}
          </select>
          <select value={recDepartmentId} onChange={(e) => setRecDepartmentId(e.target.value)}>
            <option value="">Department (optional)</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code ? `${d.code} — ` : ''}
                {d.name}
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={createRecurring}>
              Add recurring
            </button>
            <button type="button" onClick={generateRecurring}>
              Generate due now
            </button>
          </div>
        </div>
        {modifyNextId && (
          <div style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 12 }}>
            <p className="muted">Modify next occurrence only</p>
            <input
              value={modifyNextAmount}
              onChange={(e) => setModifyNextAmount(e.target.value)}
              placeholder="Next amount"
            />
            <input
              value={modifyNextDescription}
              onChange={(e) => setModifyNextDescription(e.target.value)}
              placeholder="Next description"
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" onClick={saveModifyNext}>
                Save next override
              </button>
              <button
                type="button"
                onClick={() => {
                  setModifyNextId(null);
                  setModifyNextAmount('');
                  setModifyNextDescription('');
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Description</th>
              <th>Amount</th>
              <th>Frequency</th>
              <th>Next run</th>
              <th>Flags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {recurring.map((r) => (
              <tr key={r.id}>
                <td>{r.category}</td>
                <td>{r.description || '—'}</td>
                <td>
                  {r.amount}
                  {r.next_amount != null ? ` → next ${r.next_amount}` : ''}
                </td>
                <td>{r.frequency}</td>
                <td>{r.next_run_at ? new Date(r.next_run_at).toLocaleString() : '—'}</td>
                <td>
                  {!r.is_active ? 'paused' : r.skip_next ? 'skip next' : 'active'}
                  {r.next_description ? '; desc override' : ''}
                </td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => skipNext(r.id)} disabled={!!r.skip_next}>
                    Skip next
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setModifyNextId(r.id);
                      setModifyNextAmount(r.next_amount != null ? String(r.next_amount) : '');
                      setModifyNextDescription(r.next_description || '');
                    }}
                  >
                    Modify next
                  </button>
                  {r.is_active === false ? (
                    <button type="button" onClick={() => setRecurringActive(r.id, true)}>
                      Resume
                    </button>
                  ) : (
                    <button type="button" onClick={() => setRecurringActive(r.id, false)}>
                      Pause
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!recurring.length && (
              <tr>
                <td colSpan={7} className="muted">
                  No recurring expenses yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="approval-matrix">
        <h3>Approval matrix</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Amount must exceed a level&apos;s min to require that step. Roles are comma-separated.
          Export via <code>GET /expenses/settings/export</code> (Stage 138 E1).
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
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={addLevel} disabled={levels.length >= 5}>
            Add level
          </button>
          <button type="button" onClick={saveApprovalMatrix}>
            Save matrix
          </button>
          <button
            type="button"
            onClick={async () => {
              // Stage 138 E1 — expense approval settings CSV
              setError('');
              setMessage('');
              try {
                const token = localStorage.getItem('token');
                const tenant = localStorage.getItem('tenant');
                const res = await fetch(`${apiBase}/expenses/settings/export`, {
                  headers: authHeaders(),
                });
                if (!res.ok) throw new Error('Expense settings export failed');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'expense_settings_export.csv';
                a.click();
                URL.revokeObjectURL(url);
                setMessage('Expense approval settings CSV exported (Stage 138 E1)');
              } catch (err: any) {
                setError(err.message || 'Expense settings export failed');
              }
            }}
          >
            Export approval settings CSV
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
          <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
            <option value="">Store (optional)</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ` : ''}
                {s.name}
              </option>
            ))}
          </select>
          <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">Department (optional)</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code ? `${d.code} — ` : ''}
                {d.name}
              </option>
            ))}
          </select>
          <button onClick={createExpense}>Submit expense</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Filter expenses</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select
            value={filterStatus}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter expenses by status"
          >
            <option value="">All statuses</option>
            <option value="pending">pending</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
          </select>
          <select
            value={filterStoreId}
            onChange={(e) => writeExpenseFilters({ storeId: e.target.value })}
            aria-label="Filter expenses by store"
          >
            <option value="">All stores</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={filterDepartmentId}
            onChange={(e) => writeExpenseFilters({ departmentId: e.target.value })}
            aria-label="Filter expenses by department"
          >
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
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
            <th>Store</th>
            <th>Dept</th>
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
              <td className="muted">
                {stores.find((s) => s.id === r.store_id)?.name || (r.store_id ? '—' : '—')}
              </td>
              <td className="muted">
                {departments.find((d) => d.id === r.department_id)?.name ||
                  (r.department_id ? '—' : '—')}
              </td>
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
