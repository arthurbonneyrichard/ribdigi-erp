# Store-scoped RBAC Complete — remaining checklist

**Status:** **MISSING** (do not claim)  
**As of tip ancestry:** ADR-005 membership **Complete** (flag default OFF)  
**Related:** overall RBAC readiness **PARTIAL**  
**Living matrix:** **landed** — `docs/STORE_SCOPED_RBAC_TEST_MATRIX.md` · `ops/mvp/store-scope-rbac-matrix.json` · `backend/tests/test_store_scope_rbac_matrix.py` (`pytest -m store_scope`)

## ADR-005 Complete ≠ store-scoped RBAC Complete

| Claim | Meaning | Status |
|-------|---------|--------|
| **ADR-005 membership Complete** | User↔store assign/list/revoke + `/me` + admin UI + flag-gated scope union + cashier fail-closed + POS bind + automated flag-ON soak | **Complete** (prod flag default **OFF** intentional) |
| **Store-scoped RBAC Complete** | `store_manager` (and scoped cashiers) cannot read/write company-level dumps or foreign-store data across **all** ERP surfaces beyond intentional product ALLOWs; residual field-leak backlog empty or product-accepted | **MISSING** |

ADR-005 is the **membership + scope wiring** product. Store-scoped RBAC Complete is the **breadth** claim over ops/reports/AI/admin/settings surfaces (historically advanced via continuum redacts). Closing ADR-005 does **not** flip store-scoped RBAC Complete. Landing the living matrix documents/enforces the spine — it also does **not** alone flip Complete.

Honesty flags (`GET /me/store-memberships` etc.):

- `adr005_complete_claimed` = **true**
- `store_scoped_rbac_complete_claimed` = **false**

## What is already landed (PARTIAL evidence — not Complete)

- `manager_id` (+ flag-ON membership union) scoping on major commerce/ops/report/AI paths
- Company-level dump denies for many admin/settings/catalog/master surfaces
- Cost / PII / approval-matrix / BI-config / budget-limit redacts (continuum-hardened)
- Managed-store `manager_id` self-scope dump **closed**
- Scoped audit `details` FX re-dump **closed** (`currency` / `exchange_rate` / `*_base` / `fx_gain_loss` / `settlement_base` on `/audit-logs` JSON+CSV)
- CREDIT_LIMIT_EXCEEDED 409 `additional_amount` FX re-dump **closed** (base settlement; `invoice_total`/`invoice_total_base`/master already closed)
- CREDIT_LIMIT_EXCEEDED 409 `currency` FX re-dump **closed** (document FX identity in `extra_details`; sales-invoice currency already closed)
- Scoped audit `details` party ledger balance re-dump **closed** (`customer_balance` / `supplier_balance_*` on `/audit-logs` JSON+CSV)
- Scoped audit `details` department_id re-dump **closed** (`department_id` on `/audit-logs` JSON+CSV; expense/recurring already redacted)
- Scoped audit `details` attachment storage key re-dump **closed** (`key` on expense/invoice/journal attachment_upload; `storage_key` on cold archive on `/audit-logs` JSON+CSV; attachment_url / uploaded.key already redacted)
- Scoped audit `details` emailed_to / send-recipient re-dump **closed** (`to` on `invoice_sent`/`pos_receipt_sent`; nested `delivery.to` on `po_sent` on `/audit-logs` JSON+CSV; document `emailed_to` already redacted)
- Scoped audit `details` CLE master re-dump **closed** (`credit_limit` / `available` / `current_balance` / `projected_balance` / `additional_amount` on `/audit-logs` JSON+CSV; FX already closed)
- Scoped audit `details` store manager_id re-dump **closed** (`expected_manager_id` on `transfer_manager_override`; sibling `manager_id` / `from_store_manager_id` / `to_store_manager_id` on `/audit-logs` JSON+CSV; store/WH/transfer manager ids already redacted)
- Intentional product ALLOWs retained: company/tenant logo binary GET; caller-scoped `/auth/sessions` + `/notifications/settings`
- **Living store-scope test matrix** (indexed suite + CI `store_scope` marker) covering cross-store deny, membership-on soak, cashier fail-closed, manager union, intentional ALLOWs, plus breadth index into deep modules

## Remaining checklist before any Complete claim

Engineering (closable without ops theater):

1. **Residual continuum field leaks** — only as product-prioritized slices (paused as default CONTINUE path; not dump spam). Empty backlog or explicit ALLOW list with product sign-off. Latest closed: audit store manager_id.
2. **First-class `export` / `view_cost` actions** — **Complete** (engine slice for these actions): engine + system role grants + deps auto-`read`; commerce/dashboard/ops/AI **and** admin/settings/catalog CSV paths gated on module `export` (not mere `read`); report/BI/AI/stock-count cost omit helpers unified on `inventory:view_cost` / `business_insights:view_cost` (legacy managed/WH fallback retained when claims omitted). Intentional non-module gates retained: admin `require_roles` dumps (tenant settings/backup/api-keys/webhooks/jobs) and caller-scoped `/auth/sessions` + passkeys exports. Does **not** imply overall RBAC Complete or store-scoped RBAC Complete.
3. **Living store-scope test matrix** — **landed** (`ops/mvp/store-scope-rbac-matrix.json` + `test_store_scope_rbac_matrix.py` + CI `-m store_scope`). Documents/enforces cross-store deny, membership soak, cashier fail-closed, manager union, intentional ALLOWs; indexes deep continuum modules. **Not** store-scoped RBAC Complete by itself.
4. **Temp membership / elevation / break-glass** — temp membership `expires_at` **Complete** (column + scope exclusion + admin UI + tests); elevation / break-glass MVP **Complete** (time-bounded grant, required reason, grantor subset, audit, auto-expiry ≤24h, early revoke, deny after expiry — not overall RBAC Complete).
5. **Concurrent approval stress pack** — **Complete** (expense + PR approve/reject/convert race suite; overall RBAC slice — not store-scope Complete).

Ops / product (required for Completes that stay ops-blocked elsewhere):

6. Product acceptance that remaining intentional ALLOWs are correct (matrix lists them; product sign-off still open).
7. Staging soak with `STORE_MEMBERSHIP_SCOPE_ENABLED=true` (ops cutover — does **not** reopen ADR-005 Complete; does **not** alone claim store-scoped Complete).

## Explicit non-claims

Do **not** mark store-scoped RBAC Complete from:

- ADR-005 automated soak alone
- Living store-scope test matrix alone (spine evidence ≠ full-surface Complete)
- Continuum dump redacts without product Complete criteria
- Overall RBAC approval hardening (owner lockout / grantor subset / % limits / etc.)
- First-class `export`/`view_cost` engine slice alone

## Related Completes still MISSING / PARTIAL

| Claim | Status |
|-------|--------|
| Overall RBAC Complete | **MISSING** / readiness **PARTIAL** |
| Offline Complete + 7-day VERIFIED | **MISSING** (ops) |
| Paid billing Complete | **PARTIAL** / ops-blocked |
| Go-live / attestation | **MISSING** |

## Next CONTINUE (recommended)

Prefer engine Completes over continuum dumps:

1. Residual continuum field-leak (product-prioritized named surface only)
2. Product sign-off on intentional ALLOWs + residual backlog empty (when aiming for store-scoped Complete)
3. Staging soak with `STORE_MEMBERSHIP_SCOPE_ENABLED=true` (ops — does not alone claim store-scoped Complete)
