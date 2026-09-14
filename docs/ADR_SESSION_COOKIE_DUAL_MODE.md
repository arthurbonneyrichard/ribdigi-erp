# ADR: Dual-mode httpOnly session cookies (SEC-M2 / SEC-M5)

**Status:** Accepted (Phase A–C landed; M2/M5 still OPEN — staging soak + Phase D remain)  
**Date:** 2026-09-14  
**Related:** `SECURITY_AUDIT.md` SEC-M2, SEC-M5 · `backend/app/session_cookies.py` · `frontend/lib/authSession.ts`

## Context

Browser sessions historically store access and refresh JWTs in `localStorage` and
send `Authorization: Bearer …`. XSS can exfiltrate those tokens. A separate
`ribdigi_principal` cookie is set from JavaScript for Next.js middleware console
routing only — it is **not** an authentication boundary (SEC-M5).

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
8. `ribdigi_principal` remains a UX/routing cookie until a later slice replaces
   console-boundary checks with a server-readable session signal.

## Non-goals (Phases A–C)

- Claiming SEC-M2 or SEC-M5 **FIXED** (staging soak + evidence still required for M2;
  Phase D required for M5)
- Replacing `ribdigi_principal` with a secure session principal (Phase D)
- Enabling the flag by default in production examples
- Offline Complete / go-live / ADR-005 / paid billing Completes

## Migration phases

| Phase | Work | Closes |
|-------|------|--------|
| **A** | Flag OFF by default; cookie issuance + cookie auth + CSRF scaffold + tests + `credentials: 'include'` | Foundation only |
| **B** | Client helpers; stop writing tokens on login when `cookie_session`; central `api`/`apiFetch`; migrate remaining SPA raw token fetch sites | Partial M2 (still OPEN) |
| **C (this slice)** | When flag ON, null JSON `access_token`/`refresh_token` on login/2FA/refresh; keep JSON tokens when flag OFF; tests | Partial M2 (still OPEN — staging soak required before FIXED) |
| D | Replace `ribdigi_principal` UX cookie with derived session/principal from httpOnly path | M5 FIXED |

Phase C alone does **not** mark M2 FIXED: production default remains flag OFF,
Bearer/`localStorage` dual-mode still exists when OFF, and staging soak with
flag ON + evidence that the LS path is unused is still required.

## Consequences

- Tip stays safe with flag default OFF.
- Enabling the flag without staging soak evidence still leaves residual risk —
  do **not** mark M2 FIXED until cookies are the auth boundary end-to-end with
  evidence.
- CSRF is mandatory only for cookie auth; existing Bearer clients unchanged when
  flag OFF.
- CORS already allows credentials; `X-CSRF-Token` is on the allowlist.

## Honesty

SEC-M2 and SEC-M5 remain **OPEN** (Phase C PARTIAL progress on M2; Phase D not
started for M5). Overall security status stays
`🟠 SECURITY FIXES REQUIRED BEFORE LAUNCH` until Phase C staging soak + Phase D
land with evidence. Do **not** mark M2 FIXED on this slice alone.
