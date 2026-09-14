# ADR: Dual-mode httpOnly session cookies (SEC-M2 / SEC-M5)

**Status:** Accepted (Phase A foundation + Phase B client migration started; M2/M5 still OPEN)  
**Date:** 2026-09-14  
**Related:** `SECURITY_AUDIT.md` SEC-M2, SEC-M5 · `backend/app/session_cookies.py` · `frontend/lib/authSession.ts`

## Context

Browser sessions historically store access and refresh JWTs in `localStorage` and
send `Authorization: Bearer …`. XSS can exfiltrate those tokens. A separate
`ribdigi_principal` cookie is set from JavaScript for Next.js middleware console
routing only — it is **not** an authentication boundary (SEC-M5).

Moving remaining raw `localStorage.getItem('token')` call sites off to httpOnly
cookies + CSRF is a multi-PR epic. Flipping everything in one tip risks breaking
auth across the ERP. This ADR defines a **safe dual-mode** migration.

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
4. JSON bodies **continue** to return `access_token` / `refresh_token` during
   dual-mode so existing clients keep working (Phase C may stop returning them).
5. `GET /auth/csrf` rotates the CSRF cookie when the flag is on; reports
   `enabled: false` when off.
6. Frontend `lib/api.ts` sends `credentials: 'include'` and mirrors
   `ribdigi_csrf` into `X-CSRF-Token` when present.
7. **Phase B:** `frontend/lib/authSession.ts` helpers prefer cookie session when
   the server returns `cookie_session: true` (or CSRF cookie / marker is present).
   Login (`persistLoginSession`) **does not** write access/refresh to
   `localStorage` in that mode. Central `authHeaders` / `api` / `apiFetch` omit
   Bearer when cookie mode is preferred so most `api()` traffic inherits cookies.
   High-traffic raw fetch sites (dashboard exports, POS downloads, Shell
   onboarding CSV, platform evidence) migrated to `apiFetch`.
8. `ribdigi_principal` remains a UX/routing cookie until a later slice replaces
   console-boundary checks with a server-readable session signal.

## Non-goals (Phases A–B)

- Sweeping **all** remaining raw `localStorage.getItem('token')` sites (Phase C)
- Claiming SEC-M2 or SEC-M5 **FIXED**
- Replacing `ribdigi_principal` with a secure session principal (Phase D)
- Enabling the flag by default in production examples
- Offline Complete / go-live / ADR-005 / paid billing Completes

## Migration phases

| Phase | Work | Closes |
|-------|------|--------|
| **A** | Flag OFF by default; cookie issuance + cookie auth + CSRF scaffold + tests + `credentials: 'include'` | Foundation only |
| **B (this slice)** | Client helpers; stop writing tokens on login when `cookie_session`; central `api`/`apiFetch` prefer cookies; migrate high-traffic downloads | Partial M2 (still OPEN) |
| C | Remove remaining raw token `localStorage` sites; optionally stop returning tokens in JSON; harden Secure+SameSite for prod | M2 FIXED |
| D | Replace `ribdigi_principal` UX cookie with derived session/principal from httpOnly path | M5 FIXED |

## Consequences

- Tip stays safe with flag default OFF.
- Enabling the flag without finishing Phase C still leaves some raw Bearer
  fetch sites and JSON token returns — do **not** mark M2 FIXED until storage
  is gone end-to-end.
- CSRF is mandatory only for cookie auth; existing Bearer clients unchanged.
- CORS already allows credentials; `X-CSRF-Token` is on the allowlist.

## Honesty

SEC-M2 and SEC-M5 remain **OPEN** (Phase B PARTIAL progress only). Overall
security status stays `🟠 SECURITY FIXES REQUIRED BEFORE LAUNCH` until Phase
C/D land with evidence.
