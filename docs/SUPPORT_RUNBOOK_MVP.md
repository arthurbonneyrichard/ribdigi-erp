# Support Runbook MVP — Admin Manual ↔ Ops Pack Fidelity

**Status:** Complete (MVP) — Stage 30 S1  
**Evidence:** `backend/tests/test_support_runbook_s1.py` · `/opt/cursor/artifacts/launch/stage30_s1_support_runbook.json`  
**Map:** `ops/support/admin-ops-map.json`  
**Related:** `docs/ADMIN_MANUAL.md` §§7 / 11 / 12 · Stage 26–30 `ops/` packs · [INCIDENT_PACK_MVP.md](INCIDENT_PACK_MVP.md) · [EVIDENCE_LEDGER_MVP.md](EVIDENCE_LEDGER_MVP.md)

This is the **MVP support & Admin runbook fidelity surface**: map `ADMIN_MANUAL` maintenance / troubleshooting sections to Stage 26–30 operator packs without inventing live ops success or a hosted support desk Complete.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Follow UI steps in ADMIN_MANUAL; use linked `ops/` packs for infra drills |
| `ci_proven` | This map + ADMIN_MANUAL citations synced by `test_support_runbook_s1.py` |
| `deferred` | Live support SLA Complete; inventing green PITR/cutover from the manual |

## Section map (summary)

| ADMIN_MANUAL | Ops packs |
|--------------|-----------|
| §7 Backup & Recovery | `DR_LOGICAL_BACKUP_RUNBOOK.md`, `DR_WAL_PITR_RUNBOOK.md`, `PITR_DRILL_PACK_MVP.md`, Stage 27 B1 offsite |
| §11 Maintenance & Monitoring | `OPS_MONITORING_MVP.md`, `GRAFANA_PACK_MVP.md`, `INCIDENT_PACK_MVP.md` |
| §12 Troubleshooting / Emergency | `INCIDENT_PACK_MVP.md`, `CUTOVER_PACK_MVP.md`, `TLS_INGRESS_PACK_MVP.md`, `PGBOUNCER_SOAK_PACK_MVP.md`, `EVIDENCE_LEDGER_MVP.md` |

## Automation hooks

1. Maintain `ops/support/admin-ops-map.json` (synced by `test_support_runbook_s1.py`).
2. ADMIN_MANUAL §§7 / 11 / 12 cite Stage 30 S1 + pack docs with Remaining honesty.
3. CI proves packaging honesty only: `live_ops_success_claimed: false`, `support_sla_claimed: false`.

## Explicitly not claimed

- Live support SLA / status-page Complete
- Treating ADMIN_MANUAL UI steps as proof of green PITR / cutover / PagerDuty
- Re-packaging Stage 26–29 packs as new Complete
- Hosted helpdesk SaaS Complete

## Stage 170 S1 amendment

Tenant MVP support readiness consolidates this pack with Stage 169 offline/sync ops: [SUPPORT_READINESS_MVP.md](SUPPORT_READINESS_MVP.md) (`ops/mvp/support-readiness.json`, `test_stage170_support_s1.py`). Live support SLA remains not claimed.

## Sign-off

Stage 30 S1 is met when this doc + admin-ops map + evidence JSON exist, `test_support_runbook_s1.py` passes, and ADMIN_MANUAL / launch / roadmap cite Stage 30 S1 without inventing live ops success.
