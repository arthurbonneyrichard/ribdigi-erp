# Stage 85 Plan — House Roster & Tenant Access Ops

**Status:** Closed — exit met (H85x); freeze ADR-177  
**Base:** Platform Subscriptions Roster + Admin Email Password Reset + Org-Chart Role Catalog → House Roster & Tenant Access Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-176](ADR_176_STAGE85_OPEN.md)  
**Exit:** [STAGE_85_EXIT_CRITERIA.md](STAGE_85_EXIT_CRITERIA.md) · [ADR-177](ADR_177_STAGE85_FREEZE.md)  
**Prior freeze:** [ADR-175](ADR_175_STAGE84_FREEZE.md) · [STAGE_84_EXIT_CRITERIA.md](STAGE_84_EXIT_CRITERIA.md)

## Org chart (owner outline)

```
RIBDIGI ERP
              │
  ┌───────────┴───────────┐
  ▼                       ▼
RIBDIGI HOUSE        TENANT COMPANY
Platform Owner            │
  │                  TENANT ADMIN
  ├─ Tenants              ├─ Users
  ├─ Plans                ├─ Roles
  ├─ Platform Users       └─ Permissions
  └─ Subscriptions roster     ├─ Manager (store_manager)
     (metadata honesty)       ├─ Cashier
                              ├─ Accountant
                              ├─ Inventory Officer
                              ├─ Sales Officer
                              └─ Custom Roles
```

## Delivery packs (derived)

```
Platform Subscriptions Roster Pack
        +
Admin Email Password Reset Pack
        +
Org-Chart Role Catalog Pack
        ↓
House Roster & Tenant Access Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `platform` / `/platform/billing` / `/users` / `/admin/permissions` — do not invent parallel consoles.
3. No demo data / fake MRR / fabricated subscriptions revenue.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–84 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **R1** | Platform subscriptions roster (tenant×plan metadata) | P0 | COMPLETE |
| **E1** | Admin email-initiated password reset | P0 | COMPLETE |
| **L1** | Org-chart role catalog (labels + system matrix read-only) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H85x** | Stage 85 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout Complete (ADR-002)
- Claiming subscriptions roster as billing / `subscriptions_live_claimed` Complete
- User↔Store membership table Complete (ADR-005)
- Reopening Stages 80–84 frozen feature scopes
- Per-user module grant/deny API
- Main `ci.yml` deploy jobs

## R1 acceptance criteria

- [x] `GET /api/v1/platform/subscriptions` (or billing enrichment) lists customer tenants × plan_code / status — no MRR.
- [x] Platform Billing UI shows the roster with honesty messaging.
- [x] Automated proof: `backend/tests/test_platform_subscriptions_r1.py`.

## E1 acceptance criteria

- [x] Tenant Admin can trigger email password reset for a user (`POST /users/{id}/password-reset-email`).
- [x] Uses existing one-time token + emailer; audited; Stage 83 prompt reset remains.
- [x] Automated proof: `backend/tests/test_admin_email_reset_e1.py`.

## L1 acceptance criteria

- [x] Role catalog exposes org-chart labels (Manager ↔ store_manager; Tenant Admin ↔ company_admin).
- [x] `/admin/permissions` shows read-only system-role matrix.
- [x] Automated proof: `backend/tests/test_org_role_catalog_l1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_85_FIDELITY.md` maps R1–L1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage85_fidelity_d1.py`.

## H85x acceptance criteria

- [x] `docs/STAGE_85_EXIT_CRITERIA.md` + `docs/ADR_177_STAGE85_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage85_exit_h85x.py`.
