# Stage 232 Plan — Tenant MVP Accounts Receivable & Payable Accounting Surface Discoverability

**Status:** Closed — exit met (H232x); freeze ADR-471  
**Base:** Shell Accounts Receivable / Payable + Accounting routes + Credit UI labels  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-470](ADR_470_STAGE232_OPEN.md)  
**Exit:** [STAGE_232_EXIT_CRITERIA.md](STAGE_232_EXIT_CRITERIA.md) · freeze [ADR-471](ADR_471_STAGE232_FREEZE.md)  
**Fidelity:** [STAGE_232_FIDELITY.md](STAGE_232_FIDELITY.md)  
**Impact audit:** [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)  
**Prior freeze:** [ADR-469](ADR_469_STAGE231_FREEZE.md)

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Shell Accounts Receivable / Accounts Payable leaves | P0 | COMPLETE |
| **R1** | Accounting receivables / payables routes | P0 | COMPLETE |
| **U1** | Credit titles + Accounting AR/AP cross-links | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H232x** | Stage 232 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Building a parallel AR/AP engine (Stage 22 Credit remains authority)
- Claiming Open Banking / go-live Completes
- Reopening Stage 22 / Stage 98 / Stages 1–231 feature scopes

## Acceptance

- [x] Shell exposes **Accounts Receivable** and **Accounts Payable**.
- [x] `/accounting/receivables` and `/accounting/payables` route into Credit `kind=`.
- [x] Credit page titles match AR/AP; Accounting page links them.
- [x] Automated proof: `test_stage232_shell_s1.py`, `test_stage232_routes_r1.py`, `test_stage232_ui_u1.py`.
