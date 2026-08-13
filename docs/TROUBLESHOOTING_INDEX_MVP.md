# Troubleshooting Index MVP — Stage 171 T1

**Status:** Complete (MVP packaging) — Stage 171 T1  
**Evidence:** `backend/tests/test_stage171_troubleshoot_t1.py`  
**Register:** `ops/mvp/troubleshooting-index.json`  
**Related:** [KNOWLEDGE_BASE_MVP.md](KNOWLEDGE_BASE_MVP.md) · [FAQ_OFFLINE_POS_MVP.md](FAQ_OFFLINE_POS_MVP.md) · [OFFLINE_SYNC_ESCALATION_MVP.md](OFFLINE_SYNC_ESCALATION_MVP.md) · [BACKUP_RESTORE_DRILL_HONESTY_MVP.md](BACKUP_RESTORE_DRILL_HONESTY_MVP.md) · [STAGE_171_PLAN.md](STAGE_171_PLAN.md)

Symptom → pack index for Tenant MVP cashiers, admins, and support intake. Packaging only — not live support SLA or Offline Complete.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `support_sla_claimed` | **false** |
| `offline_complete_claimed` | **false** |
| `live_dr_claimed` | **false** |
| `go_live_claimed` | **false** |
| `attestation_claimed` | **false** |

## Symptom map

| Symptom | First stop | Escalate / related |
|---------|------------|--------------------|
| Browser shows OFFLINE; sales not posting | FAQ F1 + `OFFLINE_SYNC_RUNBOOK_MVP.md` | `OFFLINE_SYNC_ESCALATION_MVP.md` |
| Offline catalog empty / TTL expired | FAQ F1 (refresh catalog) | Severity matrix if store-wide |
| Hold cart; reserved qty stuck | FAQ F1 (expire stale soft-reserves) | Support readiness S1 |
| Sync conflict / Accept client blocked | FAQ F1 + Settings Offline sync | Escalation E1 → Stage 30 I1 |
| Device revoked; queue pending | FAQ F1 + Stage 168 R1 notes | Escalation E1 |
| Backup/restore drill unclear | `BACKUP_RESTORE_DRILL_HONESTY_MVP.md` | Migration gate if schema involved |
| Login / RBAC / wrong tenant | `USER_MANUAL.md` §16 + Security guide | Support readiness intake |
| P1 outage / multi-store POS down | `INCIDENT_SEVERITY_MATRIX_MVP.md` | Stage 30 I1 + escalation |

## Explicitly not claimed

- Live support SLA / PagerDuty Complete
- Live DR / PITR drill success from this index alone
- Offline Complete or go-live Complete
