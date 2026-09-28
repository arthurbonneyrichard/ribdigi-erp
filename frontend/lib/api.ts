import { clearSessionTheme } from './theme';

/** Browser calls the Next.js origin; Next rewrites /api/v1 to the backend (avoids CORS Failed to fetch). */
export function apiRoot(): string {
  if (typeof window !== 'undefined') return '/api/v1';
  const raw =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1';
  return raw.replace(/\/$/, '');
}

const base = apiRoot();

// Backend X-Tenant-ID is UuidIdValue — slugs like platform must not be sent
// or /me returns 422 and Shell clears the session back to login.
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function tenantHeaderValue(raw: string | null): string | null {
  const value = (raw || '').trim();
  if (!value || !UUID_RE.test(value)) return null;
  return value;
}

/** Sign-in and recovery must not send a leftover Platform/tenant session. */
function isPublicAuthPath(path: string): boolean {
  return (
    path.startsWith('/auth/login') ||
    path.startsWith('/auth/refresh') ||
    path.startsWith('/auth/2fa/verify') ||
    path.startsWith('/auth/password-reset') ||
    path.startsWith('/auth/verify-email') ||
    path.startsWith('/auth/resend-verification') ||
    path.startsWith('/auth/webauthn/login')
  );
}

export function unreachableApiMessage(): string {
  return 'Cannot reach the server. Check that the API is running, then sign in with the workspace slug (not the company name).';
}

// Shared in-flight refresh so concurrent 401s trigger a single token refresh.
let refreshPromise: Promise<boolean> | null = null;

/** Clear local auth and send the user to login (used on 401 and idle timeout). */
export function clearSessionAndRedirect() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant');
  try {
    sessionStorage.clear();
  } catch {
    /* ignore */
  }
  clearSessionTheme();
  void import('./meCache')
    .then((m) => m.invalidateMeCache())
    .catch(() => undefined);
  void import('./prefetchCache')
    .then((m) => m.invalidatePrefetchCache())
    .catch(() => undefined);
  if (window.location.pathname !== '/') {
    window.location.replace('/');
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
    if (code === 503) return 'This extra is not ready on the server yet. Rooms and reservations still work.';
    if (code >= 500) return 'Could not complete that. Try again. Hotel extras may need a database update; rooms and reservations are separate.';
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

/** Same-origin fetch with auth headers. Use for blobs/PDFs; JSON callers use `api()`. */
export async function apiFetch(path: string, opts: RequestInit = {}, retryOn401 = true): Promise<Response> {
  const publicAuth = isPublicAuthPath(path);
  const token = typeof window !== 'undefined' && !publicAuth ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' && !publicAuth ? localStorage.getItem('tenant') : null;
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

  const controller = new AbortController();
  const timeoutMs = isFormData ? 60000 : 20000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(base + path, {
      ...opts,
      headers,
      cache: 'no-store',
      signal: opts.signal ?? controller.signal,
    });
  } catch (err: unknown) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('The request timed out. Check your connection and try again.');
    }
    const raw = err instanceof Error ? err.message : '';
    if (!raw || /failed to fetch|networkerror|load failed/i.test(raw)) {
      throw new Error(unreachableApiMessage());
    }
    throw err;
  }
  clearTimeout(timer);

  if (response.status === 401 && retryOn401 && !path.startsWith('/auth/') && typeof window !== 'undefined') {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiFetch(path, opts, false);
    }
    clearSessionAndRedirect();
  }

  return response;
}

export async function api(path: string, opts: RequestInit = {}, retryOn401 = true) {
  const response = await apiFetch(path, opts, retryOn401);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: unknown }).detail;
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
