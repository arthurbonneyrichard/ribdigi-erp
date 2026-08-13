# Incident Severity Matrix MVP — Stage 170 V1

**Status:** Complete (MVP packaging) — Stage 170 V1  
**Evidence:** `backend/tests/test_stage170_severity_v1.py`  
**Register:** `ops/mvp/incident-severity-matrix.json`  
**Related:** [INCIDENT_PACK_MVP.md](INCIDENT_PACK_MVP.md) · [SUPPORT_SLA_BOUNDARY_MVP.md](SUPPORT_SLA_BOUNDARY_MVP.md) · [SECURITY_GUIDE.md](SECURITY_GUIDE.md) §15 · [STAGE_170_PLAN.md](STAGE_170_PLAN.md)

Tenant MVP severity matrix extending Stage 30 I1 P1–P4 with product/offline/sync trigger examples. Does **not** claim live on-call, PagerDuty, or incident drill execution Complete.

## Severity matrix

| Level | Ack target | Tenant MVP / offline-sync examples | Escalate to |
|-------|------------|--------------------------------------|-------------|
| **P1** Critical | 15 min | Tenant-wide outage; suspected data breach; cross-tenant leak; auth totally down | On-call + security (Stage 30 I1 / SECURITY_GUIDE §15) |
| **P2** High | 1 hour | POS cannot sell online or flush offline queue for multiple cashiers; sync push failing for all active devices; reserved stock stuck after hold expiry bug | Ops on-call; product lead if data integrity |
| **P3** Medium | 24 hours | Single-device revoke confusion; catalog TTL stale UX; one conflict storm; Hold soft-reserve UX defect | Support L2 / engineering backlog |
| **P4** Low | 7 days | Docs/runbook gaps; non-blocking UI copy; hardening follow-ups | Backlog |

Ack targets align with Stage 30 I1 / Stage 36 SLA boundary packaging. `support_sla_claimed` and `oncall_rota_live` remain **false**.

## Honesty

| Flag | Value |
|------|-------|
| `pagerduty_hosted_claimed` | **false** |
| `oncall_rota_live` | **false** |
| `incident_drill_executed` | **false** |
| `go_live_claimed` | **false** |

## Explicitly not claimed

- Live paging / PagerDuty Complete
- Fabricated ack SLAs from CI
- Offline Complete or go-live Complete
