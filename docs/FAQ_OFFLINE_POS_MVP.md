# FAQ — Offline / POS / Hold MVP — Stage 171 F1

**Status:** Complete (MVP packaging) — Stage 171 F1  
**Evidence:** `backend/tests/test_stage171_faq_f1.py`  
**Register:** `ops/mvp/faq-offline-pos.json`  
**Related:** [KNOWLEDGE_BASE_MVP.md](KNOWLEDGE_BASE_MVP.md) · [OFFLINE_SYNC_RUNBOOK_MVP.md](OFFLINE_SYNC_RUNBOOK_MVP.md) · [USER_MANUAL.md](USER_MANUAL.md) · [STAGE_171_PLAN.md](STAGE_171_PLAN.md)

FAQ packaging for POS offline/sync, Hold/soft-reserve, catalog cache, conflicts, and device revoke. Answers describe shipped MVP behavior only. **Offline Complete remains MISSING.**

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `offline_complete_claimed` | **false** |
| `hosted_kb_saas_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## FAQ

### How do I sell when the browser is offline?

1. Bind a device under Settings → Offline sync (**Bind browser**) while online.
2. Refresh the offline catalog on POS (4h TTL; stock is stale / non-authoritative).
3. When OFFLINE, Complete sale enqueues into IndexedDB and flushes via `/sync/push` when back online.
4. This is **not** Offline Complete attestation.

### What does Hold cart do?

Hold parks the current cart (`/pos#holds`). When online, Hold soft-reserves stock (`product.reserved_qty`). Resume/discard releases the reserve. Soft-reserves expire after **4 hours**. Hold is **not** a sale.

### Why is offline search empty or stale?

Refresh the offline catalog when online. After TTL expiry, refresh again. Stock figures are labeled non-authoritative until a successful online refresh.

### Accept client failed / conflict?

Settings → Offline sync shows conflict summary. Accept client re-applies only when the original op was never applied; already-applied POS is blocked to prevent double-post. Escalate via `OFFLINE_SYNC_ESCALATION_MVP.md` if needed.

### Device revoked with pending queue?

Revoke soft-blocks the device. Pending queue ops are **kept** (not auto-applied). Bind a new active device before flushing. Offline Complete remains deferred.

### Where are backup drills documented?

Operators use `BACKUP_RESTORE_DRILL_HONESTY_MVP.md` — live DR Completes stay false.

## Explicitly not claimed

- Offline Complete product claim
- USB/serial hardware driver Completes
- Fabricated FAQ resolution SLAs

See also Stage 190 Offline materials remaining-gate index: [`OFFLINE_MATERIALS_REMAINING_GATE_MVP.md`](OFFLINE_MATERIALS_REMAINING_GATE_MVP.md).

## Stage 172 B1 / O1 amendment

Day-one ordered checklists: [CASHIER_BIND_CATALOG_MVP.md](CASHIER_BIND_CATALOG_MVP.md) · [CASHIER_POS_DAYONE_MVP.md](CASHIER_POS_DAYONE_MVP.md) (`test_stage172_bind_b1.py`, `test_stage172_ops_o1.py`).
