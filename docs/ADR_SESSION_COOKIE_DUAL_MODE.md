# ADR: Dual-mode httpOnly session cookies (SEC-M2 / SEC-M5)

**Status:** Accepted (Phase A–D landed; **SEC-M5 FIXED**; **SEC-M2 OPEN** — staging soak remain)  
**Date:** 2026-09-14  
**Related:** `SECURITY_AUDIT.md` SEC-M2, SEC-M5 · `backend/app/session_cookies.py` · `frontend/lib/authSession.ts`

## Context

Browser sessions historically store access and refresh JWTs in `localStorage` and
send `Authorization: Bearer …`. XSS can exfiltrate those tokens. A separate
`ribdigi_principal` cookie was historically set from JavaScript for Next.js
middleware console routing only — it was **not** an authentication boundary
(SEC-M5). Phase D removes that anti-pattern.

Moving off `localStorage` JWTs to httpOnly cookies + CSRF is a multi-PR epic.
Flipping everything in one tip risks breaking auth across the ERP. This ADR
defines a **safe dual-mode** migration.

## Decision

1. **Feature flag** `AUTH_HTTPONLY_COOKIES_ENABLED` defaults **`false`**.
   Production tip remains Bearer/`localStorage` until the migration completes.
2. When enabled, login / 2FA / WebAuthn verify / refresh **also** set:
   - `ribdigi_access` — httpOnly, Secure (prod), SameSite (default Lax)
   - `ribdigi_refresh` — httpOnly, Secure (prod), SameSite
   - `ribdigi_csrf` — **not** httpOnly (readable so the SPA can send
     `X-CSRF-Token` — double-submit)
3. **`current_claims` dual-mode:** prefer `Authorization` Bearer; else, when the
   flag is on, accept the access cookie. Cookie-authenticated unsafe methods
   require matching CSRF header/cookie. Bearer and API-key auth skip CSRF.
4. **Phase C:** When the flag is ON, login / 2FA / WebAuthn verify / refresh JSON
   bodies return `access_token: null` and `refresh_token: null` with
   `cookie_session: true` so SPA clients cannot keep writing JWTs to
   `localStorage`. When the flag is OFF, JSON still returns Bearer tokens
   (backward compat). Helper: `session_cookies.json_auth_tokens`.
5. `GET /auth/csrf` rotates the CSRF cookie when the flag is on; reports
   `enabled: false` when off.
6. Frontend `lib/api.ts` sends `credentials: 'include'` and mirrors
   `ribdigi_csrf` into `X-CSRF-Token` when present.
7. **Phase B:** `frontend/lib/authSession.ts` helpers prefer cookie session when
   the server returns `cookie_session: true` (or CSRF cookie / marker is present).
   Login (`persistLoginSession`) **does not** write access/refresh to
   `localStorage` in that mode. Central `authHeaders` / `api` / `apiFetch` omit
   Bearer when cookie mode is preferred. **App/component pages no longer call
   `localStorage.getItem('token')` directly** — they use `apiFetch` /
   `authHeaders` / `authSession` (helpers still read the token for dual-mode
   Bearer when the flag is OFF).
8. **Phase D (SEC-M5 FIXED):** Principal is held **in memory** from login JSON
   and refreshed from authenticated `GET /me` (`applyPrincipalFromMe`). The SPA
   **never** treats `localStorage.principal` or the legacy JS-writable
   `ribdigi_principal` cookie as authentication. `persistLoginSession` /
   `clearLoginSession` clear any legacy LS principal blob and expire the
   principal cookie. Next middleware **no longer redirects** based on that
   cookie (it only clears stale values). Console boundary = Shell /
   PlatformShell `/me` redirects + backend platform-vs-tenant enforcement.

## Non-goals

- Claiming SEC-M2 **FIXED** (staging soak + evidence that Bearer/`localStorage`
  path is unused with flag ON still required)
- Enabling the flag by default in production examples
- Offline Complete / go-live / ADR-005 / paid billing Completes

## Migration phases

| Phase | Work | Closes |
|-------|------|--------|
| **A** | Flag OFF by default; cookie issuance + cookie auth + CSRF scaffold + tests + `credentials: 'include'` | Foundation only |
| **B** | Client helpers; stop writing tokens on login when `cookie_session`; central `api`/`apiFetch`; migrate remaining SPA raw token fetch sites | Partial M2 (still OPEN) |
| **C** | When flag ON, null JSON `access_token`/`refresh_token` on login/2FA/refresh; keep JSON tokens when flag OFF; tests | Partial M2 (still OPEN — staging soak required before FIXED) |
| **D (this slice)** | Replace `ribdigi_principal` UX cookie / LS principal with in-memory principal from login + `/me`; clear on logout; middleware stops trusting forgeable cookie | **SEC-M5 FIXED** |

Phase C/D alone do **not** mark M2 FIXED: production default remains flag OFF,
Bearer/`localStorage` dual-mode still exists when OFF, and staging soak with
flag ON + evidence that the LS path is unused is still required.

## Consequences

- Tip stays safe with flag default OFF.
- Enabling the flag without staging soak evidence still leaves residual M2 risk —
  do **not** mark M2 FIXED until cookies are the auth boundary end-to-end with
  evidence.
- CSRF is mandatory only for cookie auth; existing Bearer clients unchanged when
  flag OFF.
- CORS already allows credentials; `X-CSRF-Token` is on the allowlist.
- Console soft-routing no longer depends on a forgeable client cookie.

## Honesty

**SEC-M5** is **FIXED** (Phase D). **SEC-M2** remains **OPEN** (Phase C PARTIAL;
staging soak outstanding). Overall security status stays
`🟠 SECURITY FIXES REQUIRED BEFORE LAUNCH` while M2 is open. Do **not** mark
M2 FIXED on this slice.
