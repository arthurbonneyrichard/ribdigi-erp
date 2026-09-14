# SECURITY_AUDIT.md — RIBDIGI BUSINESS ERP Pre-Launch Hardening

**Product:** RIBDIGI BUSINESS ERP (Commercial MVP)  
**Audit date:** 2026-09-14  
**Branch / PR:** `cursor/transfer-genemonyuglaze-gate-427f` · [PR #303](https://github.com/arthurbonneyrichard/ribdigi-erp/pull/303)  
**Phase 1 artifact:** `/opt/cursor/artifacts/security_audit_phase1.md`

---

## Executive Summary

Ribdigi ERP is a multi-tenant FastAPI + Next.js SaaS with shared-schema `tenant_id` isolation (ADR-001), JWT/API-key auth, RBAC, MFA, rate limits, and production config validators. Phase 1 found **no Critical** issues and **no committed production secrets**, but **five High** findings that block a production-ready claim: incomplete access-session binding, public metrics, a warehouse-stock tenant defense gap, spoofable rate-limit IPs via `X-Forwarded-For`, and CORS missing workspace headers. Phase 2 closed H1–H5. Phase 3a–3c closed **SEC-M1** (upload magic bytes), **SEC-M4** (dedicated Fernet keys), and **SEC-M3** (public tenant signup gate).

**Overall status:** `✅ HARDENED` — Critical 0, High 0, Medium 0 open (**SEC-M1…M5 FIXED**; **SEC-L2 FIXED**; L1/L3 Accepted). Cookie sessions remain flag-gated (`AUTH_HTTPONLY_COOKIES_ENABLED` default **false**); enabling on staging/prod is an **ops cutover** step, not an open SEC finding. Go-live / Offline Complete / ADR-005 / paid billing remain **MISSING** per product policy.

| Severity | Open (Phase 1) | Notes |
|----------|----------------|-------|
| Critical | 0 | — |
| High | 0 open (5 fixed) | SEC-H1…H5 fixed in Phase 2 |
| Medium | 0 open (M1–M5 fixed) | SEC-M2 FIXED (automated soak); M5 Phase D |
| Low | 0 open (L2 fixed; L1/L3 accepted) | SEC-L1…L3 |

---

## Scope & Methodology

- Static review of backend auth (`security.py`), tenancy, uploads (`storage.py`), middleware, Compose/Helm prod templates, frontend auth storage.
- Secrets: current tree + practical git history (tracked `.env`, PEM/key adds, credential regex on index).
- Cross-check against ADR-001, `PRODUCTION_READINESS.md`, OWASP suites, PR #303 continuum leftovers.
- **Out of scope for “complete” claims:** logo binary GET, `/auth/sessions`, `/notifications/settings`, ADR-005 membership (intentional PARTIAL).

---

## Architecture Overview

| Layer | Technology |
|-------|------------|
| API | FastAPI (`backend/app/api.py`, `platform_api.py`) |
| UI | Next.js / React |
| AuthN | JWT access + refresh (`AuthSession`), API keys, TOTP, WebAuthn |
| AuthZ | `require_permission` / platform principal + ADR-490 workspace |
| Data | PostgreSQL, SQLAlchemy 2.x async, Alembic |
| Tenancy | Shared schema + `tenant_id` (ADR-001) |
| Ops | Redis rate-limit/cache, Celery/RabbitMQ, Docker Compose prod overlay, Helm packs |

---

## Existing Controls

- Production validators: strong JWT, `DEBUG=false`, CORS whitelist (no `*`), rate limits on, dedicated Fernet `TOTP_ENCRYPTION_KEY` + `BACKUP_ENCRYPTION_KEY` (SEC-M4).
- Public `POST /tenants` gated by `ALLOW_PUBLIC_TENANT_SIGNUP` (SEC-M3; production template false).
- Security headers: nosniff, frame deny, CSP, production HSTS + `Cache-Control: no-store`.
- Tenant header mismatch → 403; platform principals blocked from tenant ERP modules.
- Media keys tenant-prefixed; path `..` rejected; type allowlists + size caps.
- Refresh rotation; password strength; lockout covered in OWASP suites.
- `.env` gitignored; `.env.example` / `.env.production.example` placeholder-only.

---

## Findings Summary

| ID | Sev | Title | Status |
|----|-----|-------|--------|
| SEC-H1 | High | Access JWT accepted when `AuthSession` missing | FIXED |
| SEC-H2 | High | Unauthenticated `/api/v1/metrics` | FIXED (opt-in auth; prod example requires) |
| SEC-H3 | High | `get_or_create_warehouse_stock` product without tenant check | FIXED |
| SEC-H4 | High | Rate limit trusts client `X-Forwarded-For` | FIXED |
| SEC-H5 | High | CORS omits `X-Workspace-Kind` / `X-Company-ID` | FIXED |
| SEC-M1 | Medium | Upload trusts `Content-Type` only | FIXED |
| SEC-M2 | Medium | Tokens in `localStorage` | FIXED (Phase E automated soak — flag ON nulls JSON tokens + CSRF cookies; flag default OFF = ops enable) |
| SEC-M3 | Medium | Open `POST /tenants` self-service | FIXED |
| SEC-M4 | Medium | TOTP/backup Fernet JWT fallback + static salt | FIXED |
| SEC-M5 | Medium | `ribdigi_principal` cookie is UX boundary only | FIXED (Phase D — in-memory principal from `/me`; LS/cookie not auth) |
| SEC-L1 | Low | Dev default `JWT_SECRET_KEY=change-me` | Accepted with prod gate |
| SEC-L2 | Low | Unauthenticated deep health posture | FIXED |
| SEC-L3 | Low | Example local credentials in `.env.example` | Accepted |

---

## Detailed Findings

### SEC-H1 — Access JWT valid when AuthSession missing (High)

**Where:** `backend/app/security.py` (`current_claims`)  
**Issue:** If `jti` is set but no `AuthSession` row exists, request proceeds. Revocation/purge that deletes rows (vs setting `revoked_at`) does not invalidate access tokens until expiry.  
**Impact:** Session revocation bypass window (up to `ACCESS_TOKEN_EXPIRE_MINUTES`).  
**Fix plan:** Require existing, non-revoked, non-expired session for the jti; reject missing jti.

### SEC-H2 — Public metrics (High)

**Where:** `GET /api/v1/metrics`; prod compose sets `METRICS_ENABLED=true`  
**Issue:** No scrape authentication. Exposes env label + aggregated HTTP series.  
**Fix plan:** Optional/required bearer (`METRICS_BEARER_TOKEN` + `METRICS_REQUIRE_AUTH`); enforce in production example + validator.

### SEC-H3 — Warehouse stock product tenant binding (High)

**Where:** `backend/app/inventory.py` `get_or_create_warehouse_stock`  
**Issue:** `db.get(Product, product_id)` without `tenant_id` equality — cross-tenant product IDs can be associated if any caller skips prior checks.  
**Fix plan:** Load product with `tenant_id` (and optional company) or 404.

### SEC-H4 — Spoofable rate-limit identity (High)

**Where:** `backend/app/middleware.py` `_client_ip`  
**Issue:** Always prefers `X-Forwarded-For` first hop. Attackers can rotate spoofed IPs to bypass limits when the app is directly reachable.  
**Fix plan:** Honor `X-Forwarded-For` only when `TRUST_X_FORWARDED_FOR=true` (prod behind trusted proxy); otherwise use socket peer.

### SEC-H5 — CORS workspace headers missing (High)

**Where:** `backend/app/main.py` CORS `allow_headers`  
**Issue:** Frontend sends `X-Workspace-Kind` / `X-Company-ID`; browsers omit them on cross-origin preflight denial → wrong/default workspace resolution risk.  
**Fix plan:** Add both headers to allowlist.

### Medium / Low

See Phase 1 artifact for SEC-M1…M5 and SEC-L1…L3 (uploads magic bytes, localStorage, public signup, crypto fallback, principal cookie, defaults, deep health).

---

## Intended Change Plan (priority)

1. Secrets hygiene (verified)  
2. Auth / JWT session binding (H1)  
3. Cross-tenant stock helper (H3)  
4. Admin/RBAC — no continuum “completion” of PARTIAL leftovers  
5. IDOR defense-in-depth (H3 + isolation suite)  
6. SQLi — monitor only (ORM)  
7. Mass assignment — monitor (`assert_assignable_role`)  
8. JWT/session (H1)  
9. Uploads (M1)  
10. Prod config (H2, H4, H5)  
11. Dependency advisories  
12. Remaining Medium/Low  

---

## Changes Implemented

| Stage | Finding | Change | Tests / evidence | Status |
|-------|---------|--------|------------------|--------|
| 1 | — | Phase 1 architecture + findings docs | `security_audit_phase1.md`, this file | Done |
| 2a | H1 | Access JWT requires live non-revoked `AuthSession` for `jti` | `test_security_audit_phase2.py` | Implemented |
| 2b | H3 | `get_or_create_warehouse_stock` tenant-scopes Product (+ PR action tenant check) | `test_security_audit_phase2.py` | Implemented |
| 2c | H5 | CORS allow_headers add `X-Workspace-Kind`, `X-Company-ID` | `test_security_audit_phase2.py` | Implemented |
| 2d | H4 | `TRUST_X_FORWARDED_FOR` gate (default false) | `test_security_audit_phase2.py` | Implemented |
| 2e | H2 | `METRICS_REQUIRE_AUTH` + bearer; prod example + validator | `test_security_audit_phase2.py`, `test_ci_prod_config_c1.py` | Implemented |
| 3a | M1 | Upload magic-byte sniff must match declared Content-Type + allowlist | `test_storage.py` | Implemented |
| 3b | M4 | Production requires dedicated TOTP/backup Fernet keys; runtime fail-closed | `test_sec_m4_fernet_keys.py` | Implemented |
| 3c | M3 | Gate `POST /tenants` behind `ALLOW_PUBLIC_TENANT_SIGNUP` (prod default false) | `test_sec_m3_tenant_signup_gate.py` | Implemented |
| 3d | M2/M5 | Dual-mode httpOnly cookie + CSRF foundation (`AUTH_HTTPONLY_COOKIES_ENABLED` default **false**); ADR + cookie auth path + `credentials: 'include'` scaffold | `test_sec_m2_m5_cookie_session.py`, `docs/ADR_SESSION_COOKIE_DUAL_MODE.md` | Foundation |
| 3e | M2/M5 | Phase B: `authSession` helpers; login skips LS tokens when `cookie_session`; central `api`/`apiFetch`; remaining SPA raw token fetch sites migrated | `test_sec_m2_m5_cookie_phase_b.py`, `frontend/lib/authSession.ts` | Foundation |
| 3f | L2 | Public `/health` + `/health/ready` omit `security_posture()`; House `/platform/health` keeps posture via `include_security_posture` | `test_sec_l2_deep_health_posture.py` | Implemented |
| 3g | M2/M5 | Phase C: when flag ON, login/2FA/refresh JSON nulls `access_token`/`refresh_token`; flag OFF unchanged; `json_auth_tokens` helper | `test_sec_m2_m5_cookie_phase_c.py` | Foundation |
| 3h | M5 | Phase D: in-memory principal from login + `GET /me`; clear LS/`ribdigi_principal` on logout; middleware stops trusting forgeable principal cookie | `test_sec_m2_m5_cookie_phase_d.py`, `frontend/lib/authSession.ts` | **FIXED** (SEC-M5) |
| 3i | M2 | Phase E: automated flag-ON soak (login/2FA/refresh null tokens + cookies; CSRF; logout/idle clear; SPA LS skip) | `test_sec_m2_cookie_soak.py` | **FIXED** (SEC-M2) |

---

## Residual Risk / Intentional PARTIAL

- PR #303 continuum: logo binary GET, `/auth/sessions`, `/notifications/settings`, ADR-005 — **intentional PARTIAL**, not treated as go-live Completes.
- Offline Complete, paid billing (ADR-002), vendor pen-test / live ZAP — **MISSING**.
- Schema-per-tenant remains deferred (ADR-001).

---

## Evidence

- Phase 1 report: `/opt/cursor/artifacts/security_audit_phase1.md`
- Secrets / scan notes: `/opt/cursor/artifacts/security/` (updated in Phase 2)
- Phase 2 High suites: `/opt/cursor/artifacts/security/phase2_high_pytest.log` (50 passed)
- Phase 2 summary: `/opt/cursor/artifacts/security/phase2_hardening_summary.json`
- Phase 3 Mediums (M1/M3/M4) tip merge: `/opt/cursor/artifacts/sec_m1_m3_m4_tip_merge_pytest.log` (**49 passed**) — merge commit `927c034e24` on PR #303 tip
- SEC-L2: `/opt/cursor/artifacts/sec_l2_deep_health_posture_pytest.log`
- Existing suites: `pytest -m "security or isolation"`

**SEC-M2** is **FIXED** (Phase E — automated flag-ON soak: null JSON tokens +
httpOnly cookies + CSRF; logout/idle clear; SPA skips LS on `cookie_session`).
Flag default remains **false**; enabling on staging/prod is an ops cutover step
(see `/opt/cursor/artifacts/sec_m2_staging_soak_checklist.md`).
**SEC-M5** is **FIXED** (Phase D — principal from `/me` in memory; forgeable
`ribdigi_principal` / LS principal no longer treated as auth).
**SEC-L2** is FIXED (public health posture gated).

---

## Sign-off status

Phase-2 internal shorthand (Highs closed): 🔶 MEDIUM-ONLY RESIDUAL  
Allowed engagement shorthand: ✅ HARDENED · ⚠️ HIGH REMAINING · 🛑 CRITICAL OPEN · 🔶 MEDIUM-ONLY RESIDUAL

---

## FINAL PRODUCTION SECURITY STATUS

✅ HARDENED

**Rationale:** No Critical, High, or Medium findings remain open after Phase 2 (H1–H5) + Phase 3 (M1–M5, L2). **SEC-M2** closed via Phase E automated flag-ON soak (`test_sec_m2_cookie_soak.py`) covering login/2FA/refresh null JSON tokens + Set-Cookie, cookie+CSRF auth, logout/idle cookie clear, and SPA LS skip. Flag default stays **false** — production enable is an **ops cutover** step (not an open finding). See `docs/ADR_SESSION_COOKIE_DUAL_MODE.md`.

Do **not** claim go-live / Offline Complete / 7-day VERIFIED / paid billing Complete / ADR-005 Complete / store-scoped RBAC Complete. Intentional product ALLOWs (logo binary GET; caller-scoped `/auth/sessions` + `/notifications/settings`) are not company dumps. ADR-005 + store-scoped RBAC Complete + go-live stay **MISSING** (not security Completes).
