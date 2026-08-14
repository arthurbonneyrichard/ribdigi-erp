const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  code?: string;
  status?: number;

  constructor(message: string, opts?: { code?: string; status?: number }) {
    super(message);
    this.name = 'ApiError';
    this.code = opts?.code;
    this.status = opts?.status;
  }
}

/** Auth + workspace headers for raw fetch/download calls (mirrors `api()`). */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const workspaceKind =
    typeof window !== 'undefined' ? localStorage.getItem('workspace_kind') : null;
  const companyId = typeof window !== 'undefined' ? localStorage.getItem('company_id') : null;
  const headers: Record<string, string> = { ...(extra || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (tenant) headers['X-Tenant-ID'] = tenant;
  if (workspaceKind) headers['X-Workspace-Kind'] = workspaceKind;
  if (companyId && workspaceKind === 'company') headers['X-Company-ID'] = companyId;
  return headers;
}

export async function api(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeaders(opts.headers as Record<string, string> | undefined),
  };

  const response = await fetch(base + path, { ...opts, headers, cache: 'no-store' });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || detail?.code || body.message || 'Request failed';
    const code = typeof detail === 'object' && detail ? detail.code : undefined;
    throw new ApiError(message, { code, status: response.status });
  }
  return body;
}
