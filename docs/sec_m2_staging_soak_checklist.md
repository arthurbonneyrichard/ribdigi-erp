# SEC-M2 staging / ops cutover checklist

**Status:** SEC-M2 is **FIXED** in code via Phase E automated soak
(`backend/tests/test_sec_m2_cookie_soak.py`). This checklist is the **operator**
enable step — flag default remains `AUTH_HTTPONLY_COOKIES_ENABLED=false` in
`.env.production.example`.

**Not claimed:** Offline Complete · 7-day VERIFIED · go-live · paid billing
Complete · ADR-005 Complete · store-scoped RBAC Complete.

## Automated evidence (already landed)

| Check | Coverage |
|-------|----------|
| Login null JSON tokens + Set-Cookie httpOnly | `test_sec_m2_soak_login_null_tokens_set_cookie_httponly` |
| Refresh null JSON + cookie rotate | `test_sec_m2_soak_refresh_null_tokens_rotates_cookies` |
| 2FA verify null JSON + cookies | `test_sec_m2_soak_2fa_verify_null_tokens_and_cookies` |
| Cookie-only auth (no Bearer) | soak login + 2FA status GET |
| CSRF required on mutating cookie auth | `test_sec_m2_soak_csrf_required_for_mutating_cookie_auth` |
| Logout clears cookies + revokes | `test_sec_m2_soak_logout_clears_cookies` |
| Idle-logout clears cookies + revokes | `test_sec_m2_soak_idle_logout_clears_cookies` |
| SPA skips LS tokens on `cookie_session` | `test_sec_m2_soak_spa_skips_localstorage_tokens_on_cookie_session` |
| WebAuthn wiring (same helpers) | `test_sec_m2_soak_webauthn_verify_uses_same_cookie_helpers` |
| Flag default OFF | soak + Phase A–D defaults tests |

Run:

```bash
cd backend && .venv/bin/pytest \
  tests/test_sec_m2_cookie_soak.py \
  tests/test_sec_m2_m5_cookie_session.py \
  tests/test_sec_m2_m5_cookie_phase_b.py \
  tests/test_sec_m2_m5_cookie_phase_c.py \
  tests/test_sec_m2_m5_cookie_phase_d.py \
  -q
```

## Operator staging enable (cutover)

1. Staging env: set `AUTH_HTTPONLY_COOKIES_ENABLED=true`
2. Confirm `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE` (lax/strict), and
   `AUTH_COOKIE_DOMAIN` match the staging host
3. Login / 2FA / WebAuthn / refresh — browser DevTools: JSON tokens null;
   `Set-Cookie` for `ribdigi_access` / `ribdigi_refresh` / `ribdigi_csrf`
4. Confirm `localStorage` has no `token` / `refresh_token` after login
5. Mutating API calls send `X-CSRF-Token` matching `ribdigi_csrf`
6. Logout / idle-logout clears cookies
7. Export/download flows use `credentials: 'include'` (central `apiFetch`)
8. Only then enable the same flag in production

## Honesty

- Code finding **SEC-M2 = FIXED** with automated soak evidence.
- Leaving the flag OFF in production examples is intentional until ops completes
  this cutover.
- Do not treat “flag still false in prod” as reopening M2 after Phase E.
