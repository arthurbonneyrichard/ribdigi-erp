# RIBDIGI BUSINESS ERP — Commercial Launch Checklist

**Status:** Documented (Stage 7 L7x)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md), [STAGE_7_EXIT_CRITERIA.md](STAGE_7_EXIT_CRITERIA.md), [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

This is the **operator go-live checklist** for a commercial MVP launch. It is **not** a claim that deferred infra (Kubernetes chart review, WAL/PITR, vendor pen test, PgBouncer, certified 1000-VU run) is Complete.

Use this list before promoting a staging build to production. Check items only when verified in the target environment — never on demo data or fake success.

## 1. Configuration & secrets

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
- [x] Expense create → approve → journal (Stage 18 T1 launch smoke + Stage 14 E1)
- [x] Trial balance / P&L readable for the fiscal period (Stage 18 T1 launch smoke + Stage 14 A2/E1)
- [x] Logical backup create → verify → dry-run restore (`confirm_text=RESTORE` only on intentional restore) — Stage 18 T1 / B1 / Stage 5 B1

## 5. Reliability & cache

- [ ] Dashboard / catalog cache soft-fails if Redis blips (`CACHE_ENABLED` as intended)
- [ ] Permissions cache invalidates after role / record_scope change
- [ ] Celery beat schedules include: low-stock, payment-due, quotation-expiry, recurring expenses, backups, report emails, FX refresh, bank feed sync, webhook retries, AI jobs (if enabled)
- [ ] Admin `GET /jobs` + manual `POST /jobs/{name}/run` works for an operator dry-run

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
