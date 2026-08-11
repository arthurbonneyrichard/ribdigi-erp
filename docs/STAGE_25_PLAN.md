# Stage 25 Plan — Actuals → AI Analysis → Business Insights

**Status:** Closed — exit met (H25x / ADR-056)  
**Base:** Commerce actuals → Basic RIBDIGI AI analysis → Business insights  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR (historical):** [ADR-055](ADR_055_STAGE25_OPEN.md)  
**Exit:** [STAGE_25_EXIT_CRITERIA.md](STAGE_25_EXIT_CRITERIA.md) · [ADR-056](ADR_056_STAGE25_FREEZE.md) · [STAGE_25_FIDELITY.md](STAGE_25_FIDELITY.md)

Stage 25 closes the owner product outline after Stage 24 freeze: **actual Inventory + Sales + Purchases + Expenses → basic RIBDIGI AI analysis → business insights**. Inventory, sales, and expense AI engines already exist and are Complete under Stage 20 (BR-21); commerce actuals are Complete under Stages 11–18 / 24 G1. This track extends proven `ai_*.py` / `/ai/*` surfaces for the missing purchases analysis path, cross-domain synthesis, and insights/UI fidelity — **not** external LLM/Prophet/IsolationForest, PO OCR auto-apply, paid billing, schema-per-tenant, i18n packs, ADR-003/005, Open Banking, tax e-file, K8s/WAL/PITR, Grafana, certified 1000-VU, or reopening Stages 1–24.

## Product outline (owner)

```
Actual Inventory
        +
Actual Sales
        +
Actual Purchases
        +
Actual Expenses
        ↓
Basic RIBDIGI AI Analysis
        ↓
Business Insights
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven `ai_inventory` / `ai_sales` / `ai_expenses` / `ai_insights` engines — do not rewrite stacks or invent fake AI success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–24 feature scopes. Inv/Sales/Expense AI already Complete — regression under D1 only. Deferred ADRs (001–006) and ops platforms stay deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | Purchases actuals → AI analysis | P0 | COMPLETE |
| **X1** | Cross-domain analysis (Inv + Sales + Purch + Exp) | P0 | COMPLETE |
| **B1** | Business Insights surface (all four actuals) | P1 | COMPLETE |
| **U1** | AI UI fidelity (purchases + analysis panels) | P1 | COMPLETE |
| **D1** | Spec / BR / readiness / USER_MANUAL / API fidelity sync | P2 | COMPLETE |
| **H25x** | Stage 25 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- External LLM provider; Prophet/ML upgrades; IsolationForest / SIEM anomaly volume
- PO OCR auto-apply (human-confirmed apply remains Stage 10)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Kubernetes / Helm; Grafana / PagerDuty / SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- Reopening Stages 1–24 frozen feature scopes (incl. Stage 20 AI engines as greenfield)

## P1 acceptance criteria

- [x] Dedicated purchases AI analysis over live PO / GRN / purchase-invoice actuals (extend `ai_sales` / `ai_expenses` pattern — not a parallel stack).
- [x] Tenant-scoped + `require_permission("ai", …)`; cashier without `ai` → 403; no cross-tenant leakage.
- [x] Automated proof: `backend/tests/test_ai_purchases_analysis_p1.py`.
- [x] API / BR-21.11 / plan / launch / roadmap cite Stage 25 P1.
- [x] No fake LLM/Prophet claims; Remaining external ML stays deferred.

## X1 acceptance criteria

- [x] Single orchestration endpoint over live Inv + Sales + Purch + Exp analyzers (extend proven `ai_*` — not a parallel stack).
- [x] Response includes per-domain summaries + `cross_signals` synthesis (multi-domain kinds).
- [x] Tenant-scoped + `require_permission("ai", …)`; cashier without `ai` → 403; no cross-tenant leakage.
- [x] Automated proof: `backend/tests/test_ai_cross_domain_x1.py`.
- [x] API / BR-21.12 / plan / launch / roadmap cite Stage 25 X1.
- [x] No fake LLM/Prophet claims; Remaining external ML stays deferred.

## B1 acceptance criteria

- [x] `GET /ai/insights` cards cite domains across Inventory, Sales, Purchases, Expenses (`domains` + `actuals_covered`).
- [x] Purchase actual signals on the insights surface (spend WoW, overdue bills, draft PO backlog) + light Inv/Sales↔Purch cross cards.
- [x] Dashboard + `/ai` Business Insights copy/UI show four-actual cites.
- [x] Tenant-scoped; no cross-tenant leakage.
- [x] Automated proof: `backend/tests/test_ai_business_insights_b1.py`.
- [x] BR-21.2 / API / plan / launch / roadmap cite Stage 25 B1.
- [x] No fake LLM claims; Remaining external ML stays deferred.

## U1 acceptance criteria

- [x] `/ai` UI loads purchases analysis (`GET /ai/purchases/analysis`).
- [x] `/ai` UI loads cross-domain analysis (`GET /ai/cross-domain/analysis`).
- [x] `/ai` UI wires document analyze (`POST /ai/documents/analyze` multipart) — suggest-only.
- [x] Sales/expense/insights panels remain (extend, do not rewrite).
- [x] Automated proof: `backend/tests/test_ai_ui_fidelity_u1.py`.
- [x] USER_MANUAL / API / plan / launch / roadmap cite Stage 25 U1.

## D1 acceptance criteria

- [x] `docs/STAGE_25_FIDELITY.md` maps P1–U1 evidence → BR-21.2 / 21.11 / 21.12 and deferred items.
- [x] BR-21 fidelity cites include Stage 25 D1 / `STAGE_25_FIDELITY.md`.
- [x] USER_MANUAL §14 purchases / cross-domain / document analyze + Stage 25 fidelity cite synced.
- [x] API docs purchases / cross-domain / insights / documents + Stage 25 D1 cite.
- [x] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP cite Stage 25 D1.
- [x] Automated proof: `backend/tests/test_stage25_fidelity_d1.py`.

## H25x acceptance criteria

- [x] Exit criteria document with no CRITICAL/MISSING rows for P1–D1 / H25x — `docs/STAGE_25_EXIT_CRITERIA.md`.
- [x] Scope freeze ADR accepted — `docs/ADR_056_STAGE25_FREEZE.md`.
- [x] Fidelity note closed with H25x evidence — `docs/STAGE_25_FIDELITY.md`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS / API cite exit + freeze.
- [x] Automated proof: `backend/tests/test_stage25_exit_h25x.py`.
- [x] Stages 1–24 freezes remain; Stage 26+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 25 exit met (P1–D1 / H25x). Scope frozen under ADR-056. Stages 1–24 remain frozen for their scopes. Next delivery track requires an explicit open ADR after CONTINUE/NEXT.
