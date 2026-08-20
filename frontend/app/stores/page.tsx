'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type DayHours = { open?: string; close?: string; closed?: boolean };
type OperatingHours = Partial<Record<'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun', DayHours>>;
type Store = {
  id: string;
  code: string;
  name: string;
  address?: string;
  phone?: string | null;
  manager_id?: string | null;
  branch_id?: string | null;
  is_active?: boolean;
  operating_hours?: OperatingHours | null;
  drawer_mode?: string;
  drawer_host?: string | null;
  drawer_port?: number;
  drawer_open_on_cash?: boolean;
};
type Branch = {
  id: string;
  code: string;
  name: string;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  manager_id?: string | null;
  is_active?: boolean;
};
type Department = {
  id: string;
  code: string;
  name: string;
  branch_id?: string | null;
  head_user_id?: string | null;
  is_active?: boolean;
};

const WEEKDAYS: { key: keyof OperatingHours; label: string }[] = [
  { key: 'mon', label: 'Mon' },
  { key: 'tue', label: 'Tue' },
  { key: 'wed', label: 'Wed' },
  { key: 'thu', label: 'Thu' },
  { key: 'fri', label: 'Fri' },
  { key: 'sat', label: 'Sat' },
  { key: 'sun', label: 'Sun' },
];

function defaultHours(): OperatingHours {
  const openDay = { open: '09:00', close: '18:00', closed: false };
  return {
    mon: { ...openDay },
    tue: { ...openDay },
    wed: { ...openDay },
    thu: { ...openDay },
    fri: { ...openDay },
    sat: { closed: true },
    sun: { closed: true },
  };
}

function summarizeHours(hours?: OperatingHours | null): string {
  if (!hours) return '—';
  const bits = WEEKDAYS.map(({ key, label }) => {
    const d = hours[key];
    if (!d) return null;
    if (d.closed) return `${label} closed`;
    if (d.open && d.close) return `${label} ${d.open}-${d.close}`;
    return null;
  }).filter(Boolean);
  return bits.length ? bits.join(' · ') : '—';
}
type Warehouse = {
  id: string;
  code: string;
  name: string;
  warehouse_type?: string;
  manager_id?: string | null;
  address?: string | null;
  capacity?: number | null;
  store_id?: string | null;
  is_active?: boolean;
};
type UserRow = { id: string; email?: string; full_name?: string; name?: string };
type Product = { id: string; name: string; sku: string; stock_qty: number; is_active?: boolean };
type Transfer = {
  id: string;
  transfer_number: string;
  from_store_id: string;
  to_store_id: string;
  status: string;
  awaiting_approval?: string | null;
  fully_approved?: boolean;
  can_ship?: boolean;
  rejection_reason?: string | null;
  items: { product_id: string; quantity: number }[];
};

export default function Page() {
  const [stores, setStores] = useState<Store[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [managerId, setManagerId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [hours, setHours] = useState<OperatingHours>(defaultHours());
  const [editStoreId, setEditStoreId] = useState('');
  const [editName, setEditName] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editManagerId, setEditManagerId] = useState('');
  const [editBranchId, setEditBranchId] = useState('');
  const [editHours, setEditHours] = useState<OperatingHours>(defaultHours());
  const [whCode, setWhCode] = useState('');
  const [whName, setWhName] = useState('');
  const [whType, setWhType] = useState('retail');
  const [whAddress, setWhAddress] = useState('');
  const [whCapacity, setWhCapacity] = useState('');
  const [whManagerId, setWhManagerId] = useState('');
  const [whStoreId, setWhStoreId] = useState('');
  const [editWhId, setEditWhId] = useState('');
  const [brCode, setBrCode] = useState('');
  const [brName, setBrName] = useState('');
  const [brAddress, setBrAddress] = useState('');
  const [brPhone, setBrPhone] = useState('');
  const [brEmail, setBrEmail] = useState('');
  const [brManagerId, setBrManagerId] = useState('');
  const [editBrId, setEditBrId] = useState('');
  const [deptCode, setDeptCode] = useState('');
  const [deptName, setDeptName] = useState('');
  const [deptBranchId, setDeptBranchId] = useState('');
  const [deptHeadId, setDeptHeadId] = useState('');
  const [editDeptId, setEditDeptId] = useState('');
  const [fromStore, setFromStore] = useState('');
  const [toStore, setToStore] = useState('');
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('1');
  const [xferRejectReason, setXferRejectReason] = useState('');
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
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [storeManageFilter, setStoreManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [warehouseManageFilter, setWarehouseManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [branchManageFilter, setBranchManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [departmentManageFilter, setDepartmentManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [transferManageFilter, setTransferManageFilter] = useState<
    'all' | 'draft' | 'requested' | 'in_transit' | 'received' | 'cancelled'
  >('all');
  const [entitlement, setEntitlement] = useState<{
    stores_active?: number;
    stores_total?: number;
    stores_remaining?: number | null;
    effective_store_limit?: number | null;
    subscription_store_entitlement?: number | null;
    store_limit?: number | null;
    over_entitlement?: boolean;
    unlimited?: boolean;
  } | null>(null);
  const [storeLimitDraft, setStoreLimitDraft] = useState('');

  type StatusFilter = 'all' | 'active' | 'inactive';
  const byStatus = <T extends { is_active?: boolean }>(rows: T[], filter: StatusFilter) =>
    rows.filter((r) => {
      if (filter === 'all') return true;
      const active = r.is_active !== false;
      return filter === 'inactive' ? !active : active;
    });
  const managedStores = byStatus(stores, storeManageFilter);
  const managedWarehouses = byStatus(warehouses, warehouseManageFilter);
  const managedBranches = byStatus(branches, branchManageFilter);
  const managedDepartments = byStatus(departments, departmentManageFilter);
  const managedTransfers = transfers.filter((t) => {
    if (transferManageFilter === 'all') return true;
    return (t.status || 'draft') === transferManageFilter;
  });

  async function refresh() {
    const [s, p, t, settings, wh, u, br, dep, ent] = await Promise.all([
      api('/stores'),
      api('/products'),
      api('/stores/transfers'),
      api('/inventory/settings').catch(() => ({ data: { fefo_strict_warehouse: false } })),
      api('/warehouses').catch(() => ({ data: [] })),
      api('/users').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/stores/entitlement').catch(() => ({ data: null })),
    ]);
    setStores(s.data || []);
    setProducts(p.data || []);
    setTransfers(t.data || []);
    setWarehouses(wh.data || []);
    setUsers(u.data || []);
    setBranches(br.data || []);
    setDepartments(dep.data || []);
    setFefoStrict(!!settings.data?.fefo_strict_warehouse);
    setEntitlement(ent.data || null);
    if (ent.data?.store_limit != null) {
      setStoreLimitDraft(String(ent.data.store_limit));
    } else if (ent.data?.effective_store_limit != null) {
      setStoreLimitDraft('');
    }
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

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createStore() {
    setError('');
    try {
      await api('/stores', {
        method: 'POST',
        body: JSON.stringify({
          code,
          name: name.trim(),
          // Omit blank address so Create does not 422 (AddressValue).
          ...(address.trim() ? { address: address.trim() } : {}),
          phone: phone.trim() || null,
          manager_id: managerId || null,
          branch_id: branchId || null,
          operating_hours: hours,
        }),
      });
      setCode('');
      setName('');
      setAddress('');
      setPhone('');
      setManagerId('');
      setBranchId('');
      setHours(defaultHours());
      setMessage('Store created');
      await refresh();
    } catch (err: any) {
      const detail = err?.detail || err?.data?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        setError(detail.message);
      } else {
        setError(err.message);
      }
    }
  }

  async function saveStoreLimit() {
    setError('');
    setMessage('');
    try {
      const raw = storeLimitDraft.trim();
      await api('/tenants/me/store-limit', {
        method: 'PATCH',
        body: JSON.stringify({
          store_limit: raw === '' ? null : Number(raw),
        }),
      });
      setMessage('Store allocation updated');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Failed to update store allocation');
    }
  }

  function startEditStore(s: Store) {
    setEditStoreId(s.id);
    setEditName(s.name || '');
    setEditAddress(s.address || '');
    setEditPhone(s.phone || '');
    setEditManagerId(s.manager_id || '');
    setEditBranchId(s.branch_id || '');
    setEditHours(s.operating_hours ? { ...defaultHours(), ...s.operating_hours } : defaultHours());
  }

  async function saveStoreEdit() {
    if (!editStoreId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${editStoreId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editName.trim() || undefined,
          // Omit blank address so Save does not 422 (AddressValue); leave prior.
          ...(editAddress.trim() ? { address: editAddress.trim() } : {}),
          // Omit blank phone so Save does not 422 (E164PhoneValue); leave prior value.
          ...(editPhone.trim() ? { phone: editPhone.trim() } : {}),
          manager_id: editManagerId || null,
          clear_manager: !editManagerId,
          branch_id: editBranchId || null,
          clear_branch: !editBranchId,
          operating_hours: editHours,
        }),
      });
      setMessage('Store updated');
      setEditStoreId('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const userLabel = (id: string) => {
    const u = users.find((x) => x.id === id);
    return u?.full_name || u?.name || u?.email || id.slice(0, 8);
  };

  const branchLabel = (id: string) => {
    const b = branches.find((x) => x.id === id);
    return b ? `${b.code} — ${b.name}` : id.slice(0, 8);
  };

  function setDayHours(
    target: 'create' | 'edit',
    day: keyof OperatingHours,
    patch: Partial<DayHours>,
  ) {
    const setter = target === 'create' ? setHours : setEditHours;
    setter((prev) => {
      const cur = prev[day] || {};
      const next = { ...cur, ...patch };
      if (next.closed) return { ...prev, [day]: { closed: true } };
      return {
        ...prev,
        [day]: {
          open: next.open || '09:00',
          close: next.close || '18:00',
          closed: false,
        },
      };
    });
  }

  function HoursEditor({
    value,
    onDay,
  }: {
    value: OperatingHours;
    onDay: (day: keyof OperatingHours, patch: Partial<DayHours>) => void;
  }) {
    return (
      <div style={{ display: 'grid', gap: 6 }}>
        {WEEKDAYS.map(({ key, label }) => {
          const d = value[key] || { closed: true };
          const closed = !!d.closed;
          return (
            <div key={key} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ width: 36 }}>{label}</span>
              <label className="muted" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={closed}
                  onChange={(e) => onDay(key, { closed: e.target.checked })}
                  aria-label={`Store ${label} closed`}
                />
                Closed
              </label>
              {!closed && (
                <>
                  <input
                    type="time"
                    value={d.open || '09:00'}
                    onChange={(e) => onDay(key, { open: e.target.value, closed: false })}
                    aria-label={`Store ${label} open time`}
                  />
                  <span className="muted">–</span>
                  <input
                    type="time"
                    value={d.close || '18:00'}
                    onChange={(e) => onDay(key, { close: e.target.value, closed: false })}
                    aria-label={`Store ${label} close time`}
                  />
                </>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  async function createWarehouse() {
    setError('');
    setMessage('');
    try {
      await api('/warehouses', {
        method: 'POST',
        body: JSON.stringify({
          code: whCode.trim(),
          name: whName.trim(),
          warehouse_type: whType,
          // Omit blank address so Create does not 422 (AddressValue).
          ...(whAddress.trim() ? { address: whAddress.trim() } : {}),
          capacity: whCapacity === '' ? null : Number(whCapacity),
          manager_id: whManagerId || null,
          store_id: whStoreId || null,
        }),
      });
      setWhCode('');
      setWhName('');
      setWhType('retail');
      setWhAddress('');
      setWhCapacity('');
      setWhManagerId('');
      setWhStoreId('');
      setMessage('Warehouse created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveWarehouseEdit() {
    if (!editWhId) return;
    setError('');
    setMessage('');
    try {
      await api(`/warehouses/${editWhId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: whName.trim() || undefined,
          warehouse_type: whType,
          // Omit blank address so Save does not 422 (AddressValue); leave prior.
          ...(whAddress.trim() ? { address: whAddress.trim() } : {}),
          capacity: whCapacity === '' ? null : Number(whCapacity),
          clear_capacity: whCapacity === '',
          manager_id: whManagerId || null,
          clear_manager: !whManagerId,
          store_id: whStoreId || null,
          clear_store: !whStoreId,
        }),
      });
      setEditWhId('');
      setWhCode('');
      setWhName('');
      setWhType('retail');
      setWhAddress('');
      setWhCapacity('');
      setWhManagerId('');
      setWhStoreId('');
      setMessage('Warehouse updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function startEditWarehouse(w: Warehouse) {
    setEditWhId(w.id);
    setWhCode(w.code);
    setWhName(w.name);
    setWhType(w.warehouse_type || 'retail');
    setWhAddress(w.address || '');
    setWhCapacity(w.capacity != null ? String(w.capacity) : '');
    setWhManagerId(w.manager_id || '');
    setWhStoreId(w.store_id || '');
  }

  function resetBranchForm() {
    setEditBrId('');
    setBrCode('');
    setBrName('');
    setBrAddress('');
    setBrPhone('');
    setBrEmail('');
    setBrManagerId('');
  }

  async function createBranch() {
    setError('');
    setMessage('');
    try {
      await api('/branches', {
        method: 'POST',
        body: JSON.stringify({
          code: brCode.trim(),
          name: brName.trim(),
          // Omit blank address so Create does not 422 (AddressValue).
          ...(brAddress.trim() ? { address: brAddress.trim() } : {}),
          phone: brPhone.trim() || null,
          email: brEmail.trim() || null,
          manager_id: brManagerId || null,
        }),
      });
      resetBranchForm();
      setMessage('Branch created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveBranchEdit() {
    if (!editBrId) return;
    setError('');
    setMessage('');
    try {
      await api(`/branches/${editBrId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: brName.trim() || undefined,
          // Omit blank address so Save does not 422 (AddressValue); leave prior.
          ...(brAddress.trim() ? { address: brAddress.trim() } : {}),
          // Omit blank phone so Save does not 422 (E164PhoneValue); leave prior value.
          ...(brPhone.trim() ? { phone: brPhone.trim() } : {}),
          email: brEmail.trim() || null,
          manager_id: brManagerId || null,
          clear_manager: !brManagerId,
        }),
      });
      resetBranchForm();
      setMessage('Branch updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function startEditBranch(b: Branch) {
    setEditBrId(b.id);
    setBrCode(b.code);
    setBrName(b.name);
    setBrAddress(b.address || '');
    setBrPhone(b.phone || '');
    setBrEmail(b.email || '');
    setBrManagerId(b.manager_id || '');
  }

  async function setBranchActive(branchId: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/branches/${branchId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Branch reactivated' : 'Branch deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setStoreActive(storeId: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/stores/${storeId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Store reactivated' : 'Store deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setWarehouseActive(warehouseId: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/warehouses/${warehouseId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Warehouse reactivated' : 'Warehouse deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function resetDeptForm() {
    setEditDeptId('');
    setDeptCode('');
    setDeptName('');
    setDeptBranchId('');
    setDeptHeadId('');
  }

  async function createDepartment() {
    setError('');
    setMessage('');
    try {
      await api('/departments', {
        method: 'POST',
        body: JSON.stringify({
          code: deptCode.trim(),
          name: deptName.trim(),
          branch_id: deptBranchId || null,
          head_user_id: deptHeadId || null,
        }),
      });
      resetDeptForm();
      setMessage('Department created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveDepartmentEdit() {
    if (!editDeptId) return;
    setError('');
    setMessage('');
    try {
      await api(`/departments/${editDeptId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: deptName.trim() || undefined,
          branch_id: deptBranchId || null,
          clear_branch: !deptBranchId,
          head_user_id: deptHeadId || null,
          clear_head: !deptHeadId,
        }),
      });
      resetDeptForm();
      setMessage('Department updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function startEditDepartment(d: Department) {
    setEditDeptId(d.id);
    setDeptCode(d.code);
    setDeptName(d.name);
    setDeptBranchId(d.branch_id || '');
    setDeptHeadId(d.head_user_id || '');
  }

  async function setDepartmentActive(departmentId: string, isActive: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/departments/${departmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      setMessage(isActive ? 'Department reactivated' : 'Department deactivated');
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
          // Blank → null (omit clears); garbage rejected by SmtpHostValue → 422.
          drawer_host: drawerHost.trim() || null,
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

  async function loadInventory(storeId: string) {
    setViewStore(storeId);
    setError('');
    try {
      const r = await api(`/stores/${storeId}/inventory?include_zero=true`);
      setInventory(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
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
    setMessage('');
    if (action === 'reject' || action === 'cancel') {
      const reason = xferRejectReason.trim();
      if (!reason) {
        setError(
          action === 'cancel'
            ? 'Enter a cancel reason before cancelling a store transfer'
            : 'Enter a reject reason before rejecting a store transfer'
        );
        return;
      }
    }
    try {
      const r = await api(`/stores/transfers/${id}/${action}`, {
        method: 'POST',
        body:
          action === 'reject' || action === 'cancel'
            ? JSON.stringify({ reason: xferRejectReason.trim() })
            : undefined,
      });
      if (action === 'reject' || action === 'cancel') {
        setXferRejectReason('');
      }
      setMessage(`${r.data.transfer_number} → ${r.data.status}`);
      await refresh();
      if (viewStore) await loadInventory(viewStore);
    } catch (err: any) {
      setError(err.message);
    }
  }

  const storeName = (id: string) => stores.find((s) => s.id === id)?.name || id;

  return (
    <Shell>
      <h1>Multi-Store</h1>
      <p className="muted">Branches, departments, stores, warehouses, FEFO mode, and transfers</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <label className="muted">
          <input type="checkbox" checked={fefoStrict} onChange={() => toggleFefo()} /> FEFO
          strict warehouse (stock-out only from batches tagged to that warehouse)
        </label>
      </div>

      <div className="grid">
        <div className="card">
          <h3>{editBrId ? 'Edit branch' : 'New branch'}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input
              value={brCode}
              onChange={(e) => setBrCode(e.target.value)}
              placeholder="Code"
              disabled={!!editBrId}
            />
            <input
              value={brName}
              onChange={(e) => setBrName(e.target.value)}
              placeholder="Name"
              aria-label={editBrId ? 'Edit branch name' : 'Branch name'}
              title="Branch name (1–150 chars; letters/digits required)"
            />
            <input
              value={brAddress}
              onChange={(e) => setBrAddress(e.target.value)}
              placeholder="Address"
              aria-label="Branch address"
            />
            <input
              value={brPhone}
              onChange={(e) => setBrPhone(e.target.value)}
              placeholder="Phone (optional, E.164 e.g. +233...)"
              aria-label="Branch phone"
            />
            <input value={brEmail} onChange={(e) => setBrEmail(e.target.value)} placeholder="Email" />
            <select value={brManagerId} onChange={(e) => setBrManagerId(e.target.value)}>
              <option value="">Manager (optional)</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.name || u.email || u.id.slice(0, 8)}
                </option>
              ))}
            </select>
            {editBrId ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" onClick={saveBranchEdit} disabled={!brName.trim()}>
                  Save branch
                </button>
                <button type="button" onClick={resetBranchForm}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={createBranch}
                disabled={!brCode.trim() || !brName.trim()}
                aria-label="Create branch"
              >
                Create branch
              </button>
            )}
          </div>
        </div>
        <div className="card">
          <h3>{editDeptId ? 'Edit department' : 'New department'}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input
              value={deptCode}
              onChange={(e) => setDeptCode(e.target.value)}
              placeholder="Code"
              disabled={!!editDeptId}
            />
            <input
              value={deptName}
              onChange={(e) => setDeptName(e.target.value)}
              placeholder="Name (e.g. Sales)"
              aria-label={editDeptId ? 'Edit department name' : 'Department name'}
              title="Department name (1–150 chars; letters/digits required)"
            />
            <select value={deptBranchId} onChange={(e) => setDeptBranchId(e.target.value)}>
              <option value="">Branch (optional)</option>
              {branches
                .filter((b) => b.is_active !== false)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} — {b.name}
                  </option>
                ))}
            </select>
            <select value={deptHeadId} onChange={(e) => setDeptHeadId(e.target.value)}>
              <option value="">Department head (optional)</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.name || u.email || u.id.slice(0, 8)}
                </option>
              ))}
            </select>
            {editDeptId ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" onClick={saveDepartmentEdit} disabled={!deptName.trim()}>
                  Save department
                </button>
                <button type="button" onClick={resetDeptForm}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={createDepartment}
                disabled={!deptCode.trim() || !deptName.trim()}
                aria-label="Create department"
              >
                Create department
              </button>
            )}
          </div>
        </div>
        <div className="card">
          <h3>New store</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code" />
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name"
              aria-label="Store name"
              title="Store name (1–150 chars; letters/digits required)"
            />
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Address"
              aria-label="Store address"
            />
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone (optional, E.164 e.g. +233...)"
              aria-label="Store phone"
            />
            <select value={managerId} onChange={(e) => setManagerId(e.target.value)}>
              <option value="">Manager (optional)</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.name || u.email || u.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select value={branchId} onChange={(e) => setBranchId(e.target.value)}>
              <option value="">Branch (optional)</option>
              {branches
                .filter((b) => b.is_active !== false)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} — {b.name}
                  </option>
                ))}
            </select>
            <label className="muted">Operating hours</label>
            <HoursEditor value={hours} onDay={(day, patch) => setDayHours('create', day, patch)} />
            <button
              onClick={createStore}
              disabled={!code.trim() || !name.trim()}
              aria-label="Create store"
            >
              Create store
            </button>
          </div>
        </div>
        <div className="card">
          <h3>{editWhId ? 'Edit warehouse' : 'New warehouse'}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input
              value={whCode}
              onChange={(e) => setWhCode(e.target.value)}
              placeholder="Code"
              disabled={!!editWhId}
            />
            <input
              value={whName}
              onChange={(e) => setWhName(e.target.value)}
              placeholder="Name"
              aria-label={editWhId ? 'Edit warehouse name' : 'Warehouse name'}
              title="Warehouse name (1–150 chars; letters/digits required)"
            />
            <select value={whType} onChange={(e) => setWhType(e.target.value)} title="Warehouse type">
              <option value="retail">Retail</option>
              <option value="bulk">Bulk</option>
              <option value="cold_storage">Cold storage</option>
              <option value="other">Other</option>
            </select>
            <input
              value={whAddress}
              onChange={(e) => setWhAddress(e.target.value)}
              placeholder="Address"
              aria-label="Warehouse address"
            />
            <input
              value={whCapacity}
              onChange={(e) => setWhCapacity(e.target.value)}
              placeholder="Capacity (optional)"
            />
            <select value={whManagerId} onChange={(e) => setWhManagerId(e.target.value)}>
              <option value="">Manager (optional)</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.name || u.email || u.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select value={whStoreId} onChange={(e) => setWhStoreId(e.target.value)}>
              <option value="">Linked store (optional)</option>
              {stores
                .filter((s) => s.is_active !== false)
                .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
            {editWhId ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={saveWarehouseEdit} disabled={!whName.trim()}>
                  Save warehouse
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditWhId('');
                    setWhCode('');
                    setWhName('');
                    setWhType('retail');
                    setWhAddress('');
                    setWhCapacity('');
                    setWhManagerId('');
                    setWhStoreId('');
                  }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={createWarehouse}
                disabled={!whCode.trim() || !whName.trim()}
                aria-label="Create warehouse"
              >
                Create warehouse
              </button>
            )}
          </div>
        </div>
        <div className="card">
          <h3>New transfer</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <select value={fromStore} onChange={(e) => setFromStore(e.target.value)}>
              {stores
                .filter((s) => s.is_active !== false)
                .map((s) => (
                <option key={s.id} value={s.id}>
                  From: {s.name}
                </option>
              ))}
            </select>
            <select value={toStore} onChange={(e) => setToStore(e.target.value)}>
              {stores
                .filter((s) => s.is_active !== false)
                .map((s) => (
                <option key={s.id} value={s.id}>
                  To: {s.name}
                </option>
              ))}
            </select>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {products
                .filter((p) => p.is_active !== false)
                .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.stock_qty})
                </option>
              ))}
            </select>
            <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty" />
            <button onClick={createTransfer}>Create & request</button>
          </div>
        </div>
        <div className="card">
          <h3>Cash drawer</h3>
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
              {stores
                .filter((s) => s.is_active !== false)
                .map((s) => (
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
                  placeholder="Host (e.g. 127.0.0.1)"
                  aria-label="Cash drawer host"
                />
                <input
                  value={drawerPort}
                  onChange={(e) => setDrawerPort(e.target.value)}
                  placeholder="Port (9100)"
                  aria-label="Cash drawer port"
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
            <button
              onClick={saveDrawerSettings}
              disabled={!drawerStoreId}
              aria-label="Save drawer settings"
            >
              Save drawer settings
            </button>
          </div>
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>Branches</h3>
      <p className="muted">Code, manager, address, and contact; deactivate without data loss (BR-2.2).</p>
      <select
        value={branchManageFilter}
        onChange={(e) => setBranchManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage branch list by status"
        aria-label="Branch status filter"
        style={{ marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Manager</th>
            <th>Phone</th>
            <th>Email</th>
            <th>Address</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {managedBranches.map((b) => (
            <tr key={b.id}>
              <td>{b.code}</td>
              <td>{b.name}</td>
              <td>{b.manager_id ? userLabel(b.manager_id) : '—'}</td>
              <td>{b.phone || '—'}</td>
              <td>{b.email || '—'}</td>
              <td>{b.address || '—'}</td>
              <td>{b.is_active === false ? 'no' : 'yes'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button type="button" onClick={() => startEditBranch(b)}>
                  Edit
                </button>
                {b.is_active === false ? (
                  <button type="button" className="btn-ok" onClick={() => setBranchActive(b.id, true)}>
                    Reactivate
                  </button>
                ) : (
                  <button type="button" className="btn-danger" onClick={() => setBranchActive(b.id, false)}>
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16 }}>Departments</h3>
      <p className="muted">Code, optional branch, department head; soft deactivate (BR-2.5).</p>
      <select
        value={departmentManageFilter}
        onChange={(e) => setDepartmentManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage department list by status"
        aria-label="Department status filter"
        style={{ marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Branch</th>
            <th>Head</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {managedDepartments.map((d) => (
            <tr key={d.id}>
              <td>{d.code}</td>
              <td>{d.name}</td>
              <td>{d.branch_id ? branchLabel(d.branch_id) : '—'}</td>
              <td>{d.head_user_id ? userLabel(d.head_user_id) : '—'}</td>
              <td>{d.is_active === false ? 'no' : 'yes'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button type="button" onClick={() => startEditDepartment(d)}>
                  Edit
                </button>
                {d.is_active === false ? (
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={() => setDepartmentActive(d.id, true)}
                  >
                    Reactivate
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={() => setDepartmentActive(d.id, false)}
                  >
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16 }}>Stores</h3>
      <p className="muted">Manager, branch, hours, and warehouse link (BR-2.3). Soft-deactivate hides the store from POS and new sales without deleting history.</p>
      {entitlement && (
        <div
          className="plat-stat"
          style={{
            marginBottom: 12,
            padding: '10px 12px',
            border: '1px solid var(--border, #ddd)',
            borderRadius: 8,
          }}
        >
          <strong>
            {entitlement.unlimited
              ? `${entitlement.stores_active ?? 0} active Stores Used (unlimited entitlement)`
              : `${entitlement.stores_active ?? 0} of ${entitlement.effective_store_limit} Stores Used`}
          </strong>
          {!entitlement.unlimited && (
            <span className="muted" style={{ marginLeft: 8 }}>
              {entitlement.stores_remaining ?? 0} Stores Remaining
            </span>
          )}
          {entitlement.over_entitlement ? (
            <p className="login-error" style={{ marginTop: 6 }} role="status">
              Over subscription entitlement — existing stores are kept; create/activate blocked until
              resolved.
            </p>
          ) : null}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span>Company store allocation</span>
              <input
                type="number"
                min={0}
                placeholder="Full entitlement"
                value={storeLimitDraft}
                onChange={(e) => setStoreLimitDraft(e.target.value)}
                style={{ width: 120 }}
              />
            </label>
            <button type="button" onClick={saveStoreLimit}>
              Save allocation
            </button>
            <span className="muted" style={{ fontSize: 12 }}>
              Blank = use full subscription entitlement
              {entitlement.subscription_store_entitlement != null
                ? ` (${entitlement.subscription_store_entitlement})`
                : ' (unlimited)'}
            </span>
          </div>
        </div>
      )}
      <select
        value={storeManageFilter}
        onChange={(e) => setStoreManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage store list by status"
        aria-label="Store status filter"
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
            <th>Manager</th>
            <th>Branch</th>
            <th>Address</th>
            <th>Hours</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {managedStores.map((s) => (
            <tr key={s.id}>
              <td>{s.code}</td>
              <td>
                {s.name}
                {s.is_active === false ? ' [inactive]' : ''}
              </td>
              <td>{s.manager_id ? userLabel(s.manager_id) : '—'}</td>
              <td>{s.branch_id ? branchLabel(s.branch_id) : '—'}</td>
              <td>{s.address || '—'}</td>
              <td style={{ maxWidth: 280, fontSize: 13 }}>{summarizeHours(s.operating_hours)}</td>
              <td>{s.is_active === false ? 'no' : 'yes'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button type="button" onClick={() => startEditStore(s)}>
                  Edit
                </button>
                <button onClick={() => loadInventory(s.id)}>Inventory / reorder</button>
                {s.is_active === false ? (
                  <button type="button" className="btn-ok" onClick={() => setStoreActive(s.id, true)}>
                    Activate
                  </button>
                ) : (
                  <button type="button" className="btn-danger" onClick={() => setStoreActive(s.id, false)}>
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {editStoreId && (
        <div className="card" style={{ marginTop: 16, marginBottom: 16 }}>
          <h3>Edit store · {stores.find((s) => s.id === editStoreId)?.code || editStoreId.slice(0, 8)}</h3>
          <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Name"
              aria-label="Edit store name"
              title="Store name (1–150 chars; letters/digits required)"
            />
            <input
              value={editAddress}
              onChange={(e) => setEditAddress(e.target.value)}
              placeholder="Address"
              aria-label="Store address"
            />
            <input
              value={editPhone}
              onChange={(e) => setEditPhone(e.target.value)}
              placeholder="Phone (optional, E.164 e.g. +233...)"
              aria-label="Store phone"
            />
            <select value={editManagerId} onChange={(e) => setEditManagerId(e.target.value)}>
              <option value="">No manager</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.name || u.email || u.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select value={editBranchId} onChange={(e) => setEditBranchId(e.target.value)}>
              <option value="">No branch</option>
              {branches
                .filter((b) => b.is_active !== false)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} — {b.name}
                  </option>
                ))}
            </select>
            <label className="muted">Operating hours</label>
            <HoursEditor value={editHours} onDay={(day, patch) => setDayHours('edit', day, patch)} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={saveStoreEdit}
                disabled={!editName.trim()}
                aria-label="Save store"
              >
                Save store
              </button>
              <button type="button" onClick={() => setEditStoreId('')}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {viewStore && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Inventory · {storeName(viewStore)}</h3>
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
        </div>
      )}

      <h3 style={{ marginTop: 16 }}>Warehouses</h3>
      <p className="muted">
        Type, manager, address, and capacity (BR-2.4). Soft-deactivate hides the warehouse from new
        stock ops without deleting history.
      </p>
      <select
        value={warehouseManageFilter}
        onChange={(e) => setWarehouseManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage warehouse list by status"
        aria-label="Warehouse status filter"
        style={{ marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Type</th>
            <th>Manager</th>
            <th>Address</th>
            <th>Capacity</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {managedWarehouses.map((w) => (
            <tr key={w.id}>
              <td>{w.code}</td>
              <td>
                {w.name}
                {w.is_active === false ? ' [inactive]' : ''}
              </td>
              <td>{w.warehouse_type || 'retail'}</td>
              <td>{w.manager_id ? userLabel(w.manager_id) : '—'}</td>
              <td>{w.address || '—'}</td>
              <td>{w.capacity != null ? w.capacity : '—'}</td>
              <td>{w.is_active === false ? 'no' : 'yes'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button type="button" onClick={() => startEditWarehouse(w)}>
                  Edit
                </button>
                {w.is_active === false ? (
                  <button type="button" className="btn-ok" onClick={() => setWarehouseActive(w.id, true)}>
                    Activate
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={() => setWarehouseActive(w.id, false)}
                  >
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
          {managedWarehouses.length === 0 && (
            <tr>
              <td colSpan={8} className="muted">
                No warehouses yet
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16 }}>Transfers</h3>
      <p className="muted">
        Dual approval: source store manager → destination store manager, then ship / receive.
      </p>
      <div className="card" style={{ marginBottom: 12 }}>
        <label>
          Reject / Cancel reason{' '}
          <input
            value={xferRejectReason}
            onChange={(e) => setXferRejectReason(e.target.value)}
            placeholder="Required before Reject or Cancel"
            title="Required reject/cancel reason (1–500 chars; letters/digits required)"
            aria-label="Stock transfer reject reason"
            style={{ minWidth: 280 }}
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Used by Reject and Cancel (stored as <code>rejection_reason</code>; status → cancelled).
        </p>
      </div>
      <select
        value={transferManageFilter}
        onChange={(e) =>
          setTransferManageFilter(
            e.target.value as
              | 'all'
              | 'draft'
              | 'requested'
              | 'in_transit'
              | 'received'
              | 'cancelled'
          )
        }
        title="Filter stock transfer list by status"
        aria-label="Stock transfer status filter"
        style={{ marginBottom: 12 }}
      >
        <option value="all">All statuses</option>
        <option value="draft">Draft only</option>
        <option value="requested">Requested only</option>
        <option value="in_transit">In transit only</option>
        <option value="received">Received only</option>
        <option value="cancelled">Cancelled only</option>
      </select>
      <table className="table">
        <thead>
          <tr>
            <th>Number</th>
            <th>From</th>
            <th>To</th>
            <th>Status</th>
            <th>Approval</th>
            <th>Reject / Cancel reason</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {managedTransfers.map((t) => (
            <tr key={t.id}>
              <td>{t.transfer_number}</td>
              <td>{storeName(t.from_store_id)}</td>
              <td>{storeName(t.to_store_id)}</td>
              <td>{t.status}</td>
              <td>
                {t.status === 'requested'
                  ? t.fully_approved
                    ? 'Ready to ship'
                    : t.awaiting_approval === 'dest'
                      ? 'Awaiting dest'
                      : 'Awaiting source'
                  : '—'}
              </td>
              <td>{t.rejection_reason || '—'}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {t.status === 'draft' && (
                  <button type="button" className="btn-ok" onClick={() => act(t.id, 'submit')}>
                    Submit
                  </button>
                )}
                {t.status === 'requested' && !t.fully_approved && (
                  <>
                    <button type="button" className="btn-ok" onClick={() => act(t.id, 'approve')}>
                      Approve {t.awaiting_approval === 'dest' ? 'dest' : 'source'}
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => act(t.id, 'reject')}
                      aria-label={`Reject stock transfer ${t.id}`}
                    >
                      Reject
                    </button>
                  </>
                )}
                {t.can_ship && (
                  <button type="button" className="btn-ok" onClick={() => act(t.id, 'ship')}>
                    Ship
                  </button>
                )}
                {t.status === 'in_transit' && (
                  <button type="button" className="btn-ok" onClick={() => act(t.id, 'receive')}>
                    Receive
                  </button>
                )}
                {['draft', 'requested', 'in_transit'].includes(t.status) && (
                  <button type="button" className="btn-danger" onClick={() => act(t.id, 'cancel')}>
                    Cancel
                  </button>
                )}
              </td>
            </tr>
          ))}
          {managedTransfers.length === 0 && (
            <tr>
              <td colSpan={7} className="muted">
                {transfers.length === 0
                  ? 'No transfers yet'
                  : 'No stock transfers for this filter'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Shell>
  );
}
