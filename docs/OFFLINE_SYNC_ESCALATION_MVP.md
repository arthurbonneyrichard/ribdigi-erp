# Offline / Sync Escalation Paths MVP — Stage 170 E1

**Status:** Complete (MVP packaging) — Stage 170 E1  
**Evidence:** `backend/tests/test_stage170_escalation_e1.py`  
**Register:** `ops/mvp/offline-sync-escalation.json`  
**Related:** [OFFLINE_SYNC_RUNBOOK_MVP.md](OFFLINE_SYNC_RUNBOOK_MVP.md) · [OFFLINE_COMPLETE_ATTESTATION.md](OFFLINE_COMPLETE_ATTESTATION.md) · [INCIDENT_SEVERITY_MATRIX_MVP.md](INCIDENT_SEVERITY_MATRIX_MVP.md) · [SUPPORT_READINESS_MVP.md](SUPPORT_READINESS_MVP.md) · [STAGE_170_PLAN.md](STAGE_170_PLAN.md)

Escalation paths for offline/POS/sync incidents. Indexes Stages 163–169 contracts. Does **not** claim Offline Complete or live on-call Complete.

## Escalation paths

| Symptom | First response (L1) | Escalate when | Severity hint |
|---------|---------------------|---------------|---------------|
| Browser OFFLINE; sale queued | Confirm device bound; wait for ONLINE; Flush offline queue | Flush fails for >1 cashier or queue grows unboundedly | P3 → P2 |
| `/sync/push` 409 device revoked | Bind new active device; do not delete pending ops | Tenant lost all active devices; sales blocked | P2 |
| Open conflicts | Resolve keep_server / dismiss / accept_client per policy | accept_client blocked on applied POS; business disputes sale | P3 → P2 |
| Catalog TTL expired | Refresh offline catalog when ONLINE | No device bound / pull fails tenant-wide | P3 |
| Hold soft-reserve stuck | Expire stale soft-reserves; verify `reserved_qty` | Stock locked across products after expiry failed | P2 |
| SW / API cache suspicion | Confirm SW never caches `/api/v1/*` (Stage 168 W1) | Evidence of API responses in Cache Storage | P1 if tokens/PII cached |
| Suspected cross-tenant sync leak | Stop sync; preserve evidence; security path | Any confirmed leak | **P1** |

## Path steps (packaged)

1. Capture tenant_id, device_id, client_op_id, conflict_id, timestamps.
2. Apply L1 from `OFFLINE_SYNC_RUNBOOK_MVP.md`.
3. Map severity via Stage 170 V1 matrix.
4. Escalate P1/P2 using Stage 30 I1 incident checklist (PagerDuty remains not claimed).
5. Record honesty: Offline Complete still MISSING.

## Honesty

| Flag | Value |
|------|-------|
| `offline_complete_claimed` | **false** |
| `oncall_rota_live` | **false** |
| `pagerduty_hosted_claimed` | **false** |
| `attestation_claimed` | **false** |

## Explicitly not claimed

- Offline Complete product acceptance
- Live on-call / PagerDuty Complete
- Fabricated escalation SLAs
