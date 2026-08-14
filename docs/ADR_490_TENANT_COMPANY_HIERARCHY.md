# ADR-490: Tenant → Company Hierarchy (Workspace Context)

**Status:** Accepted  
**Date:** 2026-08-14  
**Related:** [ADR-001](ADR_001_TENANCY.md), [ADR-005](ADR_005_USER_STORE_ASSIGNMENT.md), [ADR-137](ADR_137_PLATFORM_PRINCIPAL.md), [ADR-002](ADR_002_BILLING_DEFERRED.md)

## Context

RIBDIGI MVP historically **collapsed Tenant ≈ Company**: `tenants.company_name` held the operating business, and tenant admins (`company_admin`) received full ERP module permissions. Product requirement is:

```text
Platform → Tenant (SaaS customer) → Company (operating business)
  → Branch / Store / Warehouse → Users → Roles / Permissions
```

Tenant Owner/Admin must **not** automatically access company operational data (POS, sales, stock, finance). Access requires explicit **company membership** and an active **company workspace**.

ADR-005 (user↔store membership) remains deferred. This ADR introduces **user↔company membership**, which is orthogonal.

## Decision

1. **Separate entities:** `Tenant` (SaaS account) and `Company` (operating business under a tenant). Shared-schema + `tenant_id` (ADR-001) remains; company-owned rows also carry `company_id`.
2. **Backfill:** Each existing tenant receives one default `Company` from `tenants.company_name` / industry / currency. Existing operational rows backfill to that company.
3. **Membership:** `user_company_memberships` links users to companies with a company role. Tenant-level roles (`tenant_owner`, `tenant_admin`, legacy `company_admin`/`super_admin`) may administer the tenant workspace without implying ops access.
4. **Workspace context:** Session claims include `workspace_kind` ∈ {`platform`,`tenant`,`company`} and optional `company_id`. Clients may send `X-Workspace-Kind` and `X-Company-ID`; the server verifies membership and never trusts client IDs alone.
5. **Authorization:** Operational modules (POS, sales, inventory, purchasing, expenses, accounting, credit, reports, stores, warehouse, …) require `workspace_kind=company` + membership + RBAC. Tenant modules (tenant dashboard, companies CRUD, subscription/limits, tenant settings) require `workspace_kind=tenant` (or platform for House APIs).
6. **Subscription limits:** Enforce `max_companies` (and related caps) on the tenant from plan metadata / tenant columns. Live billing remains deferred (ADR-002); limits are real gates, not fabricated MRR.
7. **Business types:** Configurable `business_types` catalog (not hard-coded application branches).
8. **Store membership:** Still deferred (ADR-005). Store context remains session/document + `stores.manager_id`.

## Consequences

- Existing single-company tenants keep working after backfill; cashiers default into company workspace.
- Tenant admins default into **tenant** workspace and must switch to a company to operate ERP modules.
- Multi-company tenants get real `company_id` isolation.
- Does **not** Complete ADR-002 billing, ADR-005 store membership, or schema-per-tenant.

## Phase 2 follow-up (2026-08-14)

- Operational **list** endpoints for sales docs, purchasing, expenses, COA, journals, customers/suppliers, stores, and warehouses apply `company_scope_filter`.
- Matching **creates** stamp `company_id` for invoices, expenses, parties, POs, stores/warehouses, and catalog rows.
- Unique keys for accounts, expense/product categories, brands, units, warehouses, products, and customer groups are company-scoped (`20260814_0097`).
- Remaining PARTIAL: some purchasing/sales document creates (quotations/returns/GRNs), stock movement helpers, and export CSVs still need full company stamping/filtering.
