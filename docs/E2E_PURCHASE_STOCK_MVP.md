# E2E Purchase-to-Stock MVP — Supplier → PO → GRN → Stock Packaging

**Status:** Complete (MVP) — Stage 35 P1  
**Evidence:** `backend/tests/test_e2e_purchase_stock_p1.py` · `/opt/cursor/artifacts/launch/stage35_p1_e2e_purchase_stock.json`  
**Register:** `ops/mvp/e2e-purchase-stock.json`  
**Related:** [E2E_ORG_BOOTSTRAP_MVP.md](E2E_ORG_BOOTSTRAP_MVP.md) · [E2E_USERS_RBAC_MVP.md](E2E_USERS_RBAC_MVP.md) · [STAGE_11_PLAN.md](STAGE_11_PLAN.md) · [STAGE_24_PLAN.md](STAGE_24_PLAN.md) · [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) · [STAGE_35_PLAN.md](STAGE_35_PLAN.md)

This is the **MVP E2E purchase-to-stock packaging surface**: a checklist for creating a supplier and products, raising a PO, receiving goods (GRN), and verifying warehouse stock on a real test tenant before sale-to-payment smoke. It extends Stage 11 purchasing chain and Stage 24 commerce gates — it does **not** claim live purchasing success, demo catalog seed, PO Kanban polish Complete, or that E2E smoke was executed.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Checklist step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Operator action or deferred polish still required |

Every step keeps `done: false`. Top-level `live_purchase_stock_claimed: false` / `e2e_smoke_executed_claimed: false` / `demo_tenant_claimed: false` / `po_kanban_claimed: false`.

## Register scope

1. Create supplier (real test tenant — no demo seed).
2. Create products for the purchase path.
3. Create purchase order (document numbering).
4. Receive goods (GRN) into warehouse.
5. Verify stock increase / movements.
6. Optional purchase invoice linkage (Stage 11 chain).
7. Tenant isolation on purchasing path.
8. PO/GRN shared document-numbering honesty (Stage 24 N1).
9. PO Kanban polish deferred Remaining.
10. Live purchase-to-stock execution Remaining.

## Automation hooks

1. Maintain `ops/mvp/e2e-purchase-stock.json` (synced by `test_e2e_purchase_stock_p1.py`).
2. Align honesty with org bootstrap / users-RBAC / Stage 11 / Stage 24 flags.
3. CI proves packaging honesty only — never forges live purchasing success.

## Explicitly not claimed

- Live purchase-to-stock executed Complete because Stage 35 P1 packaging exists
- Demo tenants / seed products / fake GRN success as Complete
- PO Kanban polish Complete (Stage 24 Remaining)
- Multi-bin / FIFO-LIFO-WA Complete
- Live E2E smoke executed Complete
- Live go-live / §7 / attestation Complete

## Sign-off

Stage 35 P1 is met when this doc + register JSON + evidence JSON exist, `test_e2e_purchase_stock_p1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 35 P1 without inventing live purchasing success or demo catalog seed.
