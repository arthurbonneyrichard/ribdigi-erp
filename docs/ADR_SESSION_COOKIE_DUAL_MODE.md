# ADR: Dual-mode httpOnly session cookies (SEC-M2 / SEC-M5)

**Status:** Accepted (Phase A–E landed; **SEC-M2 FIXED**; **SEC-M5 FIXED**)  
**Date:** 2026-09-14  
**Related:** `SECURITY_AUDIT.md` SEC-M2, SEC-M5 · `backend/app/session_cookies.py` · `frontend/lib/authSession.ts` · `backend/tests/test_sec_m2_cookie_soak.py`

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
   Production tip remains Bearer/`localStorage` until operators enable the flag
   on staging/prod (cutover step — not an open SEC finding once Phase E soak
   evidence exists).
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
9. **Phase E (SEC-M2 FIXED):** Automated flag-ON soak suite proves login / 2FA /
   refresh null JSON + cookies, cookie-only auth, CSRF on mutating methods,
   logout/idle cookie clear, and SPA LS skip. Operator staging checklist remains
   for Secure/SameSite/domain cutover — not a code gap.

## Non-goals

- Flipping `AUTH_HTTPONLY_COOKIES_ENABLED` default to **true** in production
  examples (ops enable remains intentional)
- Offline Complete / go-live / ADR-005 / paid billing Completes

## Migration phases

| Phase | Work | Closes |
|-------|------|--------|
| **A** | Flag OFF by default; cookie issuance + cookie auth + CSRF scaffold + tests + `credentials: 'include'` | Foundation only |
| **B** | Client helpers; stop writing tokens on login when `cookie_session`; central `api`/`apiFetch`; migrate remaining SPA raw token fetch sites | Foundation |
| **C** | When flag ON, null JSON `access_token`/`refresh_token` on login/2FA/refresh; keep JSON tokens when flag OFF; tests | Foundation |
| **D** | Replace `ribdigi_principal` UX cookie / LS principal with in-memory principal from login + `/me`; clear on logout; middleware stops trusting forgeable cookie | **SEC-M5 FIXED** |
| **E (this slice)** | Automated flag-ON soak evidence + operator staging checklist; honesty FIXED; flag default stays OFF | **SEC-M2 FIXED** |

## Consequences

- Tip stays safe with flag default OFF until ops enable on staging/prod.
- CSRF is mandatory only for cookie auth; existing Bearer clients unchanged when
  flag OFF.
- CORS already allows credentials; `X-CSRF-Token` is on the allowlist.
- Console soft-routing no longer depends on a forgeable client cookie.

## Honesty

**SEC-M2** and **SEC-M5** are **FIXED**. Overall security status is
`✅ HARDENED` (no open Critical/High/Medium). Flag default OFF is intentional —
production enable is an ops cutover step documented in
`/opt/cursor/artifacts/sec_m2_staging_soak_checklist.md`. Do **not** claim
go-live / Offline Complete / ADR-005 / paid billing Completes on this slice.
