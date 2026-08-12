# Stage 95 Plan — Tenant MVP Navigation Ops

**Status:** Closed — exit met (H95x); freeze ADR-197  
**Base:** Tenant Shell IA Regrouping + Party & Stock Discoverability + Chrome & Settings Alias Fidelity → Tenant MVP Navigation Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-196](ADR_196_STAGE95_OPEN.md)  
**Exit:** [STAGE_95_EXIT_CRITERIA.md](STAGE_95_EXIT_CRITERIA.md) · freeze [ADR-197](ADR_197_STAGE95_FREEZE.md)  
**Fidelity:** [STAGE_95_FIDELITY.md](STAGE_95_FIDELITY.md)  
**Prior freeze:** [ADR-195](ADR_195_STAGE94_FREEZE.md) · [STAGE_94_EXIT_CRITERIA.md](STAGE_94_EXIT_CRITERIA.md)

## Product outline (owner)

Owner-supplied **RIBDIGI ERP — MVP NAVIGATION** tree (Dashboard, Inventory, Stock, Sales, Purchase, Finance & Accounts, People, Stores, Warehouse, Reports, User Management, Settings). Stage 95 proves **discoverability / IA fidelity** against that tree using existing MVP engines — not a claim that every leaf is a new standalone route.

## Delivery packs (derived)

```
Tenant Shell IA Regrouping Pack
        +
Party & Stock Discoverability Pack
        +
Chrome & Settings Alias Fidelity Pack
        ↓
Tenant MVP Navigation Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending `Shell.tsx`, `useTabQuery`, Company/Stores labels — do not invent parallel consoles or duplicate CRUD pages.
3. No demo data / fake MRR. No fabricated email success. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–94 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **N1** | Tenant Shell IA regrouping | P0 | COMPLETE |
| **P1** | Party & stock discoverability | P0 | COMPLETE |
| **C1** | Chrome & settings alias fidelity | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H95x** | Stage 95 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- New leaf routes for every MVP-nav item (variants, QR bulk, etc.) when capability already exists under tabs
- Reopening Stages 80–94 frozen feature scopes (including House Stage 94)
- Main `ci.yml` deploy jobs

## N1 acceptance criteria

- [x] Shell primary nav uses MVP-aligned section labels (Commerce / People / Finance / Operations) and renames Company→Settings, Multi-Store→Stores, Admin→User Management; `MENU_MODULE_BY_PATH` stays in sync for path→module gates.
- [x] Automated proof: `backend/tests/test_stage95_shell_ia_n1.py`.

## P1 acceptance criteria

- [x] First-class Shell discoverability links for Customers, Suppliers, Stock, Low stock, Warehouse (deep-link to existing tabs/sections); `useTabQuery` writes `?tab=` on change.
- [x] Automated proof: `backend/tests/test_stage95_party_stock_p1.py`.

## C1 acceptance criteria

- [x] Topbar profile/logout; mobile sidebar collapse; Settings/Stores page titles honest to MVP outline aliases.
- [x] Automated proof: `backend/tests/test_stage95_chrome_c1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_95_FIDELITY.md` maps N1–C1 → readiness / launch / deploy / security; USER_MANUAL sidebar diagram matches Shell.
- [x] Automated proof: `backend/tests/test_stage95_fidelity_d1.py`.

## H95x acceptance criteria

- [x] `docs/STAGE_95_EXIT_CRITERIA.md` + `docs/ADR_197_STAGE95_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage95_exit_h95x.py`.
