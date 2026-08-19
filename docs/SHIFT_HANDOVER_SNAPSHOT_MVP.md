# Shift-Handover Snapshot MVP — Stage 175 S1

**Status:** Complete (MVP packaging) — Stage 175 S1  
**Evidence:** `backend/tests/test_stage175_snapshot_s1.py`  
**Register:** `ops/mvp/shift-handover-snapshot.json`  
**Related:** [SHIFT_HANDOVER_CHECKLIST_MVP.md](SHIFT_HANDOVER_CHECKLIST_MVP.md) · [STORE_OPEN_HEALTH_MVP.md](STORE_OPEN_HEALTH_MVP.md) · [STORE_CLOSE_DRAIN_MVP.md](STORE_CLOSE_DRAIN_MVP.md) · [STAGE_175_PLAN.md](STAGE_175_PLAN.md)

Live-state snapshot for shift handoff: open Holds, pending sync depth, conflict ownership notes.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Open Holds

1. Open `/pos#holds`; count open held carts for this store.
2. Note any soft-reserves near **4h** expiry; expire stale if appropriate.
3. Tell incoming cashier which Holds are intentional vs abandoned.

### Pending sync depth

1. Settings → Offline sync: note queue depth / pending ops.
2. Prefer ONLINE flush before handoff when possible.
3. A lower depth is **not** Offline Complete.

### Conflict owners

1. List open conflicts with summary (Stage 167 U1).
2. Note who owns each (outgoing cashier / manager) and Accept-client honesty rules.
3. Escalate stuck items via `OFFLINE_SYNC_ESCALATION_MVP.md`.

## Explicitly not claimed

- Offline Complete attestation
- Zero-conflict / zero-queue Completes
- Live support SLA Completes
