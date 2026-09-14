# Store-scoped RBAC — intentional product ALLOWs (accepted)

**Status:** **ACCEPTED** product policy (commercial MVP)  
**Date:** 2026-09-17  
**Parent Complete criteria:** [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md)  
**Living matrix:** [`STORE_SCOPED_RBAC_TEST_MATRIX.md`](STORE_SCOPED_RBAC_TEST_MATRIX.md) · class `intentional_allow`  
**Evidence tests:** `backend/tests/test_store_scope_ops_hardening.py` (logo binary GET; own sessions + notification settings)

## Decision

The following surfaces remain **intentionally ALLOWED** for `store_manager` (and other
scoped roles) under store-scoped RBAC. They are **not** company-level dumps, **not**
foreign-store data leaks, and **not** Completes blockers. Product accepts them as
workspace / self-service policy for Commercial MVP v1.0.

| Surface | Decision | Security rationale | Evidence |
|---------|----------|--------------------|----------|
| Company / tenant **logo binary GET** | **ACCEPT ALLOW** | Workspace chrome only. Branding *writes* already denied. Binary GET is needed so managed-store UI can render tenant/company logo without exposing profile/settings dumps. Mistaken deny (`b0fc721a15`) was reverted. | `test_store_manager_company_tenant_logo_binary_get_allowed` |
| Caller-scoped **`/auth/sessions`** (list + export) | **ACCEPT ALLOW** | Self-service session inventory for the authenticated caller (`claims.sub`) only. Tenant-wide `/auth/tenant-sessions` remains `STORE_SCOPE_DENIED`. No other users’ sessions. | `test_store_manager_own_sessions_and_notification_settings_allowed` |
| Caller-scoped **`/notifications/settings`** (GET/PATCH/export) | **ACCEPT ALLOW** | Per-user notification preferences bound to `claims.sub`. Not company notification policy, not inbox dumps of foreign entities beyond existing scope joins. | same test as sessions |

## Explicit non-ALLOWs (unchanged)

- Tenant-wide session inventory (`/auth/tenant-sessions` + export) — **denied** for store_manager
- Company/tenant logo **writes**, profile GET dumps, settings CSV exports — **denied**
- Company notification admin / SMTP / broadcast master surfaces — **denied** / out of SM scope

## Complete implications

- Closing this sign-off empties remaining-checklist item **6** (product ALLOW acceptance).
- Does **not** alone claim store-scoped RBAC Complete (needs residual empty + living matrix + membership soak evidence).
- Does **not** claim overall RBAC Complete, Offline Complete, paid billing Complete, or go-live.
- Staging enable of `STORE_MEMBERSHIP_SCOPE_ENABLED` remains an **ops cutover** (flag default OFF).

## Sign-off

| Role | Decision | Notes |
|------|----------|-------|
| Product (Commercial MVP) | **ACCEPT** all three ALLOWs | Formalized for market-ready packaging 2026-09-17 |
| Engineering | Confirmed by living matrix `intentional_allow` cases | CI `-m store_scope` |
| Security | Caller-scoped / chrome-only; no foreign-store or company dump | Rationale above |
