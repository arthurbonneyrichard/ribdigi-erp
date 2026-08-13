# Tenant MVP Store-Open Checklist MVP — Stage 173 S1

**Status:** Complete (MVP packaging) — Stage 173 S1  
**Evidence:** `backend/tests/test_stage173_storeopen_s1.py`  
**Register:** `ops/mvp/store-open-checklist.json`  
**Related:** [STORE_OPEN_LOWSTOCK_MVP.md](STORE_OPEN_LOWSTOCK_MVP.md) · [STORE_OPEN_HEALTH_MVP.md](STORE_OPEN_HEALTH_MVP.md) · [CASHIER_QUICKSTART_MVP.md](CASHIER_QUICKSTART_MVP.md) · [STAGE_173_PLAN.md](STAGE_173_PLAN.md)

Recurring open-of-day checklist hub for manager/cashier. Distinct from Stage 172 day-one cashier onboarding. Does **not** claim Offline Complete, live training, or go-live.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `live_training_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Open-of-day order

1. Sign in with correct tenant; confirm role can operate POS for the store.
2. Complete **L1** — select store/warehouse context; glance low-stock.
3. Complete **H1** — expire stale Holds; check offline device health; glance sync conflict queue.
4. If a new cashier/device: run Stage 172 quickstart (bind + catalog) first.
5. Leave Offline Complete / live training as Remaining.

## Explicitly not claimed

- Offline Complete product acceptance
- Fabricated “store opened green” Completes
- Live training / go-live Completes

## Stage 174 C1 amendment

Recurring end-of-day (not open-of-day): [STORE_CLOSE_CHECKLIST_MVP.md](STORE_CLOSE_CHECKLIST_MVP.md) (`ops/mvp/store-close-checklist.json`, `test_stage174_storeclose_c1.py`).

## Stage 175 P1 amendment

Mid-shift handoff pointers back to this open pack: [SHIFT_HANDOVER_POINTERS_MVP.md](SHIFT_HANDOVER_POINTERS_MVP.md) (`ops/mvp/shift-handover-pointers.json`, `test_stage175_pointers_p1.py`).
