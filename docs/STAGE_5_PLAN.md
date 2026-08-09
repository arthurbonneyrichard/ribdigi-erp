# Stage 5 Plan — Polish, Security & Launch Hardening

**Status:** Open (ADR-015)  
**Base:** Phase 5 roadmap (`docs/DEVELOPMENT_ROADMAP.md` §6) + `PRODUCTION_READINESS.md` launch gates  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 5 here is **not** a rewrite of auth, audit, or backup. Core engines already exist. This plan closes remaining production-readiness holes, then freezes Stage 5.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (security middleware, OWASP smoke, backup restore, AI RBAC).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Production security gate (rate limit / headers / CORS) | P0 | COMPLETE |
| **O1** | OWASP automated suite beyond smoke | P0 | COMPLETE |
| **A1** | AI audit + prompt/data protections | P0 | COMPLETE |
| **B1** | Logical backup restore proof + DR drill runbook | P0 | COMPLETE |
| **H5** | Deep `/health` (+ optional Prometheus `/metrics`) | P0 | COMPLETE |
| **L1** | Load-test baseline scripts | P0 | COMPLETE |
| **H5x** | Stage 5 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- Public API keys + webhooks platform
- Onboarding checklist UX (P1)
- Redis app-data cache / PgBouncer (park after L1)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)

## S1 acceptance criteria

- [x] Production settings reject weak JWT, DEBUG, wildcard/empty CORS, disabled rate limits; accept Redis-required posture.
- [x] Security headers (CSP `default-src 'none'`, frame deny, COOP) on `/api/v1/health`; HSTS + `Cache-Control: no-store` when `APP_ENV=production`.
- [x] Auth vs API rate limits with `429 RATE_LIMIT_EXCEEDED` + `Retry-After` / `X-RateLimit-*` headers.
- [x] OpenAPI `/docs` disabled when production (`openapi_enabled()`); health exposes non-sensitive `security` posture.
- [x] Automated tests in `backend/tests/test_production_security_s1.py`.

## O1 acceptance criteria

- [x] Automated suite beyond smoke covers OWASP A01 (access control / IDOR / privilege escalation), A02 (secrets + JWT integrity), A03 (injection / XSS-as-JSON), A05 (safe errors), A07 (auth failures / expired token).
- [x] Existing smoke suite remains green (`test_owasp_smoke.py`).
- [x] Vendor ZAP / external pen test explicitly deferred (not a Stage 5 P0 blocker).
- [x] Automated tests in `backend/tests/test_owasp_suite_o1.py`.

## A1 acceptance criteria

- [x] Shared `ai_guard` sanitizes free-text AI prompts (max length + injection/exfil patterns) before processing.
- [x] Successful AI mutating/NL endpoints audit with `module=ai` and redacted `prompt_preview` (secrets/emails stripped).
- [x] Rejected prompts audit `ai_prompt_rejected` (committed) and return HTTP 400.
- [x] Covered endpoints: chat, report generate/export, report templates create, customer assist, document analyze.
- [x] Automated tests in `backend/tests/test_ai_audit_protections_a1.py`.

## B1 acceptance criteria

- [x] Post-restore integrity proof compares sampled backup rows to live tenant data (`prove_restore_integrity`).
- [x] `POST /backup/{id}/verify` decrypts + proves against live data; audits `restore_verify`.
- [x] Apply restore returns `proof` and requires `confirm_text=RESTORE` for destructive apply.
- [x] Automated drill test: backup → mutate → dry-run → restore → verify (`test_backup_restore_proof_b1.py`).
- [x] Operator runbook `docs/DR_LOGICAL_BACKUP_RUNBOOK.md` (logical `.ribbak`; WAL/PITR deferred).

## H5 acceptance criteria

- [x] Shallow `GET /health` remains liveness-safe (security posture, no hard dependency).
- [x] Deep checks via `?deep=true` and `GET /health/ready` probe database, Redis, and Celery broker.
- [x] Overall `error` (DB down / required Redis down) returns HTTP 503; optional broker/redis issues are `degraded`.
- [x] Optional Prometheus text `GET /metrics` (`METRICS_ENABLED`, request counters via middleware).
- [x] Automated tests in `backend/tests/test_health_metrics_h5.py`.
- [x] Full Prometheus/Grafana/PagerDuty stack remains deferred (ADR-015).

## L1 acceptance criteria

- [x] Documented baseline targets + runbook (`docs/LOAD_TEST_BASELINE.md`).
- [x] httpx harness with scenarios: health, login, products, dashboard (`backend/loadtest/`).
- [x] CLI `python -m loadtest.run_baseline` (+ `--smoke`) and Makefile `loadtest-smoke`.
- [x] Optional Locust file for staging capacity runs (Locust not a prod dependency).
- [x] Automated ASGI smoke in `backend/tests/test_loadtest_baseline_l1.py`.
- [x] Full 1000-VU production certification remains an operator staging drill (not CI).

## Sign-off

Stage 5 exit will be recorded in `docs/STAGE_5_EXIT_CRITERIA.md` with a freeze ADR when P0 workstreams are complete.
