# ADR: Dual-mode httpOnly session cookies (SEC-M2 / SEC-M5)

**Status:** Accepted (foundation slice; migration incomplete)  
**Date:** 2026-09-14  
**Related:** `SECURITY_AUDIT.md` SEC-M2, SEC-M5 · `backend/app/session_cookies.py`

## Context

Browser sessions today store access and refresh JWTs in `localStorage` and send
`Authorization: Bearer …`. XSS can exfiltrate those tokens. A separate
`ribdigi_principal` cookie is set from JavaScript for Next.js middleware console
routing only — it is **not** an authentication boundary (SEC-M5).

Moving ~33 frontend call sites off `localStorage` to httpOnly cookies + CSRF is
a multi-PR epic. Flipping everything in one tip risks breaking auth across the
ERP. This ADR defines a **safe dual-mode foundation**.

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
   dual-mode so existing clients keep working.
5. `GET /auth/csrf` rotates the CSRF cookie when the flag is on; reports
   `enabled: false` when off.
6. Frontend `lib/api.ts` sends `credentials: 'include'` and mirrors
   `ribdigi_csrf` into `X-CSRF-Token` when present — without removing
   localStorage Bearer usage yet.
7. `ribdigi_principal` remains a UX/routing cookie until a later slice replaces
   console-boundary checks with a server-readable session signal.

## Non-goals (this slice)

- Removing `localStorage` token writes from login or ~33 call sites
- Claiming SEC-M2 or SEC-M5 **FIXED**
- Replacing `ribdigi_principal` with a secure session principal
- Offline Complete / go-live / ADR-005 / paid billing Completes

## Migration phases (recommended)

| Phase | Work | Closes |
|-------|------|--------|
| **A (this ADR)** | Flag OFF by default; cookie issuance + cookie auth + CSRF scaffold + tests + `credentials: 'include'` | Foundation only |
| B | Enable flag in staging; migrate shared `api()` / `authHeaders` consumers; stop writing tokens on login when cookie_session true | Partial M2 |
| C | Remove remaining raw `localStorage.getItem('token')` sites; stop returning tokens in JSON (or return empty); Secure+SameSite hardened for prod | M2 FIXED |
| D | Replace `ribdigi_principal` UX cookie with derived session/principal from httpOnly path or short-lived non-secret routing claim | M5 FIXED |

## Consequences

- Tip stays safe with flag default OFF.
- Enabling the flag without finishing Phase B/C still leaves XSS-exfiltrable
  tokens in localStorage — do **not** mark M2 FIXED until storage is gone.
- CSRF is mandatory only for cookie auth; existing Bearer clients unchanged.
- CORS already allows credentials; `X-CSRF-Token` is on the allowlist.

## Honesty

SEC-M2 and SEC-M5 remain **OPEN**. Overall security status stays
`🟠 SECURITY FIXES REQUIRED BEFORE LAUNCH` until Phase C/D land with evidence.
