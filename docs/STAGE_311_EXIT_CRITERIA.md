# Stage 311 — Exit criteria (H311x)

**Status:** COMPLETE — exit met; freeze [ADR-630](./ADR_630_STAGE311_FREEZE.md)  
**Open ADR:** [ADR-629](./ADR_629_STAGE311_OPEN.md)  
**Plan:** [STAGE_311_PLAN.md](./STAGE_311_PLAN.md) · [STAGE_311_FIDELITY.md](./STAGE_311_FIDELITY.md)

## Pack verdicts

| Pack | Verdict |
|------|---------|
| **I1** | COMPLETE |
| **B1** | COMPLETE |
| **P1** | COMPLETE |
| **D1** | COMPLETE |
| **H311x** | COMPLETE |

## Must pass before freeze (ADR-630)

1. **I1** — `SERVICE_CREDIT_WARRANTY_PACK_REMAINING_GATE_MVP.md` + `ops/mvp/service-credit-warranty-pack-remaining-gate.json` exist; honesty flags are `false`.
2. **B1** — blockers ledger documents Stage 46 W1 packaging non-claim; no live service credits Complete.
3. **P1** — pack pointers resolve to I1/B1/P1 artifacts and related Stage 46 W1 / Stage 310 / Stage 309 / Stage 40 U1 docs.
4. **D1** — fidelity cites present in required docs; honesty flags false.
5. Automated tests: `pytest tests/test_stage311_*.py` green.
6. Frontend: `npm run build` succeeds (no Stage-311 UI claim of live service credits Completes).

## Explicit non-exit

- Live service credits / warranty / uptime credit / remedy schedule live Complete
- Go-live Complete
- Reopening frozen Stages 1–310 (including Stage 46 W1 / Stage 310 / Stage 309 / Stage 40 U1)
