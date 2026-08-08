# RIBDIGI ERP — Production Readiness Gate

RIBDIGI is intended to be a commercial ERP, not a demo application. A feature is **production-ready only when implementation, automated tests, security controls, and operational requirements are verified**.

## Non-negotiable release rules

- No demo tenant, sample company, fake transaction, pre-filled login, or known default password in production.
- No endpoint may return success for work that was not actually completed.
- No hard-coded secrets or development credentials in production.
- No protected tenant data endpoint without authentication, tenant isolation and authorization.
- No database schema change outside versioned migrations.
- No financial workflow is complete until stock, ledger, tax, credit and audit side effects are transactionally correct where applicable.
- No production claim until the Phase 5 launch gates in `docs/DEVELOPMENT_ROADMAP.md` are passed.

## Required launch gates

### Platform & tenancy
- [x] Schema-per-tenant strategy implemented as specified, or architecture documents formally revised to an approved equivalent.
  - Approved equivalent: shared-schema + `tenant_id` (see `docs/ADR_001_TENANCY.md`). Schema-per-tenant remains post-MVP.
- [ ] Cross-tenant isolation integration tests pass for every tenant-owned resource.
  - Partial: SQLite suite covers product list scoping, foreign sales invoice 404, mismatched `X-Tenant-ID` (products + credit aging), suspend/activate login block, plus matrix coverage for customers/suppliers lists, credit statement/limit, product image, expenses get/list, purchase invoices, tax rates, store inventory, POS sessions/drawer, notifications, backups, and accounting accounts/journals. Remaining: exhaustive enumeration of every tenant-owned route (audit cold paths, bank connections, report schedules, media keys, AI) and record-level RBAC.
- [ ] Tenant provisioning, suspension, activation and lifecycle management complete.
  - Partial: register + defaults, company profile GET/PATCH, suspend (revokes sessions) / activate, super_admin cross-tenant lifecycle, trial `trial_ends_at` (default 14d) + 7/3/1 reminders + grace read-only (`status=grace`) then auto-suspend, company logo upload/serve/delete via `STORAGE_BACKEND=local|s3` (MinIO/S3-compatible object store; keys remain tenant-scoped). Remaining: none for media offload on this gate.

### Identity & security
- [x] Login/logout/refresh token flow complete.
- [x] Email verification and password reset complete.
  - Tokens issued; SMTP delivery with console fallback in dev; production requires `SMTP_HOST` + `SMTP_FROM_EMAIL` when `EMAIL_ENABLED=true`.
- [x] 2FA/TOTP complete for required roles.
  - Complete: TOTP setup/QR/confirm, backup codes, encrypted secrets, company_admin/super_admin enrollment gate; WebAuthn/passkeys (register/list/delete + login challenge with `methods`); MFA satisfied by TOTP and/or passkeys.
- [x] Session listing and revocation complete.
- [x] Granular module/menu/record RBAC complete.
  - Module+action RBAC enforced on routes; record-level scope still pending.
- [ ] Rate limiting, security headers and production CORS complete.
  - Partial: Redis sliding-window rate limits (`RATE_LIMIT_BACKEND=auto|redis|memory`) with memory fallback, auth vs API caps, remaining/backend headers, security headers + CORS; production can set `RATE_LIMIT_REQUIRE_REDIS=true`. Celery/RabbitMQ scheduled workloads wired separately under Reliability.
- [ ] OWASP/security tests completed.

### ERP operations
- [ ] Inventory catalog, variants, batches/expiry, stock movements and adjustments complete.
  - Partial: product CRUD with category/brand/unit FKs + image upload, hierarchical categories (`parent_id`), brands, units of measure (+ tenant seed defaults), variants (SKU/size/color/flavor), batches with expiry + FEFO stock-out, stock in/out/adjust + immutable `stock_movements` (variant/batch refs), expiring-batches report/UI, sales/POS lines accept `variant_id`; deep category trees/UI polish and multi-image galleries still pending.
- [ ] Purchasing/PO/GRN/supplier workflow complete.
  - Partial: supplier CRUD, PO draft→sent→partial/full received, GRN posts stock + supplier balance, purchase invoices (from GRN or manual) draft→approve with unpaid/partial/paid/overdue + payment allocation, purchase returns draft→post with stock out + AP/debit note journal, supplier invoice file upload/download/delete on invoices, suggest-only supplier-invoice OCR (`POST .../ocr-suggest` + draft `PATCH` for supplier # / date / notes). Remaining: none for purchasing OCR.
- [ ] Sales/invoice/payment/customer workflow complete.
  - Partial: customer CRUD, quotations (send emails customer via SMTP/console then status=sent + resend, accept/reject/convert), sales orders (confirm/invoice), invoices draft→post with optional `store_id` (posts deduct that store’s warehouse stock), payments, sales returns with restock/discard + AR/journal, line `variant_id` on quote/order/invoice/return, salesperson + store performance reports with CSV/PDF/Excel export.
- [ ] POS cart, barcode, payment, receipt, shift and stock deduction complete.
  - Partial: cart checkout with stock out (incl. variant lines; store session deducts linked warehouse), shift open/close + cash reconciliation/variance notification, payment methods, thermal receipt (JSON/text/PDF 58/80mm) + email/SMS send; hardware cash drawer (`stores.drawer_mode` none|mock|network|browser_bridge, `PATCH /stores/{id}/drawer`, `POST /pos/sessions/{id}/drawer/open`, auto-pulse on cash sales, ESC/POS kick bytes on receipt JSON). Remaining: vendor-specific USB/serial drivers beyond TCP ESC/POS / browser bridge.
- [ ] Expenses and approval workflow complete.
  - Partial: categories + default seed, threshold auto-approve, configurable N-level approval matrix (`tenants.expense_approval_matrix` / `PATCH /expenses/settings` levels + role gates per step; legacy `expense_approval_threshold` / `expense_l2_threshold` kept in sync), action log + no self-approve / no duplicate-step actor, approve/reject + journal, recurring create/generate + Celery beat automation, receipt file upload/download/delete via local or S3/MinIO media store, suggest-only receipt OCR (`POST .../ocr-suggest` PDF text + Tesseract images; human `PATCH /expenses/{id}` apply). Remaining: none for expense OCR.
- [ ] Double-entry accounting, journals, COA and financial statements complete.
  - Partial: COA defaults (Cash 1000 + Bank 1010 + Cheques Receivable 1020 + Cheques Payable 2015), balanced journals, auto-post from invoice/GRN/purchase invoice (manual)/purchase return/payment/expense approval, trial balance + P&L, cash-flow across liquid accounts, bank statement import + match/ignore/complete against journal lines (`/accounting/bank-statements`); CSV/OFX-QFX feed upload (`POST .../import`); confidence-scored auto-match + `auto-clear`; multi-line clearing groups (`clear-group`); customer/supplier payments, expenses, and POS settle to Cash vs Bank by `payment_method` (card/transfer→1010, cash→1000, cheque→1020/2015 clearing, POS credit→AR); optional per-payment `liquid_account_id` GL override; cheque lifecycle deposit/clear/bounce/cancel; direct bank API connectors (`bank_account_connections`, providers `mock`|`http_json`, `POST .../bank-connections/{id}/sync`, Celery `sync_bank_feeds`, external_ref dedupe into recon statements). Remaining: native Open Banking/Plaid vendor adapters (http_json covers aggregator feeds).
- [x] Credit limits, balances, payments and aging complete.
  - Complete: AR/AP aging buckets (AP prefers purchase invoices, falls back to uninvoiced POs), statements, auto-allocate payments oldest-first, supplier payments + journals, credit-limit warnings, early-payment discounts for AR give and AP take (`early_pay_discount_pct`/`days`, quote APIs, settle with Dr/Cr Sales Discounts 4100 or Purchase Discounts Taken 4200), multi-currency credit (tenant base + `exchange_rates`, document `currency`/`exchange_rate` on sales/purchase invoices and payments, GL + party balances in base, FX gain/loss 4300 on settle rate variance), live FX feed / auto-update (`POST /credit/exchange-rates/refresh`, `FX_PROVIDER` open_er_api|frankfurter, Celery `refresh_fx_rates`, tenant `fx_auto_refresh`).
- [ ] VAT/tax calculation and reporting complete.
  - Partial: tax types/modes, default rate, auto-calc on sales invoices + POS, product tax override/exempt, compound rate components (`basis=net|compound`), sales reverse charge (memo tax excluded from customer total + filing box 2a), purchase reverse charge (`is_reverse_charge` → AP=net, self-assess Dr 1300 / Cr 2100 on approve, filing input+output), output/input tax report, jurisdiction-neutral filing pack + Ghana GRA VAT return template (`tax_jurisdiction`/`tax_registration_number`, `GET /reports/tax/filing`, export `tax_filing_gh`). Remaining: other jurisdictions, GRA e-file portal submission, standard/zero/exempt supply splits.
- [ ] Multi-store/warehouse inventory and transfer workflow complete.
  - Partial: stores with linked warehouses, warehouse stock balances, transfer draft→requested→in_transit→received/cancelled with stock movements; store sales reporting (`GET /reports/sales/by-store`); invoice post + POS sale deduct store warehouse stock when `store_id` / session store is set (unlocated stock auto-allocated); per-store warehouse reorder_level/reorder_qty + low-stock report/notifications; optional `fefo_strict_warehouse` (FEFO only from warehouse-tagged batches). Remaining: advanced multi-bin locations.
- [ ] Reports and exports complete.
  - Partial: sales/inventory/purchase/expense/cash-flow reports, salesperson + store performance, balance sheet, unified CSV/PDF/Excel (`xlsx`) export including tax filing pack + Ghana VAT return (`tax_filing_gh`); scheduled report email (`report_schedules` + Celery `run_due_report_emails`). Remaining: additional jurisdiction filing templates.
- [ ] In-app notifications and channel preferences complete.
  - Partial: categorized alerts, unread count/bell, mark read/all, preferences, low-stock + payment-due scan, email channel (SMTP), SMS channel (Twilio with console fallback) + profile phone + `/settings/sms`. Remaining: none for auth-linked MFA channels (WebAuthn lives under Identity).

### Reliability & operations
- [ ] Automated backup and tested restore complete.
  - Partial: encrypted tenant logical backups (`.ribbak`), SHA-256 integrity, download, dry-run + guarded restore, retention prune, schedule settings + `/backup/run-due` + Celery beat due runner, admin UI; full pg_dump/WAL/S3 offsite and DR drill still pending.
- [ ] Point-in-time recovery/WAL strategy complete.
- [ ] Immutable audit logging for sensitive operations complete.
  - Partial: append-only APIs, hash-chained integrity verify, filtered query + CSV export, login/logout/user-create audited; full middleware coverage and 7-year cold archive still pending.
- [ ] Redis/Celery/RabbitMQ used for intended production workloads.
  - Partial: Redis for distributed API/auth rate limiting; Celery worker + beat on RabbitMQ broker (Redis results) for low-stock scan, payment-due scan, recurring expenses, due backups, report emails, FX rate refresh, and bank feed sync (`sync_bank_feeds`); admin `GET /jobs` + `POST /jobs/{name}/run`; AI nightly jobs still pending.
- [ ] Monitoring, metrics, logging and alerting complete.
- [ ] Kubernetes production deployment reviewed.
- [ ] Load/performance tests meet documented targets.
- [ ] Disaster recovery drill passes.

### AI
- [ ] AI provider configured securely.
- [ ] Tenant-safe data access enforced.
- [ ] AI functions use real tenant data and satisfy documented acceptance criteria.
- [ ] AI audit logging and prompt/data protections complete.

## Current repository rule

Until every applicable item above is verified, Cursor and developers must describe unfinished items as `PARTIAL`, `MISSING`, or `BLOCKED` — never as complete or production-ready.
