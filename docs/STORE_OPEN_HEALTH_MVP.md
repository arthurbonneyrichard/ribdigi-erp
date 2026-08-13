# Store-Open Hold / Device / Conflict Health MVP — Stage 173 H1

**Status:** Complete (MVP packaging) — Stage 173 H1  
**Evidence:** `backend/tests/test_stage173_health_h1.py`  
**Register:** `ops/mvp/store-open-health.json`  
**Related:** [STORE_OPEN_CHECKLIST_MVP.md](STORE_OPEN_CHECKLIST_MVP.md) · [CASHIER_POS_DAYONE_MVP.md](CASHIER_POS_DAYONE_MVP.md) · [OFFLINE_SYNC_RUNBOOK_MVP.md](OFFLINE_SYNC_RUNBOOK_MVP.md) · [OFFLINE_SYNC_ESCALATION_MVP.md](OFFLINE_SYNC_ESCALATION_MVP.md) · [STAGE_173_PLAN.md](STAGE_173_PLAN.md)

Open-of-day health checks: stale Hold soft-reserves, offline device status, sync conflict queue. **Offline Complete remains MISSING.**

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Hold expiry

1. On POS holds (`/pos#holds`), review parked carts.
2. Run **Expire stale soft-reserves** (4h expiry) or rely on list auto-expiry.
3. Confirm released `reserved_qty` before morning rush.

### Offline device health

1. Settings → Offline sync: confirm this register’s device is **active** (not revoked).
2. If revoked with pending queue: bind a new device before flush (queue kept).
3. Refresh offline catalog if TTL expired (stock non-authoritative).

### Sync conflict queue

1. Glance open conflicts / queue depth under Offline sync.
2. Resolve with Accept client only when original op never applied.
3. Escalate stuck conflicts via `OFFLINE_SYNC_ESCALATION_MVP.md`.

## Explicitly not claimed

- Offline Complete product claim
- Zero-conflict SLA Completes
- Live support SLA Completes
