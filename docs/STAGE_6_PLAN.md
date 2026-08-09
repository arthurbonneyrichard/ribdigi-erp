# Stage 6 Plan — Integrations, Onboarding & Performance

**Status:** Closed — exit met; freeze ADR-018  
**Base:** Remaining Phase 5 roadmap items (BR-18 API/webhooks, onboarding, caching) + `PRODUCTION_READINESS.md`  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** [STAGE_6_EXIT_CRITERIA.md](STAGE_6_EXIT_CRITERIA.md) · **Freeze:** [ADR-018](ADR_018_STAGE6_FREEZE.md)  


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
| **N2** | Tenant onboarding checklist (API + Shell) | P0 | COMPLETE |
| **P2** | Redis app-data cache for dashboard/catalog | P0 | COMPLETE |
| **H6x** | Stage 6 exit criteria + freeze ADR | Exit | COMPLETE |

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

## N2 acceptance criteria

- [x] `tenants.onboarding_state` JSON (Alembic `0080`); `{dismissed_at, skipped[]}`.
- [x] Auto-detect steps: setup company → add products → create supplier → stock on hand → first sale.
- [x] API: `GET /onboarding/checklist`; admin skip/unskip/dismiss/restore; dismissible at ≥80%.
- [x] Shell persistent Getting started banner with progress bar and step links.
- [x] Automated tests in `backend/tests/test_onboarding_checklist_n2.py`.

## P2 acceptance criteria

- [x] `backend/app/cache.py` AppCache (Redis preferred, memory fallback; soft-fail).
- [x] Config: `CACHE_ENABLED`, `CACHE_BACKEND`, TTLs (dashboard 300s, catalog 600s), `CACHE_REDIS_PREFIX`.
- [x] Cache `GET /dashboard`, `GET /products`, `GET /catalog/categories` (flat + tree keys).
- [x] Invalidate on product/catalog/stock/sale/expense mutations (`invalidate_tenant` / catalog / dashboard).
- [x] Automated tests in `backend/tests/test_app_cache_p2.py`.

## H6x acceptance criteria

- [x] `docs/STAGE_6_EXIT_CRITERIA.md` records K1–P2 COMPLETE with evidence.
- [x] Freeze ADR-018 accepted (no new Stage 6 feature scope; Stage 7 requires explicit open).
- [x] Automated smoke: `backend/tests/test_stage6_exit_h6x.py`.

## Sign-off

Stage 6 exit recorded in `docs/STAGE_6_EXIT_CRITERIA.md`; freeze ADR-018.
