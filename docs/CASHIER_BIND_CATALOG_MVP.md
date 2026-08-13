# Cashier Bind + Catalog Day-One MVP — Stage 172 B1

**Status:** Complete (MVP packaging) — Stage 172 B1  
**Evidence:** `backend/tests/test_stage172_bind_b1.py`  
**Register:** `ops/mvp/cashier-bind-catalog.json`  
**Related:** [CASHIER_QUICKSTART_MVP.md](CASHIER_QUICKSTART_MVP.md) · [OFFLINE_SYNC_RUNBOOK_MVP.md](OFFLINE_SYNC_RUNBOOK_MVP.md) · [FAQ_OFFLINE_POS_MVP.md](FAQ_OFFLINE_POS_MVP.md) · [STAGE_172_PLAN.md](STAGE_172_PLAN.md)

Day-one steps for device bind and offline catalog refresh before relying on offline POS search/queue.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist (while ONLINE)

1. Go to Settings → Offline sync (`/company#offline-sync`).
2. **Bind browser** for this cashier device (active device required for offline queue + catalog).
3. On POS, run **Refresh offline catalog** (requires bound device).
4. Confirm catalog cache age; default TTL is **4 hours**.
5. Treat offline stock figures as **stale / non-authoritative** until next successful refresh.
6. If the device was revoked, bind a new active device before flushing queued ops (queue is kept, not auto-applied).

## Explicitly not claimed

- Offline Complete attestation
- Authoritative offline stock Completes
- USB/serial hardware Completes
