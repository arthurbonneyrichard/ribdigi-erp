# Retail security audit

**Date:** 17 October 2026 UTC. **Status: PARTIAL.** Not a penetration test.

| Control | Status | Evidence |
| --- | --- | --- |
| Authentication | PARTIAL | MVP login, refresh, email verify, reset, TOTP, and passkeys are documented in `PRODUCTION_READINESS.md`. This pass did not sign in. |
| RBAC | PARTIAL | Cashier supplier payment 403 was proven on 15 October (`test_cashier_pos_only.py`, 4 passed). Not re-run. A sales officer with `credit:read` can still record a supplier payment. |
| Tenant isolation | BLOCKED for a full claim | Shared schema plus `tenant_id`. Readiness still says the isolation suite does not cover every tenant-owned resource. |
| File access | NOT TESTED this pass | Older attachment isolation tests exist. Not re-run. |
| Audit log | PARTIAL | Append-only hash chain is the documented MVP. PO amend, GRN, and POS rows were not inspected on a live tenant. |
| Rate limit and lockout | NOT TESTED this pass | Documented. |
| Secrets | NOT TESTED this pass | No secrets were printed. Production env was not opened. |

Platform support remains packages read-only. Package changes require a platform admin, owner, or finance role.
