# Stage 6 Plan — Integrations, Onboarding & Performance

**Status:** Open (ADR-017)  
**Base:** Remaining Phase 5 roadmap items (BR-18 API/webhooks, onboarding, caching) + `PRODUCTION_READINESS.md`  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 6 closes commercial-MVP integration and launch-ops holes left after Stage 5 freeze. It is **not** Kubernetes, WAL/PITR, or vendor pen test.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (JWT auth → API keys; notifications → webhooks; rate-limit Redis → app cache).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **K1** | Tenant API keys (BR-18.1) | P0 | PENDING |
| **W1** | Webhooks + HMAC signing (API docs §17) | P0 | PENDING |
| **N2** | Tenant onboarding checklist (API + Shell) | P0 | PENDING |
| **P2** | Redis app-data cache for dashboard/catalog | P0 | PENDING |
| **H6x** | Stage 6 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- Certified 1000-VU staging run (ops; scripts exist from L1)
- Prophet/LLM upgrades; multi-bin; user↔store membership (ADR-005)

## Sign-off

Stage 6 exit will be recorded in `docs/STAGE_6_EXIT_CRITERIA.md` with a freeze ADR when P0 workstreams are complete.
