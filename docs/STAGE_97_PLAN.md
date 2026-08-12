# Stage 97 Plan — Tenant MVP Module Leaf Honesty Ops

**Status:** Closed — exit met (H97x); freeze ADR-201  
**Base:** Sales Surface Honesty + Purchase & Finance Discoverability + Inventory & Settings Leaf Honesty → Tenant MVP Module Leaf Honesty Ops  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-200](ADR_200_STAGE97_OPEN.md)  
**Exit:** [STAGE_97_EXIT_CRITERIA.md](STAGE_97_EXIT_CRITERIA.md) · freeze [ADR-201](ADR_201_STAGE97_FREEZE.md)  
**Fidelity:** [STAGE_97_FIDELITY.md](STAGE_97_FIDELITY.md)  
**Prior freeze:** [ADR-199](ADR_199_STAGE96_FREEZE.md) · [STAGE_96_EXIT_CRITERIA.md](STAGE_96_EXIT_CRITERIA.md)

## Delivery packs (derived)

```
Sales Surface Honesty Pack
        +
Purchase & Finance Discoverability Pack
        +
Inventory & Settings Leaf Honesty Pack
        ↓
Tenant MVP Module Leaf Honesty Ops
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending sales invoices, purchasing settings/invoices, barcode_labels, Company/Accounting anchors, Shell — do not invent parallel consoles.
3. No demo data / fake MRR. No fabricated invoice statuses. No impersonation.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–96 feature scopes (Stage 96 Outline Surface remains frozen). Main `ci.yml` stays deploy-free (**Stage 18 C1**).
6. ADR-002 / ADR-005 remain deferred; ADR-003 stays soft-delete-only (`hard_delete_claimed: false`).

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Sales surface honesty | P0 | COMPLETE |
| **P1** | Purchase & Finance discoverability | P0 | COMPLETE |
| **I1** | Inventory & Settings leaf honesty | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H97x** | Stage 97 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Paid billing / fabricated MRR / checkout / `subscriptions_live_claimed` Complete (ADR-002)
- User↔Store membership Complete (ADR-005)
- Hard-delete archival Complete (ADR-003)
- Impersonation into customer ERP
- Full Billers CRUD / performance suite
- Parallel Income approval module mirroring Expenses
- WYSIWYG document designer Complete
- Fiscal-period close console Complete
- POS Hold/Resume (new engine → later stage)
- Reopening Stages 80–96 frozen feature scopes
- Main `ci.yml` deploy jobs

## S1 acceptance criteria

- [x] Optional `status` on `GET /sales/invoices` (`unpaid` → posted∪sent; paid/partial/overdue/draft/cancelled); invoice filter UI + URL sync; quotation→invoice honesty copy (draft + Post required).
- [x] Automated proof: `backend/tests/test_stage97_sales_honesty_s1.py`.

## P1 acceptance criteria

- [x] Purchasing `settings` tab hosts PR approval matrix; Outstanding Purchases discoverability (`status=outstanding`); `#opening-balances` / `#fiscal-period` anchors; Shell deep-links.
- [x] Automated proof: `backend/tests/test_stage97_purchase_finance_p1.py`.

## I1 acceptance criteria

- [x] Catalog Sub Categories labeling; QR option on product labels API/UI; Settings aliases Tax Rates / Email / SMS / Backup & Restore with Company `#email`/`#sms` anchors.
- [x] Automated proof: `backend/tests/test_stage97_inventory_settings_i1.py`.

## D1 acceptance criteria

- [x] `docs/STAGE_97_FIDELITY.md` maps S1–I1 → readiness / launch / deploy / security.
- [x] Automated proof: `backend/tests/test_stage97_fidelity_d1.py`.

## H97x acceptance criteria

- [x] `docs/STAGE_97_EXIT_CRITERIA.md` + `docs/ADR_201_STAGE97_FREEZE.md`.
- [x] Automated proof: `backend/tests/test_stage97_exit_h97x.py`.
