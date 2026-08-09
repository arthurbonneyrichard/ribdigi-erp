# Stage 7 Plan — Launch Reliability Closeout

**Status:** Open (ADR-019)  
**Base:** Remaining Phase 5 polish items after Stage 6 freeze + `PRODUCTION_READINESS.md`  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 7 closes reliability and ops-hygiene holes that block a confident commercial launch. It is **not** Kubernetes, WAL/PITR, or vendor pen test.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (W1 webhooks → retries; P2 AppCache → permissions cache).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **W2** | Webhook delivery retries + exponential backoff | P0 | COMPLETE |
| **C2** | Permissions Redis cache (1h TTL) | P0 | COMPLETE |
| **K2** | API key usage statistics | P1 | COMPLETE |
| **L7x** | Launch checklist doc + Stage 7 exit/freeze | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- Certified 1000-VU staging run; Prophet/LLM; multi-bin; PgBouncer

## W2 acceptance criteria

- [x] Failed deliveries enter `pending_retry` with `next_retry_at` (exponential backoff).
- [x] Celery/job `retry_due_webhooks` re-attempts with fresh HMAC `t=`; max attempts configurable.
- [x] Terminal `failed` after max attempts; success → `delivered` and stops retries.
- [x] Alembic `0081` (`next_retry_at`); automated tests in `backend/tests/test_webhook_retries_w2.py`.

## C2 acceptance criteria

- [x] `current_claims` / `GET /me` resolve permissions via AppCache (`ribdigi:cache:perms:{tenant_id}:{user_id}`, TTL 1h).
- [x] Soft-fail when `CACHE_ENABLED=false` or Redis unavailable (same pattern as P2).
- [x] Invalidate on user role / `record_scope` change and custom-role updates that sync assigned users.
- [x] Automated tests in `backend/tests/test_permissions_cache_c2.py`.

## K2 acceptance criteria

- [x] Alembic `0082`: `api_keys.request_count` + `api_key_usage_daily` (per-day counts).
- [x] Each authenticated API-key request increments lifetime + daily counters and persists `last_used_at`.
- [x] `GET /api-keys/{id}/usage?days=` returns totals and zero-filled daily series (1–90 days).
- [x] Security UI shows requests / last used and a requests-per-day chart.
- [x] Automated tests in `backend/tests/test_api_key_usage_k2.py`.

## Sign-off

Stage 7 exit will be recorded in `docs/STAGE_7_EXIT_CRITERIA.md` with a freeze ADR when planned workstreams are complete.
