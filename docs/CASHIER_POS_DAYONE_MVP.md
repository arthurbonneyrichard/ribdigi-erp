# Cashier POS Day-One Ops MVP — Stage 172 O1

**Status:** Complete (MVP packaging) — Stage 172 O1  
**Evidence:** `backend/tests/test_stage172_ops_o1.py`  
**Register:** `ops/mvp/cashier-pos-dayone.json`  
**Related:** [CASHIER_QUICKSTART_MVP.md](CASHIER_QUICKSTART_MVP.md) · [CASHIER_BIND_CATALOG_MVP.md](CASHIER_BIND_CATALOG_MVP.md) · [FAQ_OFFLINE_POS_MVP.md](FAQ_OFFLINE_POS_MVP.md) · [OFFLINE_SYNC_ESCALATION_MVP.md](OFFLINE_SYNC_ESCALATION_MVP.md) · [STAGE_172_PLAN.md](STAGE_172_PLAN.md)

Day-one cashier ops for Hold/soft-reserve, offline sale sync flush, and conflict accept-client. Packaging only — **Offline Complete remains MISSING.**

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Checklist

### Hold / soft-reserve

1. On POS, **Hold cart** parks the cart (`/pos#holds`) — not a sale.
2. When online, Hold soft-reserves stock (`product.reserved_qty`).
3. Resume or discard releases the soft reserve.
4. Soft-reserves expire after **4 hours**; use **Expire stale soft-reserves** if needed.

### Sync flush (after offline sales)

1. Confirm top bar shows ONLINE after reconnect.
2. Bound device flushes IndexedDB queue via `/sync/push`.
3. Watch Settings → Offline sync for queue depth / conflicts.
4. Do not claim Offline Complete because flush succeeded once.

### Accept client (conflicts)

1. Open Settings → Offline sync conflict summary.
2. **Accept client** re-applies only when the original op was never applied.
3. Already-applied POS is blocked (prevents double-post).
4. Escalate unresolved conflicts via `OFFLINE_SYNC_ESCALATION_MVP.md`.

## Explicitly not claimed

- Offline Complete product claim
- Fabricated conflict-free sync SLAs
- Live support SLA Completes

## Stage 173 H1 amendment

Open-of-day Hold/device/conflict health: [STORE_OPEN_HEALTH_MVP.md](STORE_OPEN_HEALTH_MVP.md) (`ops/mvp/store-open-health.json`, `test_stage173_health_h1.py`).
