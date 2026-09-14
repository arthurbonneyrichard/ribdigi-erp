/**
 * SEC-M2 / SEC-M5 Phase B — dual-mode session helpers.
 *
 * When the server returns `cookie_session: true` (flag ON), the SPA must not
 * persist access/refresh JWTs in localStorage. Most traffic should ride
 * httpOnly cookies via `credentials: 'include'` + CSRF.
 *
 * Flag default remains OFF on the server; until Phase C removes remaining raw
 * `localStorage.getItem('token')` sites, Bearer dual-mode stays supported.
 */

export const COOKIE_SESSION_MARKER = 'ribdigi_cookie_session';
export const CSRF_COOKIE_NAME = 'ribdigi_csrf';

export type LoginAuthPayload = {
  access_token?: string | null;
  refresh_token?: string | null;
  cookie_session?: boolean | null;
  user?: { tenant_id?: string; principal?: string; redirect_path?: string } | null;
  principal?: string | null;
  redirect_path?: string | null;
  must_enroll_2fa?: boolean | null;
};

export function readBrowserCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${name}=`;
  const hit = document.cookie.split('; ').find((row) => row.startsWith(prefix));
  if (!hit) return null;
  return decodeURIComponent(hit.slice(prefix.length));
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
 */
export function persistLoginSession(data: LoginAuthPayload): void {
  if (typeof window === 'undefined') return;
  const tenantId = data.user?.tenant_id;
  if (tenantId) localStorage.setItem('tenant', tenantId);

  const principal = data.principal || data.user?.principal || 'tenant';
  localStorage.setItem('principal', principal);
  // SEC-M5 still OPEN: readable UX cookie for Next middleware console routing.
  document.cookie = `ribdigi_principal=${encodeURIComponent(principal)}; path=/; SameSite=Lax`;

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

/** Clear Bearer tokens + cookie-session marker (logout / idle). */
export function clearLoginSession(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem(COOKIE_SESSION_MARKER);
  localStorage.removeItem('principal');
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

/** Whether the SPA believes an auth session exists (Bearer or cookie path). */
export function hasAuthSession(): boolean {
  if (typeof window === 'undefined') return false;
  if (localStorage.getItem('token')) return true;
  return prefersCookieSession();
}
