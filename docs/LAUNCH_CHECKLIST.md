# RIBDIGI BUSINESS ERP — Commercial Launch Checklist

**Status:** Documented (Stage 7 L7x)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md), [STAGE_7_EXIT_CRITERIA.md](STAGE_7_EXIT_CRITERIA.md), [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

This is the **operator go-live checklist** for a commercial MVP launch. It is **not** a claim that deferred infra (Kubernetes chart review, WAL/PITR, vendor pen test, PgBouncer, certified 1000-VU run) is Complete.

Use this list before promoting a staging build to production. Check items only when verified in the target environment — never on demo data or fake success.

## 1. Configuration & secrets

Operator env verification (not auto-closed by Stage 21 D1). Product fidelity for BR-1–4 is documented in `docs/STAGE_21_FIDELITY.md`.

- [ ] `APP_ENV=production`, `DEBUG=false`
- [ ] Strong unique `JWT_SECRET_KEY` / app secrets (not repo defaults)
- [ ] Production `CORS_ORIGINS` whitelist (no `*`)
- [ ] `RATE_LIMIT_ENABLED=true`; prefer `RATE_LIMIT_REQUIRE_REDIS=true` for multi-instance
- [ ] `DATABASE_URL` points at managed PostgreSQL; Alembic heads applied (`alembic upgrade head`)
- [ ] `REDIS_URL` reachable (rate limit + app cache + Celery results)
- [ ] Celery broker (`CELERY_BROKER_URL` / RabbitMQ) + worker + beat running
- [ ] `SMTP_HOST` + `SMTP_FROM_EMAIL` when `EMAIL_ENABLED=true` (no silent “email sent” without delivery)
- [ ] Object storage configured if using S3/MinIO (`STORAGE_BACKEND`)
- [ ] No demo tenants, seed passwords, or hard-coded production credentials in the deploy

## 2. Identity & security

Operator env verification. Automated BR-1/3/4 proofs: Stage 21 T1/I1/U1/V1/N1 (`docs/STAGE_21_FIDELITY.md`).

- [ ] First real company admin registered; email verification works end-to-end
- [ ] Company admin / super_admin 2FA (TOTP and/or WebAuthn) enrolled
- [ ] Session list + revoke verified; idle logout behaves as expected
- [ ] RBAC smoke: cashier cannot write users; tenant header mismatch returns 403
- [ ] Rate-limit headers and `429` visible under burst traffic
- [ ] `/api/v1/health?deep=true` and `/health/ready` green (DB / Redis / broker)
- [ ] OpenAPI disabled in production; security headers present (CSP, HSTS where TLS terminates)

## 3. Integrations (Stage 6–7)

- [ ] Tenant API key created; `X-API-Key` read path works; secret stored out-of-band
- [ ] API key usage visible (`GET /api-keys/{id}/usage` / Security UI chart)
- [ ] Webhook endpoint registered (HTTPS); test delivery HMAC verifies
- [ ] Failed webhook enters `pending_retry`; beat/job `retry_due_webhooks` redelivers
- [ ] Onboarding checklist appears for new tenants; dismiss only at ≥80%

## 4. Core ERP smoke (real tenant data)

- [ ] Product create + stock-in + movement visible
- [x] Supplier → PO → GRN → purchase invoice → supplier payment (Stage 11 C1 automated: `test_purchasing_chain_c1.py`)
- [x] Customer → quotation/order/invoice → payment (Stage 12 C1: `test_sales_chain_c1.py`)
- [x] POS sale with stock deduction + receipt (Stage 12 C2: `test_pos_chain_c2.py`)
- [x] POS insufficient-stock sale leaves no orphans (Stage 13 H1: `test_pos_sale_atomicity_h1.py`)
- [x] POS multi-tender + receipt send + cash-portion drawer + close (Stage 13 H2: `test_pos_execution_chain_h2.py`)
- [x] Expense category → COA → approve → TB/P&L/cash-flow (Stage 14 E1: `test_expense_coa_chain_e1.py`)
- [x] Expense store/department dims (Stage 14 E2: `test_expense_org_dimensions_e2.py`)
- [x] Journal store dimension + store-filtered P&L/cash-flow (Stage 14 A1: `test_journal_store_dimension_a1.py`)
- [x] Trial balance / balance sheet `as_of_date` (Stage 14 A2: `test_trial_balance_as_of_a2.py`)
- [x] Tax rate PATCH/deactivate + period helpers (Stage 14 T1: `test_tax_rate_lifecycle_t1.py`)
- [x] Credit UI allocate to invoice/bill (Stage 14 R1: `test_credit_payment_allocate_r1.py`)
- [x] Expense approve/reject domain audit (Stage 14 A3: `test_expense_audit_a3.py`)
- [x] Stage 14 exit + freeze (H14x: `test_stage14_exit_h14x.py`, ADR-034)
- [x] Invoice stock → AR → tax → JE (Stage 15 C1: `test_sales_inventory_ledger_chain_c1.py`)
- [x] Standard-cost COGS / Inventory GL (Stage 15 I1: `test_sales_cogs_inventory_i1.py`)
- [x] Invoice post stock preflight atomicity (Stage 15 H1: `test_sales_invoice_atomicity_h1.py`)
- [x] Sales return warehouse restock + FX-safe AR (Stage 15 R1: `test_sales_return_chain_r1.py`)
- [x] Live sales tax → report → filing (Stage 15 T1: `test_sales_tax_filing_t1.py`)
- [x] Sales invoice/return domain audit (Stage 15 A1: `test_sales_audit_a1.py`)
- [x] Stage 15 fidelity sync (D1: `test_stage15_fidelity_d1.py`, `docs/STAGE_15_FIDELITY.md`)
- [x] Stage 15 exit + freeze (H15x: `test_stage15_exit_h15x.py`, ADR-036)
- [x] Inter-store transfer → warehouse stock → movements (Stage 16 M1: `test_multistore_transfer_chain_m1.py`)
- [x] Notification emission matrix (Stage 16 N1: `test_notification_emission_n1.py`)
- [x] Reports suite fidelity (Stage 16 R1: `test_reports_suite_r1.py`)
- [x] Credit + Tax Reports packaging (Stage 16 R2: `test_credit_tax_reports_r2.py`)
- [x] Transfer history / consolidated ops reporting (Stage 16 M2: `test_transfer_history_m2.py`)
- [x] Notification channel delivery (Stage 16 N2: `test_notification_channel_delivery_n2.py`)
- [x] Stage 16 fidelity sync (D1: `test_stage16_fidelity_d1.py`, `docs/STAGE_16_FIDELITY.md`)
- [x] Stage 16 exit + freeze (H16x: `test_stage16_exit_h16x.py`, ADR-038)
- [x] Catalog fidelity proof (Stage 17 C1: `test_catalog_fidelity_c1.py`)
- [x] Stock ops chain (Stage 17 S1: `test_stock_ops_chain_s1.py`)
- [x] Stock count variance chain (Stage 17 S2: `test_stock_count_chain_s2.py`)
- [x] Warehouse transfer chain (Stage 17 W1: `test_warehouse_transfer_chain_w1.py`)
- [x] Low-stock + reorder-PO (Stage 17 L1: `test_low_stock_reorder_l1.py`)
- [x] Inventory domain audit (Stage 17 A1: `test_inventory_audit_a1.py`)
- [x] Stage 17 fidelity sync (D1: `test_stage17_fidelity_d1.py`, `docs/STAGE_17_FIDELITY.md`)
- [x] Stage 17 exit + freeze (H17x: `test_stage17_exit_h17x.py`, ADR-040)
- [x] Stage 18 Launch Integrity & Ops (closed: `docs/STAGE_18_PLAN.md`, exit `docs/STAGE_18_EXIT_CRITERIA.md`, ADR-042)
- [x] Tenant isolation matrix launch-smoke (Stage 18 S1: `test_isolation_matrix_s1.py`)
- [x] RBAC / session / BR-17 audit hardening (Stage 18 A1: `test_security_hardening_a1.py`)
- [x] Backup schedule / retention / failure notify (Stage 18 B1: `test_backup_schedule_b1.py`; runbook `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`)
- [x] Cross-module integrity: inventory Σ movements · TB/GL · POS money-path (Stage 18 I1: `test_cross_module_integrity_i1.py`)
- [x] Structured request logs + health/metrics hooks (Stage 18 L1: `test_request_logging_l1.py`, `docs/OPS_MONITORING_MVP.md`)
- [x] OWASP expand · load evidence · launch E2E smoke (Stage 18 T1: `test_owasp_suite_t1.py`, `test_loadtest_evidence_t1.py`, `test_launch_smoke_t1.py`)
- [x] CI + production Compose/env fidelity (Stage 18 C1: `test_ci_prod_config_c1.py`, `.env.production.example`, `docker-compose.prod.yml`; no K8s deploy)
- [x] Stage 18 fidelity sync (D1: `test_stage18_fidelity_d1.py`, `docs/STAGE_18_FIDELITY.md`)
- [x] Stage 18 exit + freeze (H18x: `test_stage18_exit_h18x.py`, ADR-042)
- [x] Stage 19 API / Settings / Operator Reliability (closed: `docs/STAGE_19_PLAN.md`, ADR-044) — K1–D1 / H19x complete
- [x] Auth API fidelity (Stage 19 K1: `test_auth_api_fidelity_k1.py` — JWT login/refresh, API keys, tenant-scoped rate-limit headers)
- [x] Products + Customers API fidelity (Stage 19 P1: `test_products_customers_api_p1.py` — catalog CRUD/import/stock/barcode + customers/groups/balance/history; X-API-Key reads)
- [x] Sales + Purchases API fidelity (Stage 19 S1: `test_sales_purchases_api_s1.py` — quote/order/invoice/payment/return/POS + PR/PO/GRN/PI/supplier payment; X-API-Key reads)
- [x] API standards fidelity (Stage 19 A1: `test_api_standards_a1.py` — env envelope, `/api/v1`, limit lists, OpenAPI, webhooks; BR-18.6)
- [x] Auth & session BR-19 fidelity (Stage 19 U1: `test_auth_session_br19_u1.py` — bcrypt/policy/lockout/verify/reset/TOTP/sessions/idle)
- [x] Company/settings BR-20 fidelity (Stage 19 C1: `test_company_settings_br20_c1.py` — legal/logo/formats/SMTP/numbering/templates)
- [x] Reliability & cache LAUNCH §5 (Stage 19 R1: `test_reliability_cache_r1.py` — Redis soft-fail, perms invalidation, beat matrix, jobs dry-run, logical DR runbook)
- [x] Stage 19 fidelity sync (D1: `test_stage19_fidelity_d1.py`, `docs/STAGE_19_FIDELITY.md`)
- [x] Stage 19 exit + freeze (H19x: `test_stage19_exit_h19x.py`, ADR-044)
- [x] Stage 20 AI Business Assistant Fidelity (closed: `docs/STAGE_20_PLAN.md`, ADR-046) — C1–D1 / H20x complete
- [x] AI ERP chat fidelity (Stage 20 C1: `test_ai_chat_fidelity_c1.py` — NL Q&A, draft-PO command, role gates, history)
- [x] AI dashboard insights fidelity (Stage 20 I1: `test_ai_insights_fidelity_i1.py` — sales/expense anomalies, restock actions, weekly digest)
- [x] AI inventory intelligence fidelity (Stage 20 V1: `test_ai_inventory_intel_v1.py` — demand 7/30/90, reorder, seasonality, dead stock)
- [x] AI low-stock prediction fidelity (Stage 20 L1: `test_ai_low_stock_prediction_l1.py` — 7–14d horizon, velocity/seasonality/lead time, confidence, suggestions)
- [x] AI sales analysis fidelity (Stage 20 S1: `test_ai_sales_analysis_s1.py` — trend forecast, RFM, affinity, peak hour/day)
- [x] AI NL report generator fidelity (Stage 20 R1: `test_ai_report_generator_r1.py` — NL generate, export csv/pdf, saved templates)
- [x] AI customer + security fidelity (Stage 20 U1: `test_ai_customer_security_u1.py` — churn/best/promos + login/txn alerts + notify)
- [x] Stage 20 fidelity sync (D1: `test_stage20_fidelity_d1.py`, `docs/STAGE_20_FIDELITY.md`)
- [x] Stage 20 exit + freeze (H20x: `test_stage20_exit_h20x.py`, ADR-046)
- [x] Stage 21 Tenant Lifecycle, Org & Dashboard Fidelity (closed: `docs/STAGE_21_PLAN.md`, ADR-048) — T1–D1 / H21x complete
- [x] Tenant registration & lifecycle fidelity (Stage 21 T1: `test_tenant_lifecycle_t1.py` — register/verify/trial, profile/logo, statuses/reminders/grace/plan)
- [x] Tenant isolation & init seeds fidelity (Stage 21 I1: `test_tenant_isolation_seeds_i1.py` — cross-tenant isolation, seed_tenant_defaults, tenant-scoped backup)
- [x] Org units fidelity (Stage 21 O1: `test_org_units_o1.py` — branches/stores/warehouses/departments CRUD, soft-deactivate, manager/hours/type, dept expense filter)
- [x] Company / currency / tax fidelity (Stage 21 C1: `test_company_currency_tax_c1.py` — legal/addresses/contact, FX rates/refresh, invoice currency, tax default/category/compound)
- [x] Users & roles fidelity (Stage 21 U1: `test_users_roles_u1.py` — CRUD/import/activate, system+custom roles, record_scope override; ADR-003/005 deferred)
- [x] Dashboard KPIs fidelity (Stage 21 V1: `test_dashboard_kpis_v1.py` — KPI cards, DoD/MoM, low/OOS/expiring, recent sales/top products/chart series)
- [x] Dashboard notifications fidelity (Stage 21 N1: `test_dashboard_notifications_n1.py` — unread count, stock/orders/payments/system groups, mark read/unread, 90-day history)
- [x] Stage 21 fidelity sync (D1: `test_stage21_fidelity_d1.py`, `docs/STAGE_21_FIDELITY.md` — BR-1–4 + tenancy readiness + USER_MANUAL / API / launch §§1–2)
- [x] Stage 21 exit + freeze (H21x: `test_stage21_exit_h21x.py`, ADR-048)
- [x] Stage 22 Expenses, Ledger, Credit & Tax Surface Fidelity (closed: `docs/STAGE_22_PLAN.md`, ADR-050) — E1–D1 / H22x complete
- [x] Expense categories & entry fidelity (Stage 22 E1: `test_expense_categories_entry_e1.py` — predefined/custom categories, budgets, full expense entry fields)
- [x] Expense approval & recurring fidelity (Stage 22 A1: `test_expense_approval_recurring_a1.py` — thresholds/multi-level/comments/notify + recurring frequency/generate/notify/skip/modify)
- [x] COA fidelity (Stage 22 C1: `test_coa_fidelity_c1.py` — seeded types/hierarchy, non-system CRUD, opening balance; industry-agnostic system COA)
- [x] Cash/bank, recon, cheques fidelity (Stage 22 B1: `test_cash_bank_recon_b1.py` — liquid accounts, deposits/withdrawals/transfers, statement recon, cheque issue/deposit/bounce/clear)
- [x] AR/AP aging, payments, overdue + financial export (Stage 22 P1: `test_ar_ap_export_p1.py` — AR/AP auto, aging buckets, partial pay, due notify, P&L/TB PDF+Excel)
- [x] Customer credit surface fidelity (Stage 22 R1: `test_customer_credit_r1.py` — credit limit, block+override, balance, collections, statement)
- [x] Tax configuration fidelity (Stage 22 T1: `test_tax_config_fidelity_t1.py` — tax types, inclusive/exclusive, compound tax)
- [x] Stage 22 fidelity sync (D1: `test_stage22_fidelity_d1.py`, `docs/STAGE_22_FIDELITY.md` — BR-9–12 + finance readiness + USER_MANUAL / API / launch)
- [x] Stage 22 exit + freeze (H22x: `test_stage22_exit_h22x.py`, ADR-050)
- [ ] Stage 23 Reports Dimension & Commercial MVP Gate Fidelity (open: `docs/STAGE_23_PLAN.md`, ADR-051) — F1–C1–I1–G1 complete; B1 next
- [x] Financial report dimension filters (Stage 23 F1: `test_financial_report_filters_f1.py` — balance sheet / P&L / cash-flow `store_id` + `branch_id`)
- [x] Financial comparative fidelity (Stage 23 C1: `test_financial_comparative_c1.py` — P&L / cash-flow / BS `compare=true` prior period + change_pct)
- [x] Isolation matrix residual (Stage 23 I1: `test_isolation_matrix_i1.py` — liquid accounts/transfers, expense categories/recurring, report dimensions, mismatched header)
- [x] Commercial MVP gate closure (Stage 23 G1: `test_mvp_gate_closure_g1.py` — isolation/lifecycle/expenses/accounting/tax/reports Complete MVP; Remaining deferred-only)
- [x] Expense create → approve → journal (Stage 18 T1 launch smoke + Stage 14 E1)
- [x] Trial balance / P&L readable for the fiscal period (Stage 18 T1 launch smoke + Stage 14 A2/E1)
- [x] Logical backup create → verify → dry-run restore (`confirm_text=RESTORE` only on intentional restore) — Stage 18 T1 / B1 / Stage 5 B1

## 5. Reliability & cache

- [x] Dashboard / catalog cache soft-fails if Redis blips (`CACHE_ENABLED` as intended) — Stage 19 R1 (`test_reliability_cache_r1.py`)
- [x] Permissions cache invalidates after role / record_scope change — Stage 19 R1 (`test_reliability_cache_r1.py`)
- [x] Celery beat schedules include: low-stock, payment-due, quotation-expiry, recurring expenses, backups, report emails, FX refresh, bank feed sync, webhook retries, AI jobs (if enabled) — Stage 19 R1 (`test_reliability_cache_r1.py`)
- [x] Admin `GET /jobs` + manual `POST /jobs/{name}/run` works for an operator dry-run — Stage 19 R1 (`test_reliability_cache_r1.py`; logical DR packaging: `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`)

## 6. Explicitly deferred (do not block Stage 7 exit)

Record as **ops follow-ups**, not Stage 7 incompletes:

- Kubernetes / Helm production chart review
- Full Prometheus / Grafana / PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI Top 10
- PgBouncer
- Certified ~1000-VU staging capacity run (`docs/LOAD_TEST_BASELINE.md` scripts exist)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)

## 7. Sign-off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Engineering | | | Stage 7 workstreams W2/C2/K2/L7x closed |
| Operations | | | Env checklist §§1–5 verified |
| Product | | | Accept deferred §6 as post-launch |

**Stage 7 L7x** records that this checklist **exists and is authoritative for MVP go-live hygiene**. Operator rows above remain unchecked until a real environment is signed off.
