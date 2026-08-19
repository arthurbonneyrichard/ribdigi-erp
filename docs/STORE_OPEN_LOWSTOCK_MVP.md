# Store-Open Store Select + Low-Stock MVP — Stage 173 L1

**Status:** Complete (MVP packaging) — Stage 173 L1  
**Evidence:** `backend/tests/test_stage173_lowstock_l1.py`  
**Register:** `ops/mvp/store-open-lowstock.json`  
**Related:** [STORE_OPEN_CHECKLIST_MVP.md](STORE_OPEN_CHECKLIST_MVP.md) · [USER_MANUAL.md](USER_MANUAL.md) · [STAGE_173_PLAN.md](STAGE_173_PLAN.md)

Open-of-day store/warehouse selection and low-stock glance packaging.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

1. Confirm active **store** (and warehouse if multi-warehouse) before POS sales.
2. Open **Inventory → Low stock** (or store reorder policy surfaces) for a morning glance.
3. Note `stock_status` traffic lights and `suggested_order_qty` where shown — draft PO is not auto-placed.
4. Do not treat offline catalog stock as authoritative for reorder decisions.
5. Escalate store-wide stock outages via support readiness / severity packs if needed.

## Explicitly not claimed

- Automatic purchase Complete from this glance
- Authoritative offline stock Completes
- Offline Complete / go-live Completes
