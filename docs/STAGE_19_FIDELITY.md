# Stage 19 Fidelity Notes — API, Settings & Operator Reliability

**Status:** Closed with Stage 19 D1; exit met (H19x / ADR-044)  
**Surface:** API surface → Company & security settings → Operator reliability  
**Open ADR (historical):** [ADR-043](ADR_043_STAGE19_OPEN.md)  
**Exit:** [STAGE_19_EXIT_CRITERIA.md](STAGE_19_EXIT_CRITERIA.md) · [ADR-044](ADR_044_STAGE19_FREEZE.md)  
**Plan:** [STAGE_19_PLAN.md](STAGE_19_PLAN.md)

Stage 19 proves commercial-MVP API / settings / operator-reliability fidelity on existing Stage 1 / 5 / 6 / 7 / 11–13 engines — BR-18–20 checkbox sync with live evidence, LAUNCH §5 reliability proofs, and logical DR packaging — **not** Kubernetes/Helm, Grafana/PagerDuty, WAL/S3 PITR, PgBouncer, certified 1000-VU, vendor pen test, paid billing, schema-per-tenant, ADR-005, multi-bin, FIFO, WebSocket, Open Banking, tax e-file, Prophet/LLM, cursor pagination, or richer WYSIWYG template designer.

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| BR-18.1 Auth API | Checkbox drift vs JWT/refresh/API keys/rate limits | Stage 19 K1 evidence + sync |
| BR-18.2–18.3 Products/Customers API | Partial marks | Stage 19 P1 live CRUD/import/stock/barcode + groups/balance/history |
| BR-18.4–18.5 Sales/Purchases API | Chain engines without Stage 19 API fidelity | Stage 19 S1 sales + purchasing surfaces |
| BR-18.6 API standards | Envelope/version/OpenAPI/webhooks undermarked | Stage 19 A1 + API docs §1 |
| BR-19 auth/2FA/sessions | Engines Complete; BR unchecked | Stage 19 U1 + SECURITY_GUIDE password/lockout honesty |
| BR-20 company/settings | Profile/SMTP/numbering exist; BR unchecked | Stage 19 C1; WYSIWYG designer deferred |
| LAUNCH §5 reliability | Unchecked Redis/perms/beat/jobs rows | Stage 19 R1 + DR runbook packaging |
| Spec / readiness / launch | Workstream docs synced piecemeal | This note + `test_stage19_fidelity_d1.py` |

## Workstream → evidence → BR → remaining

| WS | Evidence | BR / launch mapping | Remaining |
|----|----------|---------------------|-----------|
| **K1** | `test_auth_api_fidelity_k1.py` — JWT login/refresh, API keys, tenant-scoped rate-limit headers | BR-18.1 | Plan-tier rate caps |
| **P1** | `test_products_customers_api_p1.py` — catalog CRUD/import/stock/barcode + customers/groups/balance/history; X-API-Key reads | BR-18.2–18.3 | Dedicated catalog CSV export |
| **S1** | `test_sales_purchases_api_s1.py` — quote/order/invoice/payment/return/POS + PR/PO/GRN/PI/supplier payment | BR-18.4–18.5 | — |
| **A1** | `test_api_standards_a1.py` — `env()` envelope, `/api/v1`, list `limit`, OpenAPI, webhooks | BR-18.6 | Cursor pagination |
| **U1** | `test_auth_session_br19_u1.py` — bcrypt/policy/lockout/verify/reset/TOTP/sessions/idle; SECURITY_GUIDE min-8 / 30m lockout | BR-19.1–19.3 | Password history/expiry (deferred) |
| **C1** | `test_company_settings_br20_c1.py` — legal/logo/formats/SMTP/numbering/templates/header-footer | BR-20.1–20.4 | Richer WYSIWYG designer |
| **R1** | `test_reliability_cache_r1.py` + `DR_LOGICAL_BACKUP_RUNBOOK.md` — Redis soft-fail, perms invalidation, beat matrix, jobs dry-run | LAUNCH §5 | WAL/PITR; Grafana/PagerDuty |
| **D1** | This note + `test_stage19_fidelity_d1.py` | BR-18–20 + SECURITY_GUIDE + API docs + readiness + launch §§1–5 | — |
| **H19x** | `STAGE_19_EXIT_CRITERIA.md`; ADR-044; `test_stage19_exit_h19x.py` | Stage 19 exit + freeze | Next track needs open ADR |

## Evidence tests

- `backend/tests/test_auth_api_fidelity_k1.py`
- `backend/tests/test_products_customers_api_p1.py`
- `backend/tests/test_sales_purchases_api_s1.py`
- `backend/tests/test_api_standards_a1.py`
- `backend/tests/test_auth_session_br19_u1.py`
- `backend/tests/test_company_settings_br20_c1.py`
- `backend/tests/test_reliability_cache_r1.py`
- `backend/tests/test_stage19_fidelity_d1.py`
- `backend/tests/test_stage19_exit_h19x.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-18.1–18.6, BR-19.1–19.3, BR-20.1–20.4
- `docs/SECURITY_GUIDE.md` — Stage 19 K1 / U1 password-lockout honesty / D1
- `docs/API_DOCUMENTATION.md` — Stage 19 K1 / P1 / S1 / A1 (+ D1 cite)
- `PRODUCTION_READINESS.md` — API / Identity / Reliability bullets + Stage 19 D1 / H19x
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 19 D1 / H19x notes
- `docs/LAUNCH_CHECKLIST.md` — K1–R1 / D1 / H19x evidence; §5 Reliability & cache
- `docs/DR_LOGICAL_BACKUP_RUNBOOK.md` — Stage 19 R1 packaging
- `docs/STAGE_19_PLAN.md` — Closed (H19x / ADR-044)
- `docs/STAGE_19_EXIT_CRITERIA.md` · `docs/ADR_044_STAGE19_FREEZE.md`
- `docs/ADR_043_STAGE19_OPEN.md`

## Deferred (not Stage 19)

- Kubernetes / Helm production chart; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack; centralized SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU capacity certificate; vendor penetration test / ZAP-in-CI Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); multi-bin; FIFO/LIFO/WA
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Prophet/LLM upgrades; PO Kanban polish; richer WYSIWYG template designer
- Cursor pagination; password history/expiry enforcement
- Reopening Stages 1–18 frozen feature scopes
