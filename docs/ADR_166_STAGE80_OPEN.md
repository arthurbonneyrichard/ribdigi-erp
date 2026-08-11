# ADR-166: Stage 80 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-165 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 79 Commercial Data Exit Fidelity exit criteria are met (`docs/STAGE_79_EXIT_CRITERIA.md`) with R1–D1 / H79x Complete (ADR-165). Product owner approved opening Stage 80 after Stage 79 freeze via CONTINUE/NEXT with a distinct product outline: **Platform Owner Dashboard Charts → Tenant Role-Scoped Dashboards → Dual-Console Dashboard Fidelity**.

Audit of current dual-console (ADR-137 + Stage 68) found:

| Area | Status |
|------|--------|
| Platform vs tenant principal isolation | EXISTS (ADR-137) |
| Platform user / tenant CRUD | EXISTS |
| Tenant RBAC + custom roles | EXISTS (`company_admin` = Tenant Admin) |
| Tenant executive dashboard KPIs/charts | EXISTS |
| Platform dashboard KPIs | EXISTS (cards only) |
| Platform dashboard charts | MISSING |
| Cashier / Store Manager scoped dashboards | MISSING |
| Permission-driven dashboard sections (backend) | PARTIAL |
| Paid billing / MRR | DEFERRED (ADR-002) |

Owner product outline:

```
Commercial Data Exit Packaged (Stage 79)
     ↓
Platform Owner Dashboard Charts
     ↓
Tenant Role-Scoped Dashboards
     ↓
Dual-Console Dashboard Fidelity
```

## Decision

1. **Stage 80 delivery track is open** per `docs/STAGE_80_PLAN.md`.
2. **Stage 1–79 freezes remain** for their respective scopes.
3. Deliver Stage 80 **one workstream at a time** (P1 → T1 → D1 → H80x).
4. Explicitly out of this pass: paid billing / fabricated MRR Complete (ADR-002); inventing fake chart series; reopening Stage 68 honesty packs as new Complete; reopening Stages 1–79 frozen feature scopes; main `ci.yml` deploy jobs. Honesty flags stay false for: `mrr_fabricated_claimed: false`, `billing_complete_claimed: false`, `go_live_claimed: false`, `sections_1_3_verified: false`, `section_7_signed: false`.
5. Extend proven ADR-137 / dashboard patterns — do not invent a parallel identity stack.
6. Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Consequences

- Agents may implement Stage 80 plan items without reopening Stage 1–79 feature scope.
- Stage 80 exit requires `docs/STAGE_80_EXIT_CRITERIA.md` with no CRITICAL/MISSING rows for planned workstreams.
