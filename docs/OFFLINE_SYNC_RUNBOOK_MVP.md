# Offline / Sync Operator Runbook MVP — Stage 169 R1

**Status:** Complete (MVP packaging) — Stage 169 R1  
**Evidence:** `backend/tests/test_stage169_offline_runbook_r1.py`  
**Register:** `ops/mvp/offline-sync-runbook.json`  
**Related:** [OFFLINE_COMPLETE_ATTESTATION.md](OFFLINE_COMPLETE_ATTESTATION.md) · Stages 163–168 fidelity notes · [STAGE_169_PLAN.md](STAGE_169_PLAN.md)

Operator runbook for tenant offline/sync surfaces. Indexes proven contracts from Stages 163–168. Does **not** claim Offline Complete.

## Preconditions

- Company admin / super_admin for device registration
- Bound browser device (`Settings → Offline sync → Bind browser`) for IndexedDB flush / catalog pull
- POS write permission for sales flush

## Procedures

### 1. Register and bind a device

1. Open `/company#offline-sync`.
2. Register device (web/android/ios/desktop/other).
3. **Bind browser** so IndexedDB flush and catalog refresh use that `device_id`.

### 2. Offline POS sale flush

1. When browser is OFFLINE, Complete sale enqueues into IndexedDB (`client_request_id` / `client_op_id`).
2. When ONLINE, **Flush offline queue** on POS (calls `POST /sync/push`).
3. Review conflicts under Settings if status is `conflict`.

### 3. Offline catalog

1. **Refresh offline catalog** on POS (pull + 4h TTL).
2. Treat stock as **non-authoritative** when OFFLINE.

### 4. Conflict resolve

1. Open conflicts show reason / client keys / accept_client policy.
2. **Keep server** / **Dismiss** — no re-apply.
3. **Accept client** — re-applies only if original op was never applied (never double-post applied POS).

### 5. Revoke a device (mid-queue honesty)

1. **Revoke** soft-blocks the device (409 on push/pull/ack).
2. Pending queue ops are **retained** (not auto-applied).
3. Bind a new active device before flushing again.

### 6. Hold soft-reserve expiry

1. Soft-reserved holds expire after 4h (`expires_at`).
2. Use **Expire stale soft-reserves** or rely on list auto-expire.

## Honesty

| Claim | Status |
|-------|--------|
| Offline Complete | **MISSING** / not claimed |
| `attestation_claimed` | **false** |
| SW caches `/api/v1/*` | **false** (forbidden) |

## Explicitly not claimed

- Full browser Playwright offline E2E Complete
- Offline Complete product acceptance
- Fabricated sync success

## Stage 170 E1 amendment

Escalation paths for offline/sync incidents: [OFFLINE_SYNC_ESCALATION_MVP.md](OFFLINE_SYNC_ESCALATION_MVP.md) (`ops/mvp/offline-sync-escalation.json`, `test_stage170_escalation_e1.py`).

## Stage 171 F1 / T1 amendment

Cashier/admin FAQ and symptom index: [FAQ_OFFLINE_POS_MVP.md](FAQ_OFFLINE_POS_MVP.md) · [TROUBLESHOOTING_INDEX_MVP.md](TROUBLESHOOTING_INDEX_MVP.md) (`ops/mvp/faq-offline-pos.json`, `ops/mvp/troubleshooting-index.json`). Offline Complete remains not claimed.

## Stage 172 Q1 amendment

Cashier day-one quickstart: [CASHIER_QUICKSTART_MVP.md](CASHIER_QUICKSTART_MVP.md) (`ops/mvp/cashier-quickstart.json`, `test_stage172_quickstart_q1.py`). Offline Complete remains not claimed.

## Stage 173 H1 amendment

Store-open device/conflict health: [STORE_OPEN_HEALTH_MVP.md](STORE_OPEN_HEALTH_MVP.md) (`ops/mvp/store-open-health.json`, `test_stage173_health_h1.py`). Offline Complete remains not claimed.
