'use client';

import { useEffect, useState } from 'react';
import FormModal from '../../../components/FormModal';
import { api, getAccessToken } from '../../../lib/api';
import { industryAllowsModule } from '../../../lib/industryModules';
import { getMe } from '../../../lib/meCache';
import { hideStoreUx as shouldHideStoreUx, isHotelIndustry } from '../../../lib/tenantNav';

type RoleRow = {
  role: string;
  label: string;
  system?: boolean;
  base_role?: string | null;
  record_scope?: string;
  is_active?: boolean;
  cloneable?: boolean;
  clone_group?: 'system_template' | 'tenant_role';
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

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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

function pickAssignablePerms(
  perms?: Record<string, string[]> | null,
  industry?: string | null,
): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  if (!perms || perms['*']?.includes('*')) return out;
  for (const mod of TENANT_RBAC_MODULES) {
    if (!industryAllowsModule(industry, mod)) continue;
    const acts = (perms[mod] || []).filter((a) =>
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
  const next = current.includes(action)
    ? current.filter((a) => a !== action)
    : [...current, action];
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
                checked={(value[mod] || []).includes(act)}
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

function CloneFromPicker({
  roles,
  value,
  onSelect,
}: {
  roles: RoleRow[];
  value: string;
  onSelect: (role: RoleRow | null) => void;
}) {
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();
  const cloneable = roles.filter((r) => r.cloneable !== false && !PLATFORM_USER_ROLES.has(r.role));
  const systemRows = cloneable.filter((r) => r.system !== false && r.clone_group !== 'tenant_role');
  const tenantRows = cloneable.filter((r) => r.system === false || r.clone_group === 'tenant_role');
  const match = (r: RoleRow) =>
    !needle || r.label.toLowerCase().includes(needle) || r.role.toLowerCase().includes(needle);
  const systemHits = systemRows.filter(match);
  const tenantHits = tenantRows.filter(match);
  const empty = !systemHits.length && !tenantHits.length;

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search compatible roles"
        aria-label="Clone from system role"
      />
      <div
        role="listbox"
        aria-label="Clone from"
        style={{
          border: '1px solid var(--border, #d0d5dd)',
          borderRadius: 8,
          maxHeight: 168,
          overflow: 'auto',
          padding: 6,
        }}
      >
        <button
          type="button"
          onClick={() => onSelect(null)}
          style={{
            display: 'block',
            width: '100%',
            textAlign: 'left',
            background: !value ? 'var(--surface-muted, #f2f4f7)' : 'transparent',
            border: 0,
            padding: '6px 8px',
          }}
        >
          Create without cloning
        </button>
        {empty ? (
          <p className="muted" style={{ margin: '8px 6px' }}>
            No compatible roles available
          </p>
        ) : null}
        {systemHits.length ? (
          <>
            <p className="muted" style={{ margin: '8px 6px 4px', fontSize: 12 }}>
              System templates
            </p>
            {systemHits.map((r) => (
              <button
                key={r.role}
                type="button"
                role="option"
                aria-selected={value === r.role}
                onClick={() => onSelect(r)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  background: value === r.role ? 'var(--surface-muted, #f2f4f7)' : 'transparent',
                  border: 0,
                  padding: '6px 8px',
                }}
              >
                Clone from {r.label}
              </button>
            ))}
          </>
        ) : null}
        {tenantHits.length ? (
          <>
            <p className="muted" style={{ margin: '8px 6px 4px', fontSize: 12 }}>
              This company&apos;s roles
            </p>
            {tenantHits.map((r) => (
              <button
                key={r.role}
                type="button"
                role="option"
                aria-selected={value === r.role}
                onClick={() => onSelect(r)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  background: value === r.role ? 'var(--surface-muted, #f2f4f7)' : 'transparent',
                  border: 0,
                  padding: '6px 8px',
                }}
              >
                Clone from {r.label}
              </button>
            ))}
          </>
        ) : null}
      </div>
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
    base_role: '',
  });
  const [meIndustry, setMeIndustry] = useState<string | null>(null);
  const [createPerms, setCreatePerms] = useState<Record<string, string[]>>({});
  const [permRole, setPermRole] = useState<string | null>(null);
  const [permMap, setPermMap] = useState<Record<string, string[]>>({});
  const [permBusy, setPermBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [userAddOpen, setUserAddOpen] = useState(false);
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
    setCreatePerms((prev) => {
      if (Object.keys(prev).length) return prev;
      const industry = meRes.data?.industry || null;
      const selected = catalog.find((r) => r.role === roleForm.base_role && r.cloneable);
      if (selected) return pickAssignablePerms(selected.permissions, industry);
      return {};
    });
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
  const openAddUser = () => {
    setError('');
    setMessage('');
    const next = { ...emptyForm, store_ids: [] as string[] };
    if (!hideStoreAssign && soleStoreId) next.store_ids = [soleStoreId];
    setForm(next);
    setUserAddOpen(true);
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
          phone: form.phone.trim() || null,
          branch_id: hideStoreUx ? null : form.branch_id.trim() || null,
          department_id: form.department_id.trim() || null,
          store_id: hideStoreAssign ? null : form.store_ids[0] || null,
          store_ids: hideStoreAssign ? [] : form.store_ids,
          record_scope: form.record_scope || null,
        }),
      });
      setForm(emptyForm);
      setMessage('User created. They can sign in with this workspace.');
      setUserAddOpen(false);
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
    if (!label) {
      setError('Custom role label is required.');
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
          key: roleForm.key.trim(),
          label,
          ...(roleForm.base_role ? { base_role: roleForm.base_role } : {}),
          ...(Object.keys(createPerms).length ? { permissions: createPerms } : {}),
        }),
      });
      setRoleForm({ key: '', label: '', base_role: '' });
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
    if (!Object.keys(permMap).length) {
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
        body: JSON.stringify({ permissions: permMap }),
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
      const token = getAccessToken();
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/users/import/template`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
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
      const token = getAccessToken();
      const tenant = localStorage.getItem('tenant');
      const formData = new FormData();
      formData.append('file', importFile);
      const res = await fetch(`${apiBase}/users/import?dry_run=${dryRun ? 'true' : 'false'}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
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
    <>
      <div className="list-page-head">
        <div>
          <h1 style={{ margin: 0 }}>User Management</h1>
          <p className="muted" style={{ margin: '8px 0 0' }}>
            Add staff with a short form (name, email, temporary password, role, and store access).
            Single-store companies assign that one store; multi-store companies pick one or several
            in this company. Platform owner roles are not created here. Deactivate stops sign-in but
            keeps history; Delete removes the account.
          </p>
        </div>
        {(canWrite || (canWriteStores && !hideStoreUx)) ? (
        <div className="list-head-actions">
          {canWrite ? (
            <button type="button" className="list-btn-primary" onClick={openAddUser} aria-label="Add User">
              Add User
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
        </div>
        ) : null}
      </div>
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

      {canWrite && userAddOpen ? (
        <FormModal
          title="Add user"
          busy={busy}
          dirty={Boolean(form.full_name.trim() || form.email.trim() || form.password.trim())}
          onClose={() => setUserAddOpen(false)}
        >
        <form
          id="create-user"
          onSubmit={createUser}
          style={{ display: 'grid', gap: 8 }}
        >
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name"
            aria-label="User full name"
            required
          />
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Email"
            aria-label="User email"
            required
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Temporary password"
            aria-label="User password"
            required
          />
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Phone (optional, E.164 e.g. +233...)"
            aria-label="User phone"
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            aria-label="User role"
          >
            {assignableRoles().map((r) => (
              <option key={r.role} value={r.role}>
                {r.label}
                {isCustomRole(r) ? ' (custom)' : ''}
              </option>
            ))}
          </select>
          {!hideStoreUx ? (
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
            title="Optional branch assignment (UuidIdValue)"
          >
            <option value="">Branch (optional)</option>
            {activeBranches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.code} — {b.name}
              </option>
            ))}
          </select>
          ) : null}
          {!hideStoreAssign ? (
          <fieldset style={{ border: '1px solid var(--border, #ddd)', padding: 8, margin: 0 }}>
            <legend>
              {stores.length <= 1
                ? 'Store (this company)'
                : 'Assigned stores (this company)'}
            </legend>
            {stores.length === 0 ? (
              <p className="muted" style={{ margin: 0 }}>No store to assign yet.</p>
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
              <div style={{ display: 'grid', gap: 4 }}>
                <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={form.store_ids.length === 0}
                    onChange={() => setForm({ ...form, store_ids: [] })}
                    aria-label="All stores in this company"
                  />
                  All stores in this company
                </label>
                {storesForBranch(form.branch_id).map((s) => (
                  <label key={s.id} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
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
          <select
            value={form.department_id}
            onChange={(e) => setForm({ ...form, department_id: e.target.value })}
            aria-label="User department"
            title="Optional department assignment (UuidIdValue)"
          >
            <option value="">Department (optional)</option>
            {activeDepartments(form.branch_id).map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} — {d.name}
              </option>
            ))}
          </select>
          <select
            value={form.record_scope}
            onChange={(e) => setForm({ ...form, record_scope: e.target.value })}
            aria-label="User record scope"
          >
            {RECORD_SCOPES.map((s) => (
              <option key={s.value || 'default'} value={s.value}>
                Record scope: {s.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy || !form.full_name.trim() || !form.password.trim()}
            aria-label="Create user"
          >
            {busy ? 'Creating…' : 'Create User'}
          </button>
        </form>
        </FormModal>
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
              title="Store code (1–50 chars; letters/digits required)"
              required
            />
            <input
              value={storeForm.name}
              onChange={(e) => setStoreForm({ ...storeForm, name: e.target.value })}
              placeholder="Name"
              aria-label="Store name"
              title="Store name (1–150 chars; letters/digits required)"
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
              placeholder="Phone (optional, E.164 e.g. +233...)"
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

      {canWrite && (
        <form onSubmit={createCustomRole} className="card" style={{ margin: '20px 0', display: 'grid', gap: 8 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Custom roles</h2>
          <p className="muted" style={{ margin: 0 }}>
            Clone a system role&apos;s permissions into a tenant-specific role key, then tick the
            modules this company actually uses. Saved permissions apply to navigation, pages, buttons,
            and APIs. Soft-deactivate with <strong>Deactivate</strong> (keeps assignees; blocks new
            assignment). Delete is blocked while any user still has the role. System roles stay
            immutable — clone them instead of granting platform-owner rights.
          </p>
          <input
            value={roleForm.key}
            onChange={(e) => setRoleForm({ ...roleForm, key: e.target.value })}
            placeholder="Role key (e.g. warehouse_lead)"
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
          <CloneFromPicker
            roles={roles}
            value={roleForm.base_role}
            onSelect={(source) => {
              setRoleForm({ ...roleForm, base_role: source?.role || '' });
              setCreatePerms(pickAssignablePerms(source?.permissions, meIndustry));
            }}
          />
          <p className="muted" style={{ margin: 0 }}>
            Selecting a source copies permissions as an editable starting point. It does not copy
            users or keep a live link. Store assignments stay separate.
          </p>
          <PermissionGrid value={createPerms} onChange={setCreatePerms} industry={meIndustry} />
          <button type="submit" disabled={busy || !roleForm.key.trim() || !roleForm.label.trim()} aria-label="Create custom role">
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
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {managedCustomRoles.map((r) => (
              <li key={r.role}>
                {r.label} <code>{r.role}</code>
                {r.is_active === false ? (
                  <span className="muted" style={{ marginLeft: 6 }}>
                    [inactive]
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
              <li className="muted">No custom roles for this filter</li>
            )}
          </ul>
        </form>
      )}

      {canWrite && (
        <div className="card" style={{ margin: '20px 0', display: 'grid', gap: 12 }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Bulk import users</h2>
          <p className="muted" style={{ margin: 0 }}>
            Download the CSV template, fill rows (role must be a system role; temporary password must
            meet policy), validate, then import. Import is all-or-nothing.
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
      )}

      <select
        value={userManageFilter}
        onChange={(e) => setUserManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage user list by status"
        aria-label="User status filter"
        style={{ marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <input
        value={userQuery}
        onChange={(e) => setUserQuery(e.target.value)}
        placeholder={hideStoreUx ? 'Search name, email, department' : 'Search name, email, department, branch, store'}
        aria-label="Search users"
        style={{ marginLeft: 8, marginBottom: 8 }}
      />
      {!hideStoreUx ? (
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
        style={{ marginLeft: 8, marginBottom: 8 }}
      >
        <option value="">All branches</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      ) : null}
      {!hideStoreUx ? (
      <select
        value={storeFilter}
        onChange={(e) => setStoreFilter(e.target.value)}
        aria-label="Filter users by store"
        style={{ marginLeft: 8, marginBottom: 8 }}
      >
        <option value="">All stores</option>
        {storesForBranch(branchFilter).map((s) => (
          <option key={s.id} value={s.id}>
            {s.code} — {s.name}
          </option>
        ))}
      </select>
      ) : null}
      <select
        value={deptFilter}
        onChange={(e) => setDeptFilter(e.target.value)}
        aria-label="Filter users by department"
        style={{ marginLeft: 8, marginBottom: 8 }}
      >
        <option value="">All departments</option>
        {departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>

      <table className="table">
        <thead>
          <tr>
            <th>Full Name</th>
            <th>Email</th>
            <th>Role</th>
            {!hideStoreUx ? <th>Branch</th> : null}
            {!hideStoreAssign ? <th>Store</th> : null}
            <th>Department</th>
            <th>Scope</th>
            <th>Active</th>
            {canWrite && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {managedUsers.length === 0 && (
            <tr>
              <td colSpan={(canWrite ? 7 : 6) + (hideStoreUx ? 0 : 1) + (hideStoreAssign ? 0 : 1)} className="muted">
                {rows.length ? 'No users for this filter' : 'No users yet'}
              </td>
            </tr>
          )}
          {managedUsers.map((r) => (
            <tr key={r.id}>
              <td>
                {r.full_name}
                {r.is_active === false ? (
                  <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                    [inactive]
                  </span>
                ) : null}
              </td>
              <td>{r.email}</td>
              <td>
                {canWrite ? (
                  <select
                    value={r.role}
                    onChange={(e) => setRole(r.id, e.target.value)}
                    aria-label={`Change role for ${r.email}`}
                  >
                    {assignableRoles(r.role).map((role) => (
                      <option key={role.role} value={role.role}>
                        {role.label}
                        {isCustomRole(role) ? ' (custom)' : ''}
                        {role.is_active === false ? ' [inactive]' : ''}
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
                    {activeBranches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.code}
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
                    {activeDepartments(r.branch_id || undefined).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.code}
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
              <td>{r.is_active ? 'Yes' : 'No'}</td>
              {canWrite && (
                <td>
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
      {canWrite && permRole ? (
        <FormModal
          title={`Edit permissions: ${permRole}`}
          busy={permBusy}
          dirty={true}
          onClose={() => setPermRole(null)}
        >
          <p className="muted" style={{ marginTop: 0 }}>
            Existing RBAC modules only. This does not grant platform-owner rights. Changes apply to
            users with this custom role (nav, pages, buttons, and APIs).
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
    </>
  );
}
