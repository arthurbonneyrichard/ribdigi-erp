# Stage 35 Plan — Commercial End-to-End Operational Smoke Fidelity

**Status:** Open — V1 complete; R1 next (ADR-075)  
**Base:** Org Bootstrap Pack + Users/RBAC Pack + Purchase-to-Stock Pack + Sale-to-Payment Pack + Verify Financials Pack + Backup/Restore Pack → Commercial End-to-End Operational Smoke Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-075](ADR_075_STAGE35_OPEN.md)

Stage 35 opens after Stage 34 freeze: **Org Bootstrap Packaging + Users/RBAC Packaging + Purchase-to-Stock Packaging + Sale-to-Payment Packaging + Verify Financials Packaging + Backup/Restore Packaging → Commercial End-to-End Operational Smoke Fidelity**. Stages 26–34 delivered Complete (MVP) ops, release, certification, hardening, go-live support, closeout, handoff, continuity, and customer-assurance **packaging** with honest Remaining for live execution and deferred ADRs. This track packages an **operator end-to-end smoke checklist** for a real test tenant (not demo seed) covering company setup through POS/accounting/audit and backup/restore — **not** forging live smoke success, inventing demo tenants, claiming production go-live / §7 Complete, or reopening Stages 1–34.

## Product outline (owner)

```
REGISTER REAL TEST TENANT
        ↓
COMPLETE COMPANY SETUP
        ↓
CREATE BRANCH
        ↓
CREATE STORE
        ↓
CREATE WAREHOUSE
        ↓
CREATE USERS
        ↓
ASSIGN RBAC
        ↓
CREATE SUPPLIER
        ↓
CREATE PRODUCTS
        ↓
CREATE PURCHASE ORDER
        ↓
RECEIVE GOODS
        ↓
VERIFY STOCK
        ↓
CREATE CUSTOMER
        ↓
SELL THROUGH POS
        ↓
RECEIVE PAYMENT
        ↓
VERIFY STOCK REDUCTION
        ↓
VERIFY TAX
        ↓
VERIFY ACCOUNTING
        ↓
VERIFY CREDIT
        ↓
VERIFY REPORTS
        ↓
VERIFY AUDIT LOG
        ↓
BACKUP
        ↓
RESTORE TEST
        ↓
Commercial End-to-End Operational Smoke Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 21–24 commerce / Stage 33 F1 first-tenant / Stage 18–27 backup honesty patterns — do not invent fake live smoke success or demo tenants.
3. No demo data / fake success. Alembic only when schema is required. Real test-tenant flows only in clearly isolated test/operator environments.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–34 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006), live go-live / §7, SOC 2 / ISO, and Stage 34 S1/B1 remain deferred unless explicitly in this plan (checklist packaging only).
7. Do not re-ship Stage 26–34 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **T1** | Org bootstrap packaging (tenant → company → branch → store → warehouse) | P0 | COMPLETE |
| **U1** | Users + RBAC assignment packaging | P0 | COMPLETE |
| **P1** | Purchase-to-stock packaging (supplier → products → PO → receive → verify stock) | P0 | COMPLETE |
| **S1** | Sale-to-payment packaging (customer → POS → payment → stock reduction) | P0 | COMPLETE |
| **V1** | Verify financials packaging (tax → accounting → credit → reports → audit) | P1 | COMPLETE |
| **R1** | Backup + restore test packaging | P1 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P2 | PENDING |
| **H35x** | Stage 35 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Demo tenants / seed passwords / hard-coded production credentials
- Claiming live E2E smoke executed Complete because packaging exists
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–34 packs as new Complete
- Completing Stage 34 deferred S1/B1 inside this track unless explicitly reopened
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–34 frozen feature scopes

## T1 acceptance criteria

- [x] Org bootstrap packaging consolidating real-test-tenant → company → branch → store → warehouse checklist (extends Stage 21 T1 / Stage 33 F1; not forging live bootstrap success or demo tenants).
- [x] Automated proof: `backend/tests/test_e2e_org_bootstrap_t1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 35 T1.

## U1 acceptance criteria

- [x] Users + RBAC assignment packaging for the E2E smoke path (not forging live user provisioning Complete).
- [x] Automated proof: `backend/tests/test_e2e_users_rbac_u1.py`.
- [x] SECURITY_GUIDE / LAUNCH_CHECKLIST honesty updated.
- [x] Plan / launch / roadmap cite Stage 35 U1.

## P1 acceptance criteria

- [x] Purchase-to-stock packaging (supplier → products → PO → receive → verify stock) for E2E smoke (not forging live purchasing success).
- [x] Automated proof: `backend/tests/test_e2e_purchase_stock_p1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 35 P1.

## S1 acceptance criteria

- [x] Sale-to-payment packaging (customer → POS → payment → stock reduction) for E2E smoke (not forging live POS success).
- [x] Automated proof: `backend/tests/test_e2e_sale_payment_s1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 35 S1.

## V1 acceptance criteria

- [x] Verify financials packaging (tax → accounting → credit → reports → audit) for E2E smoke (not forging live verification Complete).
- [x] Automated proof: `backend/tests/test_e2e_verify_financials_v1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 35 V1.

## R1 acceptance criteria

- [ ] Backup + restore test packaging for E2E smoke closeout (extends DR / backup packs; not forging live restore success).
- [ ] Automated proof: `backend/tests/test_e2e_backup_restore_r1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 35 R1.

## D1 acceptance criteria

- [ ] `docs/STAGE_35_FIDELITY.md` maps T1–R1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 35 D1.
- [ ] Automated proof: `backend/tests/test_stage35_fidelity_d1.py`.

## H35x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for T1–D1 / H35x — `docs/STAGE_35_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_076_STAGE35_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage35_exit_h35x.py`.
- [ ] Stages 1–34 freezes remain; Stage 36+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 35 open under ADR-075. V1 complete; R1 next. Stages 1–34 remain frozen for their scopes.
