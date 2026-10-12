'use client';

import { useEffect, useState } from 'react';
import FormModal from '../../../components/FormModal';
import AttachmentPreview from '../../../components/AttachmentPreview';
import { api, getAccessToken } from '../../../lib/api';
import { formatWhen, plainLabel } from '../../../lib/format';
import { useStoreContext } from '../../../lib/storeContext';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';

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
  category_id?: string | null;
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
  const [expPrefix, setExpPrefix] = useState('');
  const [expNext, setExpNext] = useState('');
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
    category_id: string;
    store_id: string;
    had_store: boolean;
    branch_id: string;
    had_branch: boolean;
    department_id: string;
    had_department: boolean;
  } | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [incomes, setIncomes] = useState<any[]>([]);
  const [incomeDesc, setIncomeDesc] = useState('');
  const [incomeAmount, setIncomeAmount] = useState('');
  const [incomePayer, setIncomePayer] = useState('');
  const [attachPreview, setAttachPreview] = useState<{ apiPath: string; title: string } | null>(null);
  const [newCatCode, setNewCatCode] = useState('');
  const [newCatName, setNewCatName] = useState('');
  const [newCatBudget, setNewCatBudget] = useState('0');
  const [newCatAccountId, setNewCatAccountId] = useState('');
  const [expenseAccounts, setExpenseAccounts] = useState<any[]>([]);
  const [accountDrafts, setAccountDrafts] = useState<Record<string, string>>({});
  const [budgetDrafts, setBudgetDrafts] = useState<Record<string, string>>({});
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
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [supplierId, setSupplierId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [createBusy, setCreateBusy] = useState(false);
  const [expenseAddOpen, setExpenseAddOpen] = useState(false);
  const [rowBusyId, setRowBusyId] = useState<string | null>(null);

  async function refresh() {
    const storeTrim = (storeId || ctxStoreId || '').trim();
    const expensesPath = storeTrim ? `/expenses?store_id=${encodeURIComponent(storeTrim)}` : '/expenses';
    const [exp, cats, settings, liquid, st, br, dep, accounts, rec, supp, inc] = await Promise.all([
      api(expensesPath),
      api('/expenses/categories'),
      api('/expenses/settings'),
      api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
      api('/stores').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/accounting/accounts').catch(() => ({ data: [] })),
      api('/expenses/recurring').catch(() => ({ data: [] })),
      api('/suppliers').catch(() => ({ data: [] })),
      api('/incomes').catch(() => ({ data: [] })),
    ]);
    setRows(exp.data || []);
    setIncomes(inc.data || []);
    setCategories(cats.data || []);
    setLiquidAccounts(liquid.data || []);
    setStores(st.data || []);
    if (ctxStoreId && (st.data || []).some((s: any) => s.id === ctxStoreId)) {
      setStoreId(ctxStoreId);
    }
    setBranches(br.data || []);
    setDepartments(dep.data || []);
    setRecurring(rec.data || []);
    setSuppliers(supp.data || []);
    const glExpense = (accounts.data || []).filter(
      (a: any) =>
        String(a.account_type || '').toLowerCase() === 'expense' && a.is_active !== false
    );
    setExpenseAccounts(glExpense);
    setThreshold(settings.data?.expense_approval_threshold ?? 100);
    setL2Threshold(settings.data?.expense_l2_threshold ?? 1000);
    setLevels(settings.data?.levels || []);
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
          account_id: newCatAccountId.trim() || null,
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
      const accountId = (accountDrafts[cat.id] || '').trim();
      const payload: Record<string, unknown> = {
        budget_amount: Number(budgetDrafts[cat.id]) || 0,
      };
      // trim so Save category (UuidIdValue account_id) does not 422; clear when blank
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
    if (createBusy) return;
    setError('');
    setMessage('');
    setCreateBusy(true);
    try {
      const r = await api('/expenses', {
        method: 'POST',
        body: JSON.stringify({
          category_id: categoryId.trim() || null,
          amount: Number(amount),
          description: description.trim() || null,
          payee: payee.trim() || null,
          // null when blank so Create does not 422 (IsoDateQueryValue); omit → today.
          expense_date: expenseDate.trim() || null,
          payment_method: paymentMethod,
          liquid_account_id: liquidAccountId.trim() || null,
          reference: reference.trim() || null,
          branch_id: branchId.trim() || null,
          department_id: departmentId.trim() || null,
          store_id: storeId.trim() || null,
        }),
      });
      setMessage(
        r.data.status === 'approved'
          ? `Expense saved and posted to the books (${r.data.amount})`
          : `Expense saved — waiting for approval (${r.data.amount})`,
      );
      setDescription('');
      setPayee('');
      setReference('');
      setExpenseDate('');
      setSupplierId('');
      setExpenseAddOpen(false);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCreateBusy(false);
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
          category_id: recCategoryId.trim() || null,
          amount: Number(recAmount),
          description: recDescription.trim() || null,
          payee: recPayee.trim() || null,
          frequency: recFrequency,
          payment_method: recPaymentMethod,
          branch_id: recBranchId.trim() || null,
          department_id: recDepartmentId.trim() || null,
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
          category_id: recCategoryId.trim() || null,
          amount,
          description: recDescription.trim() || null,
          payee: recPayee.trim() || null,
          clear_payee: !recPayee.trim(),
          frequency: recFrequency,
          payment_method: recPaymentMethod,
          branch_id: recBranchId.trim() || null,
          department_id: recDepartmentId.trim() || null,
          clear_branch: !recBranchId.trim(),
          clear_department: !recDepartmentId.trim(),
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
    if (rowBusyId) return;
    setError('');
    setMessage('');
    const reason = rejectReason.trim();
    if (!reason) {
      setError('Enter a reason before voiding this expense');
      return;
    }
    setRowBusyId(id);
    try {
      await api(`/expenses/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage('Expense voided (reason stored on the record)');
      setRejectReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRowBusyId(null);
    }
  }

  async function removeExpense(id: string) {
    if (rowBusyId) return;
    setError('');
    setMessage('');
    setRowBusyId(id);
    try {
      await api(`/expenses/${id}`, { method: 'DELETE' });
      setMessage('Expense removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRowBusyId(null);
    }
  }

  async function uploadAttachment(id: string, file: File) {
    setError('');
    try {
      const token = getAccessToken();
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
      const token = getAccessToken();
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
      const payee = String(ocrDraft.payee || '').trim();
      if (payee) body.payee = payee;
      const description = String(ocrDraft.description || '').trim();
      if (description) body.description = description;
      const reference = String(ocrDraft.reference || '').trim();
      if (reference) body.reference = reference;
      const expenseDate = String(ocrDraft.expense_date || '').trim();
      if (expenseDate) body.expense_date = expenseDate;
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
      category_id: r.category_id || '',
      store_id: r.store_id || '',
      had_store: Boolean(r.store_id),
      branch_id: r.branch_id || '',
      had_branch: Boolean(r.branch_id),
      department_id: r.department_id || '',
      had_department: Boolean(r.department_id),
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
        category_id: editDraft.category_id.trim() || null,
      };
      const storeTrim = editDraft.store_id.trim();
      if (storeTrim) {
        body.store_id = storeTrim;
      } else if (editDraft.had_store) {
        body.clear_store = true;
      }
      const branchTrim = editDraft.branch_id.trim();
      if (branchTrim) {
        body.branch_id = branchTrim;
      } else if (editDraft.had_branch) {
        body.clear_branch = true;
      }
      const departmentTrim = editDraft.department_id.trim();
      if (departmentTrim) {
        body.department_id = departmentTrim;
      } else if (editDraft.had_department) {
        body.clear_department = true;
      }
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
  }).filter((r) => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    const hay = [r.category, r.payee, r.description, r.reference, r.status, String(r.amount)]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return hay.includes(q);
  });
  const approvedSpend = rows
    .filter((r) => r.status === 'approved')
    .reduce((s, r) => s + Number(r.amount || 0), 0);
  const pendingSpend = rows
    .filter((r) => r.status === 'pending')
    .reduce((s, r) => s + Number(r.amount || 0), 0);

  return (
    <div className="work">
      <div className="list-page-head">
        <div>
          <h1 style={{ margin: 0 }}>Expenses</h1>
          <p className="muted">
            Record what the company paid. Small amounts are approved automatically. Attach the receipt
            on the list. Tax on supplier bills is handled under Purchases. Other income below is money
            the company received, separate from a sale.
          </p>
        </div>
        <div className="work-actions" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => document.getElementById('budgets')?.scrollIntoView({ behavior: 'smooth' })}
            aria-label="Manage expense categories"
          >
            Categories
          </button>
          <button type="button" className="list-btn-primary" onClick={() => setExpenseAddOpen(true)} aria-label="Add expense">
            Add expense
          </button>
        </div>
      </div>

      <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input value={expPrefix} onChange={(e) => setExpPrefix(e.target.value)} aria-label="Expense number prefix" placeholder="Prefix" />
        <input value={expNext} onChange={(e) => setExpNext(e.target.value)} aria-label="Expense next number" placeholder="Next #" />
        <button
          type="button"
          aria-label="Save expense numbering"
          onClick={() => {
            const prefix = expPrefix.trim();
            const next = expNext.trim();
            const numbering: { prefix?: string; next_number?: number } = {};
            if (prefix) numbering.prefix = prefix;
            if (next) numbering.next_number = Number(next);
            const body = Object.keys(numbering).length ? { expense_numbering: numbering } : {};
            api('/expenses/settings', { method: 'PATCH', body: JSON.stringify(body) }).catch((err) =>
              setError(err.message || 'Could not save numbering'),
            );
          }}
        >
          Save numbering
        </button>
      </div>

      <div className="card" id="expense-register" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>Paid and unpaid expenses</h2>
        <p className="muted">Paid means it is approved and recorded. Unpaid means it is still waiting for approval.</p>
      <div className="erp-toolbar">
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search payee, category, description…"
          aria-label="Search expenses"
        />
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
          <option value="all">All</option>
          <option value="approved">Paid</option>
          <option value="pending">Unpaid</option>
          <option value="rejected">Voided</option>
        </select>
      </div>
      <table className="table compact">
        <thead>
          <tr>
            <th>Category</th>
            <th>Paid to</th>
            <th>What for</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Receipt</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {managedExpenses.length === 0 ? (
            <tr>
              <td colSpan={7} className="muted">
                {expenseManageFilter === 'all' ? 'No expenses match this search' : 'No expenses for this filter'}
              </td>
            </tr>
          ) : (
            managedExpenses.map((r) => (
            <tr key={r.id}>
              <td>{r.category}</td>
              <td>{r.payee || '—'}</td>
              <td>
                {r.description}
                {r.rejection_reason ? (
                  <div className="muted" style={{ fontSize: 12 }}>
                    Void: {r.rejection_reason}
                  </div>
                ) : null}
              </td>
              <td>{r.amount}</td>
              <td>
                {r.status === 'approved'
                  ? 'Posted'
                  : r.status === 'rejected'
                    ? 'Voided'
                    : 'Waiting'}
              </td>
              <td>
                {r.has_attachment ? (
                  <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                    type="button"
                    aria-label={`Preview expense attachment ${r.id}`}
                    onClick={() =>
                      setAttachPreview({
                        apiPath: `/expenses/${r.id}/attachment`,
                        title: `Receipt — ${r.reference || r.description || r.id.slice(0, 8)}`,
                      })
                    }
                  >
                    Preview
                  </button>
                    <button onClick={() => downloadAttachment(r.id)} aria-label="Download expense attachment">
                      Download
                    </button>
                    <button onClick={() => suggestOcr(r.id)} aria-label={`Suggest expense OCR ${r.id}`}>OCR</button>
                    <button onClick={() => removeAttachment(r.id)} aria-label={`Remove expense attachment ${r.id}`}>Remove</button>
                  </span>
                ) : (
                  <label style={{ cursor: 'pointer' }}>
                    <span className="muted">Upload</span>
                    <input
                      type="file"
                      style={{ display: 'none' }}
                      aria-label={`Upload expense attachment ${r.id}`}
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
                <div className="erp-row-actions">
                {(r.status === 'pending' || r.status === 'rejected') && (
                  <button
                    type="button"
                    onClick={() => startEdit(r)}
                    aria-label={`Edit expense ${r.id}`}
                    disabled={rowBusyId === r.id}
                  >
                    Edit
                  </button>
                )}
                {r.status === 'pending' && (
                  <>
                    <button
                      className="btn-ok"
                      onClick={() => approve(r.id)}
                      aria-label="Approve expense"
                      disabled={rowBusyId === r.id}
                    >
                      Approve
                    </button>
                    <button
                      className="btn-danger"
                      onClick={() => reject(r.id)}
                      aria-label={`Reject expense ${r.id}`}
                      disabled={!rejectReason.trim() || rowBusyId === r.id}
                      title={
                        rejectReason.trim()
                          ? 'Void expense'
                          : 'Enter a void reason first'
                      }
                    >
                      Void
                    </button>
                  </>
                )}
                {r.status === 'rejected' && (
                  <button
                    className="btn-danger"
                    type="button"
                    onClick={() => removeExpense(r.id)}
                    disabled={rowBusyId === r.id}
                    aria-label={`Remove voided expense ${r.id}`}
                  >
                    Remove
                  </button>
                )}
                </div>
              </td>
            </tr>
          ))
          )}
        </tbody>
      </table>
      </div>
      <div className="card cat-panel" style={{ marginBottom: 16 }}>
        <h3>Other income</h3>
        <div className="erp-form-grid">
          <input value={incomeDesc} onChange={(e) => setIncomeDesc(e.target.value)} placeholder="Description" aria-label="Income description" />
          <input value={incomeAmount} onChange={(e) => setIncomeAmount(e.target.value)} placeholder="Amount" aria-label="Income amount" />
          <input value={incomePayer} onChange={(e) => setIncomePayer(e.target.value)} placeholder="Payer (optional)" aria-label="Income payer" />
          <button
            type="button"
            onClick={async () => {
              setError('');
              try {
                await api('/incomes', {
                  method: 'POST',
                  body: JSON.stringify({
                    description: incomeDesc.trim(),
                    amount: Number(incomeAmount),
                    payer: incomePayer.trim() || null,
                    payment_method: paymentMethod,
                    liquid_account_id: liquidAccountId.trim() || null,
                  }),
                });
                setIncomeDesc('');
                setIncomeAmount('');
                setIncomePayer('');
                await refresh();
                setMessage('Income posted to the ledger');
              } catch (err: any) {
                setError(err.message);
              }
            }}
            aria-label="Post other income"
          >
            Post income
          </button>
        </div>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Payer</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {incomes.map((row) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.income_date) || '—'}</td>
                  <td>{row.description}</td>
                  <td>{row.payer || '—'}</td>
                  <td>{row.amount}</td>
                </tr>
              ))}
              {incomes.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">No other income recorded</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {error && <p className="erp-banner err" role="alert">{error}</p>}
      {message && <p className="erp-banner ok" role="status">{message}</p>}

      <div className="erp-kpis">
        <div className="card">
          <div className="muted">Posted this list</div>
          <div className="kpi">{approvedSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="card">
          <div className="muted">Waiting approval</div>
          <div className="kpi">{pendingSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="card">
          <div className="muted">Rows</div>
          <div className="kpi">{rows.length}</div>
        </div>
      </div>

      {expenseAddOpen ? (
      <FormModal
        title="Add expense"
        busy={createBusy}
        dirty={Boolean(amount.trim() || description.trim() || payee.trim() || reference.trim())}
        onClose={() => setExpenseAddOpen(false)}
      >
        <div className="erp-form-grid">
          <label>
            Category
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            aria-label="Expense spend category"
            title="Expense spend category (catalog picker; API category label 1–100)"
          >
            {categories
              .filter((c) => c.is_active !== false || c.id === categoryId)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.account_code ? ` · ${c.account_code}` : ''}
                  {c.is_active === false ? ' (inactive)' : ''}
                </option>
              ))}
          </select>
          </label>
          <label>
            Amount
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Amount paid"
            aria-label="Expense amount"
          />
          </label>
          <label>
            Paid to
          <input
            value={payee}
            onChange={(e) => setPayee(e.target.value)}
            placeholder="Who received the money"
            aria-label="Expense payee"
          />
          </label>
          <label>
            What for
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short description"
            aria-label="Expense description"
          />
          </label>
          <label>
            Paid with
          <select
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value)}
            aria-label="Expense payment method"
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="cheque">Cheque</option>
            <option value="mobile_money">Mobile Money (MoMo)</option>
          </select>
          </label>
          <label>
            Date
          <input
            type="date"
            value={expenseDate}
            onChange={(e) => setExpenseDate(e.target.value)}
            aria-label="Expense date"
            title="Expense date (optional YYYY-MM-DD)"
          />
          </label>
          <details className="span-2" style={{ gridColumn: '1 / -1' }}>
            <summary className="muted" style={{ cursor: 'pointer', fontWeight: 700 }}>
              Optional: supplier name, receipt later, cash account, location
            </summary>
            <div className="erp-form-grid" style={{ marginTop: 10 }}>
          <label>
            Copy supplier name
          <select
            value={supplierId}
            onChange={(e) => {
              const id = e.target.value;
              setSupplierId(id);
              const s = suppliers.find((x: any) => x.id === id);
              if (s?.name) setPayee(s.name);
            }}
            aria-label="Optional supplier for payee name"
          >
            <option value="">Not a supplier bill</option>
            {suppliers
              .filter((s: any) => s.is_active !== false)
              .map((s: any) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.balance != null ? ` · balance ${s.balance}` : ''}
                </option>
              ))}
          </select>
          </label>
          <p className="muted span-2">
            This copies the name only. Supplier invoices and VAT live under Purchases and Tax —
            they are not double-counted here.
          </p>
          <label>
            Reference
          <input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="Optional reference"
            aria-label="Expense reference"
          />
          </label>
          <label>
            Cash or bank account
          <select
            value={liquidAccountId}
            onChange={(e) => setLiquidAccountId(e.target.value)}
            aria-label="Expense liquid account"
            title="Account this payment uses"
          >
            <option value="">Default for payment method</option>
            {liquidAccounts.map((a: any) => (
              <option key={a.id} value={a.id}>
                {a.code} {a.name}
              </option>
            ))}
          </select>
          </label>
          <label>
            Branch
          <select
            value={branchId}
            onChange={(e) => {
              setBranchId(e.target.value);
              setDepartmentId('');
              setStoreId('');
            }}
            aria-label="Expense branch"
            title="Branch"
          >
            <option value="">None</option>
            {branches
              .filter((b) => b.is_active !== false)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
          </select>
          </label>
          <label>
            Store
          <select
            value={storeId}
            onChange={(e) => {
              setStoreId(e.target.value);
              setCtxStoreId(e.target.value);
            }}
            aria-label="Expense store"
            title="Store"
          >
            <option value="">None</option>
            {stores
              .filter((s) => s.is_active !== false)
              .filter((s) => !branchId || s.branch_id === branchId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
          </select>
          </label>
          <label>
            Department
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            aria-label="Expense department"
            title="Department"
          >
            <option value="">None</option>
            {departments
              .filter((d) => d.is_active !== false)
              .filter((d) => !branchId || !d.branch_id || d.branch_id === branchId)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} — {d.name}
                </option>
              ))}
          </select>
          </label>
            </div>
          </details>
          <button
            type="button"
            className="btn-ok"
            aria-label="Submit expense"
            onClick={createExpense}
            disabled={createBusy || !categoryId || !amount}
          >
            {createBusy ? 'Saving…' : 'Save expense'}
          </button>
        </div>
      </FormModal>
      ) : null}

      <div className="erp-split">
      <details className="erp-advanced" id="approval-matrix">
        <summary>Approval rules</summary>
      <div className="card" style={{ marginBottom: 0, boxShadow: 'none', border: 0, padding: '0 0 8px' }}>
        <h3>Who must approve large amounts</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          A larger amount needs the next step. Type the roles who can approve that step, separated by commas.
          People in that role can be emailed when an expense is waiting. They can turn that off under Notifications.
        </p>
        {levels.map((lvl, idx) => (
          <div
            key={idx}
            style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}
          >
            <span className="muted">Step {idx + 1}</span>
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
              placeholder="Who can approve"
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
            Add step
          </button>
          <button type="button" onClick={saveApprovalMatrix} aria-label="Save expense approval matrix">
            Save approval rules
          </button>
        </div>
      </div>
      </details>
      <details className="erp-advanced" id="budgets" open>
        <summary>Categories and monthly budgets</summary>
      <div className="card" style={{ marginBottom: 0, boxShadow: 'none', border: 0, padding: '0 0 8px' }}>
        <h3>Categories and monthly budgets</h3>
        <p className="muted">
          Set a monthly budget for each category. Reports compare spending with that budget.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <input
            value={newCatCode}
            onChange={(e) => setNewCatCode(e.target.value)}
            placeholder="Code"
            aria-label="Expense category code"
            title="Expense category code (1–40 chars; letters/digits required)"
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
            aria-label="Expense category monthly budget"
            style={{ width: 120 }}
          />
          <select
            value={newCatAccountId}
            onChange={(e) => setNewCatAccountId(e.target.value)}
            title="Expense account"
            aria-label="Expense account"
          >
            <option value="">Default expense account</option>
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
              <th>Account</th>
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
                      Inactive
                    </span>
                  ) : null}
                </td>
                <td>
                  <input
                    value={budgetDrafts[c.id] ?? String(c.budget_amount ?? 0)}
                    onChange={(e) =>
                      setBudgetDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                    }
                    aria-label={`Edit expense category budget ${c.code}`}
                    style={{ width: 110 }}
                  />
                </td>
                <td>
                  <select
                    value={accountDrafts[c.id] ?? ''}
                    onChange={(e) =>
                      setAccountDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                    }
                    aria-label={`Edit expense account ${c.name || c.code}`}
                  >
                    <option value="">Default expense account</option>
                    {expenseAccounts.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{c.is_active === false ? 'No' : 'Yes'}</td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => saveCategoryBudget(c)}
                    aria-label={`Save expense category ${c.id}`}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className={c.is_active === false ? 'btn-ok' : 'btn-danger'}
                    onClick={() => setCategoryActive(c, c.is_active === false)}
                    aria-label={
                      c.is_active === false
                        ? `Activate expense category ${c.id}`
                        : `Deactivate expense category ${c.id}`
                    }
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
      </details>
      </div>
      <div className="erp-split">
      <details className="erp-advanced" id="recurring">
        <summary>Repeat on a schedule</summary>
      <div className="card" style={{ marginBottom: 0, boxShadow: 'none', border: 0, padding: '0 0 8px' }}>
        <h3>Repeat on a schedule</h3>
        <p className="muted">
          A schedule creates the next expense when it is due. Skip next moves that date forward
          without creating an expense. Edit changes the amount or payee for later expenses.
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
          Required before Skip next. The reason is kept with the record.
        </p>
        {recEditId ? (
          <p style={{ color: 'var(--deep-green, #006B2E)', marginTop: 0 }}>
            Editing schedule — change fields below, then Save schedule (or Cancel).
          </p>
        ) : null}
        <div className="erp-form-grid" style={{ marginBottom: 12 }}>
          <select
            value={recCategoryId}
            onChange={(e) => setRecCategoryId(e.target.value)}
            aria-label={
              recEditId ? 'Edit recurring expense category' : 'Recurring expense category'
            }
            title="Recurring expense category (catalog picker; API category label 1–100)"
          >
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
          <select
            value={recFrequency}
            onChange={(e) => setRecFrequency(e.target.value)}
            aria-label="Recurring frequency"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
          <select
            value={recPaymentMethod}
            onChange={(e) => setRecPaymentMethod(e.target.value)}
            aria-label="Recurring payment method"
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="cheque">Cheque</option>
            <option value="mobile_money">Mobile Money (MoMo)</option>
          </select>
          <select
            value={recBranchId}
            onChange={(e) => {
              setRecBranchId(e.target.value);
              setRecDepartmentId('');
            }}
            aria-label={
              recEditId ? 'Edit recurring expense branch' : 'Recurring expense branch'
            }
            title="Recurring expense branch (optional org dim)"
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
            value={recDepartmentId}
            onChange={(e) => setRecDepartmentId(e.target.value)}
            aria-label={
              recEditId
                ? 'Edit recurring expense department'
                : 'Recurring expense department'
            }
            title="Recurring expense department (optional org dim)"
          >
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
                <button type="button" onClick={saveRecurringEdit} disabled={!recCategoryId || recBusy} aria-label="Save recurring expense schedule">
                  {recBusy ? 'Saving…' : 'Save schedule'}
                </button>
                <button type="button" onClick={cancelRecurringEdit} disabled={recBusy} aria-label="Cancel recurring expense edit">
                  Cancel
                </button>
              </>
            ) : (
              <button type="button" onClick={createRecurring} disabled={!recCategoryId || recBusy} aria-label="Create recurring expense schedule">
                {recBusy ? 'Creating…' : 'Create schedule'}
              </button>
            )}
            <button type="button" aria-label="Generate due recurring expenses" onClick={generateDueRecurring}>
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
              <th>How often</th>
              <th>Next date</th>
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
                      Inactive
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
                <td>{plainLabel(r.frequency)}</td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {formatWhen(r.next_run_at) || '—'}
                </td>
                <td>{r.is_active ? 'On' : 'Off'}</td>
                <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => startRecurringEdit(r)} aria-label={`Edit recurring expense schedule ${r.id}`}>
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
                    aria-label={
                      r.is_active
                        ? `Deactivate recurring expense ${r.id}`
                        : `Activate recurring expense ${r.id}`
                    }
                  >
                    {r.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </details>

      <div className="card" style={{ marginBottom: 16 }}>
        <label>
          Approve comment{' '}
          <input
            value={approveComment}
            onChange={(e) => setApproveComment(e.target.value)}
            placeholder="Optional note when you approve"
            aria-label="Expense approve comment"
            title="Optional comment (1–500 chars; letters/digits required); blank omits"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Optional. Shown with the approval.
        </p>
        <label style={{ display: 'block', marginTop: 12 }}>
          Void reason{' '}
          <input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Required before Reject"
            aria-label="Expense reject reason"
            title="Required reason for Void (1–500 chars; letters/digits required)"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Required before you void an expense. The reason is kept with the record.
        </p>
      </div>
      </div>

      {ocrDraft && ocrFor && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Suggestions from the receipt</h3>
          <p className="muted">
            Check these fields before you apply them.
          </p>
          <div style={{ display: 'grid', gap: 8 }}>
            <input
              value={ocrDraft.amount}
              onChange={(e) => setOcrDraft({ ...ocrDraft, amount: e.target.value })}
              placeholder="Amount"
              aria-label="OCR expense amount"
            />
            <input
              value={ocrDraft.payee}
              onChange={(e) => setOcrDraft({ ...ocrDraft, payee: e.target.value })}
              placeholder="Payee"
              aria-label="Expense OCR payee"
            />
            <input
              value={ocrDraft.description}
              onChange={(e) => setOcrDraft({ ...ocrDraft, description: e.target.value })}
              placeholder="Description"
              aria-label="Expense OCR description"
            />
            <input
              value={ocrDraft.reference}
              onChange={(e) => setOcrDraft({ ...ocrDraft, reference: e.target.value })}
              placeholder="Reference"
              aria-label="Expense OCR reference"
            />
            <input
              value={ocrDraft.expense_date}
              onChange={(e) => setOcrDraft({ ...ocrDraft, expense_date: e.target.value })}
              placeholder="Date YYYY-MM-DD"
              aria-label="Expense OCR date"
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" aria-label="Apply expense OCR suggestion" onClick={applyOcr}>
                Apply to expense
              </button>
              <button
                type="button"
                onClick={() => {
                  setOcrFor(null);
                  setOcrDraft(null);
                  setOcrMeta(null);
                }}
                aria-label="Dismiss expense OCR"
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
            Change the amount or payee before this expense is approved.
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
              value={editDraft.category_id}
              onChange={(e) => setEditDraft({ ...editDraft, category_id: e.target.value })}
              aria-label="Edit expense category"
              title="Category"
            >
              <option value="">Keep current category</option>
              {categories
                .filter((c) => c.is_active !== false || c.id === editDraft.category_id)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name}
                  </option>
                ))}
            </select>
            <select
              value={editDraft.store_id}
              onChange={(e) => setEditDraft({ ...editDraft, store_id: e.target.value })}
              aria-label="Edit expense store"
              title="Store"
            >
              <option value="">{editDraft.had_store ? 'Clear store' : 'No store'}</option>
              {stores
                .filter((s) => s.is_active !== false || s.id === editDraft.store_id)
                .filter((s) => !editDraft.branch_id || s.branch_id === editDraft.branch_id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
            </select>
            <select
              value={editDraft.branch_id}
              onChange={(e) =>
                setEditDraft({
                  ...editDraft,
                  branch_id: e.target.value,
                  store_id: '',
                  department_id: '',
                })
              }
              aria-label="Edit expense branch"
              title="Branch"
            >
              <option value="">{editDraft.had_branch ? 'Clear branch' : 'No branch'}</option>
              {branches
                .filter((b) => b.is_active !== false || b.id === editDraft.branch_id)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} — {b.name}
                  </option>
                ))}
            </select>
            <select
              value={editDraft.department_id}
              onChange={(e) => setEditDraft({ ...editDraft, department_id: e.target.value })}
              aria-label="Edit expense department"
              title="Department"
            >
              <option value="">
                {editDraft.had_department ? 'Clear department' : 'No department'}
              </option>
              {departments
                .filter((d) => d.is_active !== false || d.id === editDraft.department_id)
                .filter(
                  (d) =>
                    !editDraft.branch_id || !d.branch_id || d.branch_id === editDraft.branch_id,
                )
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code} — {d.name}
                  </option>
                ))}
            </select>
            <select
              value={editDraft.payment_method}
              onChange={(e) => setEditDraft({ ...editDraft, payment_method: e.target.value })}
              aria-label="Edit payment method"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="card">Card</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_money">Mobile Money (MoMo)</option>
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={saveEdit} disabled={editBusy} aria-label="Save expense changes">
                {editBusy ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" onClick={cancelEdit} disabled={editBusy} aria-label="Cancel expense edit">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {attachPreview && (
        <AttachmentPreview
          open
          apiPath={attachPreview.apiPath}
          title={attachPreview.title}
          onClose={() => setAttachPreview(null)}
          onError={(msg) => setError(msg)}
        />
      )}
    </div>
  );
}
