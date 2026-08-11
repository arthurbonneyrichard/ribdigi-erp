# Stage 68 Plan — Platform ↔ Tenant Console Fidelity

**Status:** Open — D1 complete; H68x next  
**Base:** Ribdigi House Console Honesty Pack + Tenant Company Console Honesty Pack → Platform ↔ Tenant Console Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-142](ADR_142_STAGE68_OPEN.md)  
**Prior freeze:** [ADR-141](ADR_141_STAGE67_FREEZE.md) · [STAGE_67_EXIT_CRITERIA.md](STAGE_67_EXIT_CRITERIA.md)  
**Platform ADR:** [ADR-137](ADR_137_PLATFORM_PRINCIPAL.md)

Stage 68 opens after Stage 67 freeze: **Ribdigi House Console Honesty Packaging + Tenant Company Console Honesty Packaging → Platform ↔ Tenant Console Fidelity**. The owner product outline is the dual-console commercial surface:

```
RIBDIGI ERP
              │
  ┌───────────┴───────────┐
  │                       │
  ▼                       ▼
RIBDIGI HOUSE        TENANT COMPANY
Platform Owner          Dashboard
   Dashboard                │
        │                   ├── POS
        ├── Tenants         ├── Sales
        ├── Plans           ├── Inventory
        ├── Subscriptions   ├── Purchasing
        ├── Billing         ├── Accounting
        ├── Platform Users  ├── Expenses
        ├── Security        ├── Credit
        ├── Audit           ├── Tax
        ├── Health          ├── Reports
        └── Settings        └── Settings
```

ADR-137 platform principal + tenant ERP shell lack a dedicated Stage track that indexes this dual-console outline without claiming paid billing Complete or re-claiming tenant modules. This track packages those surfaces on proven ADR-137 / Stage 36 B1 / Stage 52 R1 honesty assets — **not** claiming payment-provider Complete, live subscriptions Complete, fake MRR, re-packaging Stage 1–67 packs as new Complete, or reopening Stages 1–67 frozen feature scopes.

## Delivery packs (derived)

```
Ribdigi House Console Honesty Pack
        +
Tenant Company Console Honesty Pack
        ↓
Platform ↔ Tenant Console Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending ADR-137 platform console + tenant `Shell` patterns — do not invent fake billing or a parallel platform stack.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–67 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. Deferred ADRs (001–006) stay deferred (ADR-002 billing remains deferred).
7. Do not re-ship Stage 1–67 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **H1** | Ribdigi House (Platform Owner) console honesty packaging (Tenants → Plans/Billing deferred → Users → Security/Audit/Health/Settings; not paid billing Complete) | P0 | COMPLETE |
| **T1** | Tenant Company console honesty packaging (POS → Sales → Inventory → Purchasing → Accounting → Expenses → Credit → Tax → Reports → Settings; not re-claiming modules) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H68x** | Stage 68 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing / payment-provider Complete (ADR-002)
- Live subscriptions / checkout / fake MRR Complete
- Re-packaging tenant ERP modules as new Complete
- Re-packaging ADR-137 platform features as new Complete beyond honesty indexing
- Live go-live / §7 / attestation Complete
- SOC 2 / ISO 27001 certification Complete
- Main `ci.yml` deploy jobs (Stage 18 C1 remains deploy-free)
- Reopening Stages 1–67 frozen feature scopes

## H1 acceptance criteria

- [x] Ribdigi House console honesty packaging indexing Platform Owner Dashboard modules (Tenants, Plans metadata, Subscriptions/Billing deferred, Platform Users, Security, Audit, Health, Settings) with ADR-137 / Stage 36 B1 adjacency (not claiming paid billing Complete).
- [x] Automated proof: `backend/tests/test_ribdigi_house_console_h1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 68 H1.

**Deliverables:** `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json`, evidence `stage68_h1_ribdigi_house_console.json` (`test_ribdigi_house_console_h1.py`).

## T1 acceptance criteria

- [x] Tenant Company console honesty packaging indexing tenant ERP shell modules (POS, Sales, Inventory, Purchasing, Accounting, Expenses, Credit, Tax, Reports, Settings) with principal isolation vs House (not re-claiming modules as new Complete).
- [x] Automated proof: `backend/tests/test_tenant_company_console_t1.py`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [x] Plan / launch / roadmap cite Stage 68 T1.

**Deliverables:** `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json`, evidence `stage68_t1_tenant_company_console.json` (`test_tenant_company_console_t1.py`).

## D1 acceptance criteria

- [x] `docs/STAGE_68_FIDELITY.md` maps H1–T1 evidence → readiness / launch / deploy / security docs.
- [x] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 68 D1.
- [x] Automated proof: `backend/tests/test_stage68_fidelity_d1.py`.

**Deliverables:** `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`).

## H68x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for H1–D1 / H68x — `docs/STAGE_68_EXIT_CRITERIA.md`.
- [ ] Freeze ADR accepted — `docs/ADR_143_STAGE68_FREEZE.md` (planned id).
- [ ] Automated proof: `backend/tests/test_stage68_exit_h68x.py`.
