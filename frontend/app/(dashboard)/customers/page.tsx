'use client';

import { useEffect, useMemo, useState } from 'react';
import FormModal from '../../../components/FormModal';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import { api } from '../../../lib/api';
import { currencySign } from '../../../lib/format';
import { AmountField } from '../../../components/AmountField';
import { getMe } from '../../../lib/meCache';
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
  const [accountBusy, setAccountBusy] = useState(false);
  const [creditInfo, setCreditInfo] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [payDateNote, setPayDateNote] = useState('');
  const [payBusy, setPayBusy] = useState(false);
  const [canPay, setCanPay] = useState(false);

  async function refresh() {
    setError('');
    const path = status === 'all' ? '/customers' : `/customers?status=${status}`;
    const [custRes, groupRes] = await Promise.all([
      api(path),
      api('/customers/groups').catch(() => ({ data: [] })),
    ]);
    setCustomers(custRes.data || []);
    setGroups(groupRes.data || []);
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
      .then((me) => setCanPay(canWriteCredit(me.data)))
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
        setMessage('Customer updated');
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

  async function openAccount(c: Customer) {
    setAccountId(c.id);
    setAccountName(c.name);
    setAccountBusy(true);
    setCreditInfo(null);
    setHistory(null);
    setPayAmount('');
    setPayDateNote(new Date().toISOString().slice(0, 10));
    setError('');
    try {
      const [creditRes, histRes] = await Promise.all([
        api(`/customers/${c.id}/credit`).catch(() => ({ data: null })),
        api(`/customers/${c.id}/history`).catch(() => ({ data: null })),
      ]);
      setCreditInfo(creditRes.data || {
        outstanding_balance: c.balance || 0,
        credit_limit: c.credit_limit || 0,
        credit_sales: [],
      });
      setHistory(histRes.data || { payments: [], purchases: [] });
    } catch (err: any) {
      setError(err.message || 'Could not load account');
    } finally {
      setAccountBusy(false);
    }
  }

  async function recordRepayment() {
    if (!accountId || payBusy) return;
    const amount = Number(payAmount);
    if (!(amount > 0)) {
      setError('Enter an amount greater than zero');
      return;
    }
    setPayBusy(true);
    setError('');
    try {
      const notes = payDateNote.trim() ? `Received ${payDateNote.trim()}` : null;
      await api(`/customers/${accountId}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          customer_id: accountId,
          amount,
          payment_method: payMethod,
          notes,
        }),
      });
      setMessage('Payment recorded against customer balance');
      setPayAmount('');
      const current = customers.find((row) => row.id === accountId);
      if (current) await openAccount(current);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Payment failed');
    } finally {
      setPayBusy(false);
    }
  }

  return (
    <div className="card cat-panel">
      <div className="list-page-head">
        <div>
          <h1 style={{ margin: 0 }}>Customers</h1>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Tenant customer master for this company. Used on sales documents — not hotel guest CRM.
          </p>
        </div>
        <div className="list-head-actions">
          <button type="button" className="list-btn-primary" onClick={openAdd} aria-label="Add customer">
            Add customer
          </button>
        </div>
      </div>
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
          <option value="walk_in">Walk-in</option>
        </select>
      </div>
      {loading ? (
        <p className="muted">Loading customers…</p>
      ) : paged.total === 0 ? (
        <div className="list-empty">
          <p style={{ margin: 0 }}>
            {customers.length === 0 ? 'No customers yet.' : 'No customers match these filters.'}
          </p>
          <p className="muted" style={{ margin: '8px 0 0' }}>
            Add a customer to use them on quotations, orders, and invoices.
          </p>
          <button type="button" className="list-btn-primary" style={{ marginTop: 12 }} onClick={openAdd}>
            Add customer
          </button>
        </div>
      ) : (
        <div className="list-table-wrap">
          <table className="table cat-table">
            <thead>
              <tr>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('name')}>
                    Name
                  </button>
                </th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('code')}>
                    Code
                  </button>
                </th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('status')}>
                    Status
                  </button>
                </th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('group')}>
                    Group
                  </button>
                </th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('email')}>
                    Email
                  </button>
                </th>
                <th>Phone</th>
                <th>
                  <button type="button" className="list-sort" onClick={() => toggleSort('balance')}>
                    Balance
                  </button>
                </th>
                <th>Loyalty</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {paged.rows.map((c) => (
                <tr key={c.id}>
                  <td data-label="Name">
                    <strong>{c.name}</strong>
                    {c.profile_type === 'walk_in' ? <span className="muted"> (walk-in)</span> : null}
                  </td>
                  <td data-label="Code">{c.code || '—'}</td>
                  <td data-label="Status">{c.status === 'inactive' ? 'Inactive' : 'Active'}</td>
                  <td data-label="Group">{c.customer_group?.name || '—'}</td>
                  <td data-label="Email">{c.email || '—'}</td>
                  <td data-label="Phone">{c.phone || '—'}</td>
                  <td data-label="Balance">{c.balance ?? 0}</td>
                  <td data-label="Loyalty">{c.loyalty_points ?? 0}</td>
                  <td className="cat-actions">
                    <button type="button" onClick={() => openEdit(c)} aria-label={`Edit ${c.name}`}>
                      Edit
                    </button>
                    <button type="button" onClick={() => openAr(c)} aria-label={`AR for ${c.name}`}>
                      AR
                    </button>
                    <button
                      type="button"
                      onClick={() => openAccount(c)}
                      aria-label={`Account for ${c.name}`}
                    >
                      Account
                    </button>
                    <button
                      type="button"
                      onClick={() => setActive(c, c.status === 'inactive')}
                      aria-label={
                        c.status === 'inactive' ? `Activate ${c.name}` : `Deactivate ${c.name}`
                      }
                    >
                      {c.status === 'inactive' ? 'Activate' : 'Deactivate'}
                    </button>
                  </td>
                </tr>
              ))}
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
        <div className="card" style={{ marginTop: 16 }} aria-label="Customer account">
          <div className="list-page-head">
            <div>
              <h2 style={{ margin: 0 }}>Account · {accountName}</h2>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                Outstanding balance and payments on the AR ledger (invoices + customer payments).
              </p>
            </div>
            <button type="button" onClick={() => setAccountId('')} aria-label="Close customer account">
              Close
            </button>
          </div>
          {accountBusy ? <p className="muted">Loading account…</p> : null}
          {creditInfo ? (
            <p>
              Outstanding <strong>{money(Number(creditInfo.outstanding_balance || 0))}</strong>
              {Number(creditInfo.credit_limit || 0) > 0
                ? ` · limit ${money(Number(creditInfo.credit_limit))}`
                : ' · no credit limit'}
              {creditInfo.open_invoice_count
                ? ` · ${creditInfo.open_invoice_count} open invoice(s)`
                : ''}
            </p>
          ) : null}
          {canPay ? (
            <div className="list-toolbar" style={{ flexWrap: 'wrap' }}>
              <AmountField
                inline
                type="number"
                min={0}
                step="0.01"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                placeholder="Amount"
                aria-label="Repayment amount"
              />
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
              <input
                type="date"
                value={payDateNote}
                onChange={(e) => setPayDateNote(e.target.value)}
                aria-label="Repayment date"
              />
              <button type="button" onClick={recordRepayment} disabled={payBusy}>
                {payBusy ? 'Recording…' : 'Record payment'}
              </button>
            </div>
          ) : (
            <p className="muted">Recording repayments needs credit write permission.</p>
          )}
          {(creditInfo?.credit_sales || []).length > 0 ? (
            <div className="list-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Open invoice</th>
                    <th>Status</th>
                    <th>Total</th>
                    <th>Paid</th>
                    <th>Due</th>
                  </tr>
                </thead>
                <tbody>
                  {creditInfo.credit_sales.map((inv: any) => (
                    <tr key={inv.invoice_id}>
                      <td>{inv.invoice_number}</td>
                      <td>{inv.status}</td>
                      <td>{money(Number(inv.total_amount || 0))}</td>
                      <td>{money(Number(inv.paid_amount || 0))}</td>
                      <td>{money(Number(inv.amount || 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {(history?.payments || []).length > 0 ? (
            <div className="list-table-wrap" style={{ marginTop: 12 }}>
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Payment</th>
                    <th>Date</th>
                    <th>Method</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {history.payments.map((p: any) => (
                    <tr key={p.id}>
                      <td>{p.payment_number}</td>
                      <td>
                        {p.created_at ? String(p.created_at).replace('T', ' ').slice(0, 16) : '—'}
                      </td>
                      <td>{String(p.payment_method || '').replace(/_/g, ' ')}</td>
                      <td>{money(Number(p.amount || 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : !accountBusy ? (
            <p className="muted">No payment history yet.</p>
          ) : null}
        </div>
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
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Name"
              aria-label="Customer name"
              aria-invalid={Boolean(fieldErrors.name)}
            />
            {fieldErrors.name ? (
              <p className="list-toast err" role="alert">
                {fieldErrors.name}
              </p>
            ) : null}
            <input
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="Code"
              aria-label="Customer code"
            />
            <select
              value={form.profileType}
              onChange={(e) => setForm({ ...form, profileType: e.target.value })}
              aria-label="Customer profile type"
            >
              <option value="registered">Registered</option>
              <option value="walk_in">Walk-in</option>
            </select>
            <input
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              placeholder="Category"
              aria-label="Customer category"
            />
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              aria-label="Customer status"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <input
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="Email"
              aria-label="Customer email"
            />
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="Phone (E.164)"
              aria-label="Customer phone"
            />
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="Address"
              aria-label="Customer address"
            />
            <select
              value={form.groupId}
              onChange={(e) => setForm({ ...form, groupId: e.target.value })}
              aria-label="Customer group"
              aria-invalid={Boolean(fieldErrors.customer_group || fieldErrors.customer_group_id)}
            >
              <option value="">Customer group (optional)</option>
              {groups
                .filter((g) => g.is_active !== false || g.id === form.groupId)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
            </select>
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
            <input
              value={form.creditLimit}
              onChange={(e) => setForm({ ...form, creditLimit: e.target.value })}
              placeholder="Credit limit"
              aria-label="Customer credit limit"
            />
            <input
              value={form.paymentTermsDays}
              onChange={(e) => setForm({ ...form, paymentTermsDays: e.target.value })}
              placeholder="Net days"
              aria-label="Customer payment terms days"
            />
            <input
              value={form.lat}
              onChange={(e) => setForm({ ...form, lat: e.target.value })}
              placeholder="Latitude"
              aria-label="Customer latitude"
            />
            <input
              value={form.lng}
              onChange={(e) => setForm({ ...form, lng: e.target.value })}
              placeholder="Longitude"
              aria-label="Customer longitude"
            />
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
          title={`AR · ${arCustomer.name}`}
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
                Balance {arCredit.balance ?? arCustomer.balance ?? 0}
                {arCredit.credit_limit != null ? ` · limit ${arCredit.credit_limit}` : ''}
                {arCredit.overdue_amount != null ? ` · overdue ${arCredit.overdue_amount}` : ''}
              </p>
            ) : null}
            {arStatement?.lines?.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Doc</th>
                    <th>Debit</th>
                    <th>Credit</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {arStatement.lines.map((line: any, idx: number) => (
                    <tr key={line.id || idx}>
                      <td>
                        {line.date
                          ? String(line.date).replace('T', ' ').slice(0, 16)
                          : '—'}
                      </td>
                      <td>{line.document_number || line.reference || line.description || line.type || '—'}</td>
                      <td>{line.debit ?? line.amount_debit ?? ''}</td>
                      <td>{line.credit ?? line.amount_credit ?? ''}</td>
                      <td>{line.balance ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : !arBusy ? (
              <p className="muted">No statement lines.</p>
            ) : null}
            {arHistory?.summary || arHistory?.purchases?.length || arHistory?.payments?.length ? (
              <p className="muted">
                {(arHistory.summary?.purchase_count ?? (arHistory.purchases || []).length)} invoices ·{' '}
                {(arHistory.summary?.payment_count ?? (arHistory.payments || []).length)} payments
              </p>
            ) : null}
          </div>
        </FormModal>
      ) : null}
    </div>
  );
}
