/**
 * SEC-M2 / SEC-M5 Phase B/C/D — dual-mode session helpers.
 *
 * When the server returns `cookie_session: true` (flag ON), the SPA must not
 * persist access/refresh JWTs in localStorage. Most traffic should ride
 * httpOnly cookies via `credentials: 'include'` + CSRF.
 *
 * Phase C (backend): when the flag is ON, login/2FA/refresh JSON returns null
 * access/refresh tokens so clients cannot keep writing Bearer tokens.
 * Flag default remains OFF; Bearer dual-mode via `getBearerToken()` remains
 * for backward compat until staging soak flips the flag with evidence.
 *
 * Phase D (SEC-M5): principal is held in memory from login JSON / GET /me —
 * never treat localStorage `principal` or the legacy JS-writable
 * `ribdigi_principal` cookie as authentication. Clear both on logout.
 */

export const COOKIE_SESSION_MARKER = 'ribdigi_cookie_session';
export const CSRF_COOKIE_NAME = 'ribdigi_csrf';
/** Legacy UX-only cookie name — cleared on login/logout; not an auth boundary. */
export const PRINCIPAL_COOKIE_NAME = 'ribdigi_principal';

export type LoginAuthPayload = {
  access_token?: string | null;
  refresh_token?: string | null;
  cookie_session?: boolean | null;
  user?: { tenant_id?: string; principal?: string; redirect_path?: string } | null;
  principal?: string | null;
  redirect_path?: string | null;
  must_enroll_2fa?: boolean | null;
};

/** In-memory principal (login or /me). Not durable; not an auth credential. */
let memoryPrincipal: string | null = null;

export function getMemoryPrincipal(): string | null {
  return memoryPrincipal;
}

export function setMemoryPrincipal(principal: string | null | undefined): void {
  const next = (principal || '').trim();
  memoryPrincipal = next || null;
}

/** Sync principal from authenticated GET /me (authoritative for SPA UX). */
export function applyPrincipalFromMe(
  me: { principal?: string | null } | null | undefined
): void {
  if (me?.principal) setMemoryPrincipal(me.principal);
}

export function readBrowserCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${name}=`;
  const hit = document.cookie.split('; ').find((row) => row.startsWith(prefix));
  if (!hit) return null;
  return decodeURIComponent(hit.slice(prefix.length));
}

/** Expire legacy forgeable principal cookie (Phase D — never re-set from JS). */
export function clearPrincipalCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${PRINCIPAL_COOKIE_NAME}=; path=/; Max-Age=0; SameSite=Lax`;
}

/** True when login indicated cookie session, or CSRF cookie is present. */
export function prefersCookieSession(): boolean {
  if (typeof window === 'undefined') return false;
  if (localStorage.getItem(COOKIE_SESSION_MARKER) === '1') return true;
  return Boolean(readBrowserCookie(CSRF_COOKIE_NAME));
}

export function isCookieSessionResponse(data: LoginAuthPayload | null | undefined): boolean {
  return Boolean(data?.cookie_session);
}

/**
 * Persist post-login workspace identity. When `cookie_session` is true, do
 * **not** write access/refresh tokens to localStorage (and clear any stale ones).
 *
 * Principal: memory only from login payload (then refreshed via /me). Do not
 * write localStorage `principal` or `ribdigi_principal` as an auth/routing
 * credential (SEC-M5 Phase D).
 */
export function persistLoginSession(data: LoginAuthPayload): void {
  if (typeof window === 'undefined') return;
  const tenantId = data.user?.tenant_id;
  if (tenantId) localStorage.setItem('tenant', tenantId);

  const principal = data.principal || data.user?.principal || 'tenant';
  setMemoryPrincipal(principal);
  // Phase D: stop treating LS / forgeable cookie as principal auth.
  localStorage.removeItem('principal');
  clearPrincipalCookie();

  if (isCookieSessionResponse(data)) {
    localStorage.setItem(COOKIE_SESSION_MARKER, '1');
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    return;
  }

  localStorage.removeItem(COOKIE_SESSION_MARKER);
  if (data.access_token) localStorage.setItem('token', data.access_token);
  if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
}

/** Clear Bearer tokens + cookie-session marker + principal memory (logout / idle). */
export function clearLoginSession(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem(COOKIE_SESSION_MARKER);
  localStorage.removeItem('principal');
  setMemoryPrincipal(null);
  clearPrincipalCookie();
}

/**
 * Bearer token for dual-mode. Returns null when cookie session is preferred so
 * callers omit Authorization and rely on httpOnly cookies.
 */
export function getBearerToken(): string | null {
  if (typeof window === 'undefined') return null;
  if (prefersCookieSession()) return null;
  return localStorage.getItem('token');
}

/**
 * Whether the SPA believes an auth session exists (Bearer or cookie path).
 * Never uses principal LS/cookie as proof of auth (SEC-M5).
 */
export function hasAuthSession(): boolean {
  if (typeof window === 'undefined') return false;
  if (localStorage.getItem('token')) return true;
  return prefersCookieSession();
}
