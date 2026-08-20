'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import AttachmentPreview from '../../components/AttachmentPreview';
import { api } from '../../lib/api';
import { useStoreContext } from '../../lib/storeContext';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/** Keep aligned with backend SystemRoleValue / rbac.VALID_ROLES (approval matrix). */
const SYSTEM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
  'company_admin',
  'store_manager',
  'sales_officer',
  'inventory_officer',
  'accountant',
  'cashier',
] as const;

type Category = {
  id: string;
  code: string;
  name: string;
  budget_amount: number;
  is_active?: boolean;
  account_id?: string | null;
  account_code?: string | null;
  account_name?: string | null;
};
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
  approval_comment?: string | null;
  has_attachment?: boolean;
  attachment_url?: string | null;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
  store_id?: string | null;
  branch_id?: string | null;
  department_id?: string | null;
};

export default function Page() {
  const [rows, setRows] = useState<Expense[]>([]);
  const [expenseManageFilter, setExpenseManageFilter] = useState<
    'all' | 'pending' | 'approved' | 'rejected'
  >('all');
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryManageFilter, setCategoryManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
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
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [branchId, setBranchId] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [stores, setStores] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [reference, setReference] = useState('');
  const [expenseDate, setExpenseDate] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [approveComment, setApproveComment] = useState('');
  const [ocrFor, setOcrFor] = useState<string | null>(null);
  const [ocrDraft, setOcrDraft] = useState<{
    amount: string;
    payee: string;
    description: string;
    reference: string;
    expense_date: string;
  } | null>(null);
  const [ocrMeta, setOcrMeta] = useState<any>(null);
  const [editFor, setEditFor] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<{
    amount: string;
    payee: string;
    description: string;
    reference: string;
    payment_method: string;
  } | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [attachPreview, setAttachPreview] = useState<{ apiPath: string; title: string } | null>(null);
  const [newCatCode, setNewCatCode] = useState('');
  const [newCatName, setNewCatName] = useState('');
  const [newCatBudget, setNewCatBudget] = useState('0');
  const [newCatAccountId, setNewCatAccountId] = useState('');
  const [expenseAccounts, setExpenseAccounts] = useState<any[]>([]);
  const [accountDrafts, setAccountDrafts] = useState<Record<string, string>>({});
  const [budgetDrafts, setBudgetDrafts] = useState<Record<string, string>>({});
  const [expPrefix, setExpPrefix] = useState('EXP');
  const [expNext, setExpNext] = useState('1');
  const [expPreview, setExpPreview] = useState('');
  const [recurring, setRecurring] = useState<any[]>([]);
  const [recurringManageFilter, setRecurringManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [recAmount, setRecAmount] = useState('100');
  const [recDescription, setRecDescription] = useState('');
  const [recPayee, setRecPayee] = useState('');
  const [recFrequency, setRecFrequency] = useState('monthly');
  const [recPaymentMethod, setRecPaymentMethod] = useState('bank_transfer');
  const [recCategoryId, setRecCategoryId] = useState('');
  const [recBranchId, setRecBranchId] = useState('');
  const [recDepartmentId, setRecDepartmentId] = useState('');
  const [recEditId, setRecEditId] = useState<string | null>(null);
  const [recBusy, setRecBusy] = useState(false);
  const [skipNextReason, setSkipNextReason] = useState('');

  async function refresh() {
    const [exp, cats, settings, liquid, st, br, dep, accounts, rec] = await Promise.all([
      api('/expenses'),
      api('/expenses/categories'),
      api('/expenses/settings'),
      api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
      api('/stores').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/accounting/accounts').catch(() => ({ data: [] })),
      api('/expenses/recurring').catch(() => ({ data: [] })),
    ]);
    setRows(exp.data || []);
    setCategories(cats.data || []);
    setLiquidAccounts(liquid.data || []);
    setStores(st.data || []);
    if (ctxStoreId && (st.data || []).some((s: any) => s.id === ctxStoreId)) {
      setStoreId(ctxStoreId);
    }
    setBranches(br.data || []);
    setDepartments(dep.data || []);
    setRecurring(rec.data || []);
    const glExpense = (accounts.data || []).filter(
      (a: any) =>
        String(a.account_type || '').toLowerCase() === 'expense' && a.is_active !== false
    );
    setExpenseAccounts(glExpense);
    setThreshold(settings.data?.expense_approval_threshold ?? 100);
    setL2Threshold(settings.data?.expense_l2_threshold ?? 1000);
    setLevels(settings.data?.levels || []);
    const num = settings.data?.expense_numbering;
    if (num) {
      setExpPrefix(num.prefix || 'EXP');
      setExpNext(String(num.next_number ?? 1));
      setExpPreview(num.preview || '');
    }
    if (!recCategoryId && (cats.data || []).length) {
      const firstActive = (cats.data || []).find((c: any) => c.is_active !== false);
      setRecCategoryId((firstActive || cats.data[0]).id);
    }
    const drafts: Record<string, string> = {};
    const acctDrafts: Record<string, string> = {};
    for (const c of cats.data || []) {
      drafts[c.id] = String(c.budget_amount ?? 0);
      acctDrafts[c.id] = c.account_id || '';
    }
    setBudgetDrafts(drafts);
    setAccountDrafts(acctDrafts);
    if (!categoryId && cats.data?.length) {
      const firstActive = cats.data.find((c: any) => c.is_active !== false);
      setCategoryId((firstActive || cats.data[0]).id);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createCategory() {
    const name = newCatName.trim();
    if (!name) {
      setError('Expense category name is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses/categories', {
        method: 'POST',
        body: JSON.stringify({
          code: newCatCode.trim(),
          name,
          budget_amount: Number(newCatBudget) || 0,
          account_id: newCatAccountId || null,
        }),
      });
      setNewCatCode('');
      setNewCatName('');
      setNewCatBudget('0');
      setNewCatAccountId('');
      setCategoryId(r.data.id);
      await refresh();
      setMessage(
        `Category ${r.data.code} created` +
          (r.data.account_code ? ` → GL ${r.data.account_code}` : '') +
          ` (budget ${r.data.budget_amount})`
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveCategoryBudget(cat: Category) {
    setError('');
    setMessage('');
    try {
      const accountId = accountDrafts[cat.id] || '';
      const payload: Record<string, unknown> = {
        budget_amount: Number(budgetDrafts[cat.id]) || 0,
      };
      if (accountId) payload.account_id = accountId;
      else payload.clear_account = true;
      const r = await api(`/expenses/categories/${cat.id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      setMessage(
        `Saved ${r.data.name}: budget ${r.data.budget_amount}/mo` +
          (r.data.account_code ? ` · GL ${r.data.account_code}` : ' · GL default 6000')
      );
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setCategoryActive(cat: Category, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/expenses/categories/${cat.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(
        is_active
          ? `Category ${r.data.code} activated`
          : `Category ${r.data.code} deactivated (history retained)`,
      );
      // If current pickers point at deactivated category, switch to another active one
      if (!is_active) {
        const next = categories.find((c) => c.id !== cat.id && c.is_active !== false);
        if (categoryId === cat.id && next) setCategoryId(next.id);
        if (recCategoryId === cat.id && next) setRecCategoryId(next.id);
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createExpense() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses', {
        method: 'POST',
        body: JSON.stringify({
          category_id: categoryId || undefined,
          amount: Number(amount),
          description: description.trim() || null,
          payee: payee.trim() || null,
          // null when blank so Create does not 422 (IsoDateQueryValue); omit → today.
          expense_date: expenseDate.trim() || null,
          payment_method: paymentMethod,
          liquid_account_id: liquidAccountId || null,
          reference: reference.trim() || null,
          branch_id: branchId || null,
          department_id: departmentId || null,
          store_id: storeId || null,
        }),
      });
      setMessage(`Expense ${r.data.status}: ${r.data.amount}`);
      setDescription('');
      setPayee('');
      setReference('');
      setExpenseDate('');
      setStoreId('');
      setBranchId('');
      setDepartmentId('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createRecurring() {
    setError('');
    setMessage('');
    setRecBusy(true);
    try {
      const r = await api('/expenses/recurring', {
        method: 'POST',
        body: JSON.stringify({
          category_id: recCategoryId || undefined,
          amount: Number(recAmount),
          description: recDescription.trim() || null,
          payee: recPayee.trim() || null,
          frequency: recFrequency,
          payment_method: recPaymentMethod,
          branch_id: recBranchId || null,
          department_id: recDepartmentId || null,
        }),
      });
      setMessage(
        `Recurring ${r.data.frequency} schedule created — next run ${r.data.next_run_at || 'soon'}`,
      );
      setRecDescription('');
      setRecPayee('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRecBusy(false);
    }
  }

  function startRecurringEdit(r: any) {
    setError('');
    setMessage('');
    setRecEditId(r.id);
    setRecCategoryId(r.category_id || '');
    setRecAmount(String(r.amount ?? ''));
    setRecPayee(r.payee || '');
    setRecDescription(r.description || '');
    setRecFrequency(r.frequency || 'monthly');
    setRecPaymentMethod(r.payment_method || 'bank_transfer');
    setRecBranchId(r.branch_id || '');
    setRecDepartmentId(r.department_id || '');
  }

  function cancelRecurringEdit() {
    setRecEditId(null);
    setRecPayee('');
    setRecDescription('');
    setRecAmount('100');
    setRecFrequency('monthly');
    setRecPaymentMethod('bank_transfer');
    setRecBranchId('');
    setRecDepartmentId('');
  }

  async function saveRecurringEdit() {
    if (!recEditId) return;
    setError('');
    setMessage('');
    setRecBusy(true);
    try {
      const amount = Number(recAmount);
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }
      const r = await api(`/expenses/recurring/${recEditId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          category_id: recCategoryId || undefined,
          amount,
          description: recDescription.trim() || null,
          payee: recPayee.trim() || null,
          clear_payee: !recPayee.trim(),
          frequency: recFrequency,
          payment_method: recPaymentMethod,
          branch_id: recBranchId || null,
          department_id: recDepartmentId || null,
          clear_branch: !recBranchId,
          clear_department: !recDepartmentId,
        }),
      });
      setMessage(
        r.message ||
          `Schedule updated — ${r.data?.payee || r.data?.category || 'recurring'} @ ${r.data?.amount}`,
      );
      cancelRecurringEdit();
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRecBusy(false);
    }
  }

  async function generateDueRecurring() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses/recurring/generate', { method: 'POST', body: '{}' });
      const created = r.data || [];
      const refs = created.map((e: any) => e.reference).filter(Boolean).join(', ');
      setMessage(
        created.length
          ? `Generated ${created.length} expense(s)${refs ? `: ${refs}` : ''}`
          : 'No due recurring expenses',
      );
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRecurringActive(id: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/expenses/recurring/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(r.message || (is_active ? 'Recurring activated' : 'Recurring deactivated'));
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function skipNextRecurring(id: string) {
    setError('');
    setMessage('');
    const reason = skipNextReason.trim();
    if (!reason) {
      setError('Enter a skip reason before skipping the next occurrence');
      return;
    }
    try {
      const r = await api(`/expenses/recurring/${id}/skip-next`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      const next = r.data?.next_run_at
        ? String(r.data.next_run_at).replace('T', ' ').slice(0, 19)
        : '—';
      setMessage(r.message ? `${r.message} → next ${next}` : `Skipped; next run ${next}`);
      setSkipNextReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function approve(id: string) {
    setError('');
    setMessage('');
    const comment = approveComment.trim();
    try {
      const r = await api(`/expenses/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify(comment ? { comment } : {}),
      });
      setMessage(r.message || (r.data?.status === 'approved' ? 'Expense approved' : 'Level approved'));
      setApproveComment('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function reject(id: string) {
    setError('');
    setMessage('');
    const reason = rejectReason.trim();
    if (!reason) {
      setError('Enter a reject reason before rejecting an expense');
      return;
    }
    try {
      await api(`/expenses/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
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
    setEditFor(null);
    setEditDraft(null);
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

  function startEdit(r: Expense) {
    setError('');
    setMessage('');
    setOcrFor(null);
    setOcrDraft(null);
    setOcrMeta(null);
    setEditFor(r.id);
    setEditDraft({
      amount: String(r.amount ?? ''),
      payee: r.payee || '',
      description: r.description || '',
      reference: r.reference || '',
      payment_method: r.payment_method || 'cash',
    });
  }

  function cancelEdit() {
    setEditFor(null);
    setEditDraft(null);
  }

  async function saveEdit() {
    if (!editFor || !editDraft) return;
    setError('');
    setMessage('');
    setEditBusy(true);
    try {
      const amount = Number(editDraft.amount);
      if (!Number.isFinite(amount) || amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }
      const body: Record<string, unknown> = {
        amount,
        payee: editDraft.payee.trim() || null,
        description: editDraft.description.trim() || null,
        reference: editDraft.reference.trim() || null,
        payment_method: editDraft.payment_method.trim() || 'cash',
      };
      const r = await api(`/expenses/${editFor}`, { method: 'PATCH', body: JSON.stringify(body) });
      setMessage(
        `Updated ${r.data?.reference || editFor.slice(0, 8)} — ${r.data?.payee || 'expense'} (${r.data?.amount})`
      );
      cancelEdit();
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setEditBusy(false);
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
            // null when blank so Save does not 422 (ApprovalLevelLabelValue).
            label: (l.label || '').trim() || null,
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

  async function saveExpenseNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/expenses/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          expense_numbering: {
            prefix: expPrefix.trim(),
            next_number: Math.max(1, Number(expNext) || 1),
          },
        }),
      });
      const num = r.data?.expense_numbering;
      if (num) {
        setExpPrefix(num.prefix || 'EXP');
        setExpNext(String(num.next_number ?? 1));
        setExpPreview(num.preview || '');
      }
      setMessage(`Numbering saved — ${num?.preview || ''}`.trim());
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

  const managedCategories = categories.filter((c) => {
    if (categoryManageFilter === 'all') return true;
    const active = c.is_active !== false;
    return categoryManageFilter === 'inactive' ? !active : active;
  });
  const managedRecurring = recurring.filter((r) => {
    if (recurringManageFilter === 'all') return true;
    const active = r.is_active !== false;
    return recurringManageFilter === 'inactive' ? !active : active;
  });
  const managedExpenses = rows.filter((r) => {
    if (expenseManageFilter === 'all') return true;
    return (r.status || 'pending') === expenseManageFilter;
  });

  return (
    <Shell>
      <h1>Expenses</h1>
      <p className="muted">
        Auto-approve ≤ {threshold}
        {levels.length > 1 ? `; ${levels.length} approval levels above that` : ''}. Receipts supported.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="erp-split">
      <div className="card" style={{ display: 'grid', gap: 8 }}>
        <strong>Document numbering</strong>
        <p className="muted" style={{ margin: 0 }}>
          When reference is left blank on create (including recurring generate), the next
          EXP-YYYY-NNNN is assigned automatically. Explicit vendor references are kept as entered.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Expense</span>
          <input
            value={expPrefix}
            onChange={(e) => setExpPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={expNext}
            onChange={(e) => setExpNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{expPreview || '—'}</span>
          <button type="button" onClick={saveExpenseNumbering}>
            Save numbering
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Approval matrix</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Amount must exceed a level&apos;s min to require that step. Roles are comma-separated.
          Pending expenses email current-step role holders (opt out under Notifications →
          expense_approval).
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
              aria-label={`Expense approval level ${idx + 1} min amount`}
            />
            <input
              value={lvl.label || ''}
              onChange={(e) => updateLevel(idx, { label: e.target.value })}
              placeholder="Label"
              title="Optional level label (1–120 chars; letters/digits required)"
              style={{ width: 140 }}
              aria-label={`Expense approval level ${idx + 1} label`}
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
              placeholder="roles (comma-separated system roles)"
              list="expense-approval-system-roles"
              style={{ minWidth: 220, flex: 1 }}
              aria-label={`Expense approval level ${idx + 1} roles`}
            />
            <button
              type="button"
              onClick={() => removeLevel(idx)}
              disabled={levels.length <= 1}
              aria-label={`Remove expense approval level ${idx + 1}`}
            >
              Remove
            </button>
          </div>
        ))}
        <datalist id="expense-approval-system-roles">
          {SYSTEM_ROLES.map((r) => (
            <option key={r} value={r} />
          ))}
        </datalist>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={addLevel} disabled={levels.length >= 5} aria-label="Add expense approval level">
            Add level
          </button>
          <button type="button" onClick={saveApprovalMatrix} aria-label="Save expense approval matrix">
            Save matrix
          </button>
        </div>
      </div>

      </div>
      <div className="erp-split">
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Category budgets</h3>
        <p className="muted">
          Monthly budgets scale to the report period (Net 30 days = 1×). Optional GL posts approved
          spend to that expense account (default 6000).
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <input
            value={newCatCode}
            onChange={(e) => setNewCatCode(e.target.value)}
            placeholder="Code"
            style={{ width: 90 }}
          />
          <input
            aria-label="Expense category name"
            value={newCatName}
            onChange={(e) => setNewCatName(e.target.value)}
            placeholder="Name"
            style={{ minWidth: 140 }}
          />
          <input
            value={newCatBudget}
            onChange={(e) => setNewCatBudget(e.target.value)}
            placeholder="Monthly budget"
            style={{ width: 120 }}
          />
          <select
            value={newCatAccountId}
            onChange={(e) => setNewCatAccountId(e.target.value)}
            title="GL expense account"
          >
            <option value="">GL: default 6000</option>
            {expenseAccounts.map((a: any) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            aria-label="Add expense category"
            onClick={createCategory}
            disabled={!newCatCode.trim() || !newCatName.trim()}
          >
            Add category
          </button>
        </div>
        <select
          value={categoryManageFilter}
          onChange={(e) => setCategoryManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
          title="Filter manage category list by status"
          aria-label="Expense category status filter"
          style={{ marginBottom: 8 }}
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Monthly budget</th>
              <th>GL account</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {managedCategories.map((c) => (
              <tr key={c.id}>
                <td>{c.code}</td>
                <td>
                  {c.name}
                  {c.is_active === false ? (
                    <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                      [inactive]
                    </span>
                  ) : null}
                </td>
                <td>
                  <input
                    value={budgetDrafts[c.id] ?? String(c.budget_amount ?? 0)}
                    onChange={(e) =>
                      setBudgetDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                    }
                    style={{ width: 110 }}
                  />
                </td>
                <td>
                  <select
                    value={accountDrafts[c.id] ?? ''}
                    onChange={(e) =>
                      setAccountDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                    }
                  >
                    <option value="">Default 6000</option>
                    {expenseAccounts.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{c.is_active === false ? 'no' : 'yes'}</td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => saveCategoryBudget(c)}>
                    Save
                  </button>
                  <button
                    type="button"
                    className={c.is_active === false ? 'btn-ok' : 'btn-danger'}
                    onClick={() => setCategoryActive(c, c.is_active === false)}
                    title={
                      c.is_active === false
                        ? 'Reactivate category for new expenses'
                        : 'Soft-deactivate without deleting history'
                    }
                  >
                    {c.is_active === false ? 'Activate' : 'Deactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Recurring expenses</h3>
        <p className="muted">
          Schedules auto-generate due expenses (Celery + manual Generate). Generated entries use the
          EXP-YYYY-NNNN series when reference is blank. Advance notify (T−1) uses category
          `recurring_expense_due` via Notifications scan-due / Celery. Use <strong>Skip next</strong>{' '}
          with a typed reason to advance `next_run_at` by one period without creating an expense
          (reason is audit-only; schedule description is unchanged). Use{' '}
          <strong>Edit schedule</strong> to change template amount/payee for future generations.
        </p>
        <label style={{ display: 'block', marginBottom: 10 }}>
          Skip next reason{' '}
          <input
            value={skipNextReason}
            onChange={(e) => setSkipNextReason(e.target.value)}
            placeholder="Required before Skip next"
            aria-label="Skip next reason"
            title="Required reason for Skip next (1–500 chars; letters/digits required)"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 0, marginBottom: 10 }}>
          Used by Skip next on active schedules (stored on audit <code>recurring_expense_skipped</code>
          , not the template description).
        </p>
        {recEditId ? (
          <p style={{ color: '#166534', marginTop: 0 }}>
            Editing schedule — change fields below, then Save schedule (or Cancel).
          </p>
        ) : null}
        <div className="erp-form-grid" style={{ marginBottom: 12 }}>
          <select value={recCategoryId} onChange={(e) => setRecCategoryId(e.target.value)}>
            {categories
              .filter((c) => c.is_active !== false || c.id === recCategoryId)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.is_active === false ? ' (inactive)' : ''}
                </option>
              ))}
          </select>
          <input
            value={recAmount}
            onChange={(e) => setRecAmount(e.target.value)}
            placeholder="Amount"
            aria-label="Recurring amount"
          />
          <input
            value={recPayee}
            onChange={(e) => setRecPayee(e.target.value)}
            placeholder="Payee (optional)"
            aria-label="Recurring payee"
          />
          <input
            value={recDescription}
            onChange={(e) => setRecDescription(e.target.value)}
            placeholder="Description"
            aria-label="Recurring description"
          />
          <select value={recFrequency} onChange={(e) => setRecFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
          <select value={recPaymentMethod} onChange={(e) => setRecPaymentMethod(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="cheque">Cheque</option>
          </select>
          <select
            value={recBranchId}
            onChange={(e) => {
              setRecBranchId(e.target.value);
              setRecDepartmentId('');
            }}
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
          <select value={recDepartmentId} onChange={(e) => setRecDepartmentId(e.target.value)}>
            <option value="">No department</option>
            {departments
              .filter((d) => d.is_active !== false)
              .filter((d) => !recBranchId || !d.branch_id || d.branch_id === recBranchId)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} — {d.name}
                </option>
              ))}
          </select>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {recEditId ? (
              <>
                <button type="button" onClick={saveRecurringEdit} disabled={!recCategoryId || recBusy}>
                  {recBusy ? 'Saving…' : 'Save schedule'}
                </button>
                <button type="button" onClick={cancelRecurringEdit} disabled={recBusy}>
                  Cancel
                </button>
              </>
            ) : (
              <button type="button" onClick={createRecurring} disabled={!recCategoryId || recBusy}>
                {recBusy ? 'Creating…' : 'Create schedule'}
              </button>
            )}
            <button type="button" onClick={generateDueRecurring}>
              Generate due now
            </button>
          </div>
        </div>
        <select
          value={recurringManageFilter}
          onChange={(e) =>
            setRecurringManageFilter(e.target.value as 'all' | 'active' | 'inactive')
          }
          title="Filter manage recurring schedule list by status"
          aria-label="Recurring expense status filter"
          style={{ marginBottom: 8 }}
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Payee</th>
              <th>Amount</th>
              <th>Freq</th>
              <th>Next run</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {managedRecurring.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No recurring schedules yet
                </td>
              </tr>
            )}
            {managedRecurring.map((r) => (
              <tr key={r.id}>
                <td>
                  {r.category}
                  {r.is_active === false ? (
                    <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                      [inactive]
                    </span>
                  ) : null}
                  {r.description ? (
                    <div className="muted" style={{ fontSize: 12 }}>
                      {r.description}
                    </div>
                  ) : null}
                </td>
                <td>{r.payee || '—'}</td>
                <td>{r.amount}</td>
                <td>{r.frequency}</td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {r.next_run_at ? String(r.next_run_at).replace('T', ' ').slice(0, 19) : '—'}
                </td>
                <td>{r.is_active ? 'yes' : 'no'}</td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => startRecurringEdit(r)}>
                    Edit schedule
                  </button>
                  {r.is_active ? (
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => skipNextRecurring(r.id)}
                      disabled={!skipNextReason.trim()}
                      aria-label={`Skip next recurring expense ${r.id}`}
                      title={
                        skipNextReason.trim()
                          ? 'Skip next occurrence'
                          : 'Enter a skip reason before skipping'
                      }
                    >
                      Skip next
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className={r.is_active ? 'btn-danger' : 'btn-ok'}
                    onClick={() => setRecurringActive(r.id, !r.is_active)}
                  >
                    {r.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>New expense</h3>
        <div className="erp-form-grid">
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            {categories
              .filter((c) => c.is_active !== false || c.id === categoryId)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.account_code ? ` · GL ${c.account_code}` : ''}
                  {c.budget_amount ? ` · budget ${c.budget_amount}` : ''}
                  {c.is_active === false ? ' (inactive)' : ''}
                </option>
              ))}
          </select>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" />
          <input
            value={payee}
            onChange={(e) => setPayee(e.target.value)}
            placeholder="Payee"
            aria-label="Expense payee"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description"
            aria-label="Expense description"
          />
          <input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="Reference"
            aria-label="Expense reference"
          />
          <input
            value={expenseDate}
            onChange={(e) => setExpenseDate(e.target.value)}
            placeholder="Date YYYY-MM-DD (optional)"
            aria-label="Expense date"
            title="Expense date (optional YYYY-MM-DD)"
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
          <select
            value={branchId}
            onChange={(e) => {
              setBranchId(e.target.value);
              setDepartmentId('');
              setStoreId('');
            }}
            title="Branch (optional)"
          >
            <option value="">All / no branch</option>
            {branches
              .filter((b) => b.is_active !== false)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
          </select>
          <select
            value={storeId}
            onChange={(e) => {
              setStoreId(e.target.value);
              setCtxStoreId(e.target.value);
            }}
            title="Store (optional)"
          >
            <option value="">No store</option>
            {stores
              .filter((s) => s.is_active !== false)
              .filter((s) => !branchId || s.branch_id === branchId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
          </select>
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            title="Department (optional)"
          >
            <option value="">No department</option>
            {departments
              .filter((d) => d.is_active !== false)
              .filter((d) => !branchId || !d.branch_id || d.branch_id === branchId)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} — {d.name}
                </option>
              ))}
          </select>
          <button type="button" className="btn-ok" onClick={createExpense}>
            Submit expense
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <label>
          Approve comment{' '}
          <input
            value={approveComment}
            onChange={(e) => setApproveComment(e.target.value)}
            placeholder="Optional — stored as approval_comment"
            aria-label="Expense approve comment"
            title="Optional comment (1–500 chars; letters/digits required); blank omits"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Used by Approve on pending expenses (no hardcoded <code>Approved</code> comment).
        </p>
        <label style={{ display: 'block', marginTop: 12 }}>
          Reject reason{' '}
          <input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Required before Reject"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Used by Reject on pending expenses (stored as <code>rejection_reason</code>).
        </p>
      </div>

      {ocrDraft && ocrFor && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>OCR suggestions</h3>
          <p className="muted">
            Engine: {ocrMeta?.engine || '—'} · Confidence: {ocrMeta?.confidence ?? '—'}
            {ocrMeta?.tesseract_available === false ? ' · Tesseract not on server (PDF text still works)' : ''}
          </p>
          <div style={{ display: 'grid', gap: 8 }}>
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
              aria-label="Expense OCR date"
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

      {editDraft && editFor && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Edit expense</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Pending or rejected expenses only (BR-9.2). Use this to fix amount/payee before approve — including
            expenses generated from recurring schedules.
          </p>
          <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
            <input
              value={editDraft.amount}
              onChange={(e) => setEditDraft({ ...editDraft, amount: e.target.value })}
              placeholder="Amount"
              aria-label="Edit amount"
            />
            <input
              value={editDraft.payee}
              onChange={(e) => setEditDraft({ ...editDraft, payee: e.target.value })}
              placeholder="Payee"
              aria-label="Edit payee"
            />
            <input
              value={editDraft.description}
              onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })}
              placeholder="Description"
              aria-label="Edit description"
            />
            <input
              value={editDraft.reference}
              onChange={(e) => setEditDraft({ ...editDraft, reference: e.target.value })}
              placeholder="Reference"
              aria-label="Edit reference"
            />
            <select
              value={editDraft.payment_method}
              onChange={(e) => setEditDraft({ ...editDraft, payment_method: e.target.value })}
              aria-label="Edit payment method"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="card">Card</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_money">Mobile money</option>
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={saveEdit} disabled={editBusy}>
                {editBusy ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" onClick={cancelEdit} disabled={editBusy}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <select
          value={expenseManageFilter}
          onChange={(e) =>
            setExpenseManageFilter(
              e.target.value as 'all' | 'pending' | 'approved' | 'rejected'
            )
          }
          title="Filter expense list by status"
          aria-label="Expense status filter"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending only</option>
          <option value="approved">Approved only</option>
          <option value="rejected">Rejected only</option>
        </select>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Branch</th>
            <th>Store</th>
            <th>Department</th>
            <th>Payee</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Approval</th>
            <th>Reject reason</th>
            <th>Approve comment</th>
            <th>Receipt</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {managedExpenses.length === 0 ? (
            <tr>
              <td colSpan={13} className="muted">
                No expenses for this filter
              </td>
            </tr>
          ) : (
            managedExpenses.map((r) => (
            <tr key={r.id}>
              <td>{r.category}</td>
              <td>
                {branches.find((b) => b.id === r.branch_id)?.code ||
                  (r.branch_id ? r.branch_id.slice(0, 8) : '—')}
              </td>
              <td>
                {stores.find((s) => s.id === r.store_id)?.code ||
                  (r.store_id ? r.store_id.slice(0, 8) : '—')}
              </td>
              <td>
                {departments.find((d) => d.id === r.department_id)?.code ||
                  (r.department_id ? r.department_id.slice(0, 8) : '—')}
              </td>
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
              <td className="muted">{r.rejection_reason || '—'}</td>
              <td className="muted">{r.approval_comment || '—'}</td>
              <td>
                {r.has_attachment ? (
                  <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() =>
                        setAttachPreview({
                          apiPath: `/expenses/${r.id}/attachment`,
                          title: `Receipt — ${r.reference || r.description || r.id.slice(0, 8)}`,
                        })
                      }
                    >
                      Preview
                    </button>
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
                {(r.status === 'pending' || r.status === 'rejected') && (
                  <button type="button" onClick={() => startEdit(r)} style={{ marginRight: 8 }}>
                    Edit
                  </button>
                )}
                {r.status === 'pending' && (
                  <>
                    <button
                      className="btn-ok"
                      onClick={() => approve(r.id)}
                      style={{ marginRight: 8 }}
                      aria-label="Approve expense"
                    >
                      Approve
                    </button>
                    <button className="btn-danger" onClick={() => reject(r.id)}>Reject</button>
                  </>
                )}
              </td>
            </tr>
          ))
          )}
        </tbody>
      </table>
      {attachPreview && (
        <AttachmentPreview
          open
          apiPath={attachPreview.apiPath}
          title={attachPreview.title}
          onClose={() => setAttachPreview(null)}
          onError={(msg) => setError(msg)}
        />
      )}
    </Shell>
  );
}
