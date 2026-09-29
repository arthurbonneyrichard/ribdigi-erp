'use client';

import { useEffect, useMemo, useState } from 'react';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import { api } from '../../../lib/api';
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
  customer_group_id?: string | null;
  customer_group?: { id: string; name: string } | null;
  latitude?: number | null;
  longitude?: number | null;
};

type Group = { id: string; name: string; discount_percent?: number; is_active?: boolean };

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
    setError('');
    setMessage('');
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
      }
      await refresh();
    } catch (err: any) {
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
                  <td className="cat-actions">
                    <button type="button" onClick={() => openEdit(c)} aria-label={`Edit ${c.name}`}>
                      Edit
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

      {formOpen ? (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="cat-head">
            <h2>{editingId ? 'Edit customer' : 'Add customer'}</h2>
            <button type="button" onClick={() => setFormOpen(false)} disabled={saveBusy}>
              Close
            </button>
          </div>
          <div className="erp-form-grid">
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Name"
              aria-label="Customer name"
            />
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
            >
              <option value="">Group (optional)</option>
              {groups
                .filter((g) => g.is_active !== false || g.id === form.groupId)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
            </select>
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
        </div>
      ) : null}
    </div>
  );
}
