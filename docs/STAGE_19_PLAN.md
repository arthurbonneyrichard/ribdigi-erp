# Stage 19 Plan — API, Settings & Operator Reliability Fidelity

**Status:** Open  
**Base:** API surface → Company & security settings → Operator reliability  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-043](ADR_043_STAGE19_OPEN.md)

Stage 19 closes commercial-MVP API / settings / operator-reliability fidelity after Stage 18 freeze. Auth, API keys, webhooks, domain APIs, company settings, Redis cache, Celery jobs, and logical backup engines already exist (Stages 1 / 5 / 6 / 7 / 11–13). This track proves BR-18–20 and launch §5 with live evidence and docs sync — **not** Kubernetes, WAL/PITR, Grafana, certified 1000-VU, or greenfield APIs.

## Product outline (owner)

```
API surface
 ├── Authentication API (JWT · refresh · rate limit · API keys)
 ├── Domain APIs (Products · Customers · Sales · Purchases)
 └── API standards (REST · errors · pagination · /api/v1 · OpenAPI · webhooks)

Company & security settings
 ├── Authentication · 2FA · Sessions (BR-19 fidelity sync)
 └── Company · Formatting · Email · Numbering/Templates (BR-20)

Operator reliability
 ├── Redis cache soft-fail (dashboard/catalog)
 ├── Permissions cache invalidation
 ├── Celery beat schedule matrix
 ├── Admin jobs dry-run (GET/POST /jobs)
 └── Logical DR drill packaging (no WAL/PITR)
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 1/5/6/7 patterns (auth, API keys, webhooks, cache, jobs) and Stage 11–13 domain chain proofs — do not rewrite engines.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–18 feature scopes.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **K1** | Auth API fidelity (BR-18.1) | P0 | COMPLETE |
| **P1** | Products + Customers API fidelity (BR-18.2–18.3) | P0 | COMPLETE |
| **S1** | Sales + Purchases API fidelity (BR-18.4–18.5) | P0 | COMPLETE |
| **A1** | API standards fidelity (BR-18.6) | P0 | COMPLETE |
| **U1** | Auth & session BR-19 fidelity sync | P0 | COMPLETE |
| **C1** | Company/settings BR-20 fidelity sync | P1 | PENDING |
| **R1** | Reliability & cache (LAUNCH §5) | P0 | PENDING |
| **D1** | Spec / BR-18–20 / readiness / launch fidelity sync | P2 | PENDING |
| **H19x** | Stage 19 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack; centralized SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU capacity certificate; vendor penetration test / ZAP-in-CI Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); multi-bin; FIFO/LIFO/WA
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Prophet/LLM upgrades; PO Kanban polish; richer WYSIWYG template designer
- Reopening Stages 1–18 frozen feature scopes

## K1 acceptance criteria

- [x] JWT login / refresh / rate-limit headers proven for API access; API-key path remains green; BR-18.1 checkboxes synced only with evidence.
- [x] Automated proof: `backend/tests/test_auth_api_fidelity_k1.py`.

## P1 acceptance criteria

- [x] Products/categories/brands/units CRUD + import + stock/barcode lookup and customers/groups CRUD + balance/history proven via JWT (and `X-API-Key` where permitted); BR-18.2–18.3 synced with evidence.
- [x] Automated proof: `backend/tests/test_products_customers_api_p1.py`.

## S1 acceptance criteria

- [x] Sales + Purchases API surfaces proven (extend Stage 12/11 chain evidence); remaining BR-18.4–18.5 boxes synced with evidence.
- [x] Automated proof: `backend/tests/test_sales_purchases_api_s1.py`.

## A1 acceptance criteria

- [x] REST/JSON/error envelope/pagination/`/api/v1`/OpenAPI + webhook standards proven and documented; BR-18.6 synced with evidence.
- [x] Automated proof: `backend/tests/test_api_standards_a1.py`.

## U1 acceptance criteria

- [x] Login / password policy / lockout / email verify / reset / TOTP+WebAuthn / sessions / idle-logout mapped to checked BR-19 ACs with live proof (engines already Complete in readiness).
- [x] Automated proof: `backend/tests/test_auth_session_br19_u1.py`.

## C1 acceptance criteria

- [ ] Legal/logo/formats/SMTP/numbering/print templates proven; BR-20 synced; richer WYSIWYG designer stays deferred.
- [ ] Automated proof: `backend/tests/test_company_settings_br20_c1.py`.

## R1 acceptance criteria

- [ ] Dashboard/catalog cache soft-fails on Redis blip; permissions cache invalidates on role/`record_scope` change; Celery beat schedule matrix + admin `GET/POST /jobs` dry-run automated; logical DR drill packaging documented (no WAL/PITR).
- [ ] Automated proof: `backend/tests/test_reliability_cache_r1.py`.

## D1 acceptance criteria

- [ ] BR-18–20, SECURITY_GUIDE / API docs, readiness, launch checklist §§1–5 aligned — `docs/STAGE_19_FIDELITY.md`.
- [ ] Guard test: `backend/tests/test_stage19_fidelity_d1.py`.

## H19x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

K1–P1–S1–A1–U1 complete. Pending C1 → H19x. Stages 1–18 remain frozen for their scopes.
