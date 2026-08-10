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
- [ ] Expense create → approve → journal
- [ ] Trial balance / P&L readable for the fiscal period
- [ ] Logical backup create → verify → dry-run restore (`confirm_text=RESTORE` only on intentional restore)

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
