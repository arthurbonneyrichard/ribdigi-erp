# PgBouncer Soak Pack MVP — Operator Soak / Pooler Packaging

**Status:** Complete (MVP) — Stage 29 B2  
**Evidence:** `backend/tests/test_pgbouncer_soak_b2.py` · `/opt/cursor/artifacts/db/stage29_b2_pgbouncer_soak.json`  
**Checklist map:** `ops/postgres/pgbouncer-soak-checklist.json`  
**Soak schema:** `ops/postgres/soak-evidence.example.json`  
**Optional k8s snippet:** `ops/postgres/pgbouncer-deployment.example.yaml`  
**Related:** [PGBOUNCER_MVP.md](PGBOUNCER_MVP.md) (Stage 27 P1)

This is the **MVP PgBouncer soak / Helm-pooler packaging surface**: soak checklist + evidence schema + optional in-cluster Deployment snippet extending Stage 27 P1. It is **not** live soak numbers certified in CI and does **not** claim PgBouncer as the default Helm data plane.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Deploy pooler, point `DATABASE_URL`, verify `SHOW POOLS`, run soak, record evidence |
| `ci_proven` | Stage 27 P1 packaging + asyncpg transaction-mode safety + this pack honesty |
| `deferred` | Live soak Complete in CI; default in-cluster Helm pooler; managed-cloud proxy Complete |

## Automation hooks

1. Maintain `ops/postgres/pgbouncer-soak-checklist.json` (synced by `test_pgbouncer_soak_b2.py`).
2. Optional k8s snippet stays under `ops/postgres/` — **not** wired into `helm/ribdigi/` as default.
3. CI proves packaging honesty only: `live_soak_executed: false`, `helm_pooler_default_claimed: false`.

## Explicitly not claimed

- Green soak p95 / error-rate certificate from CI
- Making PgBouncer the default in-cluster Helm data plane
- Managed RDS Proxy / cloud pooler Complete
- Treating Stage 27 P1 / Stage 29 B2 Complete as “pooler soak certified”

## Sign-off

Stage 29 B2 is met when this doc + checklist + soak schema + optional Deployment snippet + evidence JSON exist, `test_pgbouncer_soak_b2.py` passes, and PRODUCTION_READINESS / launch / roadmap cite Stage 29 B2 without inventing live soak success.

See also Stage 208 Tenant MVP PgBouncer Soak remaining-gate index fidelity (`docs/PGBOUNCER_SOAK_REMAINING_GATE_MVP.md`, ADR-422 / ADR-423) — packaging non-claim as live PgBouncer soak Complete.
