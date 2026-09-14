# Store-scoped RBAC Complete — remaining checklist

**Status:** **Complete** (engineering + product ALLOW acceptance + automated/local soak)  
**As of tip ancestry:** ADR-005 membership **Complete** (flag default OFF); continuum residual dump **NONE** (safe backlog empty); intentional ALLOWs **product-accepted** ([`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md)); living matrix + flag-ON soak evidence landed  
**Related:** overall RBAC readiness still **PARTIAL** (not overall RBAC Complete)  
**Living matrix:** **landed** — [`STORE_SCOPED_RBAC_TEST_MATRIX.md`](STORE_SCOPED_RBAC_TEST_MATRIX.md) · `ops/mvp/store-scope-rbac-matrix.json` · `backend/tests/test_store_scope_rbac_matrix.py` (`pytest -m store_scope`)  
**Local / automated soak:** [`STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md`](STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md) · ADR-005 soak suite · matrix living cases  
**Staging soak (ops enable only):** [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md) · evidence [`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md) · go-live [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md) §3C  
**Intentional ALLOWs:** **ACCEPTED** — logo binary GET · `/auth/sessions` · `/notifications/settings` ([policy](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md))

## ADR-005 Complete ≠ store-scoped RBAC Complete (both now Complete)

| Claim | Meaning | Status |
|-------|---------|--------|
| **ADR-005 membership Complete** | User↔store assign/list/revoke + `/me` + admin UI + flag-gated scope union + cashier fail-closed + POS bind + automated flag-ON soak | **Complete** (prod flag default **OFF** intentional) |
| **Store-scoped RBAC Complete** | `store_manager` (and scoped cashiers) cannot read/write company-level dumps or foreign-store data across ERP surfaces beyond **product-accepted** intentional ALLOWs; residual field-leak backlog empty | **Complete** (flag default **OFF**; staging enable = ops cutover ≠ reopen) |

Closing ADR-005 alone did **not** flip store-scoped RBAC Complete. Complete for store-scoped RBAC required: empty residual dump backlog + living matrix + product ALLOW acceptance + automated/local membership-scope soak evidence (SEC-M2 / ADR-005 parallel). Staging flag enable remains ops.

Honesty flags (`GET /me/store-memberships` etc.):

- `adr005_complete_claimed` = **true**
- `store_scoped_rbac_complete_claimed` = **true**

## What is landed (Complete evidence)

- `manager_id` (+ flag-ON membership union) scoping on major commerce/ops/report/AI paths
- Company-level dump denies for many admin/settings/catalog/master surfaces
- Cost / PII / approval-matrix / BI-config / budget-limit redacts (continuum-hardened)
- Managed-store `manager_id` self-scope dump **closed**
- Continuum residual field-leak backlog **NONE** (safe named SM-visible leftovers empty)
- Living store-scope test matrix (indexed suite + CI `store_scope` marker)
- Product-accepted intentional ALLOWs: company/tenant logo binary GET; caller-scoped `/auth/sessions` + `/notifications/settings`
- Automated flag-ON membership soak + local demo-seed soak pack
- First-class `export` / `view_cost` engine slice **Complete** (not overall RBAC Complete)
- Temp membership `expires_at` **Complete**; elevation / break-glass MVP **Complete**
- Concurrent approval stress pack **Complete**

## Remaining checklist before Complete — **EMPTY**

| # | Item | Status |
|---|------|--------|
| 1 | Residual continuum field leaks | **Closed** — safe backlog empty (NONE) |
| 2 | First-class `export` / `view_cost` | **Complete** (engine slice) |
| 3 | Living store-scope test matrix | **Landed** |
| 4 | Temp membership / elevation / break-glass | **Complete** |
| 5 | Concurrent approval stress pack | **Complete** |
| 6 | Product ACCEPT on intentional ALLOWs | **Accepted** — [`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md) |
| 7 | Membership-scope soak evidence | **Complete** via automated flag-ON soak + local demo-seed soak ([evidence](STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md)); staging enable remains ops cutover (does **not** reopen Complete) |

## Explicit non-claims

Do **not** mark from this Complete alone:

- Overall RBAC Complete (still **MISSING** / readiness **PARTIAL**)
- Offline Complete + 7-day VERIFIED (**MISSING** / ops)
- Paid billing Complete (**PARTIAL** / ops-blocked)
- Go-live / attestation (**MISSING**)
- Production `STORE_MEMBERSHIP_SCOPE_ENABLED=true` default (ops cutover; default remains **false**)

## Related Completes

| Claim | Status |
|-------|--------|
| Store-scoped RBAC Complete | **Complete** (flag default OFF) |
| Overall RBAC Complete | **MISSING** / readiness **PARTIAL** |
| Offline Complete + 7-day VERIFIED | **MISSING** (ops) |
| Paid billing Complete | **PARTIAL** / ops-blocked |
| Go-live / attestation | **MISSING** |
| ADR-005 membership Complete | **Complete** (flag default OFF) |
| Commercial MVP market-ready | **Conditional** — see [`MARKET_READY_LAUNCH.md`](MARKET_READY_LAUNCH.md) |

## Next ops (does not reopen this Complete)

1. Staging execution of [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md) before any prod flag default ON
2. Do **not** resume continuum dump spam unless a new **named** SM-visible surface is product-prioritized
3. Market-ready packaging: [`MARKET_READY_LAUNCH.md`](MARKET_READY_LAUNCH.md)
