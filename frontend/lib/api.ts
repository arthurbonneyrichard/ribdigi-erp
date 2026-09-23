import { clearSessionTheme } from './theme';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Backend X-Tenant-ID is UuidIdValue — slugs like platform must not be sent
// or /me returns 422 and Shell clears the session back to login.
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function tenantHeaderValue(raw: string | null): string | null {
  const value = (raw || '').trim();
  if (!value || !UUID_RE.test(value)) return null;
  return value;
}

// Shared in-flight refresh so concurrent 401s trigger a single token refresh.
let refreshPromise: Promise<boolean> | null = null;

/** Clear local auth and send the user to login (used on 401 and idle timeout). */
export function clearSessionAndRedirect() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant');
  clearSessionTheme();
  void import('./meCache')
    .then((m) => m.invalidateMeCache())
    .catch(() => undefined);
  void import('./prefetchCache')
    .then((m) => m.invalidatePrefetchCache())
    .catch(() => undefined);
  if (window.location.pathname !== '/') {
    window.location.href = '/';
  }
}

/** Default client idle auto-logout (BR-19.3). Prefer tenant `inactivity_timeout_minutes` from `/me`. */
export const DEFAULT_IDLE_TIMEOUT_MINUTES = 30;
export const IDLE_LOGOUT_MS = DEFAULT_IDLE_TIMEOUT_MINUTES * 60 * 1000;

export function idleTimeoutMs(minutes?: number | null): number {
  const n = Number(minutes);
  if (!Number.isFinite(n)) return IDLE_LOGOUT_MS;
  const clamped = Math.min(480, Math.max(5, Math.round(n)));
  return clamped * 60 * 1000;
}

async function refreshSession(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  const raw = localStorage.getItem('refresh_token');
  const trimmedRefreshToken = (raw || '').trim();
  if (!trimmedRefreshToken) return false;
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const r = await fetch(base + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: trimmedRefreshToken }),
          cache: 'no-store',
        });
        if (!r.ok) return false;
        const body = await r.json().catch(() => ({}));
        const data = body?.data || body;
        if (!data?.access_token) return false;
        localStorage.setItem('token', data.access_token);
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
        return true;
      } catch {
        return false;
      }
    })();
    refreshPromise.finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/** Safe user-facing API error. Never include tokens, passwords, SQL, or stack traces. */
export function formatApiError(body: unknown, status: number): string {
  const fallbackByStatus = (code: number): string => {
    if (code === 401) return 'Your session expired. Please sign in again.';
    if (code === 403) return 'You do not have permission to do that.';
    if (code === 404) return 'Not found.';
    if (code === 409) return 'That record already exists.';
    if (code === 422) return 'Some fields are invalid. Check email, role, phone (E.164), and password.';
    if (code === 503) return 'The service is busy. Try again in a moment.';
    if (code >= 500) return 'The server could not complete this request.';
    return 'Request failed';
  };
  const looksUnsafe = (text: string): boolean => {
    const t = text.trim();
    if (!t || t.length > 280) return true;
    if (/[<>]/.test(t)) return true;
    if (/\b(bearer\s+[a-z0-9._-]+|eyJ[A-Za-z0-9_-]{20,}|postgres|sqlalchemy|traceback|stack trace)\b/i.test(t)) {
      return true;
    }
    return false;
  };
  const cleanMsg = (raw: unknown): string => {
    if (typeof raw !== 'string') return '';
    const text = raw.replace(/^Value error,\s*/i, '').trim();
    if (!text || looksUnsafe(text)) return '';
    return text;
  };

  const payload = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const detail = payload.detail;
  if (typeof detail === 'string') {
    const text = cleanMsg(detail);
    if (text) return text;
  } else if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const rec = detail as Record<string, unknown>;
    const text = cleanMsg(rec.message) || cleanMsg(rec.msg);
    if (text) return text;
  } else if (Array.isArray(detail)) {
    const parts: string[] = [];
    for (const item of detail) {
      if (typeof item === 'string') {
        const text = cleanMsg(item);
        if (text) parts.push(text);
        continue;
      }
      if (!item || typeof item !== 'object') continue;
      const rec = item as Record<string, unknown>;
      let text = cleanMsg(rec.msg) || cleanMsg(rec.message);
      const loc = Array.isArray(rec.loc) ? rec.loc : [];
      const field = loc.find((x) => typeof x === 'string' && x !== 'body' && x !== 'query');
      if (field === 'password' && text) {
        text = 'Password is invalid. Use at least 8 characters with upper, lower, number, and symbol.';
      } else if (typeof field === 'string' && field !== 'password' && text && !looksUnsafe(field)) {
        text = `${field}: ${text}`;
      }
      if (text) parts.push(text);
    }
    if (parts.length) return parts.join(' ');
  }
  const top = cleanMsg(payload.message);
  if (top) return top;
  return fallbackByStatus(status);
}

export async function api(path: string, opts: RequestInit = {}, retryOn401 = true) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const isFormData = typeof FormData !== 'undefined' && opts.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const tenantId = tenantHeaderValue(tenant);
  if (tenantId) headers['X-Tenant-ID'] = tenantId;
  // Let the browser set multipart boundary for FormData
  if (isFormData) delete headers['Content-Type'];

  const response = await fetch(base + path, { ...opts, headers, cache: 'no-store' });

  // Session expired: try a one-time refresh + retry, otherwise send back to login.
  // Auth endpoints are excluded so the login/2FA flow is never disrupted.
  if (response.status === 401 && retryOn401 && !path.startsWith('/auth/') && typeof window !== 'undefined') {
    const refreshed = await refreshSession();
    if (refreshed) {
      return api(path, opts, false);
    }
    clearSessionAndRedirect();
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = formatApiError(body, response.status);
    const err = new Error(message) as Error & { detail?: unknown; status?: number };
    err.detail = detail;
    err.status = response.status;
    throw err;
  }
  return body;
}

/** Load a GET without failing sibling Promise.all calls (pages must not stay on Loading). */
export async function apiOptional(path: string, opts: RequestInit = {}) {
  try {
    const body = await api(path, opts);
    return { ...body, error: null as string | null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Request failed';
    return { data: null, message: undefined, error: message };
  }
}
