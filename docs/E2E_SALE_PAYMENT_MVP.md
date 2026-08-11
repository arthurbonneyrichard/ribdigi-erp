# E2E Sale-to-Payment MVP — Customer → POS → Payment → Stock Packaging

**Status:** Complete (MVP) — Stage 35 S1  
**Evidence:** `backend/tests/test_e2e_sale_payment_s1.py` · `/opt/cursor/artifacts/launch/stage35_s1_e2e_sale_payment.json`  
**Register:** `ops/mvp/e2e-sale-payment.json`  
**Related:** [E2E_PURCHASE_STOCK_MVP.md](E2E_PURCHASE_STOCK_MVP.md) · [E2E_USERS_RBAC_MVP.md](E2E_USERS_RBAC_MVP.md) · [STAGE_12_PLAN.md](STAGE_12_PLAN.md) · [STAGE_13_PLAN.md](STAGE_13_PLAN.md) · [STAGE_24_PLAN.md](STAGE_24_PLAN.md) · [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) · [STAGE_35_PLAN.md](STAGE_35_PLAN.md)

This is the **MVP E2E sale-to-payment packaging surface**: a checklist for creating a customer, selling through POS, receiving payment, and verifying stock reduction on a real test tenant before financial verification smoke. It extends Stage 12–13 POS/sales chains and Stage 24 commerce gates — it does **not** claim live POS success, demo sales seed, vendor USB/serial drivers Complete, or that E2E smoke was executed.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Checklist step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Operator action or deferred polish still required |

Every step keeps `done: false`. Top-level `live_sale_payment_claimed: false` / `e2e_smoke_executed_claimed: false` / `demo_tenant_claimed: false` / `usb_serial_drivers_claimed: false`.

## Register scope

1. Create customer for real test tenant (no demo seed).
2. POS sale against in-stock products/warehouse.
3. Receive payment (cash / multi-tender as applicable).
4. Verify stock reduction / movements.
5. Receipt / cash-drawer close honesty (Stage 13).
6. Insufficient-stock atomicity honesty (no orphans).
7. Tenant isolation on POS/sales path.
8. Sales/POS document-numbering honesty (Stage 24 N1).
9. Vendor USB/serial POS drivers deferred Remaining.
10. Live sale-to-payment execution Remaining.

## Automation hooks

1. Maintain `ops/mvp/e2e-sale-payment.json` (synced by `test_e2e_sale_payment_s1.py`).
2. Align honesty with purchase-to-stock / users-RBAC / Stage 12–13 / Stage 24 flags.
3. CI proves packaging honesty only — never forges live POS success.

## Explicitly not claimed

- Live sale-to-payment executed Complete because Stage 35 S1 packaging exists
- Demo tenants / seed customers / fake POS success as Complete
- Vendor USB/serial POS drivers Complete (Stage 24 Remaining)
- Live E2E smoke executed Complete
- Live go-live / §7 / attestation Complete

## Sign-off

Stage 35 S1 is met when this doc + register JSON + evidence JSON exist, `test_e2e_sale_payment_s1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 35 S1 without inventing live POS success or demo sales seed.
