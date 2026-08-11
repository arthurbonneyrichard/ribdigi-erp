# E2E Users + RBAC MVP — Operator Smoke Path Packaging

**Status:** Complete (MVP) — Stage 35 U1  
**Evidence:** `backend/tests/test_e2e_users_rbac_u1.py` · `/opt/cursor/artifacts/launch/stage35_u1_e2e_users_rbac.json`  
**Register:** `ops/mvp/e2e-users-rbac.json`  
**Related:** [E2E_ORG_BOOTSTRAP_MVP.md](E2E_ORG_BOOTSTRAP_MVP.md) · [SECURITY_GUIDE.md](SECURITY_GUIDE.md) · [STAGE_21_PLAN.md](STAGE_21_PLAN.md) · [ADR_004_MENU_PERMISSIONS.md](ADR_004_MENU_PERMISSIONS.md) · [ADR_005_USER_STORE_ASSIGNMENT.md](ADR_005_USER_STORE_ASSIGNMENT.md) · [STAGE_35_PLAN.md](STAGE_35_PLAN.md)

This is the **MVP E2E users + RBAC packaging surface**: a checklist for creating real test-tenant users, assigning roles, and verifying RBAC / tenant-isolation smoke before purchase and POS paths. It extends Stage 21 U1 and Stage 35 T1 — it does **not** claim live user provisioning Complete, demo passwords, or that E2E smoke was executed.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Checklist step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Operator action or deferred ADR still required |

Every step keeps `done: false`. Top-level `live_users_provisioned_claimed: false` / `e2e_smoke_executed_claimed: false` / `demo_tenant_claimed: false` / `store_membership_claimed: false`.

## Register scope

1. Company admin user (no demo password).
2. Manager user with org scope.
3. Inventory officer.
4. Cashier.
5. Role assignment / catalog.
6. RBAC smoke: cashier cannot write users.
7. Tenant header mismatch → 403.
8. ADR-004 menu = module permissions.
9. ADR-005 store membership deferred.
10. Live provisioning Remaining.

## Automation hooks

1. Maintain `ops/mvp/e2e-users-rbac.json` (synced by `test_e2e_users_rbac_u1.py`).
2. Align honesty with org bootstrap / SECURITY_GUIDE / ADR-004 / ADR-005.
3. CI proves packaging honesty only — never forges live user provisioning Complete.

## Explicitly not claimed

- Live user provisioning Complete because Stage 35 U1 packaging exists
- Demo tenants / seed passwords as Complete
- User↔store membership Complete (ADR-005 deferred)
- Live E2E smoke executed Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 21 U1 as new runtime Complete

## Sign-off

Stage 35 U1 is met when this doc + register JSON + evidence JSON exist, `test_e2e_users_rbac_u1.py` passes, and SECURITY_GUIDE / LAUNCH_CHECKLIST / plan / roadmap cite Stage 35 U1 without inventing live user provisioning Complete.
