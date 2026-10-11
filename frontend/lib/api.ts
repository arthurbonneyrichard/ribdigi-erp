import { clearSessionTheme } from './theme';
import { bumpLastActivity } from './idleSession';
import {
  clearAuthTokens,
  getAccessTokenSync,
  getRefreshTokenSync,
  hydrateAuth,
  setAuthTokens,
} from './authStorage';

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

export type ApiClientError = Error & {
  detail?: unknown;
  status?: number;
  retryAfter?: number;
  requestId?: string;
};

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

export function parseRetryAfterHeader(raw: string | null, now = Date.now()): number {
  const text = (raw || '').trim();
  if (!text) return 1;
  const seconds = Number(text);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.max(1, Math.min(60, Math.ceil(seconds)));
  const when = Date.parse(text);
  if (Number.isFinite(when)) {
    return Math.max(1, Math.min(60, Math.ceil((when - now) / 1000)));
  }
  return 1;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function requestMethod(opts: RequestInit): string {
  return String(opts.method || 'GET').toUpperCase();
}

function isGetLike(opts: RequestInit): boolean {
  const method = requestMethod(opts);
  return (method === 'GET' || method === 'HEAD') && !opts.body;
}

export function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const name = (err as { name?: string }).name;
  if (name === 'AbortError') return true;
  const msg = String((err as { message?: string }).message || '');
  return /the operation was aborted|request aborted|aborted without reason/i.test(msg);
}

function inflightKey(path: string): string {
  const tenant = typeof window !== 'undefined' ? tenantHeaderValue(localStorage.getItem('tenant')) || '' : '';
  return `${tenant || '_'}::${path}`;
}

function mergeAbortSignals(timeoutMs: number, userSignal?: AbortSignal | null): {
  signal: AbortSignal;
  cleanup: () => void;
  timedOut: () => boolean;
} {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onUserAbort = () => {
    if (!controller.signal.aborted) controller.abort();
  };
  if (userSignal) {
    if (userSignal.aborted) onUserAbort();
    else userSignal.addEventListener('abort', onUserAbort, { once: true });
  }
  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer);
      if (userSignal) userSignal.removeEventListener('abort', onUserAbort);
    },
    timedOut: () => timedOut,
  };
}

// Shared in-flight refresh so concurrent 401s trigger a single token refresh.
let refreshPromise: Promise<boolean> | null = null;
const inflightGets = new Map<string, Promise<any>>();
const getBackoffUntil = new Map<string, number>();
const GET_429_MAX_RETRIES = 2;
const GET_429_MAX_WAIT_MS = 8_000;

/** Confirmed unauthenticated only — never treat 403/429/5xx as expiry. */
export function isConfirmedAuthExpiry(err: unknown): boolean {
  const status = (err as { status?: number })?.status;
  return status === 401;
}

/** Clear local auth and send the user to login (used on 401 and idle timeout). */
export function clearSessionAndRedirect() {
  if (typeof window === 'undefined') return;
  void clearAuthTokens();
  localStorage.removeItem('tenant');
  try {
    sessionStorage.removeItem('ribdigi:uid');
    sessionStorage.removeItem('ribdigi:store');
  } catch {
    /* ignore */
  }
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
  void import('./posOffline')
    .then((m) => m.clearOfflineOnLogout())
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
  await hydrateAuth();
  const trimmedRefreshToken = (getRefreshTokenSync() || '').trim();
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
        await setAuthTokens(data.access_token, data.refresh_token || trimmedRefreshToken);
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
export function formatApiError(body: unknown, status: number, path?: string): string {
  const hotelRequest = typeof path === 'string' && path.includes('/hotel/');
  const fallbackByStatus = (code: number): string => {
    if (code === 401) return 'Your session expired. Please sign in again.';
    if (code === 403) return 'You do not have permission to do that.';
    if (code === 404) return 'Not found.';
    if (code === 409) return 'That record already exists.';
    if (code === 422) return 'Some fields are invalid. Check email, role, phone (E.164), and password.';
    if (code === 429) return 'Too many requests. Wait a moment, then retry.';
    if (code === 503) return 'This extra is not ready on the server yet. Rooms and reservations still work.';
    if (code >= 500) {
      if (hotelRequest) {
        return 'Could not complete that. Try again. Hotel extras may need a database update; rooms and reservations are separate.';
      }
      return 'Could not complete that. Try again.';
    }
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
    if (/^RATE_LIMIT_EXCEEDED$/i.test(text)) return '';
    return text;
  };

  if (status === 429) {
    const payload = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
    const msg = cleanMsg(payload.message);
    if (msg) return msg;
    return fallbackByStatus(429);
  }

  const payload = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const detail = payload.detail;
  if (typeof detail === 'string') {
    const text = cleanMsg(detail);
    if (text) return text;
  } else if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const rec = detail as Record<string, unknown>;
    const text = cleanMsg(rec.message) || cleanMsg(rec.msg);
    if (text) return text;
    const fieldParts: string[] = [];
    for (const [key, val] of Object.entries(rec)) {
      const msg = cleanMsg(val);
      if (!msg) continue;
      if (looksUnsafe(key)) fieldParts.push(msg);
      else fieldParts.push(`${key}: ${msg}`);
    }
    if (fieldParts.length) return fieldParts.join(' ');
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

function attachApiError(
  body: unknown,
  status: number,
  retryAfter?: number,
  requestId?: string,
  path?: string
): ApiClientError {
  const err = new Error(formatApiError(body, status, path)) as ApiClientError;
  err.detail = body && typeof body === 'object' ? (body as { detail?: unknown }).detail : undefined;
  err.status = status;
  if (retryAfter && retryAfter > 0) err.retryAfter = retryAfter;
  const fromBody =
    body && typeof body === 'object' && typeof (body as { request_id?: unknown }).request_id === 'string'
      ? String((body as { request_id: string }).request_id)
      : '';
  const rid = (requestId || fromBody).trim();
  if (rid) err.requestId = rid;
  return err;
}

export { getAccessTokenSync as getAccessToken, setAuthTokens, hydrateAuth };

/** Same-origin fetch with auth headers. Use for blobs/PDFs; JSON callers use `api()`. */
export async function apiFetch(path: string, opts: RequestInit = {}, retryOn401 = true): Promise<Response> {
  const publicAuth = isPublicAuthPath(path);
  if (typeof window !== 'undefined') await hydrateAuth();
  const token = typeof window !== 'undefined' && !publicAuth ? getAccessTokenSync() : null;
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

  const timeoutMs = isFormData ? 60000 : 20000;
  const merged = mergeAbortSignals(timeoutMs, opts.signal ?? null);
  let response: Response;
  try {
    response = await fetch(base + path, {
      ...opts,
      headers,
      cache: 'no-store',
      signal: merged.signal,
    });
  } catch (err: unknown) {
    merged.cleanup();
    if (isAbortError(err) || (err instanceof DOMException && err.name === 'AbortError')) {
      if (opts.signal?.aborted) {
        const aborted = new DOMException('The operation was aborted.', 'AbortError');
        throw aborted;
      }
      if (merged.timedOut()) {
        throw new Error('The request timed out. Check your connection and try again.');
      }
      const aborted = new DOMException('The operation was aborted.', 'AbortError');
      throw aborted;
    }
    const raw = err instanceof Error ? err.message : '';
    if (!raw || /failed to fetch|networkerror|load failed/i.test(raw)) {
      throw new Error(unreachableApiMessage());
    }
    throw err;
  }
  merged.cleanup();

  if (response.status === 401 && retryOn401 && !path.startsWith('/auth/') && typeof window !== 'undefined') {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiFetch(path, opts, false);
    }
    clearSessionAndRedirect();
  }

  return response;
}

async function apiOnce(path: string, opts: RequestInit, retryOn401: boolean, getRetries: number): Promise<any> {
  const response = await apiFetch(path, opts, retryOn401);
  const body = await response.json().catch(() => ({}));
  const requestId = response.headers.get('X-Request-ID') || undefined;
  if (response.status === 429) {
    const retryAfter = parseRetryAfterHeader(response.headers.get('Retry-After'));
    const method = requestMethod(opts);
    if (method === 'GET' && getRetries < GET_429_MAX_RETRIES) {
      const backoffKey = inflightKey(path);
      const untilExisting = getBackoffUntil.get(backoffKey) || 0;
      const now = Date.now();
      if (untilExisting > now) {
        throw attachApiError(body, 429, Math.ceil((untilExisting - now) / 1000), requestId, path);
      }
      const waitMs = Math.min(GET_429_MAX_WAIT_MS, Math.max(1000, retryAfter * 1000));
      getBackoffUntil.set(backoffKey, now + waitMs);
      await sleep(waitMs);
      if (opts.signal?.aborted) {
        throw new DOMException('The operation was aborted.', 'AbortError');
      }
      return apiOnce(path, opts, retryOn401, getRetries + 1);
    }
    throw attachApiError(body, 429, retryAfter, requestId, path);
  }
  if (!response.ok) {
    throw attachApiError(body, response.status, undefined, requestId, path);
  }
  if (typeof window !== 'undefined' && !isGetLike(opts) && !isPublicAuthPath(path)) {
    bumpLastActivity();
  }
  return body;
}

export async function api(path: string, opts: RequestInit = {}, retryOn401 = true): Promise<any> {
  // Do not share in-flight GETs that the caller may abort (stale search / navigation).
  if (isGetLike(opts) && !opts.signal) {
    const key = inflightKey(path);
    const pending = inflightGets.get(key);
    if (pending) return pending;
    const run = apiOnce(path, opts, retryOn401, 0).finally(() => {
      inflightGets.delete(key);
    });
    inflightGets.set(key, run);
    return run;
  }
  return apiOnce(path, opts, retryOn401, 0);
}

/** Load a GET without failing sibling Promise.all calls (pages must not stay on Loading). */
export async function apiOptional(path: string, opts: RequestInit = {}) {
  try {
    const body = await api(path, opts);
    return { ...body, error: null as string | null };
  } catch (err: unknown) {
    if (isAbortError(err)) {
      return { data: null, message: undefined, error: null as string | null, aborted: true as const };
    }
    const message = err instanceof Error ? err.message : 'Request failed';
    return { data: null, message: undefined, error: message };
  }
}

export function resetApiGetCoalescing() {
  inflightGets.clear();
  getBackoffUntil.clear();
}
