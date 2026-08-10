# Stage 20 Plan — AI Business Assistant Fidelity

**Status:** Open  
**Base:** AI assistant surface → Inventory & sales intelligence → Customer & security AI → Fidelity closeout  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-045](ADR_045_STAGE20_OPEN.md)

Stage 20 closes commercial-MVP AI assistant fidelity after Stage 19 freeze. Chat, insights, inventory/sales/customer/security AI, NL reports, expense OCR, and document analyze engines already exist (`/ai/*`, Celery AI jobs). This track proves BR-21 with live evidence and docs sync — **not** external LLM/Prophet stacks, K8s/WAL/PITR, Grafana, or certified 1000-VU.

## Product outline (owner)

```
AI assistant surface
 ├── ERP chat (NL Q&A · role context · history · safe commands)
 ├── Dashboard insights (+ weekly digest)
 └── NL report generator (+ templates · export)

Inventory & sales intelligence
 ├── Demand / dead stock / seasonality
 ├── Low-stock prediction (+ purchase suggestions)
 └── Sales analysis (trend · RFM · affinity · peaks)

Customer & security AI
 ├── Customer assistant (churn · best · promos)
 └── Security monitor (login/txn anomalies)

Fidelity closeout
 ├── Docs / BR-21 / readiness sync
 └── Exit + freeze
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven `ai_*.py` engines and `/ai/*` routes — do not rewrite stacks or invent fake AI success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–19 feature scopes. BR-21.6 / 21.8 already Complete — regression under D1 only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | AI ERP chat fidelity (BR-21.1) | P0 | COMPLETE |
| **I1** | Dashboard insights + weekly digest (BR-21.2) | P0 | COMPLETE |
| **V1** | Smart inventory intelligence (BR-21.3) | P0 | COMPLETE |
| **L1** | Low-stock prediction (BR-21.4) | P0 | COMPLETE |
| **S1** | Sales analysis (BR-21.5) | P1 | COMPLETE |
| **R1** | NL report generator (BR-21.7) | P1 | COMPLETE |
| **U1** | Customer + security AI (BR-21.9–21.10) | P1 | COMPLETE |
| **D1** | Spec / BR-21 / readiness / Phase 4 fidelity sync | P2 | COMPLETE |
| **H20x** | Stage 20 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- External LLM / Prophet / IsolationForest vendor model upgrades
- PO OCR auto-apply (expense/PI OCR remains Stage 10)
- Kubernetes / Helm production chart; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack; centralized SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU capacity certificate; vendor penetration test / ZAP-in-CI Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); multi-bin; FIFO/LIFO/WA
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Richer WYSIWYG template designer
- Reopening Stages 1–19 frozen feature scopes

## C1 acceptance criteria

- [x] Natural-language Q&A, role-scoped context, chat history proven; command path only when already safe (no fake writes).
- [x] Automated proof: `backend/tests/test_ai_chat_fidelity_c1.py`.
- [x] BR-21.1 synced with evidence.

## I1 acceptance criteria

- [x] Insights anomalies / restock suggestions + weekly digest path proven (Celery/email prefs where configured).
- [x] Automated proof: `backend/tests/test_ai_insights_fidelity_i1.py`.
- [x] BR-21.2 synced with evidence.

## V1 acceptance criteria

- [x] Demand forecast (7/30/90), reorder qty, seasonality, dead stock proven on live stock/sales data.
- [x] Automated proof: `backend/tests/test_ai_inventory_intel_v1.py`.
- [x] BR-21.3 synced with evidence.

## L1 acceptance criteria

- [x] 7–14 day stockout prediction with confidence + purchase suggestions proven.
- [x] Automated proof: `backend/tests/test_ai_low_stock_prediction_l1.py`.
- [x] BR-21.4 synced with evidence.

## S1 acceptance criteria

- [x] Sales trend / RFM / affinity / peak hours proven via `/ai/sales/analysis`.
- [x] Automated proof: `backend/tests/test_ai_sales_analysis_s1.py`.
- [x] BR-21.5 synced with evidence.

## R1 acceptance criteria

- [x] NL report generate + export + saved templates proven.
- [x] Automated proof: `backend/tests/test_ai_report_generator_r1.py`.
- [x] BR-21.7 synced with evidence.

## U1 acceptance criteria

- [x] Customer churn/best/promos + security login/txn alerts proven.
- [x] Automated proof: `backend/tests/test_ai_customer_security_u1.py`.
- [x] BR-21.9–21.10 synced with evidence.

## D1 acceptance criteria

- [x] BR-21, AI readiness, Phase 4 / USER_MANUAL / API docs aligned — `docs/STAGE_20_FIDELITY.md`.
- [x] Guard test: `backend/tests/test_stage20_fidelity_d1.py`.

## H20x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

C1–I1–V1–L1–S1–R1–U1–D1 complete. Pending H20x. Stages 1–19 remain frozen for their scopes. Fidelity: `docs/STAGE_20_FIDELITY.md`.
