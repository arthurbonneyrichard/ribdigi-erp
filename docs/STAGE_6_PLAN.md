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
| **K1** | Tenant API keys (BR-18.1) | P0 | COMPLETE |
| **W1** | Webhooks + HMAC signing (API docs §17) | P0 | COMPLETE |
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

## K1 acceptance criteria

- [x] `api_keys` table (Alembic `0078`); secret hashed (`rdk_` prefix), shown once on create.
- [x] Admin CRUD: `GET/POST /api-keys`, `GET/DELETE /api-keys/{id}` (company_admin/super_admin).
- [x] Auth via `X-API-Key` or `Authorization: Bearer rdk_…` with scoped permissions + tenant checks.
- [x] Audit `api_key_create` / `api_key_revoke`; Security UI list/create/revoke.
- [x] Automated tests in `backend/tests/test_api_keys_k1.py`.

## W1 acceptance criteria

- [x] `webhook_endpoints` + `webhook_deliveries` (Alembic `0079`); signing secret encrypted (`whsec_…`).
- [x] Admin CRUD + `POST /webhooks/{id}/test`; HTTPS required (localhost http allowed).
- [x] HMAC-SHA256 header `X-Ribdigi-Signature: t=…,v1=…`; delivery log status.
- [x] Fan-out `emit_event` wired for `sale.created` on invoice post; Security UI manage/test.
- [x] Automated tests in `backend/tests/test_webhooks_w1.py`.

## Sign-off

Stage 6 exit will be recorded in `docs/STAGE_6_EXIT_CRITERIA.md` with a freeze ADR when P0 workstreams are complete.
