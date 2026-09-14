# SECURITY_AUDIT.md — RIBDIGI BUSINESS ERP Pre-Launch Hardening

**Product:** RIBDIGI BUSINESS ERP (Commercial MVP)  
**Audit date:** 2026-09-14  
**Branch / PR:** `cursor/transfer-genemonyuglaze-gate-427f` · [PR #303](https://github.com/arthurbonneyrichard/ribdigi-erp/pull/303)  
**Phase 1 artifact:** `/opt/cursor/artifacts/security_audit_phase1.md`

---

## Executive Summary

Ribdigi ERP is a multi-tenant FastAPI + Next.js SaaS with shared-schema `tenant_id` isolation (ADR-001), JWT/API-key auth, RBAC, MFA, rate limits, and production config validators. Phase 1 found **no Critical** issues and **no committed production secrets**, but **five High** findings that block a production-ready claim: incomplete access-session binding, public metrics, a warehouse-stock tenant defense gap, spoofable rate-limit IPs via `X-Forwarded-For`, and CORS missing workspace headers.

**Overall status:** `🔶 MEDIUM-ONLY RESIDUAL` after Phase 2 High fixes (pending test evidence on tip). Medium findings remain open. Go-live / Offline Complete / ADR-005 / paid billing remain **MISSING** per product policy.

| Severity | Open (Phase 1) | Notes |
|----------|----------------|-------|
| Critical | 0 | — |
| High | 0 open (5 fixed) | SEC-H1…H5 fixed in Phase 2 |
| Medium | 5 | SEC-M1…M5 |
| Low | 3 | SEC-L1…L3 |

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

- Production validators: strong JWT, `DEBUG=false`, CORS whitelist (no `*`), rate limits on.
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
| SEC-M1 | Medium | Upload trusts `Content-Type` only | OPEN |
| SEC-M2 | Medium | Tokens in `localStorage` | OPEN |
| SEC-M3 | Medium | Open `POST /tenants` self-service | OPEN |
| SEC-M4 | Medium | TOTP/backup Fernet JWT fallback + static salt | OPEN |
| SEC-M5 | Medium | `ribdigi_principal` cookie is UX boundary only | OPEN |
| SEC-L1 | Low | Dev default `JWT_SECRET_KEY=change-me` | Accepted with prod gate |
| SEC-L2 | Low | Unauthenticated deep health posture | OPEN |
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
- Existing suites: `pytest -m "security or isolation"`

---

## Sign-off status

**Current emoji status (required set):** 🔶 MEDIUM-ONLY RESIDUAL

Allowed statuses for this engagement:

- ✅ HARDENED (no Critical/High open; tests green)
- ⚠️ HIGH REMAINING
- 🛑 CRITICAL OPEN
- 🔶 MEDIUM-ONLY RESIDUAL
