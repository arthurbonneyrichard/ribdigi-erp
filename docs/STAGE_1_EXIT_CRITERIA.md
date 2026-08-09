# Stage 1 Exit Criteria

**Status:** Met for foundation workstreams A–H (2026-08-09)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Freeze:** [ADR-008](ADR_008_STAGE1_FREEZE.md)

Stage 1 exit is the foundation shell (auth, tenancy, org, RBAC, settings, dashboard, audit). It is **not** a claim that every BR in later modules is Complete.

## Workstream checklist

| ID | Workstream | Verdict | Evidence |
|----|------------|---------|----------|
| A1 | Email verify before login | COMPLETE | Login gate + resend-verification |
| A2 | Change password | COMPLETE | `POST /auth/change-password` + Security UI |
| A3 | Idle session revoke | COMPLETE | `POST /auth/idle-logout` + Shell timer |
| B4 | Logo / legal name on docs | COMPLETE | `print_branding` on invoice/receipt/quote/CN |
| B5 | Plan honesty | COMPLETE | ADR-002; `billing_deferred` |
| B6 | Isolation hygiene | COMPLETE | Isolation tests (users/SMTP/warehouse) |
| C7 | Branches / departments admin | COMPLETE | Company UI edit/deactivate |
| C8 | Stores manager / hours | COMPLETE | Multi-Store detail + hours |
| C9 | Warehouse admin UI | COMPLETE | Warehouse create/edit |
| D10 | User delete policy | COMPLETE | ADR-003 soft-delete only |
| D11 | Menu = module | COMPLETE | ADR-004 + `frontend/lib/rbac.ts` |
| D12 | User↔store deferral | COMPLETE | ADR-005 |
| E13 | Apply regional formats | COMPLETE | `/me` formats + `frontend/lib/format.ts` |
| E14 | Receipt/invoice templates | COMPLETE | Templates + header/footer |
| E15 | Language | COMPLETE | ADR-006 English + i18n scaffold |
| F16 | Dashboard charts | COMPLETE | 30d/12m revenue series + SVG charts |
| F17 | KPI click-through | COMPLETE | `kpi_links` + `?tab=` deep links |
| F18 | Notifications panel | COMPLETE | Groups, unread toggle, dashboard stream |
| G19 | Audit coverage | COMPLETE | HTTP mutation middleware `http_write` |
| G20 | Audit retention | COMPLETE | ADR-007; cold archive; no purge |
| H21 | Exit criteria documented | COMPLETE | This file |
| H22 | Automated tests for Stage 1 deltas | COMPLETE | Stage 1 test modules under `backend/tests/` |
| H23 | Scope freeze recorded | COMPLETE | ADR-008 |

## Explicitly deferred (not Stage 1 blockers)

- Paid billing provider (ADR-002)
- Non-English UI packs (ADR-006)
- User↔store membership (ADR-005)
- User hard-delete / archival (ADR-003)
- Hot audit row physical prune after 7 years (ADR-007)
- Schema-per-tenant (ADR-001)

## Sign-off rule

Stage 1 foundation exit is **met** when the table above has no CRITICAL/MISSING rows for A–H and ADR-008 is accepted. Broader commercial MVP readiness remains tracked in `PRODUCTION_READINESS.md` and may still show Partial for later modules.
