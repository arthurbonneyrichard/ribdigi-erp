# Stage 25 Plan — Actuals → AI Analysis → Business Insights

**Status:** Open — P1 COMPLETE; X1 next (ADR-055)  
**Base:** Commerce actuals → Basic RIBDIGI AI analysis → Business insights  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-055](ADR_055_STAGE25_OPEN.md)

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
| **X1** | Cross-domain analysis (Inv + Sales + Purch + Exp) | P0 | PENDING |
| **B1** | Business Insights surface (all four actuals) | P1 | PENDING |
| **U1** | AI UI fidelity (purchases + analysis panels) | P1 | PENDING |
| **D1** | Spec / BR / readiness / USER_MANUAL / API fidelity sync | P2 | PENDING |
| **H25x** | Stage 25 exit criteria + freeze ADR | Exit | PENDING |

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

Filled when workstream starts.

## B1 acceptance criteria

Filled when workstream starts.

## U1 acceptance criteria

Filled when workstream starts.

## D1 acceptance criteria

Filled when workstream starts.

## H25x acceptance criteria

Filled when exit workstream starts.

## Sign-off

Plan authored; ADR-055 open. P1 complete; X1 next. Stages 1–24 remain frozen for their scopes.
