'use client';

import { useEffect, useMemo, useState } from 'react';
import FormModal from '../../../components/FormModal';
import EmptyState from '../../../components/EmptyState';
import PageHeader from '../../../components/PageHeader';
import CustomerGroupsWindow from '../../../components/CustomerGroupsWindow';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import { api } from '../../../lib/api';
import { openDocumentPrint } from '../../../lib/documentPrint';
import { createPaintGet, peekPrefetch } from '../../../lib/prefetchCache';
import { currencySign, formatDate, formatMoney } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import RowActions, { type RowActionItem } from '../../../components/RowActions';
import { AmountField } from '../../../components/AmountField';
import { normalizeIndustry } from '../../../lib/industries';
import { getMe } from '../../../lib/meCache';
import { isHotelIndustry } from '../../../lib/tenantNav';
import {
  matchesCustomerList,
  paginate,
  sortCustomers,
  type SortDir,
} from '../../../lib/listPages';

type Customer = {
  id: string;
  name: string;
  code?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  category?: string | null;
  status?: string;
  profile_type?: string;
  credit_limit?: number;
  payment_terms_days?: number;
  balance?: number;
  loyalty_points?: number;
  customer_group_id?: string | null;
  customer_group?: { id: string; name: string } | null;
  latitude?: number | null;
  longitude?: number | null;
};

type Group = { id: string; name: string; discount_percent?: number; is_active?: boolean };

function canWriteCredit(me: { permissions?: Record<string, string[]> | null } | null | undefined) {
  const perms = me?.permissions;
  if (!perms || typeof perms !== 'object') return false;
  const star = perms['*'] || [];
  if (star.includes('*') || star.includes('write')) return true;
  const credit = perms.credit || [];
  return credit.includes('write') || credit.includes('*') || credit.includes('approve');
}

/** Statement lines carry charge and payment, not a running total: add it, oldest first. */
function withRunningBalance(lines: any[]): Array<{ line: any; after: number }> {
  let running = 0;
  return (lines || []).map((line) => {
    running += Number(line.debit ?? line.amount_debit ?? 0) - Number(line.credit ?? line.amount_credit ?? 0);
    running = Math.round(running * 100) / 100;
    return { line, after: running };
  });
}

/** Sum of open invoices whose due date has passed. */
function overdueTotal(credit: any): number {
  const today = new Date().toISOString().slice(0, 10);
  const total = (credit?.credit_sales || []).reduce((sum: number, inv: any) => {
    const due = inv?.due_date ? String(inv.due_date).slice(0, 10) : '';
    return due && due < today ? sum + Number(inv.amount_base ?? inv.amount ?? 0) : sum;
  }, 0);
  return Math.round(total * 100) / 100;
}

function money(n: number) {
  const body = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  return `${currencySign()} ${body}`;
}

function fieldErrorsFromDetail(detail: unknown): Record<string, string> {
  const fields: Record<string, string> = {};
  if (Array.isArray(detail)) {
    for (const item of detail) {
      if (!item || typeof item !== 'object') continue;
      const rec = item as { loc?: unknown; msg?: unknown; message?: unknown };
      const loc = Array.isArray(rec.loc) ? rec.loc : [];
      const field = loc.find((x) => typeof x === 'string' && x !== 'body' && x !== 'query');
      const msg = typeof rec.msg === 'string' ? rec.msg : typeof rec.message === 'string' ? rec.message : '';
      if (typeof field === 'string' && msg) fields[field] = msg;
    }
  } else if (detail && typeof detail === 'object') {
    for (const [key, val] of Object.entries(detail as Record<string, unknown>)) {
      if (typeof val === 'string' && key !== 'msg' && key !== 'message') fields[key] = val;
    }
  }
  return fields;
}

const emptyForm = {
  name: '',
  code: '',
  email: '',
  phone: '',
  address: '',
  category: '',
  status: 'active',
  profileType: 'registered',
  groupId: '',
  creditLimit: '0',
  paymentTermsDays: '30',
  lat: '',
  lng: '',
};

export default function Page() {
  const formatPrefs = useCompanyFormat();
  const money = (v: unknown) => formatMoney(Number(v ?? 0) || 0, formatPrefs);
  const moneyOrBlank = (v: unknown) => (v == null || v === '' || Number(v) === 0 ? '' : money(v));
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('all');
  const [groupId, setGroupId] = useState('');
  const [profileType, setProfileType] = useState<'all' | 'registered' | 'walk_in'>('all');
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState<SortDir>(1);
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [saveBusy, setSaveBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [arCustomer, setArCustomer] = useState<Customer | null>(null);
  const [arBusy, setArBusy] = useState(false);
  const [arError, setArError] = useState('');
  const [arCredit, setArCredit] = useState<any>(null);
  const [arStatement, setArStatement] = useState<any>(null);
  const [arHistory, setArHistory] = useState<any>(null);
  const [accountId, setAccountId] = useState('');
  const [accountName, setAccountName] = useState('');
  const [accountMode, setAccountMode] = useState<'pay' | 'history'>('pay');
  const [accountError, setAccountError] = useState('');
  const [payInvoiceId, setPayInvoiceId] = useState('');
  const [payReference, setPayReference] = useState('');
  const [payChequeNumber, setPayChequeNumber] = useState('');
  const [lastPayment, setLastPayment] = useState<{ id: string; number: string } | null>(null);
  const [histFrom, setHistFrom] = useState('');
  const [histTo, setHistTo] = useState('');
  const [accountBusy, setAccountBusy] = useState(false);
  const [creditInfo, setCreditInfo] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [payDateNote, setPayDateNote] = useState('');
  const [payBusy, setPayBusy] = useState(false);
  const [canPay, setCanPay] = useState(false);
  const [hotelOps, setHotelOps] = useState(false);
  const [restaurantOps, setRestaurantOps] = useState(false);
  const [groupsOpen, setGroupsOpen] = useState(false);

  const paintGet = useMemo(() => createPaintGet(), []);

  async function refresh() {
    setError('');
    const path = status === 'all' ? '/customers' : `/customers?status=${status}`;
    const peekCust = peekPrefetch(path);
    if (peekCust?.data) setCustomers(peekCust.data || []);
    const [custRes, groupRes] = await Promise.all([
      paintGet.get(path),
      paintGet.get('/customers/groups').catch(() => ({ data: [] })),
    ]);
    paintGet.done();
    const groupList: Group[] = groupRes.data || [];
    const groupById = new Map(groupList.map((g) => [g.id, g]));
    // The list only carries the group id; attach the name so the Group column, search and sort work.
    setCustomers(
      (custRes.data || []).map((c: Customer) => {
        const g = c.customer_group_id ? groupById.get(c.customer_group_id) : undefined;
        return { ...c, customer_group: c.customer_group || (g ? { id: g.id, name: g.name } : null) };
      })
    );
    setGroups(groupList);
  }

  useEffect(() => {
    setLoading(true);
    refresh()
      .catch((err: any) => setError(err.message || 'Could not load customers'))
      .finally(() => setLoading(false));
    // status is a real API filter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    getMe()
      .then((me) => {
        setCanPay(canWriteCredit(me.data));
        setHotelOps(isHotelIndustry(me.data?.industry));
        setRestaurantOps(normalizeIndustry(me.data?.industry) === 'restaurant');
      })
      .catch(() => setCanPay(false));
  }, []);

  const filtered = useMemo(() => {
    const rows = customers.filter((c) =>
      matchesCustomerList(c, { q, status, groupId, profileType }),
    );
    return sortCustomers(rows, sortKey, sortDir);
  }, [customers, q, status, groupId, profileType, sortKey, sortDir]);

  const paged = useMemo(() => paginate(filtered, page), [filtered, page]);

  useEffect(() => {
    setPage(1);
  }, [q, status, groupId, profileType]);

  function toggleSort(key: string) {
    setSortKey(key);
    setSortDir((d) => (sortKey === key ? ((d === 1 ? -1 : 1) as SortDir) : 1));
  }

  function openAdd() {
    setEditingId('');
    setForm(emptyForm);
    setFormOpen(true);
    setMessage('');
    setError('');
    setFieldErrors({});
  }

  function openEdit(c: Customer) {
    setEditingId(c.id);
    setForm({
      name: c.name || '',
      code: c.code || '',
      email: c.email || '',
      phone: c.phone || '',
      address: c.address || '',
      category: c.category || '',
      status: c.status || 'active',
      profileType: c.profile_type || 'registered',
      groupId: c.customer_group_id || '',
      creditLimit: String(c.credit_limit ?? 0),
      paymentTermsDays: String(c.payment_terms_days ?? 30),
      lat: c.latitude == null ? '' : String(c.latitude),
      lng: c.longitude == null ? '' : String(c.longitude),
    });
    setFormOpen(true);
    setMessage('');
    setError('');
    setFieldErrors({});
  }

  function partyBody() {
    return {
      name: form.name.trim(),
      code: form.code.trim() || null,
      profile_type: form.profileType || 'registered',
      category: form.category.trim() || null,
      status: form.status || 'active',
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      address: form.address.trim() || null,
      latitude: form.lat === '' ? null : Number(form.lat),
      longitude: form.lng === '' ? null : Number(form.lng),
      credit_limit: Number(form.creditLimit) || 0,
      payment_terms_days: Number(form.paymentTermsDays) || 0,
      customer_group_id: form.groupId.trim() || null,
    };
  }

  async function save() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFieldErrors({});
    if (!form.name.trim()) {
      setFieldErrors({ name: 'Enter a customer name' });
      setError('Enter a customer name');
      return;
    }
    setSaveBusy(true);
    try {
      if (editingId) {
        await api(`/customers/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify(partyBody()),
        });
        setMessage(`${form.name.trim()} saved`);
        setFormOpen(false);
      } else {
        await api('/customers', { method: 'POST', body: JSON.stringify(partyBody()) });
        setMessage('Customer created');
        setForm(emptyForm);
        setFormOpen(false);
      }
      await refresh();
    } catch (err: any) {
      setFieldErrors(fieldErrorsFromDetail(err.detail));
      setError(err.message || 'Save failed');
    } finally {
      setSaveBusy(false);
    }
  }

  async function setActive(c: Customer, isActive: boolean) {
    setError('');
    try {
      await api(`/customers/${c.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: isActive ? 'active' : 'inactive' }),
      });
      await refresh();
      setMessage(isActive ? `${c.name} activated` : `${c.name} deactivated`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function openAr(c: Customer) {
    setArCustomer(c);
    setArError('');
    setArBusy(true);
    setArCredit(null);
    setArStatement(null);
    setArHistory(null);
    try {
      const [creditRes, stmtRes, histRes] = await Promise.all([
        api(`/customers/${c.id}/credit`).catch((err: any) => ({ error: err.message })),
        api(`/credit/customers/${c.id}/statement`).catch((err: any) => ({ error: err.message })),
        api(`/customers/${c.id}/history`).catch((err: any) => ({ error: err.message })),
      ]);
      if ((creditRes as any).error && (stmtRes as any).error && (histRes as any).error) {
        setArError((creditRes as any).error);
      }
      setArCredit((creditRes as any).data ?? null);
      setArStatement((stmtRes as any).data ?? null);
      setArHistory((histRes as any).data ?? null);
    } finally {
      setArBusy(false);
    }
  }

  async function loadHistory(id: string, from = histFrom, to = histTo) {
    const qs = new URLSearchParams();
    if (from.trim()) qs.set('from_date', from.trim());
    if (to.trim()) qs.set('to_date', to.trim());
    const tail = qs.toString() ? `?${qs.toString()}` : '';
    const histRes = await api(`/customers/${id}/history${tail}`);
    setHistory(histRes.data || { payments: [], purchases: [], returns: [] });
  }

  async function openAccount(c: Customer, mode: 'pay' | 'history' = 'pay') {
    setArCustomer(null);
    setAccountId(c.id);
    setAccountName(c.name);
    setAccountMode(mode);
    setAccountBusy(true);
    setAccountError('');
    setCreditInfo(null);
    setHistory(null);
    setPayAmount('');
    setPayMethod('cash');
    setPayInvoiceId('');
    setPayReference('');
    setPayChequeNumber('');
    setLastPayment(null);
    setHistFrom('');
    setHistTo('');
    setPayDateNote(new Date().toISOString().slice(0, 10));
    try {
      const [creditRes] = await Promise.all([
        api(`/customers/${c.id}/credit`).catch(() => ({ data: null })),
        loadHistory(c.id, '', '').catch((err: any) => {
          setAccountError(err.message || 'Could not load history');
        }),
      ]);
      setCreditInfo(
        creditRes.data || {
          outstanding_balance: c.balance || 0,
          credit_limit: c.credit_limit || 0,
          credit_sales: [],
        }
      );
    } catch (err: any) {
      setAccountError(err.message || 'Could not load account');
    } finally {
      setAccountBusy(false);
    }
  }

  function closeAccount() {
    if (payBusy) return;
    setAccountId('');
  }

  async function applyHistoryFilter() {
    if (!accountId) return;
    setAccountError('');
    setAccountBusy(true);
    try {
      await loadHistory(accountId);
    } catch (err: any) {
      setAccountError(err.message || 'Could not load history');
    } finally {
      setAccountBusy(false);
    }
  }

  async function recordRepayment() {
    if (!accountId || payBusy) return;
    const amount = Math.round(Number(payAmount) * 100) / 100;
    if (!Number.isFinite(amount) || !(amount > 0)) {
      setAccountError('Enter an amount greater than zero');
      return;
    }
    const owed = Number(creditInfo?.outstanding_balance || 0);
    const invoice = (creditInfo?.credit_sales || []).find((inv: any) => inv.invoice_id === payInvoiceId);
    if (invoice && amount - Number(invoice.amount || 0) > 0.009) {
      setAccountError(`That is more than ${invoice.invoice_number} still owes (${money(invoice.amount)})`);
      return;
    }
    if (!invoice) {
      const openSales = creditInfo?.credit_sales || [];
      // With open invoices the payment is spread over them and cannot be more than they owe.
      const cap = openSales.length
        ? openSales.reduce((sum: number, inv: any) => sum + Number(inv.amount || 0), 0)
        : owed;
      if (!(cap > 0)) {
        setAccountError(`${accountName} owes nothing right now`);
        return;
      }
      if (amount - cap > 0.009) {
        setAccountError(`That is more than ${accountName} owes (${money(cap)})`);
        return;
      }
    }
    setPayBusy(true);
    setAccountError('');
    try {
      const today = new Date().toISOString().slice(0, 10);
      const day = payDateNote.trim();
      const notes = day && day !== today ? `Received ${day}` : null;
      const res = await api(`/customers/${accountId}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          customer_id: accountId,
          amount,
          payment_method: payMethod,
          sales_invoice_id: invoice ? invoice.invoice_id : null,
          reference: payReference.trim() || null,
          cheque_number: payMethod === 'cheque' ? payChequeNumber.trim() || null : null,
          notes,
        }),
      });
      const number = String(res?.data?.payment_number || '');
      setLastPayment(res?.data?.id ? { id: String(res.data.id), number } : null);
      setMessage(`Payment ${number ? `${number} ` : ''}of ${money(amount)} recorded for ${accountName}`);
      setPayAmount('');
      setPayInvoiceId('');
      setPayReference('');
      setPayChequeNumber('');
      const [creditRes] = await Promise.all([
        api(`/customers/${accountId}/credit`).catch(() => ({ data: null })),
        loadHistory(accountId).catch(() => undefined),
      ]);
      if (creditRes.data) setCreditInfo(creditRes.data);
      await refresh();
    } catch (err: any) {
      setAccountError(err.message || 'Payment failed');
    } finally {
      setPayBusy(false);
    }
  }

  function printPaymentReceipt(id: string) {
    openDocumentPrint(`/sales/payments/${id}/print?format=pdf`).catch((err: any) =>
      setAccountError(err.message || 'Could not open the receipt')
    );
  }

  function printStatement(id: string) {
    openDocumentPrint(`/credit/customers/${id}/statement/print?format=html`).catch((err: any) =>
      setAccountError(err.message || 'Could not open the statement')
    );
  }

  const showCodeCol = customers.some((c) => Boolean(c.code));

  return (
    <div className="card cat-panel">
      <PageHeader
        title="Customers"
        subtitle={
          hotelOps
            ? 'Customers on checkout invoices. Guest profiles stay on Guests and CRM.'
            : restaurantOps
              ? 'Customers on restaurant bills. Table orders stay on the restaurant desk until a bill is posted.'
              : 'Your customers, used on quotes, orders and invoices.'
        }
        actions={
          <>
            <button type="button" className="list-btn-secondary" onClick={() => setGroupsOpen(true)} aria-label="Open customer groups">
              Customer groups
            </button>
            <button type="button" className="list-btn-primary" onClick={openAdd} aria-label="Add customer">
              Add customer
            </button>
          </>
        }
      />
      {message ? (
        <p className="list-toast ok" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="list-toast err" role="alert">
          {error}
        </p>
      ) : null}
      <div className="list-toolbar">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, code, email, phone"
          aria-label="Search customers"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as 'all' | 'active' | 'inactive')}
          aria-label="Customer status filter"
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
        <select
          value={groupId}
          onChange={(e) => setGroupId(e.target.value)}
          aria-label="Customer group filter"
        >
          <option value="">All groups</option>
          {groups
            .filter((g) => g.is_active !== false)
            .map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
        </select>
        <select
          value={profileType}
          onChange={(e) => setProfileType(e.target.value as 'all' | 'registered' | 'walk_in')}
          aria-label="Customer profile type filter"
        >
          <option value="all">All types</option>
          <option value="registered">Registered</option>
          <option value="walk_in">{hotelOps ? 'Walk-in guest' : restaurantOps ? 'Walk-in diner' : 'Walk-in'}</option>
        </select>
      </div>
      {loading ? (
        <p className="muted">Loading customers…</p>
      ) : paged.total === 0 && !restaurantOps ? (
        <EmptyState
          title={customers.length === 0 ? 'No customers yet.' : 'No customers match these filters.'}
          detail={hotelOps
            ? 'Add a customer to use them on sales quotes, orders, and checkout invoices.'
            : 'Add a customer to use them on quotations, orders, and invoices.'}
          action={
            <button type="button" className="list-btn-primary" onClick={openAdd}>
              Add customer
            </button>
          }
        />
      ) : (
        <div className={restaurantOps ? 'list-table-wrap rest-cust-table' : 'list-table-wrap'}>
          <table className="table cat-table">
            {restaurantOps ? (
              <colgroup>
                <col style={{ width: '24%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '16%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '14%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('name')}>
                    {restaurantOps ? 'Customer' : 'Name'}
                  </button>
                </th>
                {!restaurantOps && showCodeCol ? (
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('code')}>
                    Code
                  </button>
                </th>
                ) : null}
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('status')}>
                    Status
                  </button>
                </th>
                {restaurantOps ? null : (
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('group')}>
                    Group
                  </button>
                </th>
                )}
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('email')}>
                    Email
                  </button>
                </th>
                <th>Phone</th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('balance')}>
                    Owes you
                  </button>
                </th>
                {restaurantOps ? null : <th className="col-num">Points</th>}
                <th className="col-actions">{restaurantOps ? 'Actions' : ''}</th>
              </tr>
            </thead>
            <tbody>
              {paged.rows.map((c) => (
                <tr key={c.id}>
                  <td data-label={restaurantOps ? 'Customer' : 'Name'}>
                    <strong>{c.name}</strong>
                    {c.profile_type === 'walk_in' ? <span className="muted"> {hotelOps ? '(walk-in guest)' : restaurantOps ? '(walk-in diner)' : '(walk-in)'}</span> : null}
                    {restaurantOps ? (
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {c.code || 'No code'}
                        {' · '}
                        {c.customer_group?.name || 'No group'}
                      </span>
                    ) : null}
                  </td>
                  {!restaurantOps && showCodeCol ? <td data-label="Code">{c.code || '—'}</td> : null}
                  <td data-label="Status">{c.status === 'inactive' ? 'Inactive' : 'Active'}</td>
                  {restaurantOps ? null : <td data-label="Group">{c.customer_group?.name || '—'}</td>}
                  <td data-label="Email">{c.email || '—'}</td>
                  <td data-label="Phone">{c.phone || '—'}</td>
                  <td className="col-num" data-label="Owes you">{formatMoney(Number(c.balance ?? 0), formatPrefs)}</td>
                  {restaurantOps ? null : <td className="col-num" data-label="Points">{Math.floor(Number(c.loyalty_points ?? 0)).toLocaleString()}</td>}
                  <td className="col-actions" data-label="Actions">
                    <RowActions
                      label={`More actions for ${c.name}`}
                      primaryMax={1}
                      items={
                        [
                          { key: 'edit', label: 'Edit', ariaLabel: `Edit ${c.name}`, onClick: () => openEdit(c) },
                          ...(canPay
                            ? [
                                {
                                  key: 'pay',
                                  label: 'Record payment',
                                  ariaLabel: `Record payment for ${c.name}`,
                                  onClick: () => openAccount(c, 'pay'),
                                },
                              ]
                            : []),
                          {
                            key: 'history',
                            label: 'History',
                            ariaLabel: `History for ${c.name}`,
                            onClick: () => openAccount(c, 'history'),
                          },
                          {
                            key: 'ar',
                            label: restaurantOps ? 'Unpaid bills' : 'Unpaid invoices',
                            ariaLabel: `AR for ${c.name}`,
                            onClick: () => openAr(c),
                          },
                          {
                            key: 'active',
                            label: c.status === 'inactive' ? 'Activate' : 'Deactivate',
                            variant: c.status === 'inactive' ? 'ok' : 'danger',
                            ariaLabel: c.status === 'inactive' ? `Activate ${c.name}` : `Deactivate ${c.name}`,
                            onClick: () => setActive(c, c.status === 'inactive'),
                          },
                        ] as RowActionItem[]
                      }
                    />
                  </td>
                </tr>
              ))}
              {restaurantOps && paged.rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    {customers.length === 0
                      ? 'No customers yet. Add a customer to use them on restaurant bills. Table orders stay on the restaurant desk.'
                      : 'No customers match these filters.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {!loading && paged.total > 0 ? (
        <div className="list-pager">
          <span className="muted">
            {paged.total} entries · page {paged.page} of {paged.pages}
          </span>
          <div className="list-pager-nav">
            <button
              type="button"
              disabled={paged.page <= 1}
              onClick={() => setPage(paged.page - 1)}
              aria-label="Previous customer page"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={paged.page >= paged.pages}
              onClick={() => setPage(paged.page + 1)}
              aria-label="Next customer page"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}

      {accountId ? (
        <FormModal
          title={`${accountMode === 'pay' ? 'Record payment' : 'History'} · ${accountName}`}
          busy={payBusy}
          dirty={accountMode === 'pay' && Boolean(payAmount.trim() || payReference.trim())}
          onClose={closeAccount}
        >
          <div className="stack" aria-label="Customer account">
            <div className="list-toolbar" role="tablist" aria-label="Customer account view">
              <button
                type="button"
                role="tab"
                aria-selected={accountMode === 'pay'}
                className={accountMode === 'pay' ? 'list-btn-primary' : 'list-btn-secondary'}
                onClick={() => setAccountMode('pay')}
                aria-label="Show record payment"
              >
                Record payment
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={accountMode === 'history'}
                className={accountMode === 'history' ? 'list-btn-primary' : 'list-btn-secondary'}
                onClick={() => setAccountMode('history')}
                aria-label="Show customer history"
              >
                History
              </button>
              <button
                type="button"
                className="list-btn-secondary"
                onClick={() => printStatement(accountId)}
                aria-label="Print customer statement"
              >
                Print statement
              </button>
            </div>
            {accountBusy ? <p className="muted">Loading account…</p> : null}
            {accountError ? (
              <p className="list-toast err" role="alert">
                {accountError}
              </p>
            ) : null}
            {creditInfo ? (
              <p>
                Owes you <strong>{money(creditInfo.outstanding_balance)}</strong>
                {Number(creditInfo.credit_limit || 0) > 0
                  ? ` · credit limit ${money(creditInfo.credit_limit)}`
                  : ' · no credit limit'}
                {creditInfo.open_invoice_count
                  ? ` · ${creditInfo.open_invoice_count} open ${restaurantOps ? 'bill' : 'invoice'}${creditInfo.open_invoice_count === 1 ? '' : 's'}`
                  : ''}
                {creditInfo.is_over_limit ? ' · over limit' : ''}
              </p>
            ) : null}

            {accountMode === 'pay' ? (
              canPay ? (
                <>
                  {lastPayment ? (
                    <p className="list-toast ok" role="status">
                      Payment {lastPayment.number} saved.{' '}
                      <button
                        type="button"
                        className="list-btn-secondary"
                        onClick={() => printPaymentReceipt(lastPayment.id)}
                        aria-label="Print payment receipt"
                      >
                        Print receipt
                      </button>
                    </p>
                  ) : null}
                  <div className="erp-form-grid">
                    <label className="field">
                      <span>Amount</span>
                      <AmountField
                        type="number"
                        min={0}
                        step="0.01"
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                        placeholder="Amount"
                        aria-label="Repayment amount"
                      />
                    </label>
                    <label className="field">
                      <span>Pay towards</span>
                      <select
                        value={payInvoiceId}
                        onChange={(e) => {
                          const id = e.target.value;
                          setPayInvoiceId(id);
                          const inv = (creditInfo?.credit_sales || []).find((x: any) => x.invoice_id === id);
                          if (inv) setPayAmount(String(Number(inv.amount || 0)));
                        }}
                        aria-label="Repayment applies to"
                      >
                        <option value="">Oldest {restaurantOps ? 'bills' : 'invoices'} first</option>
                        {(creditInfo?.credit_sales || []).map((inv: any) => (
                          <option key={inv.invoice_id} value={inv.invoice_id}>
                            {inv.invoice_number} · owes {money(inv.amount)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Method</span>
                      <select
                        value={payMethod}
                        onChange={(e) => setPayMethod(e.target.value)}
                        aria-label="Repayment method"
                      >
                        <option value="cash">Cash</option>
                        <option value="card">Card</option>
                        <option value="bank_transfer">Bank transfer</option>
                        <option value="cheque">Cheque</option>
                      </select>
                    </label>
                    {payMethod === 'cheque' ? (
                      <label className="field">
                        <span>Cheque number</span>
                        <input
                          value={payChequeNumber}
                          onChange={(e) => setPayChequeNumber(e.target.value)}
                          placeholder="Optional"
                          aria-label="Repayment cheque number"
                        />
                      </label>
                    ) : null}
                    <label className="field">
                      <span>Reference</span>
                      <input
                        value={payReference}
                        onChange={(e) => setPayReference(e.target.value)}
                        placeholder="Optional, e.g. transfer or MoMo ID"
                        aria-label="Repayment reference"
                      />
                    </label>
                    <label className="field">
                      <span>Date received</span>
                      <input
                        type="date"
                        value={payDateNote}
                        onChange={(e) => setPayDateNote(e.target.value)}
                        aria-label="Repayment date"
                      />
                    </label>
                  </div>
                  <div className="list-toolbar">
                    {Number(creditInfo?.outstanding_balance || 0) > 0 ? (
                      <button
                        type="button"
                        className="list-btn-secondary"
                        onClick={() => {
                          setPayInvoiceId('');
                          const openSales = creditInfo?.credit_sales || [];
                          const full = openSales.length
                            ? openSales.reduce((sum: number, inv: any) => sum + Number(inv.amount || 0), 0)
                            : Number(creditInfo.outstanding_balance || 0);
                          setPayAmount(String(Math.round(full * 100) / 100));
                        }}
                        aria-label="Fill full balance"
                      >
                        Full balance
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="list-btn-primary btn-ok"
                      onClick={recordRepayment}
                      disabled={payBusy || accountBusy}
                      aria-label="Record customer payment"
                    >
                      {payBusy ? 'Recording…' : 'Record payment'}
                    </button>
                  </div>
                  {(creditInfo?.credit_sales || []).length > 0 ? (
                    <div className="list-table-wrap">
                      <table className="table cat-table">
                        <thead>
                          <tr>
                            <th>Open {restaurantOps ? 'bill' : 'invoice'}</th>
                            <th>Due date</th>
                            <th className="col-num">Total</th>
                            <th className="col-num">Paid</th>
                            <th className="col-num">Still owed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {creditInfo.credit_sales.map((inv: any) => (
                            <tr key={inv.invoice_id}>
                              <td>{inv.invoice_number}</td>
                              <td>{inv.due_date ? formatDate(inv.due_date, formatPrefs) : '—'}</td>
                              <td className="col-num">{money(inv.total_amount)}</td>
                              <td className="col-num">{money(inv.paid_amount)}</td>
                              <td className="col-num">{money(inv.amount)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : creditInfo && !accountBusy ? (
                    <p className="muted">No open {restaurantOps ? 'bills' : 'invoices'}. Payments go against the balance owed from till credit sales.</p>
                  ) : null}
                </>
              ) : (
                <p className="muted">Recording payments needs credit write permission.</p>
              )
            ) : (
              <>
                <div className="list-toolbar" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <label className="field">
                    <span>From</span>
                    <input
                      type="date"
                      value={histFrom}
                      onChange={(e) => setHistFrom(e.target.value)}
                      aria-label="Customer history from date"
                    />
                  </label>
                  <label className="field">
                    <span>To</span>
                    <input
                      type="date"
                      value={histTo}
                      onChange={(e) => setHistTo(e.target.value)}
                      aria-label="Customer history to date"
                    />
                  </label>
                  <button
                    type="button"
                    className="list-btn-secondary"
                    onClick={applyHistoryFilter}
                    disabled={accountBusy}
                    aria-label="Apply customer history dates"
                  >
                    Show
                  </button>
                </div>
                {history?.summary ? (
                  <p className="muted">
                    {history.summary.purchase_count ?? (history.purchases || []).length} sales · bought{' '}
                    {money(history.summary.purchase_total)} · paid {money(history.summary.payment_total)}
                    {Number(history.summary.return_total || 0) > 0 ? ` · returned ${money(history.summary.return_total)}` : ''}
                  </p>
                ) : null}
                <h3 style={{ margin: '8px 0 0', fontSize: 15 }}>Sales</h3>
                {(history?.purchases || []).length > 0 ? (
                  <div className="list-table-wrap">
                    <table className="table cat-table">
                      <thead>
                        <tr>
                          <th>Sale</th>
                          <th>Date</th>
                          <th>Status</th>
                          <th className="col-num">Total</th>
                          <th className="col-num">Paid</th>
                          <th className="col-num">Still owed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.purchases.map((row: any) => (
                          <tr key={`${row.type}-${row.id}`}>
                            <td>
                              {row.reference || '—'}
                              <span className="list-secondary" style={{ display: 'block' }}>
                                {row.type === 'pos' ? 'Till sale' : restaurantOps ? 'Bill' : 'Invoice'}
                              </span>
                            </td>
                            <td>{row.posted_at || row.created_at ? formatDate(row.posted_at || row.created_at, formatPrefs) : '—'}</td>
                            <td>{String(row.status || '').replace(/_/g, ' ') || '—'}</td>
                            <td className="col-num">{money(row.total_amount)}</td>
                            <td className="col-num">{money(row.paid_amount)}</td>
                            <td className="col-num">{moneyOrBlank(row.balance_due) || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : !accountBusy ? (
                  <p className="muted">No sales in this period.</p>
                ) : null}
                <h3 style={{ margin: '8px 0 0', fontSize: 15 }}>Payments</h3>
                {(history?.payments || []).length > 0 ? (
                  <div className="list-table-wrap">
                    <table className="table cat-table">
                      <thead>
                        <tr>
                          <th>Payment</th>
                          <th>Date</th>
                          <th>Method</th>
                          <th>Reference</th>
                          <th className="col-num">Amount</th>
                          <th className="col-actions">Receipt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.payments.map((p: any) => (
                          <tr key={p.id}>
                            <td>{p.payment_number}</td>
                            <td>{p.created_at ? formatDate(p.created_at, formatPrefs) : '—'}</td>
                            <td>{String(p.payment_method || '').replace(/_/g, ' ')}</td>
                            <td>{p.reference || '—'}</td>
                            <td className="col-num">{money(p.amount)}</td>
                            <td className="col-actions">
                              <button
                                type="button"
                                className="list-btn-secondary"
                                onClick={() => printPaymentReceipt(p.id)}
                                aria-label={`Print receipt ${p.payment_number}`}
                              >
                                Print
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : !accountBusy ? (
                  <p className="muted">No payments in this period.</p>
                ) : null}
                {(history?.returns || []).length > 0 ? (
                  <>
                    <h3 style={{ margin: '8px 0 0', fontSize: 15 }}>Returns</h3>
                    <div className="list-table-wrap">
                      <table className="table cat-table">
                        <thead>
                          <tr>
                            <th>Return</th>
                            <th>Date</th>
                            <th>Status</th>
                            <th>Reason</th>
                            <th className="col-num">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history.returns.map((r: any) => (
                            <tr key={r.id}>
                              <td>{r.return_number || r.credit_note_number || '—'}</td>
                              <td>{r.posted_at || r.created_at ? formatDate(r.posted_at || r.created_at, formatPrefs) : '—'}</td>
                              <td>{String(r.status || '').replace(/_/g, ' ')}</td>
                              <td>{String(r.reason || '').replace(/_/g, ' ') || '—'}</td>
                              <td className="col-num">{money(r.total_amount)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
              </>
            )}
          </div>
        </FormModal>
      ) : null}

      {groupsOpen ? (
        <CustomerGroupsWindow
          groups={groups}
          customers={customers}
          onClose={() => setGroupsOpen(false)}
          onChanged={refresh}
        />
      ) : null}

      {formOpen ? (
        <FormModal
          title={editingId ? 'Edit customer' : 'Add customer'}
          busy={saveBusy}
          dirty={Boolean(
            form.name.trim() ||
              form.code.trim() ||
              form.email.trim() ||
              form.phone.trim() ||
              form.address.trim(),
          )}
          onClose={() => setFormOpen(false)}
        >
          <div className="erp-form-grid">
            <label className="field">
              <span>Name</span>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Customer name"
                aria-label="Customer name"
                aria-invalid={Boolean(fieldErrors.name)}
              />
            </label>
            {fieldErrors.name ? (
              <p className="list-toast err" role="alert">
                {fieldErrors.name}
              </p>
            ) : null}
            <label className="field">
              <span>Phone</span>
              <input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="e.g. +233 24 123 4567"
                aria-label="Customer phone"
              />
            </label>
            <label className="field">
              <span>Email</span>
              <input
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Optional"
                aria-label="Customer email"
              />
            </label>
            <label className="field">
              <span>Address</span>
              <input
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="Optional"
                aria-label="Customer address"
              />
            </label>
            <label className="field">
              <span>Customer group</span>
              <select
                value={form.groupId}
                onChange={(e) => setForm({ ...form, groupId: e.target.value })}
                aria-label="Customer group"
                aria-invalid={Boolean(fieldErrors.customer_group || fieldErrors.customer_group_id)}
              >
                <option value="">No group (normal prices)</option>
                {groups
                  .filter((g) => g.is_active !== false || g.id === form.groupId)
                  .map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name} · {Number(g.discount_percent || 0)}% off
                    </option>
                  ))}
              </select>
            </label>
            {fieldErrors.customer_group || fieldErrors.customer_group_id ? (
              <p className="list-toast err" role="alert">
                {fieldErrors.customer_group || fieldErrors.customer_group_id}
              </p>
            ) : null}
            {fieldErrors.company ? (
              <p className="list-toast err" role="alert">
                {fieldErrors.company}
              </p>
            ) : null}
            <label className="field">
              <span>Credit limit</span>
              <input
                value={form.creditLimit}
                onChange={(e) => setForm({ ...form, creditLimit: e.target.value })}
                placeholder="0 = cash only"
                aria-label="Customer credit limit"
              />
            </label>
            <label className="field">
              <span>Payment terms (days)</span>
              <input
                value={form.paymentTermsDays}
                onChange={(e) => setForm({ ...form, paymentTermsDays: e.target.value })}
                placeholder="e.g. 30"
                aria-label="Customer payment terms days"
              />
            </label>
            <details className="span-2">
              <summary>More details</summary>
              <div className="erp-form-grid" style={{ marginTop: 8 }}>
                <label className="field">
                  <span>Code</span>
                  <input
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    placeholder="Optional"
                    aria-label="Customer code"
                  />
                </label>
                <label className="field">
                  <span>Type</span>
                  <select
                    value={form.profileType}
                    onChange={(e) => setForm({ ...form, profileType: e.target.value })}
                    aria-label="Customer profile type"
                  >
                    <option value="registered">Registered</option>
                    <option value="walk_in">{hotelOps ? 'Walk-in guest' : restaurantOps ? 'Walk-in diner' : 'Walk-in'}</option>
                  </select>
                </label>
                <label className="field">
                  <span>Category</span>
                  <input
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    placeholder="Optional"
                    aria-label="Customer category"
                  />
                </label>
                <label className="field">
                  <span>Status</span>
                  <select
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                    aria-label="Customer status"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </label>
                <label className="field">
                  <span>Map latitude</span>
                  <input
                    value={form.lat}
                    onChange={(e) => setForm({ ...form, lat: e.target.value })}
                    placeholder="Optional"
                    aria-label="Customer latitude"
                  />
                </label>
                <label className="field">
                  <span>Map longitude</span>
                  <input
                    value={form.lng}
                    onChange={(e) => setForm({ ...form, lng: e.target.value })}
                    placeholder="Optional"
                    aria-label="Customer longitude"
                  />
                </label>
              </div>
            </details>
            <button type="button" className="list-btn-primary" onClick={save} disabled={saveBusy}>
              {saveBusy ? 'Saving…' : editingId ? 'Save customer' : 'Add customer'}
            </button>
          </div>
          {editingId ? (
            <div style={{ marginTop: 16 }}>
              <PartyContactsPanel
                kind="customer"
                partyId={editingId}
                partyLabel={form.name || 'Customer'}
              />
            </div>
          ) : null}
        </FormModal>
      ) : null}
      {arCustomer ? (
        <FormModal
          title={`${restaurantOps ? 'Unpaid bills' : 'Unpaid invoices'} · ${arCustomer.name}`}
          onClose={() => setArCustomer(null)}
        >
          <div className="stack">
            {arBusy ? <p className="muted">Loading ledger…</p> : null}
            {arError ? (
              <p className="list-toast err" role="alert">
                {arError}
              </p>
            ) : null}
            {arCredit ? (
              <p>
                Owes you <strong>{money(arCredit.outstanding_balance ?? arCustomer.balance ?? 0)}</strong>
                {arCredit.credit_limit != null && Number(arCredit.credit_limit) > 0
                  ? ` · credit limit ${money(arCredit.credit_limit)}`
                  : ''}
                {overdueTotal(arCredit) > 0 ? ` · overdue ${money(overdueTotal(arCredit))}` : ''}
              </p>
            ) : null}
            <div className="list-toolbar">
              {canPay ? (
                <button
                  type="button"
                  className="list-btn-primary"
                  onClick={() => openAccount(arCustomer, 'pay')}
                  aria-label={`Record payment for ${arCustomer.name} from unpaid list`}
                >
                  Record payment
                </button>
              ) : null}
              <button
                type="button"
                className="list-btn-secondary"
                onClick={() => openAccount(arCustomer, 'history')}
                aria-label={`History for ${arCustomer.name} from unpaid list`}
              >
                History
              </button>
              <button
                type="button"
                className="list-btn-secondary"
                onClick={() => printStatement(arCustomer.id)}
                aria-label={`Print statement for ${arCustomer.name}`}
              >
                Print statement
              </button>
            </div>
            {arStatement?.lines?.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Document</th>
                    <th className="col-num">Charged</th>
                    <th className="col-num">Paid</th>
                    <th className="col-num">Owes after</th>
                  </tr>
                </thead>
                <tbody>
                  {withRunningBalance(arStatement.lines).map(({ line, after }, idx: number) => (
                    <tr key={line.id || `${line.reference}-${idx}`}>
                      <td>{line.date ? formatDate(line.date, formatPrefs) : '—'}</td>
                      <td>{line.document_number || line.reference || line.description || line.type || '—'}</td>
                      <td className="col-num">{moneyOrBlank(line.debit ?? line.amount_debit)}</td>
                      <td className="col-num">{moneyOrBlank(line.credit ?? line.amount_credit)}</td>
                      <td className="col-num">{money(after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : !arBusy ? (
              <p className="muted">Nothing charged or paid yet.</p>
            ) : null}
            {arHistory?.summary || arHistory?.purchases?.length || arHistory?.payments?.length ? (
              <p className="muted">
                {(arHistory.summary?.purchase_count ?? (arHistory.purchases || []).length)} {restaurantOps ? 'bills' : 'invoices'} ·{' '}
                {(arHistory.summary?.payment_count ?? (arHistory.payments || []).length)} payments
              </p>
            ) : null}
          </div>
        </FormModal>
      ) : null}
    </div>
  );
}
