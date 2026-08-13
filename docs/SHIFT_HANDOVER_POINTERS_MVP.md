# Shift-Handover Device + Open/Close Pointers MVP — Stage 175 P1

**Status:** Complete (MVP packaging) — Stage 175 P1  
**Evidence:** `backend/tests/test_stage175_pointers_p1.py`  
**Register:** `ops/mvp/shift-handover-pointers.json`  
**Related:** [SHIFT_HANDOVER_CHECKLIST_MVP.md](SHIFT_HANDOVER_CHECKLIST_MVP.md) · [CASHIER_BIND_CATALOG_MVP.md](CASHIER_BIND_CATALOG_MVP.md) · [STORE_OPEN_CHECKLIST_MVP.md](STORE_OPEN_CHECKLIST_MVP.md) · [STORE_CLOSE_CHECKLIST_MVP.md](STORE_CLOSE_CHECKLIST_MVP.md) · [STAGE_175_PLAN.md](STAGE_175_PLAN.md)

Handoff pointers: device bind status for the register, plus store-open/close pack links for continuity.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Device bind status

1. Settings → Offline sync: confirm this browser’s device is **active** (not revoked).
2. If incoming cashier uses a new browser, run Stage 172 B1 bind + catalog refresh.
3. Revoked device with pending queue: bind new device before flush (queue kept).

### Store-open / store-close pointers

1. Morning or first shift: follow `STORE_OPEN_CHECKLIST_MVP.md` (Stage 173).
2. Last shift / closing: follow `STORE_CLOSE_CHECKLIST_MVP.md` (Stage 174).
3. Mid-shift handoffs use this Stage 175 pack; do not skip snapshot S1.

## Explicitly not claimed

- Offline Complete product claim
- Fabricated device-health Completes
- Live training Completes
