# Store-scoped RBAC Complete — remaining checklist

**Status:** **MISSING** (do not claim)  
**As of tip ancestry:** ADR-005 membership **Complete** (flag default OFF)  
**Related:** overall RBAC readiness **PARTIAL**

## ADR-005 Complete ≠ store-scoped RBAC Complete

| Claim | Meaning | Status |
|-------|---------|--------|
| **ADR-005 membership Complete** | User↔store assign/list/revoke + `/me` + admin UI + flag-gated scope union + cashier fail-closed + POS bind + automated flag-ON soak | **Complete** (prod flag default **OFF** intentional) |
| **Store-scoped RBAC Complete** | `store_manager` (and scoped cashiers) cannot read/write company-level dumps or foreign-store data across **all** ERP surfaces beyond intentional product ALLOWs; residual field-leak backlog empty or product-accepted | **MISSING** |

ADR-005 is the **membership + scope wiring** product. Store-scoped RBAC Complete is the **breadth** claim over ops/reports/AI/admin/settings surfaces (historically advanced via continuum redacts). Closing ADR-005 does **not** flip store-scoped RBAC Complete.

Honesty flags (`GET /me/store-memberships` etc.):

- `adr005_complete_claimed` = **true**
- `store_scoped_rbac_complete_claimed` = **false**

## What is already landed (PARTIAL evidence — not Complete)

- `manager_id` (+ flag-ON membership union) scoping on major commerce/ops/report/AI paths
- Company-level dump denies for many admin/settings/catalog/master surfaces
- Cost / PII / approval-matrix / BI-config / budget-limit redacts (continuum-hardened)
- Managed-store `manager_id` self-scope dump **closed**
- Intentional product ALLOWs retained: company/tenant logo binary GET; caller-scoped `/auth/sessions` + `/notifications/settings`

## Remaining checklist before any Complete claim

Engineering (closable without ops theater):

1. **Residual continuum field leaks** — only as product-prioritized slices (paused as default CONTINUE path; not dump spam). Empty backlog or explicit ALLOW list with product sign-off.
2. **First-class `export` / `view_cost` actions** — **Complete** (engine slice for these actions): engine + system role grants + deps auto-`read`; commerce/dashboard/ops/AI **and** admin/settings/catalog CSV paths gated on module `export` (not mere `read`); report/BI/AI/stock-count cost omit helpers unified on `inventory:view_cost` / `business_insights:view_cost` (legacy managed/WH fallback retained when claims omitted). Intentional non-module gates retained: admin `require_roles` dumps (tenant settings/backup/api-keys/webhooks/jobs) and caller-scoped `/auth/sessions` + passkeys exports. Does **not** imply overall RBAC Complete or store-scoped RBAC Complete.
3. **Living store-scope test matrix** — single indexed suite covering modules claimed Complete (not only `test_store_scope_ops_hardening.py` growth).
4. **Temp membership / elevation / break-glass** — temp membership `expires_at` **PARTIAL** (column + scope exclusion + admin UI + tests); elevation / break-glass still **MISSING** (optional for store-scope Complete if product scopes Complete without them; still blocks overall RBAC Complete).
5. **Concurrent approval stress pack** — still **MISSING** (overall RBAC; not strictly store-scope).

Ops / product (required for Completes that stay ops-blocked elsewhere):

6. Product acceptance that remaining intentional ALLOWs are correct.
7. Staging soak with `STORE_MEMBERSHIP_SCOPE_ENABLED=true` (ops cutover — does **not** reopen ADR-005 Complete; does **not** alone claim store-scoped Complete).

## Explicit non-claims

Do **not** mark store-scoped RBAC Complete from:

- ADR-005 automated soak alone
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

1. Living store-scope test matrix (indexed suite)
2. Elevation / break-glass on top of temp membership `expires_at` (smallest elevation MVP)
3. Concurrent approval stress pack
4. Only resume store_manager field-leak continuum when product prioritizes a named surface
