'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api, authHeaders } from '../../lib/api';
import {
  getSelectedStoreId,
  setSelectedStoreId,
  subscribeStoreContext,
} from '../../lib/storeContext';
import { getCompanyId } from '../../lib/workspaceContext';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Store = {
  id: string;
  code: string;
  name: string;
  address?: string;
  phone?: string | null;
  manager_id?: string | null;
  branch_id?: string | null;
  warehouse_id?: string | null;
  warehouse_code?: string | null;
  warehouse_name?: string | null;
  operating_hours?: Record<string, string> | null;
  is_active?: boolean;
  drawer_mode?: string;
  drawer_host?: string | null;
  drawer_port?: number;
  drawer_open_on_cash?: boolean;
};
type Product = { id: string; name: string; sku: string; stock_qty: number };
type Transfer = {
  id: string;
  transfer_number: string;
  from_store_id: string;
  to_store_id: string;
  from_store_manager_id?: string | null;
  to_store_manager_id?: string | null;
  status: string;
  items: { product_id: string; quantity: number }[];
};

type Me = { id: string; role?: string };

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
const WEEKDAY_LABELS: Record<(typeof WEEKDAYS)[number], string> = {
  mon: 'Mon',
  tue: 'Tue',
  wed: 'Wed',
  thu: 'Thu',
  fri: 'Fri',
  sat: 'Sat',
  sun: 'Sun',
};

function emptyHours(): Record<(typeof WEEKDAYS)[number], string> {
  return { mon: '', tue: '', wed: '', thu: '', fri: '', sat: '', sun: '' };
}

function hoursFromStore(hours?: Record<string, string> | null) {
  const next = emptyHours();
  if (!hours) return next;
  for (const day of WEEKDAYS) {
    if (hours[day]) next[day] = hours[day];
  }
  return next;
}

function hoursPayload(hours: Record<(typeof WEEKDAYS)[number], string>, note: string) {
  const out: Record<string, string> = {};
  for (const day of WEEKDAYS) {
    const v = (hours[day] || '').trim();
    if (v) out[day] = v;
  }
  if (note.trim()) out.note = note.trim();
  return out;
}

export default function Page() {
  const [stores, setStores] = useState<Store[]>([]);
  const [storeEntitlement, setStoreEntitlement] = useState<{
    used: number;
    store_limit: number;
    remaining: number | null;
    can_create_store?: boolean;
  } | null>(null);
  const [branches, setBranches] = useState<{ id: string; code: string; name: string }[]>([]);
  const [users, setUsers] = useState<{ id: string; full_name?: string; email?: string }[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const [salesStore, setSalesStore] = useState('');
  const [storeSales, setStoreSales] = useState<{
    summary?: Record<string, number>;
    recent?: { source: string; number: string; total: number; tax: number; status: string; occurred_at?: string }[];
  } | null>(null);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [managerId, setManagerId] = useState('');
  const [hoursNote, setHoursNote] = useState('');
  const [createHours, setCreateHours] = useState(emptyHours());
  const [branchId, setBranchId] = useState('');
  const [editStoreId, setEditStoreId] = useState('');
  const [editName, setEditName] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editManagerId, setEditManagerId] = useState('');
  const [editBranchId, setEditBranchId] = useState('');
  const [editActive, setEditActive] = useState(true);
  const [editHoursNote, setEditHoursNote] = useState('');
  const [editHours, setEditHours] = useState(emptyHours());
  const [fromStore, setFromStore] = useState('');
  const [toStore, setToStore] = useState('');
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('1');
  const [viewStore, setViewStore] = useState('');
  const [reorderProductId, setReorderProductId] = useState('');
  const [reorderLevel, setReorderLevel] = useState('5');
  const [reorderQty, setReorderQty] = useState('20');
  const [fefoStrict, setFefoStrict] = useState(false);
  const [drawerStoreId, setDrawerStoreId] = useState('');
  const [drawerMode, setDrawerMode] = useState('mock');
  const [drawerHost, setDrawerHost] = useState('');
  const [drawerPort, setDrawerPort] = useState('9100');
  const [drawerOnCash, setDrawerOnCash] = useState(true);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [whCode, setWhCode] = useState('');
  const [whName, setWhName] = useState('');
  const [whType, setWhType] = useState('retail');
  const [whStoreId, setWhStoreId] = useState('');
  const [whManagerId, setWhManagerId] = useState('');
  const [whAddress, setWhAddress] = useState('');
  const [whCapacity, setWhCapacity] = useState('');
  const [editWhId, setEditWhId] = useState('');
  const [editWhName, setEditWhName] = useState('');
  const [editWhType, setEditWhType] = useState('retail');
  const [editWhManagerId, setEditWhManagerId] = useState('');
  const [editWhAddress, setEditWhAddress] = useState('');
  const [editWhCapacity, setEditWhCapacity] = useState('');
  const [editWhActive, setEditWhActive] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [me, setMe] = useState<Me | null>(null);
  // Stage 121 S1 / W1 — store_active / warehouse_active → GET ?is_active=
  const [storeActiveFilter, setStoreActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('store_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  const [warehouseActiveFilter, setWarehouseActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('warehouse_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 135 T1 — transfer_status → GET /stores/transfers?status=
  const [transferStatusFilter, setTransferStatusFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('transfer_status') || '')
      .trim()
      .toLowerCase();
    return ['draft', 'requested', 'in_transit', 'received', 'cancelled'].includes(v) ? v : '';
  });

  async function refresh(opts?: {
    storeActive?: string;
    warehouseActive?: string;
    transferStatus?: string;
  }) {
    const storeActive =
      opts?.storeActive !== undefined ? opts.storeActive : storeActiveFilter;
    const warehouseActive =
      opts?.warehouseActive !== undefined ? opts.warehouseActive : warehouseActiveFilter;
    const transferStatus =
      opts?.transferStatus !== undefined ? opts.transferStatus : transferStatusFilter;
    const storeQs =
      storeActive === 'true'
        ? '?is_active=true'
        : storeActive === 'false'
          ? '?is_active=false'
          : '';
    const warehouseQs =
      warehouseActive === 'true'
        ? '?is_active=true'
        : warehouseActive === 'false'
          ? '?is_active=false'
          : '';
    const transferQs = transferStatus
      ? `?status=${encodeURIComponent(transferStatus)}`
      : '';
    const companyId = getCompanyId();
    const [s, p, t, settings, b, u, w, meRes, ent] = await Promise.all([
      api(`/stores${storeQs}`),
      api('/products'),
      api(`/stores/transfers${transferQs}`),
      api('/inventory/settings').catch(() => ({ data: { fefo_strict_warehouse: false } })),
      api('/branches').catch(() => ({ data: [] })),
      api('/users').catch(() => ({ data: [] })),
      api(`/warehouses${warehouseQs}`).catch(() => ({ data: [] })),
      api('/me').catch(() => ({ data: null })),
      companyId
        ? api(`/companies/${companyId}/store-entitlement`).catch(() => ({ data: null }))
        : Promise.resolve({ data: null }),
    ]);
    setStores(s.data || []);
    setStoreEntitlement(ent.data || null);
    setProducts(p.data || []);
    setTransfers(t.data || []);
    setBranches(b.data || []);
    setUsers(u.data || []);
    setWarehouses(w.data || []);
    setMe(meRes.data || null);
    setFefoStrict(!!settings.data?.fefo_strict_warehouse);
    if (!fromStore && s.data?.length) setFromStore(s.data[0].id);
    if (!toStore && s.data?.length > 1) setToStore(s.data[1].id);
    if (!productId && p.data?.length) setProductId(p.data[0].id);
    if (!reorderProductId && p.data?.length) setReorderProductId(p.data[0].id);
    if (!drawerStoreId && s.data?.length) {
      setDrawerStoreId(s.data[0].id);
      setDrawerMode(s.data[0].drawer_mode || 'none');
      setDrawerHost(s.data[0].drawer_host || '');
      setDrawerPort(String(s.data[0].drawer_port || 9100));
      setDrawerOnCash(s.data[0].drawer_open_on_cash !== false);
    }
  }

  async function downloadCsv(path: string, filename: string) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`${filename} export failed`);
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

  function writeStoresQuery(patch: Record<string, string | null>) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    for (const [key, value] of Object.entries(patch)) {
      if (!value) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    }
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`);
  }

  useEffect(() => {
    refresh()
      .then(() => {
        const storeId = new URLSearchParams(window.location.search).get('store_id')?.trim() || '';
        if (storeId) return loadInventory(storeId, { skipUrl: true });
      })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stage 102 T1 / Stage 105 S1 / Stage 112 S1 — honor Shell #transfers / #warehouses / #fefo / #reorder / #cash-drawer
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

  async function createStore() {
    setError('');
    try {
      await api('/stores', {
        method: 'POST',
        body: JSON.stringify({
          code,
          name,
          address: address || undefined,
          phone: phone || undefined,
          manager_id: managerId || null,
          branch_id: branchId || null,
          operating_hours: hoursPayload(createHours, hoursNote),
        }),
      });
      setCode('');
      setName('');
      setAddress('');
      setPhone('');
      setManagerId('');
      setHoursNote('');
      setCreateHours(emptyHours());
      setBranchId('');
      setMessage('Store created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveStoreDetails() {
    if (!editStoreId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${editStoreId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editName || undefined,
          address: editAddress || null,
          phone: editPhone || null,
          manager_id: editManagerId || null,
          clear_manager: !editManagerId,
          branch_id: editBranchId || null,
          clear_branch: !editBranchId,
          is_active: editActive,
          operating_hours: hoursPayload(editHours, editHoursNote),
        }),
      });
      setMessage('Store details updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveDrawerSettings() {
    if (!drawerStoreId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${drawerStoreId}/drawer`, {
        method: 'PATCH',
        body: JSON.stringify({
          drawer_mode: drawerMode,
          drawer_host: drawerHost || null,
          drawer_port: Number(drawerPort) || 9100,
          drawer_open_on_cash: drawerOnCash,
        }),
      });
      setMessage('Cash drawer settings saved');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    const selected = getSelectedStoreId();
    if (selected) {
      setViewStore((prev) => prev || selected);
      setSalesStore((prev) => prev || selected);
    }
    return subscribeStoreContext((id) => {
      if (id) {
        setViewStore(id);
        setSalesStore(id);
      }
    });
  }, []);

  useEffect(() => {
    if (!salesStore) {
      setStoreSales(null);
      return;
    }
    let active = true;
    api(`/stores/${salesStore}/sales`)
      .then((r) => {
        if (active) setStoreSales(r.data || null);
      })
      .catch((err: any) => {
        if (active) {
          setStoreSales(null);
          setError(err.message);
        }
      });
    return () => {
      active = false;
    };
  }, [salesStore]);

  async function loadInventory(storeId: string, opts?: { skipUrl?: boolean }) {
    setViewStore(storeId);
    setSelectedStoreId(storeId);
    setError('');
    if (!opts?.skipUrl) writeStoresQuery({ store_id: storeId || null });
    try {
      const r = await api(`/stores/${storeId}/inventory?include_zero=true`);
      setInventory(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function loadSales(storeId: string) {
    setSalesStore(storeId);
    setSelectedStoreId(storeId);
    setError('');
  }

  async function saveReorder() {
    if (!viewStore || !reorderProductId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${viewStore}/reorder-policy`, {
        method: 'PUT',
        body: JSON.stringify({
          product_id: reorderProductId,
          reorder_level: Number(reorderLevel) || 0,
          reorder_qty: Number(reorderQty) || 0,
        }),
      });
      setMessage('Reorder policy saved');
      await loadInventory(viewStore);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function toggleFefo() {
    setError('');
    try {
      const next = !fefoStrict;
      const r = await api('/inventory/settings', {
        method: 'PATCH',
        body: JSON.stringify({ fefo_strict_warehouse: next }),
      });
      setFefoStrict(!!r.data?.fefo_strict_warehouse);
      setMessage(
        next
          ? 'FEFO strict warehouse mode on (no unassigned-batch fallback)'
          : 'FEFO strict warehouse mode off',
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createTransfer() {
    setError('');
    try {
      const r = await api('/stores/transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_store_id: fromStore,
          to_store_id: toStore,
          submit: true,
          items: [{ product_id: productId, quantity: Number(qty) }],
        }),
      });
      setMessage(`Transfer ${r.data.transfer_number} requested`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function act(id: string, action: string) {
    setError('');
    try {
      const r = await api(`/stores/transfers/${id}/${action}`, { method: 'POST' });
      setMessage(`${r.data.transfer_number} → ${r.data.status}`);
      await refresh();
      if (viewStore) await loadInventory(viewStore);
    } catch (err: any) {
      setError(err.message);
    }
  }

  const storeName = (id: string) => stores.find((s) => s.id === id)?.name || id;

  const isAdminOverride = me?.role === 'company_admin' || me?.role === 'super_admin';
  const canShip = (t: Transfer) => {
    if (!t.from_store_manager_id) return true;
    return isAdminOverride || me?.id === t.from_store_manager_id;
  };
  const canReceive = (t: Transfer) => {
    if (!t.to_store_manager_id) return true;
    return isAdminOverride || me?.id === t.to_store_manager_id;
  };

  return (
    <Shell>
      <h1>Stores</h1>
      <p className="muted">
        Stores &amp; warehouses — reorder policies, FEFO mode, and transfers (MVP Navigation:
        Stores / Warehouse).
      </p>
      {storeEntitlement && (
        <p>
          <strong>
            {storeEntitlement.used} of {storeEntitlement.store_limit} Stores Used
          </strong>
          {storeEntitlement.remaining != null ? (
            <span className="muted"> · {storeEntitlement.remaining} Stores Remaining</span>
          ) : null}
          {storeEntitlement.can_create_store === false ? (
            <span className="error"> · Store limit reached</span>
          ) : null}
        </p>
      )}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }} id="fefo">
        <label className="muted">
          <input type="checkbox" checked={fefoStrict} onChange={() => toggleFefo()} /> FEFO
          strict warehouse (stock-out only from batches tagged to that warehouse)
        </label>
        <p className="muted" style={{ marginTop: 8, marginBottom: 8 }}>
          FEFO settings CSV via <code>GET /inventory/settings/export</code> (Stage 144 F1).
        </p>
        <button
          type="button"
          onClick={() =>
            downloadCsv('/inventory/settings/export', 'inventory_fefo_settings_export.csv')
          }
        >
          Export FEFO settings CSV
        </button>
      </div>

      <div className="grid">
        <div className="card">
          <h3>New store</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code" />
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address" />
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone" />
            <select value={managerId} onChange={(e) => setManagerId(e.target.value)}>
              <option value="">No manager</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.email}
                </option>
              ))}
            </select>
            <select value={branchId} onChange={(e) => setBranchId(e.target.value)}>
              <option value="">No branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
            </select>
            <strong className="muted">Operating hours</strong>
            {WEEKDAYS.map((day) => (
              <input
                key={day}
                value={createHours[day]}
                onChange={(e) => setCreateHours({ ...createHours, [day]: e.target.value })}
                placeholder={`${WEEKDAY_LABELS[day]} e.g. 08:00-18:00`}
              />
            ))}
            <input
              value={hoursNote}
              onChange={(e) => setHoursNote(e.target.value)}
              placeholder="Hours note (optional)"
            />
            <button onClick={createStore}>Create store</button>
          </div>
        </div>
        <div className="card">
          <h3>Edit store</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <select
              value={editStoreId}
              onChange={(e) => {
                const id = e.target.value;
                setEditStoreId(id);
                const s = stores.find((x) => x.id === id);
                setEditName(s?.name || '');
                setEditAddress(s?.address || '');
                setEditPhone(s?.phone || '');
                setEditManagerId(s?.manager_id || '');
                setEditBranchId(s?.branch_id || '');
                setEditActive(s?.is_active !== false);
                setEditHours(hoursFromStore(s?.operating_hours));
                setEditHoursNote(s?.operating_hours?.note || '');
              }}
            >
              <option value="">Select store</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.is_active === false ? ' (inactive)' : ''}
                </option>
              ))}
            </select>
            {editStoreId && (
              <p className="muted" style={{ margin: 0 }}>
                Linked warehouse:{' '}
                {stores.find((s) => s.id === editStoreId)?.warehouse_code
                  ? `${stores.find((s) => s.id === editStoreId)?.warehouse_code} — ${
                      stores.find((s) => s.id === editStoreId)?.warehouse_name
                    }`
                  : 'none'}
              </p>
            )}
            <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" />
            <input
              value={editAddress}
              onChange={(e) => setEditAddress(e.target.value)}
              placeholder="Address"
            />
            <input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} placeholder="Phone" />
            <select value={editManagerId} onChange={(e) => setEditManagerId(e.target.value)}>
              <option value="">No manager</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.email}
                </option>
              ))}
            </select>
            <select value={editBranchId} onChange={(e) => setEditBranchId(e.target.value)}>
              <option value="">No branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
            </select>
            <label className="muted">
              <input
                type="checkbox"
                checked={editActive}
                onChange={(e) => setEditActive(e.target.checked)}
              />{' '}
              Active
            </label>
            <strong className="muted">Operating hours</strong>
            {WEEKDAYS.map((day) => (
              <input
                key={day}
                value={editHours[day]}
                onChange={(e) => setEditHours({ ...editHours, [day]: e.target.value })}
                placeholder={`${WEEKDAY_LABELS[day]} e.g. 08:00-18:00`}
              />
            ))}
            <input
              value={editHoursNote}
              onChange={(e) => setEditHoursNote(e.target.value)}
              placeholder="Hours note (optional)"
            />
            <button onClick={saveStoreDetails} disabled={!editStoreId}>
              Save store details
            </button>
          </div>
        </div>
        <div className="card" id="transfers">
          <h3>New transfer</h3>
          <p className="muted">
            Filter via <code>transfer_status</code> → <code>GET /stores/transfers?status=</code>; list
            export via <code>/stores/transfers/export</code> (Stage 135 T1).
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <select
              value={transferStatusFilter || 'default'}
              onChange={(e) => {
                const v = e.target.value === 'default' ? '' : e.target.value;
                setTransferStatusFilter(v);
                writeStoresQuery({ transfer_status: v || null });
                refresh({ transferStatus: v }).catch((err) => setError(err.message));
              }}
              aria-label="Transfer status filter"
            >
              <option value="default">All statuses</option>
              <option value="draft">Draft</option>
              <option value="requested">Requested</option>
              <option value="in_transit">In transit</option>
              <option value="received">Received</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button
              type="button"
              onClick={async () => {
                const qs =
                  transferStatusFilter === 'draft' ||
                  transferStatusFilter === 'requested' ||
                  transferStatusFilter === 'in_transit' ||
                  transferStatusFilter === 'received' ||
                  transferStatusFilter === 'cancelled'
                    ? `?status=${transferStatusFilter}`
                    : '';
                setError('');
                try {
                  const token = localStorage.getItem('token');
                  const tenant = localStorage.getItem('tenant');
                  const res = await fetch(`${apiBase}/stores/transfers/export${qs}`, {
                    headers: authHeaders(),
                  });
                  if (!res.ok) throw new Error('Stores transfers export failed');
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'stores_transfers_export.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                  setMessage('Stores transfers CSV downloaded (Stage 135 T1)');
                } catch (err: any) {
                  setError(err.message || 'Export failed');
                }
              }}
            >
              Export transfers CSV
            </button>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            <select value={fromStore} onChange={(e) => setFromStore(e.target.value)}>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  From: {s.name}
                </option>
              ))}
            </select>
            <select value={toStore} onChange={(e) => setToStore(e.target.value)}>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  To: {s.name}
                </option>
              ))}
            </select>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.stock_qty})
                </option>
              ))}
            </select>
            <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty" />
            <button onClick={createTransfer}>Create & request</button>
          </div>
        </div>
        <div className="card" id="cash-drawer">
          <h3>Cash drawer</h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            Drawer settings CSV via <code>GET /stores/drawer-settings/export</code> (Stage 142 C1;
            kick bytes never included).
          </p>
          <div style={{ display: 'grid', gap: 8 }}>
            <select
              value={drawerStoreId}
              onChange={(e) => {
                const id = e.target.value;
                setDrawerStoreId(id);
                const s = stores.find((x) => x.id === id);
                if (s) {
                  setDrawerMode(s.drawer_mode || 'none');
                  setDrawerHost(s.drawer_host || '');
                  setDrawerPort(String(s.drawer_port || 9100));
                  setDrawerOnCash(s.drawer_open_on_cash !== false);
                }
              }}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.drawer_mode || 'none'})
                </option>
              ))}
            </select>
            <select value={drawerMode} onChange={(e) => setDrawerMode(e.target.value)}>
              <option value="none">none (disabled)</option>
              <option value="mock">mock (log pulse)</option>
              <option value="network">network (ESC/POS TCP)</option>
              <option value="browser_bridge">browser_bridge (return kick bytes)</option>
            </select>
            {drawerMode === 'network' && (
              <>
                <input
                  value={drawerHost}
                  onChange={(e) => setDrawerHost(e.target.value)}
                  placeholder="Printer/drawer host"
                />
                <input
                  value={drawerPort}
                  onChange={(e) => setDrawerPort(e.target.value)}
                  placeholder="Port (9100)"
                />
              </>
            )}
            <label>
              <input
                type="checkbox"
                checked={drawerOnCash}
                onChange={(e) => setDrawerOnCash(e.target.checked)}
              />{' '}
              Open on cash POS sales
            </label>
            <button onClick={saveDrawerSettings} disabled={!drawerStoreId}>
              Save drawer settings
            </button>
            <button
              type="button"
              onClick={() =>
                downloadCsv('/stores/drawer-settings/export', 'store_drawer_settings_export.csv')
              }
            >
              Export drawer settings CSV
            </button>
          </div>
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>Stores</h3>
      <p className="muted" style={{ marginBottom: 8 }}>
        Filter via <code>store_active</code> → <code>GET /stores?is_active=</code> (Stage 121 S1).
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
        <label className="muted">
          Active status{' '}
          <select
            value={storeActiveFilter}
            onChange={(e) => {
              const v = e.target.value;
              setStoreActiveFilter(v);
              writeStoresQuery({ store_active: v || null });
              refresh({ storeActive: v }).catch((err) => setError(err.message));
            }}
            aria-label="Store active filter"
          >
            <option value="">All</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => {
            // Stage 121 X1 — stores CSV export
            const qs =
              storeActiveFilter === 'true'
                ? '?is_active=true'
                : storeActiveFilter === 'false'
                  ? '?is_active=false'
                  : '';
            downloadCsv(`/stores/export${qs}`, 'stores_export.csv');
          }}
        >
          Export stores CSV
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Branch</th>
            <th>Manager</th>
            <th>Warehouse</th>
            <th>Phone</th>
            <th>Address</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {stores.map((s) => (
            <tr key={s.id}>
              <td>{s.code}</td>
              <td>
                {s.name}
                {s.is_active === false ? ' (inactive)' : ''}
              </td>
              <td>
                {branches.find((b) => b.id === s.branch_id)?.code || s.branch_id || '—'}
              </td>
              <td>
                {users.find((u) => u.id === s.manager_id)?.full_name ||
                  users.find((u) => u.id === s.manager_id)?.email ||
                  '—'}
              </td>
              <td>{s.warehouse_code || '—'}</td>
              <td>{s.phone || '—'}</td>
              <td>{s.address || '—'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button onClick={() => loadInventory(s.id)}>Inventory / reorder</button>
                <button onClick={() => loadSales(s.id)}>Sales</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="grid" style={{ marginTop: 16 }} id="warehouses">
        <div className="card">
          <h3>New warehouse</h3>
          <p className="muted">Standalone or store-linked warehouses (BR-2.4).</p>
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={whCode} onChange={(e) => setWhCode(e.target.value)} placeholder="Code" />
            <input value={whName} onChange={(e) => setWhName(e.target.value)} placeholder="Name" />
            <select value={whType} onChange={(e) => setWhType(e.target.value)}>
              {['retail', 'main', 'cold', 'bulk', 'transit'].map((t) => (
                <option key={t} value={t}>
                  Type: {t}
                </option>
              ))}
            </select>
            <select value={whStoreId} onChange={(e) => setWhStoreId(e.target.value)}>
              <option value="">No linked store</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
            <select value={whManagerId} onChange={(e) => setWhManagerId(e.target.value)}>
              <option value="">No manager</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.email}
                </option>
              ))}
            </select>
            <input
              value={whAddress}
              onChange={(e) => setWhAddress(e.target.value)}
              placeholder="Address"
            />
            <input
              value={whCapacity}
              onChange={(e) => setWhCapacity(e.target.value)}
              placeholder="Capacity"
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/warehouses', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: whCode,
                      name: whName,
                      warehouse_type: whType,
                      store_id: whStoreId || null,
                      manager_id: whManagerId || null,
                      address: whAddress || null,
                      capacity: whCapacity ? Number(whCapacity) : null,
                    }),
                  });
                  setWhCode('');
                  setWhName('');
                  setWhType('retail');
                  setWhStoreId('');
                  setWhManagerId('');
                  setWhAddress('');
                  setWhCapacity('');
                  setMessage('Warehouse created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Create warehouse
            </button>
          </div>
        </div>
        <div className="card">
          <h3>Edit warehouse</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <select
              value={editWhId}
              onChange={(e) => {
                const id = e.target.value;
                setEditWhId(id);
                const w = warehouses.find((x) => x.id === id);
                setEditWhName(w?.name || '');
                setEditWhType(w?.warehouse_type || 'retail');
                setEditWhManagerId(w?.manager_id || '');
                setEditWhAddress(w?.address || '');
                setEditWhCapacity(w?.capacity != null ? String(w.capacity) : '');
                setEditWhActive(w?.is_active !== false);
              }}
            >
              <option value="">Select warehouse</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                  {w.is_active === false ? ' (inactive)' : ''}
                </option>
              ))}
            </select>
            <input value={editWhName} onChange={(e) => setEditWhName(e.target.value)} placeholder="Name" />
            <select value={editWhType} onChange={(e) => setEditWhType(e.target.value)}>
              {['retail', 'main', 'cold', 'bulk', 'transit'].map((t) => (
                <option key={t} value={t}>
                  Type: {t}
                </option>
              ))}
            </select>
            <select value={editWhManagerId} onChange={(e) => setEditWhManagerId(e.target.value)}>
              <option value="">No manager</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.email}
                </option>
              ))}
            </select>
            <input
              value={editWhAddress}
              onChange={(e) => setEditWhAddress(e.target.value)}
              placeholder="Address"
            />
            <input
              value={editWhCapacity}
              onChange={(e) => setEditWhCapacity(e.target.value)}
              placeholder="Capacity"
            />
            <label className="muted">
              <input
                type="checkbox"
                checked={editWhActive}
                onChange={(e) => setEditWhActive(e.target.checked)}
              />{' '}
              Active
            </label>
            <button
              disabled={!editWhId}
              onClick={async () => {
                setError('');
                try {
                  await api(`/warehouses/${editWhId}`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                      name: editWhName,
                      warehouse_type: editWhType,
                      manager_id: editWhManagerId || null,
                      clear_manager: !editWhManagerId,
                      address: editWhAddress || null,
                      capacity: editWhCapacity ? Number(editWhCapacity) : null,
                      is_active: editWhActive,
                    }),
                  });
                  setMessage('Warehouse updated');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Save warehouse
            </button>
          </div>
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>Warehouses</h3>
      <p className="muted" style={{ marginBottom: 8 }}>
        Filter via <code>warehouse_active</code> → <code>GET /warehouses?is_active=</code> (Stage
        121 W1).
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
        <label className="muted">
          Active status{' '}
          <select
            value={warehouseActiveFilter}
            onChange={(e) => {
              const v = e.target.value;
              setWarehouseActiveFilter(v);
              writeStoresQuery({ warehouse_active: v || null });
              refresh({ warehouseActive: v }).catch((err) => setError(err.message));
            }}
            aria-label="Warehouse active filter"
          >
            <option value="">All</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => {
            // Stage 121 X1 — warehouses CSV export
            const qs =
              warehouseActiveFilter === 'true'
                ? '?is_active=true'
                : warehouseActiveFilter === 'false'
                  ? '?is_active=false'
                  : '';
            downloadCsv(`/warehouses/export${qs}`, 'warehouses_export.csv');
          }}
        >
          Export warehouses CSV
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Type</th>
            <th>Store</th>
            <th>Manager</th>
            <th>Capacity</th>
            <th>Active</th>
          </tr>
        </thead>
        <tbody>
          {warehouses.map((w) => (
            <tr key={w.id}>
              <td>{w.code}</td>
              <td>{w.name}</td>
              <td>{w.warehouse_type || 'retail'}</td>
              <td>{stores.find((s) => s.id === w.store_id)?.code || '—'}</td>
              <td>
                {users.find((u) => u.id === w.manager_id)?.full_name ||
                  users.find((u) => u.id === w.manager_id)?.email ||
                  '—'}
              </td>
              <td>{w.capacity ?? '—'}</td>
              <td>{w.is_active === false ? 'No' : 'Yes'}</td>
            </tr>
          ))}
          {!warehouses.length && (
            <tr>
              <td colSpan={7} className="muted">
                No warehouses yet
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {salesStore && storeSales && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Sales · {storeName(salesStore)}</h3>
          <p className="muted">Store-specific invoice + POS totals (BR-13.1)</p>
          <p className="muted">
            Export via <code>{`GET /stores/{id}/sales/export`}</code> (Stage 155 S1).
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <button
              type="button"
              onClick={() =>
                downloadCsv(
                  `/stores/${salesStore}/sales/export`,
                  `store_${salesStore}_sales_export.csv`,
                ).then(() => setMessage('Store sales CSV downloaded (Stage 155 S1)'))
              }
            >
              Export sales CSV
            </button>
          </div>
          <div className="grid" style={{ marginBottom: 12 }}>
            <div>
              <div className="muted">Revenue</div>
              <div className="kpi">{storeSales.summary?.revenue ?? 0}</div>
            </div>
            <div>
              <div className="muted">Sales</div>
              <div className="kpi">{storeSales.summary?.sale_count ?? 0}</div>
            </div>
            <div>
              <div className="muted">Invoices</div>
              <div className="kpi">{storeSales.summary?.invoice_count ?? 0}</div>
            </div>
            <div>
              <div className="muted">POS</div>
              <div className="kpi">{storeSales.summary?.pos_count ?? 0}</div>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Number</th>
                <th>Total</th>
                <th>Tax</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(storeSales.recent || []).map((row) => (
                <tr key={`${row.source}-${row.number}`}>
                  <td>{row.source}</td>
                  <td>{row.number}</td>
                  <td>{row.total}</td>
                  <td>{row.tax}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
              {(storeSales.recent || []).length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    No sales for this store yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }} id="reorder">
        <h3>{viewStore ? `Inventory · ${storeName(viewStore)}` : 'Reorder policies'}</h3>
        {!viewStore ? (
          <p className="muted">Open Inventory / reorder on a store to edit policies.</p>
        ) : (
          <>
            <p className="muted">
              Export via <code>{`GET /stores/{id}/inventory/export`}</code> (Stage 155 I1).
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              <select value={reorderProductId} onChange={(e) => setReorderProductId(e.target.value)}>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                value={reorderLevel}
                onChange={(e) => setReorderLevel(e.target.value)}
                placeholder="Reorder level"
                style={{ width: 110 }}
              />
              <input
                value={reorderQty}
                onChange={(e) => setReorderQty(e.target.value)}
                placeholder="Reorder qty"
                style={{ width: 110 }}
              />
              <button onClick={saveReorder}>Save policy</button>
              <button
                type="button"
                onClick={() =>
                  downloadCsv(
                    `/stores/${viewStore}/inventory/export`,
                    `store_${viewStore}_inventory_export.csv`,
                  ).then(() => setMessage('Store inventory CSV downloaded (Stage 155 I1)'))
                }
              >
                Export inventory CSV
              </button>
            </div>
            {inventory.length === 0 && <p className="muted">No warehouse stock / policy rows yet</p>}
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Qty</th>
                  <th>Reorder</th>
                  <th>Suggest</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((i) => (
                  <tr key={i.product_id}>
                    <td>
                      {i.name} ({i.sku})
                    </td>
                    <td>{i.quantity}</td>
                    <td>
                      {i.reorder_level} / {i.reorder_qty}
                    </td>
                    <td>{i.suggested_order_qty ?? '—'}</td>
                    <td>{i.below_reorder ? 'LOW' : 'ok'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <h3 style={{ marginTop: 16 }}>Transfers</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Number</th>
            <th>From</th>
            <th>To</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {transfers.map((t) => (
            <tr key={t.id}>
              <td>{t.transfer_number}</td>
              <td>{storeName(t.from_store_id)}</td>
              <td>{storeName(t.to_store_id)}</td>
              <td>{t.status}</td>
              <td>
                {(t.status === 'draft' || t.status === 'requested') && canShip(t) && (
                  <button onClick={() => act(t.id, 'ship')} style={{ marginRight: 6 }}>
                    Ship
                  </button>
                )}
                {(t.status === 'draft' || t.status === 'requested') && !canShip(t) && (
                  <span className="muted" style={{ marginRight: 6 }}>
                    Awaiting source manager
                  </span>
                )}
                {t.status === 'in_transit' && canReceive(t) && (
                  <button onClick={() => act(t.id, 'receive')} style={{ marginRight: 6 }}>
                    Receive
                  </button>
                )}
                {t.status === 'in_transit' && !canReceive(t) && (
                  <span className="muted" style={{ marginRight: 6 }}>
                    Awaiting destination manager
                  </span>
                )}
                {['draft', 'requested', 'in_transit'].includes(t.status) && (
                  <button onClick={() => act(t.id, 'cancel')}>Cancel</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
