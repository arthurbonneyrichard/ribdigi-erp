'use client';

import { useEffect, useState, type FormEvent } from 'react';
import CashierPresencePanel from '../../../components/CashierPresencePanel';
import FormModal from '../../../components/FormModal';
import PageHeader from '../../../components/PageHeader';
import { api, apiFetch } from '../../../lib/api';
import { industryAllowsModule } from '../../../lib/industryModules';
import { getMe } from '../../../lib/meCache';
import { hideStoreUx as shouldHideStoreUx, isHotelIndustry } from '../../../lib/tenantNav';

type RoleRow = {
  role: string;
  label: string;
  system?: boolean;
  record_scope?: string;
  is_active?: boolean;
  permissions?: Record<string, string[]>;
};
type BranchRow = { id: string; code: string; name: string; is_active?: boolean };
type DepartmentRow = {
  id: string;
  code: string;
  name: string;
  branch_id?: string | null;
  is_active?: boolean;
};
type StoreRow = {
  id: string;
  code: string;
  name: string;
  is_active?: boolean;
  branch_id?: string | null;
};
type UserRow = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  email_verified?: boolean;
  is_active: boolean;
  phone?: string | null;
  branch_id?: string | null;
  department_id?: string | null;
  store_id?: string | null;
  store_ids?: string[];
  record_scope?: string | null;
};
const emptyForm = {
  email: '',
  full_name: '',
  password: '',
  role: 'cashier',
  phone: '',
  branch_id: '',
  department_id: '',
  store_ids: [] as string[],
  record_scope: '',
};

const RECORD_SCOPES = [
  { value: '', label: 'Default for role' },
  { value: 'own', label: 'Own records' },
  { value: 'department', label: 'Department' },
  { value: 'branch', label: 'Branch' },
  { value: 'all', label: 'All records' },
];

const ROLE_KEY_RE = /^[a-z][a-z0-9_]{1,48}$/;
const E164_RE = /^\+[0-9]{8,15}$/;
/** Phones may be typed with spaces or dashes (+233 24 123 4567); store them compact. */
const compactPhone = (value: string) => value.trim().replace(/[\s-]/g, '');
const PHONE_HINT = 'Enter the phone with its country code, for example +233 24 123 4567, or leave it blank.';

const PLATFORM_USER_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

/** Roles that may create/edit tenant staff. Matches backend users:write for these principals. */
const USER_ADMIN_ROLES = new Set([
  'company_admin',
  'tenant_admin',
  'tenant_owner',
  'super_admin',
  'platform_owner',
  'platform_admin',
]);

function moduleActions(perms: Record<string, string[]> | undefined, module: string): string[] {
  const raw = perms?.[module] as unknown;
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') return [raw];
  return [];
}

/** Align with POST /users (require_permission users:write). Accept users:create as the same grant. */
function canWriteUsers(role: string, perms: Record<string, string[]> | undefined): boolean {
  if (USER_ADMIN_ROLES.has(role)) return true;
  if (moduleActions(perms, '*').includes('*')) return true;
  const actions = moduleActions(perms, 'users');
  return actions.includes('write') || actions.includes('create') || actions.includes('*');
}

/** Align with POST /stores (stores:write). */
function canWriteModule(perms: Record<string, string[]> | undefined, module: string): boolean {
  if (moduleActions(perms, '*').includes('*')) return true;
  const actions = moduleActions(perms, module);
  return actions.includes('write') || actions.includes('create') || actions.includes('*');
}

/** Matches backend `custom_roles.ASSIGNABLE_MODULES` — no platform modules. */
const TENANT_RBAC_MODULES = [
  'dashboard',
  'inventory',
  'sales',
  'pos',
  'purchasing',
  'suppliers',
  'customers',
  'expenses',
  'accounting',
  'credit',
  'tax',
  'stores',
  'hotel',
  'fmcg',
  'hospital',
  'restaurant',
  'reports',
  'notifications',
  'users',
  'audit',
  'ai',
  'security',
  'backup',
  'company',
  'printers',
] as const;

const TENANT_RBAC_ACTIONS = ['read', 'write', 'approve'] as const;

const MODULE_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  inventory: 'Products and stock',
  sales: 'Sales',
  pos: 'Point of sale',
  purchasing: 'Purchasing',
  suppliers: 'Suppliers',
  customers: 'Customers',
  expenses: 'Expenses',
  accounting: 'Finance',
  credit: 'Balances',
  tax: 'Tax',
  stores: 'Stores',
  hotel: 'Hotel',
  fmcg: 'FMCG',
  hospital: 'Hospital',
  restaurant: 'Restaurant',
  reports: 'Reports',
  notifications: 'Notifications',
  users: 'Staff',
  audit: 'Audit',
  ai: 'AI Assistant',
  security: 'Security',
  backup: 'Backup',
  company: 'Company',
  printers: 'Printers',
};

const ACTION_LABELS: Record<string, string> = {
  read: 'View',
  write: 'Change',
  approve: 'Approve',
};

function moduleGrants(acts: string[] | undefined, action: string): boolean {
  if (!acts?.length) return false;
  return acts.includes('*') || acts.includes(action);
}

function pickAssignablePerms(
  perms?: Record<string, string[]> | null,
  industry?: string | null,
): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  if (!perms || perms['*']?.includes('*')) return out;
  for (const mod of TENANT_RBAC_MODULES) {
    if (!industryAllowsModule(industry, mod)) continue;
    const raw = (perms[mod] || []).map((a) => String(a || '').trim()).filter(Boolean);
    if (raw.includes('*')) {
      out[mod] = ['*'];
      continue;
    }
    const acts = raw.filter((a) =>
      (TENANT_RBAC_ACTIONS as readonly string[]).includes(a),
    );
    if (acts.length) out[mod] = acts;
  }
  return out;
}

function togglePermAction(
  map: Record<string, string[]>,
  module: string,
  action: string,
): Record<string, string[]> {
  const current = map[module] || [];
  const granted = current.includes('*') ? [...TENANT_RBAC_ACTIONS] : current.filter((a) => a !== '*');
  const next = granted.includes(action)
    ? granted.filter((a) => a !== action)
    : [...granted, action];
  const copy = { ...map };
  if (next.length) copy[module] = next;
  else delete copy[module];
  return copy;
}

function PermissionGrid({
  value,
  onChange,
  disabled,
  industry,
}: {
  value: Record<string, string[]>;
  onChange: (next: Record<string, string[]>) => void;
  disabled?: boolean;
  industry?: string | null;
}) {
  const modules = TENANT_RBAC_MODULES.filter((mod) => industryAllowsModule(industry, mod));
  return (
    <div style={{ display: 'grid', gap: 6, maxHeight: 320, overflow: 'auto' }}>
      {modules.map((mod) => (
        <div key={mod} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ minWidth: 120 }}>{mod}</span>
          {TENANT_RBAC_ACTIONS.map((act) => (
            <label key={act} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={moduleGrants(value[mod], act)}
                disabled={disabled}
                onChange={() => onChange(togglePermAction(value, mod, act))}
                aria-label={`${mod} ${act}`}
              />
              {act}
            </label>
          ))}
        </div>
      ))}
    </div>
  );
}

type ImportReportRow = {
  line: number;
  email: string;
  full_name: string;
  role: string;
  ok: boolean;
  errors: string[];
};

type ImportReport = {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  can_commit: boolean;
  imported?: number;
  rows: ImportReportRow[];
};

export default function Page() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [userManageFilter, setUserManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [roleManageFilter, setRoleManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [branches, setBranches] = useState<BranchRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [stores, setStores] = useState<StoreRow[]>([]);
  const [userStoreIds, setUserStoreIds] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState(emptyForm);
  const [roleForm, setRoleForm] = useState({
    key: '',
    label: '',
  });
  const [meIndustry, setMeIndustry] = useState<string | null>(null);
  const [createPerms, setCreatePerms] = useState<Record<string, string[]>>({});
  const [permRole, setPermRole] = useState<string | null>(null);
  const [permMap, setPermMap] = useState<Record<string, string[]>>({});
  const [permBusy, setPermBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [editUser, setEditUser] = useState<UserRow | null>(null);
  const [editForm, setEditForm] = useState({ full_name: '', phone: '', role: '', password: '' });
  const [storeAddOpen, setStoreAddOpen] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [canWriteStores, setCanWriteStores] = useState(false);
  const [hideStoreUx, setHideStoreUx] = useState(false);
  const [hideStoreAssign, setHideStoreAssign] = useState(false);
  const [permChecked, setPermChecked] = useState(false);
  const [meRole, setMeRole] = useState('');
  const [meId, setMeId] = useState('');
  const [storeForm, setStoreForm] = useState({
    code: '',
    name: '',
    address: '',
    phone: '',
    manager_id: '',
    branch_id: '',
  });
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [userQuery, setUserQuery] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [branchFilter, setBranchFilter] = useState('');
  const [storeFilter, setStoreFilter] = useState('');

  async function refresh() {
    const meRes = await getMe();
    const perms = (meRes.data?.permissions || {}) as Record<string, string[]>;
    const role = meRes.data?.role || '';
    setMeId(String(meRes.data?.id || '').trim());
    setMeRole(role);
    setCanWrite(canWriteUsers(role, perms));
    setCanWriteStores(canWriteModule(perms, 'stores'));
    setHideStoreUx(shouldHideStoreUx(meRes.data));
    setHideStoreAssign(isHotelIndustry(meRes.data?.industry));
    setMeIndustry(meRes.data?.industry || null);
    setPermChecked(true);
    const [usersRes, rolesRes, branchesRes, deptsRes, storesRes] = await Promise.all([
      api('/users'),
      // Manage list needs inactive custom roles for Activate / Deactivate (BR-3.2).
      api('/roles?include_inactive=true'),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/stores').catch(() => ({ data: [] })),
    ]);
    const listed: UserRow[] = usersRes.data || [];
    const hidePlatform = !PLATFORM_USER_ROLES.has(role);
    setRows(hidePlatform ? listed.filter((u) => !PLATFORM_USER_ROLES.has(u.role)) : listed);
    const catalog: RoleRow[] = rolesRes.data || [];
    setRoles(catalog);
    setBranches(branchesRes.data || []);
    setDepartments(deptsRes.data || []);
    setStores((storesRes.data || []).filter((s: StoreRow) => s.is_active !== false));
    const users: UserRow[] = hidePlatform
      ? listed.filter((u) => !PLATFORM_USER_ROLES.has(u.role))
      : listed;
    setUserStoreIds(
      Object.fromEntries(users.map((u) => [u.id, u.store_ids || []])),
    );
  }

  const isCustomRole = (r: RoleRow) => r.system === false;
  const roleChoiceText = (role: RoleRow) =>
    `${role.label || role.role}${isCustomRole(role) ? ' (custom)' : ''}${role.is_active === false ? ' [inactive]' : ''}`;
  const isRoleActive = (r: RoleRow) => !isCustomRole(r) || r.is_active !== false;
  const assignableRoles = (currentRole?: string) =>
    roles.filter(
      (r) =>
        !PLATFORM_USER_ROLES.has(r.role) &&
        (isRoleActive(r) || (currentRole != null && r.role === currentRole)),
    );

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  const branchLabel = (id?: string | null) => {
    if (!id) return '—';
    const b = branches.find((x) => x.id === id);
    return b ? `${b.code} — ${b.name}` : id.slice(0, 8);
  };

  const deptLabel = (id?: string | null) => {
    if (!id) return '—';
    const d = departments.find((x) => x.id === id);
    return d ? `${d.code} — ${d.name}` : id.slice(0, 8);
  };

  const storeLabel = (id?: string | null) => {
    if (!id) return '—';
    const s = stores.find((x) => x.id === id);
    return s ? `${s.code} — ${s.name}` : id.slice(0, 8);
  };

  const storesForBranch = (branchId?: string, extraIds: string[] = []) => {
    const inBranch = stores.filter((s) => !branchId || s.branch_id === branchId);
    const extra = stores.filter(
      (s) => extraIds.includes(s.id) && !inBranch.some((x) => x.id === s.id),
    );
    return extra.length ? [...inBranch, ...extra] : inBranch;
  };

  const assignedStoreNames = (userId: string, row?: UserRow) => {
    const ids = userStoreIds[userId] || row?.store_ids || [];
    if (!ids.length) return 'All stores in this company';
    return ids.map((id) => storeLabel(id)).join(', ');
  };

  const soleStoreId = stores.length === 1 ? stores[0].id : '';
  useEffect(() => {
    if (hideStoreAssign || !soleStoreId) return;
    setForm((prev) => (prev.store_ids.length ? prev : { ...prev, store_ids: [soleStoreId] }));
  }, [hideStoreAssign, soleStoreId]);
  useEffect(() => {
    if (!canWrite || typeof window === 'undefined') return;
    if (window.location.hash !== '#create-user') return;
    document.getElementById('create-user')?.scrollIntoView({ block: 'start' });
  }, [canWrite]);
  const focusAddUser = () => {
    setError('');
    setMessage('');
    const node = document.getElementById('create-user');
    node?.scrollIntoView({ block: 'start' });
    node?.querySelector<HTMLInputElement>('input')?.focus();
  };

  const activeBranches = branches.filter((b) => b.is_active !== false);
  const managedUsers = rows.filter((r) => {
    if (userManageFilter === 'all') {
      /* keep */
    } else {
      const active = r.is_active !== false;
      if (userManageFilter === 'inactive' ? active : !active) return false;
    }
    if (deptFilter && r.department_id !== deptFilter) return false;
    if (branchFilter && r.branch_id !== branchFilter) return false;
    if (storeFilter) {
      const ids = userStoreIds[r.id] || r.store_ids || [];
      if (!ids.includes(storeFilter)) return false;
    }
    const needle = userQuery.trim().toLowerCase();
    if (needle) {
      const hay = `${r.full_name} ${r.email} ${deptLabel(r.department_id)} ${branchLabel(r.branch_id)} ${assignedStoreNames(r.id, r)}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
  const managedCustomRoles = roles.filter((r) => {
    if (!isCustomRole(r)) return false;
    if (roleManageFilter === 'all') return true;
    const active = r.is_active !== false;
    return roleManageFilter === 'inactive' ? !active : active;
  });
  const activeDepartments = (branchId?: string) =>
    departments.filter(
      (d) =>
        d.is_active !== false && (!branchId || !d.branch_id || d.branch_id === branchId),
    );
  const branchOptions = (currentId?: string | null) => {
    const list = activeBranches.slice();
    if (currentId && !list.some((b) => b.id === currentId)) {
      const current = branches.find((b) => b.id === currentId);
      if (current) list.push(current);
    }
    return list;
  };
  const departmentOptions = (branchId?: string, currentId?: string | null) => {
    const list = activeDepartments(branchId);
    if (currentId && !list.some((d) => d.id === currentId)) {
      const current = departments.find((d) => d.id === currentId);
      if (current) return [...list, current];
    }
    return list;
  };

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const fullName = form.full_name.trim();
    if (!fullName) {
      setError('User full name is required.');
      setMessage('');
      return;
    }
    const trimmedPassword = form.password.trim();
    if (!trimmedPassword) {
      setError('User password is required.');
      setMessage('');
      return;
    }
    const phoneTrim = compactPhone(form.phone);
    if (phoneTrim && !E164_RE.test(phoneTrim)) {
      setError(PHONE_HINT);
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email.trim(),
          full_name: fullName,
          password: trimmedPassword,
          role: form.role,
          phone: phoneTrim || null,
          branch_id: form.branch_id.trim() || null,
          department_id: form.department_id.trim() || null,
          store_id: hideStoreAssign ? null : form.store_ids[0] || null,
          store_ids: hideStoreAssign ? [] : form.store_ids,
          record_scope: form.record_scope || null,
        }),
      });
      setForm(emptyForm);
      setMessage('User created. They can sign in with this workspace.');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function createStore(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const codeTrim = storeForm.code.trim();
    const nameTrim = storeForm.name.trim();
    if (!codeTrim || !nameTrim) {
      setError('Store code and name are required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      await api('/stores', {
        method: 'POST',
        body: JSON.stringify({
          code: codeTrim,
          name: nameTrim,
          ...(storeForm.address.trim() ? { address: storeForm.address.trim() } : {}),
          phone: storeForm.phone.trim() || null,
          manager_id: storeForm.manager_id.trim() || null,
          branch_id: storeForm.branch_id.trim() || null,
        }),
      });
      setStoreForm({
        code: '',
        name: '',
        address: '',
        phone: '',
        manager_id: '',
        branch_id: '',
      });
      setMessage('Store created');
      setStoreAddOpen(false);
      await refresh();
    } catch (err: any) {
      const detail = err?.detail || err?.data?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        setError(detail.message);
      } else {
        setError(err.message || 'Store was not created');
      }
    } finally {
      setBusy(false);
    }
  }

  async function createCustomRole(e: React.FormEvent) {
    e.preventDefault();
    const label = roleForm.label.trim();
    const key = roleForm.key.trim().toLowerCase();
    if (!label) {
      setError('Custom role label is required.');
      setMessage('');
      return;
    }
    if (!ROLE_KEY_RE.test(key)) {
      setError('Role code must start with a letter and use only lowercase letters, numbers, and underscores (for example warehouse_lead).');
      setMessage('');
      return;
    }
    if (PLATFORM_USER_ROLES.has(key) || roles.some((r) => r.system && r.role === key)) {
      setError('That code is already a built-in role. Choose a different role code.');
      setMessage('');
      return;
    }
    const permissions = pickAssignablePerms(createPerms, meIndustry);
    if (!Object.keys(permissions).length) {
      setError('Select at least one module permission.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const r = await api('/roles', {
        method: 'POST',
        body: JSON.stringify({
          key,
          label,
          permissions,
        }),
      });
      setRoleForm({ key: '', label: '' });
      setCreatePerms({});
      setMessage(`Custom role ${r.data?.role || roleForm.key} created`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteCustomRole(role: string) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${role}`, { method: 'DELETE' });
      setMessage(`Deleted role ${role}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setCustomRoleActive(role: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/roles/${role}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(is_active ? `Activated role ${role}` : `Deactivated role ${role}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveCustomRolePerms() {
    if (!permRole) return;
    const permissions = pickAssignablePerms(permMap, meIndustry);
    if (!Object.keys(permissions).length) {
      setError('Select at least one module permission.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setPermBusy(true);
    try {
      await api(`/roles/${permRole}`, {
        method: 'PATCH',
        body: JSON.stringify({ permissions }),
      });
      setMessage(`Permissions saved for ${permRole}. Assigned users pick this up on their next request.`);
      setPermRole(null);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setPermBusy(false);
    }
  }

  async function patchUser(userId: string, body: Record<string, unknown>, okMsg: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage(okMsg);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRole(userId: string, role: string) {
    await patchUser(userId, { role }, 'Role updated');
  }

  function openEditUser(row: UserRow) {
    setEditUser(row);
    setEditForm({
      full_name: row.full_name || '',
      phone: row.phone || '',
      role: row.role || '',
      password: '',
    });
  }

  async function saveEditUser(e: FormEvent) {
    e.preventDefault();
    if (!editUser) return;
    const body: Record<string, unknown> = {};
    const name = editForm.full_name.trim();
    if (name && name !== (editUser.full_name || '')) body.full_name = name;
    const phone = compactPhone(editForm.phone);
    if (phone && !E164_RE.test(phone)) {
      setError(PHONE_HINT);
      setMessage('');
      return;
    }
    if (phone && phone !== (editUser.phone || '').trim()) body.phone = phone;
    if (editUser.id !== meId && editForm.role && editForm.role !== editUser.role) {
      body.role = editForm.role;
    }
    if (editForm.password.trim()) body.password = editForm.password.trim();
    if (!Object.keys(body).length) {
      setEditUser(null);
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/users/${editUser.id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setMessage('User updated');
      setEditUser(null);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function setBranch(userId: string, branchId: string) {
    const trimmed = branchId.trim();
    const currentStores = userStoreIds[userId] || [];
    const validStores = currentStores.filter((id) =>
      storesForBranch(trimmed).some((s) => s.id === id),
    );
    await patchUser(
      userId,
      trimmed
        ? validStores.length === 1
          ? { branch_id: trimmed, store_id: validStores[0] }
          : { branch_id: trimmed }
        : { clear_branch: true, clear_department: true },
      'Branch assignment updated',
    );
    if (trimmed && validStores.length !== currentStores.length && validStores.length > 0) {
      await setUserStores(userId, validStores);
    }
  }

  async function setDepartment(userId: string, departmentId: string) {
    const trimmed = departmentId.trim();
    await patchUser(
      userId,
      trimmed ? { department_id: trimmed } : { clear_department: true },
      'Department assignment updated',
    );
  }

  async function setRecordScope(userId: string, scope: string) {
    await patchUser(
      userId,
      { record_scope: scope || 'own' },
      'Record scope updated',
    );
  }

  async function setUserStores(userId: string, storeIds: string[]) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}/stores`, {
        method: 'PUT',
        body: JSON.stringify({ store_ids: storeIds }),
      });
      setUserStoreIds((prev) => ({ ...prev, [userId]: storeIds }));
      setMessage(
        storeIds.length
          ? `Store access limited to ${storeIds.length} store(s) in this company`
          : 'Store access set to all stores in this company'
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function allowSignIn(userId: string, email: string) {
    setError('');
    setMessage('');
    try {
      await api(`/users/${userId}/confirm-email`, { method: 'POST', body: '{}' });
      setMessage(`${email} can sign in now.`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not enable sign-in');
    }
  }

  async function setActive(userId: string, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      if (is_active) {
        await api(`/users/${userId}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage('User activated');
      } else {
        await api(`/users/${userId}`, { method: 'DELETE' });
        setMessage('User deactivated');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deleteUser(row: UserRow) {
    if (meId && row.id === meId) {
      setError('You cannot delete your own account.');
      setMessage('');
      return;
    }
    const ok = window.confirm(
      `Delete ${row.full_name} (${row.email}) permanently?\n\nThis removes the staff account. This cannot be undone.`
    );
    if (!ok) return;
    setError('');
    setMessage('');
    try {
      await api(`/users/${String(row.id).trim()}/account`, { method: 'DELETE' });
      setMessage(`Deleted ${row.full_name}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Delete failed');
    }
  }

  async function downloadImportTemplate() {
    setError('');
    try {
      const res = await apiFetch('/users/import/template');
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Template download failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'users-import-template.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('CSV template downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runUserImport(dryRun: boolean) {
    if (!importFile) {
      setError('Choose a CSV file first');
      return;
    }
    setError('');
    setMessage('');
    setImportBusy(true);
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      const res = await apiFetch(`/users/import?dry_run=${dryRun ? 'true' : 'false'}`, {
        method: 'POST',
        body: formData,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = body.detail;
        if (detail && typeof detail === 'object' && detail.report) {
          setImportReport(detail.report);
          throw new Error(detail.message || 'Import validation failed');
        }
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.message || body.message || 'Import failed'
        );
      }
      setImportReport(body.data as ImportReport);
      if (dryRun) {
        setMessage(
          body.data?.can_commit
            ? `Validation OK — ${body.data.valid_rows} user(s) ready to import`
            : `Validation found ${body.data?.error_rows || 0} error row(s)`
        );
      } else {
        setMessage(`Imported ${body.data?.imported || 0} user(s)`);
        setImportFile(null);
        await refresh();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <div className="user-manage">
      <PageHeader
        title="User Management"
        subtitle="See who can sign in, then add a person with a name, email, password, and role. Deactivate stops sign-in and keeps their history."
        subtitleClassName="muted user-manage-lead"
        actions={
          (canWrite || (canWriteStores && !hideStoreUx)) ? (
            <>
              {canWrite ? (
                <button type="button" className="list-btn-primary" onClick={focusAddUser} aria-label="Add User">
                  Add user
                </button>
              ) : null}
              {canWriteStores && !hideStoreUx ? (
                <button
                  type="button"
                  className="list-btn-primary"
                  onClick={() => {
                    setError('');
                    setMessage('');
                    setStoreAddOpen(true);
                  }}
                  aria-label="Create store"
                >
                  Create store
                </button>
              ) : null}
            </>
          ) : undefined
        }
      />
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}
      {permChecked && !canWrite ? (
        <div className="card users-perm-msg" role="status" style={{ margin: '12px 0' }}>
          <p style={{ margin: 0 }}>
            You can view users in this company, but you cannot create or edit them.
            Creating users requires <code>users:write</code> (Company Admin). Your role is{' '}
            <strong>{meRole || 'unknown'}</strong>. Cashiers and other read-only roles cannot
            create users from this page, by URL, or via the API.
          </p>
        </div>
      ) : null}

      {canWrite && editUser ? (
        <FormModal
          title={`Edit ${editUser.full_name || editUser.email}`}
          busy={busy}
          dirty
          onClose={() => setEditUser(null)}
        >
          <form id="edit-user" onSubmit={saveEditUser} style={{ display: 'grid', gap: 8 }}>
            <input
              value={editForm.full_name}
              onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              placeholder="Full name"
              aria-label="Edit user full name"
              required
            />
            <input value={editUser.email} aria-label="Edit user email" readOnly />
            <input
              value={editForm.phone}
              onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
              placeholder="Phone (optional), e.g. +233 24 123 4567"
              aria-label="Edit user phone"
            />
            <select
              value={editForm.role}
              onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
              aria-label={`Edit role for ${editUser.email}`}
              disabled={editUser.id === meId}
            >
              {assignableRoles(editForm.role).map((r) => (
                <option key={r.role} value={r.role}>
                  {roleChoiceText(r)}
                </option>
              ))}
            </select>
            <input
              type="password"
              value={editForm.password}
              onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
              placeholder="New password (leave blank to keep)"
              aria-label="Edit user password"
            />
            <button type="submit" className="btn-ok" disabled={busy} aria-label={`Save user ${editUser.email}`}>
              Save user
            </button>
          </form>
        </FormModal>
      ) : null}

      {canWrite ? (
        <form id="create-user" className="card user-manage-card" onSubmit={createUser}>
          <h2>Add user</h2>
          <p className="muted">Name, email, a temporary password, role and phone. Branch, department and record access are optional.</p>
          <div className="user-manage-fields">
            <label className="user-manage-field">
              <span>Full name</span>
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Full name"
                aria-label="User full name"
                required
              />
            </label>
            <label className="user-manage-field">
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Email"
                aria-label="User email"
                required
              />
            </label>
            <label className="user-manage-field">
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="Temporary password"
                aria-label="User password"
                required
              />
            </label>
            <label className="user-manage-field">
              <span>Role</span>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                aria-label="User role"
              >
                {assignableRoles().map((r) => (
                  <option key={r.role} value={r.role}>
                    {roleChoiceText(r)}
                  </option>
                ))}
              </select>
            </label>
            <label className="user-manage-field">
              <span>Phone</span>
              <input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="e.g. +233 24 123 4567"
                aria-label="User phone"
              />
            </label>
            <details className="user-manage-optional">
              <summary>Optional details</summary>
              <div className="user-manage-optional-body">
                {!hideStoreUx ? (
                  <label className="user-manage-field">
                    <span>Branch</span>
                    <select
                      value={form.branch_id}
                      onChange={(e) => {
                        const nextBranch = e.target.value;
                        const keepStores = form.store_ids.filter((id) =>
                          storesForBranch(nextBranch).some((s) => s.id === id),
                        );
                        setForm({
                          ...form,
                          branch_id: nextBranch,
                          department_id: '',
                          store_ids: keepStores,
                        });
                      }}
                      aria-label="User branch"
                      title="Optional branch"
                    >
                      <option value="">None</option>
                      {activeBranches.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.code} — {b.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <label className="user-manage-field">
                  <span>Department</span>
                  <select
                    value={form.department_id}
                    onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                    aria-label="User department"
                    title="Optional department"
                  >
                    <option value="">None</option>
                    {activeDepartments(form.branch_id).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="user-manage-field">
                  <span>Record scope</span>
                  <select
                    value={form.record_scope}
                    onChange={(e) => setForm({ ...form, record_scope: e.target.value })}
                    aria-label="User record scope"
                  >
                    {RECORD_SCOPES.map((s) => (
                      <option key={s.value || 'default'} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
                {!hideStoreAssign ? (
                  <fieldset className="user-manage-stores">
                    <legend>
                      {stores.length <= 1
                        ? 'Store (this company)'
                        : 'Assigned stores (this company)'}
                    </legend>
                    {stores.length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>No store to assign yet. Create a store when this person needs a location.</p>
                    ) : stores.length === 1 ? (
                      <select
                        value={form.store_ids[0] || stores[0].id}
                        onChange={(e) => setForm({ ...form, store_ids: e.target.value ? [e.target.value] : [] })}
                        aria-label="User store"
                      >
                        {stores.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.code} — {s.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="user-manage-store-list">
                        <label className="user-manage-store-choice">
                          <input
                            type="checkbox"
                            checked={form.store_ids.length === 0}
                            onChange={() => setForm({ ...form, store_ids: [] })}
                            aria-label="All stores in this company"
                          />
                          All stores in this company
                        </label>
                        {storesForBranch(form.branch_id).map((s) => (
                          <label key={s.id} className="user-manage-store-choice">
                            <input
                              type="checkbox"
                              checked={form.store_ids.includes(s.id)}
                              onChange={() => {
                                const next = form.store_ids.includes(s.id)
                                  ? form.store_ids.filter((id) => id !== s.id)
                                  : [...form.store_ids, s.id];
                                setForm({ ...form, store_ids: next });
                              }}
                              aria-label={`Assign store ${s.code}`}
                            />
                            {s.code} — {s.name}
                          </label>
                        ))}
                      </div>
                    )}
                  </fieldset>
                ) : null}
              </div>
            </details>
            <div className="user-manage-submit">
              <button
                type="submit"
                className="btn-ok"
                disabled={busy || !form.full_name.trim() || !form.password.trim()}
                aria-label="Create user"
              >
                {busy ? 'Creating…' : 'Create user'}
              </button>
            </div>
          </div>
        </form>
      ) : null}

      {canWriteStores && !hideStoreUx && storeAddOpen ? (
        <FormModal
          title="New store"
          busy={busy}
          dirty={Boolean(
            storeForm.code.trim() ||
              storeForm.name.trim() ||
              storeForm.address.trim() ||
              storeForm.phone.trim(),
          )}
          onClose={() => setStoreAddOpen(false)}
        >
          <form onSubmit={createStore} style={{ display: 'grid', gap: 8 }}>
            <input
              value={storeForm.code}
              onChange={(e) => setStoreForm({ ...storeForm, code: e.target.value })}
              placeholder="Code"
              aria-label="Store code"
              title="Store code"
              required
            />
            <input
              value={storeForm.name}
              onChange={(e) => setStoreForm({ ...storeForm, name: e.target.value })}
              placeholder="Name"
              aria-label="Store name"
              title="Store name"
              required
            />
            <input
              value={storeForm.address}
              onChange={(e) => setStoreForm({ ...storeForm, address: e.target.value })}
              placeholder="Address"
              aria-label="Store address"
            />
            <input
              value={storeForm.phone}
              onChange={(e) => setStoreForm({ ...storeForm, phone: e.target.value })}
              placeholder="Phone (optional), e.g. +233 24 123 4567"
              aria-label="Store phone"
            />
            <select
              value={storeForm.manager_id}
              onChange={(e) => setStoreForm({ ...storeForm, manager_id: e.target.value })}
              aria-label="Store manager"
              title="Store manager (optional tenant user)"
            >
              <option value="">Manager (optional)</option>
              {rows.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.email}
                </option>
              ))}
            </select>
            <select
              value={storeForm.branch_id}
              onChange={(e) => setStoreForm({ ...storeForm, branch_id: e.target.value })}
              aria-label="Store branch"
              title="Store branch (optional)"
            >
              <option value="">Branch (optional)</option>
              {activeBranches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} — {b.name}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={busy || !storeForm.code.trim() || !storeForm.name.trim()}
              aria-label="Create store"
              aria-busy={busy}
            >
              {busy ? 'Creating store…' : 'Create store'}
            </button>
            {message ? <p className="form-flash ok" role="status">{message}</p> : null}
            {error ? <p className="form-flash err" role="alert">{error}</p> : null}
          </form>
        </FormModal>
      ) : null}

      <section className="card user-manage-list" aria-label="People">
        <h2>People</h2>
        <div className="user-manage-toolbar">
      <label className="user-manage-field">
        Status
      <select
        value={userManageFilter}
        onChange={(e) => setUserManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage user list by status"
        aria-label="User status filter"
      >
        <option value="all">All</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
      </label>
      <label className="user-manage-field user-manage-search">
        Search
      <input
        value={userQuery}
        onChange={(e) => setUserQuery(e.target.value)}
        placeholder={hideStoreUx ? 'Search name, email, department' : 'Search name, email, department, branch, store'}
        aria-label="Search users"
      />
      </label>
      {!hideStoreUx ? (
      <label className="user-manage-field">
        Branch
      <select
        value={branchFilter}
        onChange={(e) => {
          setBranchFilter(e.target.value);
          if (e.target.value && storeFilter) {
            const stillValid = stores.some(
              (s) => s.id === storeFilter && s.branch_id === e.target.value,
            );
            if (!stillValid) setStoreFilter('');
          }
        }}
        aria-label="Filter users by branch"
      >
        <option value="">All branches</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      </label>
      ) : null}
      {!hideStoreUx ? (
      <label className="user-manage-field">
        Store
      <select
        value={storeFilter}
        onChange={(e) => setStoreFilter(e.target.value)}
        aria-label="Filter users by store"
      >
        <option value="">All stores</option>
        {storesForBranch(branchFilter).map((s) => (
          <option key={s.id} value={s.id}>
            {s.code} — {s.name}
          </option>
        ))}
      </select>
      </label>
      ) : null}
      <label className="user-manage-field">
        Department
      <select
        value={deptFilter}
        onChange={(e) => setDeptFilter(e.target.value)}
        aria-label="Filter users by department"
      >
        <option value="">All departments</option>
        {departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      </label>
        </div>

      <div className="list-table-wrap user-manage-table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th className="user-manage-name">Name</th>
            <th className="user-manage-email">Email</th>
            <th className="user-manage-role">Role</th>
            {!hideStoreUx ? <th>Branch</th> : null}
            {!hideStoreAssign ? <th>Store</th> : null}
            <th>Department</th>
            <th>Scope</th>
            <th>Status</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {managedUsers.length === 0 && (
            <tr>
              <td colSpan={(canWrite ? 7 : 6) + (hideStoreUx ? 0 : 1) + (hideStoreAssign ? 0 : 1)} className="muted">
                {rows.length
                  ? 'No users for this filter. Choose All to see everyone in this company.'
                  : 'No users yet. Add a person with a name, email, password, and role.'}
              </td>
            </tr>
          )}
          {managedUsers.map((r) => (
            <tr key={r.id}>
              <td className="user-manage-name">
                {r.full_name}
              </td>
              <td className="user-manage-email">{r.email}</td>
              <td className="user-manage-role">
                {canWrite ? (
                  <select
                    value={r.role}
                    onChange={(e) => setRole(r.id, e.target.value)}
                    aria-label={`Change role for ${r.email}`}
                  >
                    {assignableRoles(r.role).map((role) => (
                      <option key={role.role} value={role.role}>
                        {roleChoiceText(role)}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.role
                )}
              </td>
              {!hideStoreUx ? (
              <td>
                {canWrite ? (
                  <select
                    value={r.branch_id || ''}
                    onChange={(e) => setBranch(r.id, e.target.value)}
                    aria-label={`Edit user branch for ${r.email}`}
                  >
                    <option value="">None</option>
                    {branchOptions(r.branch_id).map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.code}{b.is_active === false ? ' [inactive]' : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  branchLabel(r.branch_id)
                )}
              </td>
              ) : null}
              {!hideStoreAssign ? (
              <td>
                {canWrite && !PLATFORM_USER_ROLES.has(r.role) && r.role !== 'company_admin' ? (
                  stores.length <= 1 ? (
                    <select
                      value={(userStoreIds[r.id] || r.store_ids || [])[0] || soleStoreId}
                      onChange={(e) => {
                        const next = e.target.value.trim();
                        setUserStores(r.id, next ? [next] : soleStoreId ? [soleStoreId] : []);
                      }}
                      aria-label={`Edit user store for ${r.email}`}
                      title="Single-store companies assign this store. Company admins keep all stores in this company."
                    >
                      {stores.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.code} — {s.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div>
                      <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <input
                          type="checkbox"
                          checked={(userStoreIds[r.id] || r.store_ids || []).length === 0}
                          onChange={() => setUserStores(r.id, [])}
                          aria-label={`All stores in this company for ${r.email}`}
                        />
                        All stores in this company
                      </label>
                      {storesForBranch(r.branch_id || undefined, userStoreIds[r.id] || r.store_ids || []).map(
                        (s) => {
                          const selected = userStoreIds[r.id] || r.store_ids || [];
                          return (
                            <label key={s.id} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              <input
                                type="checkbox"
                                checked={selected.includes(s.id)}
                                onChange={() => {
                                  const next = selected.includes(s.id)
                                    ? selected.filter((id) => id !== s.id)
                                    : [...selected, s.id];
                                  setUserStores(r.id, next);
                                }}
                                aria-label={`Assign ${s.code} to ${r.email}`}
                              />
                              {s.code}
                              {r.branch_id && s.branch_id && s.branch_id !== r.branch_id
                                ? ' (other branch)'
                                : ''}
                            </label>
                          );
                        },
                      )}
                    </div>
                  )
                ) : (
                  <span className="muted">
                    {r.role === 'company_admin' || PLATFORM_USER_ROLES.has(r.role)
                      ? 'All stores in this company'
                      : assignedStoreNames(r.id, r)}
                  </span>
                )}
              </td>
              ) : null}
              <td>
                {canWrite ? (
                  <select
                    value={r.department_id || ''}
                    onChange={(e) => setDepartment(r.id, e.target.value)}
                    aria-label={`Edit user department for ${r.email}`}
                  >
                    <option value="">None</option>
                    {departmentOptions(r.branch_id || undefined, r.department_id).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}{d.is_active === false ? ' [inactive]' : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  deptLabel(r.department_id)
                )}
              </td>
              <td>
                {canWrite ? (
                  <select
                    value={r.record_scope || 'own'}
                    onChange={(e) => setRecordScope(r.id, e.target.value)}
                    aria-label={`Edit user record scope for ${r.email}`}
                  >
                    {RECORD_SCOPES.filter((s) => s.value).map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.record_scope || '—'
                )}
              </td>
              <td>
                <span className={r.is_active ? 'user-manage-status' : 'user-manage-status is-off'}>
                  {r.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              {canWrite && (
                <td className="user-manage-actions">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={() => openEditUser(r)}
                    aria-label={`Edit user ${r.email}`}
                  >
                    Edit
                  </button>
                  {r.email_verified === false ? (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => allowSignIn(r.id, r.email)}
                      aria-label={`Allow sign-in for ${r.email}`}
                    >
                      Allow sign-in
                    </button>
                  ) : null}
                  {r.is_active ? (
                    <button type="button" className="btn-danger" onClick={() => setActive(r.id, false)} aria-label={`Deactivate user ${r.id}`}>
                      Deactivate
                    </button>
                  ) : (
                    <button type="button" className="btn-ok" onClick={() => setActive(r.id, true)} aria-label={`Activate user ${r.id}`}>
                      Activate
                    </button>
                  )}
                  {r.id !== meId ? (
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => deleteUser(r)}
                      aria-label={`Delete user ${r.email}`}
                    >
                      Delete
                    </button>
                  ) : null}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      </section>

      <CashierPresencePanel />

      {canWrite && (
        <details className="user-manage-more">
          <summary>Custom roles</summary>
        <form onSubmit={createCustomRole} className="user-manage-more-body">
          <p className="muted" style={{ margin: 0 }}>
            Add a role for this company and choose what that role can open. Deactivate keeps people
            who already have it, and stops new assignments. A role cannot be deleted while someone
            still uses it.
          </p>
          <input
            value={roleForm.key}
            onChange={(e) => setRoleForm({ ...roleForm, key: e.target.value })}
            placeholder="Role code, for example warehouse_lead"
            required
            aria-label="Custom role key"
          />
          <input
            value={roleForm.label}
            onChange={(e) => setRoleForm({ ...roleForm, label: e.target.value })}
            placeholder="Display label"
            required
            aria-label="Custom role label"
          />
          <PermissionGrid value={createPerms} onChange={setCreatePerms} industry={meIndustry} />
          <button
            type="submit"
            className="btn-ok"
            disabled={busy || !roleForm.key.trim() || !roleForm.label.trim() || !Object.keys(createPerms).length}
            aria-label="Create custom role"
          >
            {busy ? 'Saving…' : 'Create custom role'}
          </button>
          <select
            value={roleManageFilter}
            onChange={(e) =>
              setRoleManageFilter(e.target.value as 'all' | 'active' | 'inactive')
            }
            title="Filter manage custom role list by status"
            aria-label="Custom role status filter"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <ul className="user-manage-role-list">
            {managedCustomRoles.map((r) => (
              <li key={r.role} className="user-manage-role-row">
                {r.label}
                {r.is_active === false ? (
                  <span className="muted" style={{ marginLeft: 6 }}>
                    Inactive
                  </span>
                ) : null}
                {r.is_active === false ? (
                  <button
                    type="button"
                    className="btn-ok"
                    style={{ marginLeft: 8 }}
                    onClick={() => setCustomRoleActive(r.role, true)}
                   aria-label={`Activate custom role ${r.role}`}>
                    Activate
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-danger"
                    style={{ marginLeft: 8 }}
                    onClick={() => setCustomRoleActive(r.role, false)}
                   aria-label={`Deactivate custom role ${r.role}`}>
                    Deactivate
                  </button>
                )}
                <button
                  type="button"
                  style={{ marginLeft: 8 }}
                  onClick={() => {
                    setPermRole(r.role);
                    setPermMap(pickAssignablePerms(r.permissions, meIndustry));
                    setError('');
                    setMessage('');
                  }}
                  aria-label={`Edit permissions for custom role ${r.role}`}
                >
                  Edit permissions
                </button>
                <button
                  type="button"
                  style={{ marginLeft: 8 }}
                  onClick={() => deleteCustomRole(r.role)}
                 aria-label={`Delete custom role ${r.role}`}>
                  Delete
                </button>
              </li>
            ))}
            {!managedCustomRoles.length && (
              <li className="muted">No custom roles for this filter. Choose All statuses, or create a role with a code and at least one permission.</li>
            )}
          </ul>
        </form>
        </details>
      )}

      {canWrite && (
        <details className="user-manage-more">
          <summary>Import from CSV</summary>
        <div className="user-manage-more-body">
          <p className="muted" style={{ margin: 0 }}>
            Download the spreadsheet template, fill one person per row, check it, then import.
            If one row is invalid, nothing is imported.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={downloadImportTemplate} aria-label="Download user CSV template">
              Download CSV template
            </button>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="User CSV import file"
            onChange={(e) => {
              setImportFile(e.target.files?.[0] || null);
              setImportReport(null);
            }}
          />
          {importFile && <p className="muted">Selected: {importFile.name}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => runUserImport(true)}
              disabled={!importFile || importBusy}
              aria-label="Validate user CSV import"
            >
              {importBusy ? 'Working…' : 'Validate'}
            </button>
            <button
              type="button"
              onClick={() => runUserImport(false)}
              disabled={!importFile || importBusy || !importReport?.can_commit}
              aria-label="Import valid user CSV rows"
            >
              Import valid rows
            </button>
          </div>
          {importReport && (
            <div>
              <p className="muted">
                {importReport.total_rows} rows · {importReport.valid_rows} valid ·{' '}
                {importReport.error_rows} errors
                {importReport.imported != null ? ` · imported ${importReport.imported}` : ''}
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Email</th>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {importReport.rows.map((r) => (
                    <tr key={`${r.line}-${r.email}`}>
                      <td>{r.line}</td>
                      <td>{r.email || '—'}</td>
                      <td>{r.full_name || '—'}</td>
                      <td>{r.role || '—'}</td>
                      <td style={{ color: r.ok ? 'var(--brand, #4AB012)' : '#b91c1c' }}>{r.ok ? 'OK' : 'Error'}</td>
                      <td>{r.errors?.length ? r.errors.join('; ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        </details>
      )}

      {canWrite && permRole ? (
        <FormModal
          title={`Edit permissions: ${permRole}`}
          busy={permBusy}
          dirty={true}
          onClose={() => setPermRole(null)}
        >
          <p className="muted" style={{ marginTop: 0 }}>
            These choices apply to everyone with this role. They do not grant platform owner access.
          </p>
          <PermissionGrid value={permMap} onChange={setPermMap} disabled={permBusy} industry={meIndustry} />
          <button
            type="button"
            onClick={() => void saveCustomRolePerms()}
            disabled={permBusy || !Object.keys(permMap).length}
            aria-label="Save role permissions"
          >
            {permBusy ? 'Saving…' : 'Save permissions'}
          </button>
        </FormModal>
      ) : null}
    </div>
  );
}
