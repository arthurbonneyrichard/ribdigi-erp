import {
  getBearerToken,
  prefersCookieSession,
  readBrowserCookie,
  CSRF_COOKIE_NAME,
} from './authSession';

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
  const token = getBearerToken();
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const workspaceKind =
    typeof window !== 'undefined' ? localStorage.getItem('workspace_kind') : null;
  const companyId = typeof window !== 'undefined' ? localStorage.getItem('company_id') : null;
  const headers: Record<string, string> = { ...(extra || {}) };
  // Phase B: prefer cookie session — omit Bearer when marker/CSRF indicates cookies.
  // Dual-mode: Bearer still sent when localStorage token exists and cookie mode is off.
  if (token) headers.Authorization = `Bearer ${token}`;
  if (tenant) headers['X-Tenant-ID'] = tenant;
  if (workspaceKind) headers['X-Workspace-Kind'] = workspaceKind;
  if (companyId && workspaceKind === 'company') headers['X-Company-ID'] = companyId;
  const csrf = readBrowserCookie(CSRF_COOKIE_NAME);
  if (csrf) headers['X-CSRF-Token'] = csrf;
  return headers;
}

/**
 * Authenticated fetch with credentials + auth headers.
 * Prefer this (or `api()`) over raw `localStorage.getItem('token')` + Bearer.
 */
export async function apiFetch(path: string, opts: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    ...authHeaders(opts.headers as Record<string, string> | undefined),
  };
  const url = path.startsWith('http') ? path : base + path;
  return fetch(url, {
    ...opts,
    headers,
    cache: opts.cache ?? 'no-store',
    credentials: 'include',
  });
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeaders(opts.headers as Record<string, string> | undefined),
  };

  // credentials: 'include' so httpOnly session cookies ride along when the
  // AUTH_HTTPONLY_COOKIES_ENABLED backend flag is turned on (no-op otherwise).
  const response = await fetch(base + path, {
    ...opts,
    headers,
    cache: 'no-store',
    credentials: 'include',
  });
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
  return body as T;
}

export { prefersCookieSession, getBearerToken };
