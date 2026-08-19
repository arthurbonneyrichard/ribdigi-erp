# Store-Close Hold Clear + Sync Queue Drain MVP — Stage 174 E1

**Status:** Complete (MVP packaging) — Stage 174 E1  
**Evidence:** `backend/tests/test_stage174_drain_e1.py`  
**Register:** `ops/mvp/store-close-drain.json`  
**Related:** [STORE_CLOSE_CHECKLIST_MVP.md](STORE_CLOSE_CHECKLIST_MVP.md) · [STORE_OPEN_HEALTH_MVP.md](STORE_OPEN_HEALTH_MVP.md) · [CASHIER_POS_DAYONE_MVP.md](CASHIER_POS_DAYONE_MVP.md) · [STAGE_174_PLAN.md](STAGE_174_PLAN.md)

End-of-day held-cart clear/expiry and sync queue drain packaging.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Held carts

1. Open POS holds (`/pos#holds`); resume and complete, discard, or leave intentional parks.
2. Run **Expire stale soft-reserves** for past-due Holds (4h) so `reserved_qty` is released.
3. Do not treat Hold as a completed sale.

### Sync queue drain

1. Confirm browser ONLINE and device still active (not revoked).
2. Allow IndexedDB queue to flush via `/sync/push`; watch Settings → Offline sync depth.
3. If revoke mid-queue: bind a new device before expecting flush (queue kept).
4. A drained queue once is **not** Offline Complete.

## Explicitly not claimed

- Offline Complete attestation
- Guaranteed empty queue Completes
- Live support SLA Completes
