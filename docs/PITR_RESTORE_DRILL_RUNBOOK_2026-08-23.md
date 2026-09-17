# PITR + restore drill runbook — commercial readiness (2026-08-23)

**Purpose:** Operator execution guide for the commercial readiness blocker “Live PITR / restore drill NOT RUN”.  
**Does NOT claim:** drill executed, go-live, or Completes.

## Authoritative existing packs (use these)

| Doc / artifact | Role |
|----------------|------|
| `docs/DR_WAL_PITR_RUNBOOK.md` | WAL archive + PITR procedure |
| `docs/DR_LOGICAL_BACKUP_RUNBOOK.md` | Logical `.ribbak` restore |
| `docs/PITR_DRILL_PACK_MVP.md` | Stage 28 packaging |
| `ops/postgres/pitr-drill-checklist.json` | Step map |
| `ops/backup/docker-compose.wal-drill.example.yml` | Optional compose sketch |

Flags remain false until a **real** staging/prod drill is logged: `operator_pitr_drill_executed: false`.

## Prerequisites

- [ ] Staging Postgres with WAL archiving + base backup available
- [ ] S3-compatible WAL / base prefixes reachable
- [ ] RPO/RTO targets agreed (strategy defaults: RPO ≤15m, RTO ≤4h)
- [ ] Named operator + backup ID recorded before start
- [ ] Commercial migrations applied on the **source** DB snapshot under test (`docs/COMMERCIAL_DEPLOY_MIGRATIONS_2026-08-23.md`)

## Drill outline

1. **Logical smoke (optional first):** restore a `.ribbak` to a scratch tenant per logical runbook; verify tenant isolation.
2. **PITR:** empty data dir → restore base backup → `restore_command` from WAL prefix → recovery target time → promote.
3. **App smoke:** `GET /api/v1/health/ready`; login; spot-check companies/stores/sample POS sale; offline device list still coherent if columns present.
4. **Entitlement smoke:** tenant `max_companies` / `max_users` columns present after migrate-on-restore path.

## Evidence template

```text
Date:
Operator:
Environment: staging | production-like
Base backup ID:
Recovery target (UTC):
Alembic head after restore:
health/ready: pass | fail
Login + tenant spot-check: pass | fail
Offline bind smoke (optional): pass | fail | n/a
Pass/Fail overall:
Notes / links:
```

## Explicitly not claimed

- CI-executed `pg_basebackup` success
- Production cutover
- Forged LAUNCH §7
- Offline Complete
