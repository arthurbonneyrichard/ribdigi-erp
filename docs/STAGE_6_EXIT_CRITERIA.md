# Stage 6 Exit Criteria

**Status:** Met for Integrations, Onboarding & Performance workstreams K1, W1, N2, P2 (2026-08-09)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Freeze:** [ADR-018](ADR_018_STAGE6_FREEZE.md)  
**Plan:** [STAGE_6_PLAN.md](STAGE_6_PLAN.md)

Stage 6 exit closes the Integrations, Onboarding & Performance track left after Stage 5 freeze. It is **not** a claim that Kubernetes, WAL/PITR, vendor pen test, PgBouncer, permissions cache, or a certified 1000-VU production run are Complete.

## Workstream checklist

| ID | Workstream | Verdict | Evidence |
|----|------------|---------|----------|
| K1 | Tenant API keys (BR-18.1) | COMPLETE | Alembic `0078`; `X-API-Key` / `rdk_…`; Security UI; `test_api_keys_k1.py` |
| W1 | Webhooks + HMAC signing | COMPLETE | Alembic `0079`; `X-Ribdigi-Signature`; `sale.created`; `test_webhooks_w1.py` |
| N2 | Tenant onboarding checklist | COMPLETE | Alembic `0080`; Shell banner; dismiss ≥80%; `test_onboarding_checklist_n2.py` |
| P2 | Redis app-data cache | COMPLETE | `app/cache.py`; dashboard 5m / catalog 10m; invalidation; `test_app_cache_p2.py` |
| H6x | Exit criteria + freeze ADR | COMPLETE | This document + ADR-018 |

## Explicitly deferred (not Stage 6 blockers)

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- User permissions Redis cache (1h TTL) and PgBouncer
- Operator staging 1000-VU capacity certification (L1 scripts exist; run is ops)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- Prophet/LLM upgrades; multi-bin; user↔store membership (ADR-005)
- Items already deferred under Stage 1–5 ADRs

## Sign-off rule

Stage 6 foundation exit is **met** when the table above has no CRITICAL/MISSING rows for K1, W1, N2, P2 and ADR-018 is accepted. Broader commercial MVP readiness remains in `PRODUCTION_READINESS.md`.
