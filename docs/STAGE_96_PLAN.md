# Stage 96 Plan — Tenant MVP Outline Surface Fidelity Ops

**Status:** Closed — exit met (H96x); freeze ADR-199  
**Base:** Dashboard Business Overview Fidelity + Global Topbar Search + Finance / Sales / Settings Leaf Fidelity → Tenant MVP Outline Surface Fidelity Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-198](ADR_198_STAGE96_OPEN.md)  
**Exit:** [STAGE_96_EXIT_CRITERIA.md](STAGE_96_EXIT_CRITERIA.md) · freeze [ADR-199](ADR_199_STAGE96_FREEZE.md)  
**Fidelity:** [STAGE_96_FIDELITY.md](STAGE_96_FIDELITY.md)  
**Prior freeze:** [ADR-197](ADR_197_STAGE95_FREEZE.md) · [STAGE_95_EXIT_CRITERIA.md](STAGE_95_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Dashboard Business Overview Fidelity Pack
        +
Global Topbar Search Pack
        +
Finance / Sales / Settings Leaf Fidelity Pack
        ↓
Tenant MVP Outline Surface Fidelity Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending dashboard API, product lookup, accounting tabs, sales orders, Company print sections — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated search hits. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–95 feature scopes (Stage 95 Shell IA remains frozen). Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **B1** | Dashboard Business Overview fidelity | P0 | COMPLETE |
| **G1** | Global topbar search | P0 | COMPLETE |
| **L1** | Finance / Sales / Settings leaf fidelity | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H96x** | Stage 96 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Full Billers CRUD / performance suite (alias only)
- Parallel Income approval module mirroring Expenses
- WYSIWYG document designer Complete
- Reopening Stages 80–95 frozen feature scopes
- Main `ci.yml` deploy jobs

## B1 acceptance criteria

- [x] Dashboard payload includes Profit Summary (MTD net_profit) + AP Payables with `kpi_links`; notification rows deep-link via `entity_type`/`entity_id`; Business Overview framing.
- [x] Automated proof: `backend/tests/test_stage96_dashboard_overview_b1.py`.

## G1 acceptance criteria

- [x] `GET /search?q=` returns RBAC-gated products + customers; Shell topbar search UI navigates to existing deep-links; no fabricated hits.
- [x] Automated proof: `backend/tests/test_stage96_global_search_g1.py`.

## L1 acceptance criteria

- [x] Shell discoverability: Money Transfer, Income (P&L), Billers (Users/salesperson alias), Delivery status; accounting `?tab=` + anchors; sales Orders delivery status filter; Company document-templates / notifications prefs anchors.
- [x] Automated proof: `backend/tests/test_stage96_leaf_fidelity_l1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_96_FIDELITY.md` maps B1–L1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage96_fidelity_d1.py`.

## H96x acceptance criteria

- [x] `docs/STAGE_96_EXIT_CRITERIA.md` + `docs/ADR_199_STAGE96_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage96_exit_h96x.py`.
