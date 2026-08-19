# Stage 315 — Exit criteria (H315x)

**Status:** COMPLETE — exit met; freeze [ADR-638](./ADR_638_STAGE315_FREEZE.md)  
**Open ADR:** [ADR-637](./ADR_637_STAGE315_OPEN.md)  
**Plan:** [STAGE_315_PLAN.md](./STAGE_315_PLAN.md) · [STAGE_315_FIDELITY.md](./STAGE_315_FIDELITY.md)

## Pack verdicts

| Pack | Verdict |
|------|---------|
| **I1** | COMPLETE |
| **B1** | COMPLETE |
| **P1** | COMPLETE |
| **D1** | COMPLETE |
| **H315x** | COMPLETE |

## Must pass before freeze (ADR-638)

1. **I1** — `SECURITY_SCAN_PACK_REMAINING_GATE_MVP.md` + `ops/mvp/security-scan-pack-remaining-gate.json` exist; honesty flags are `false`.
2. **B1** — blockers ledger documents Stage 27 S1 / Stage 210 packaging non-claim; no live security-scan Complete.
3. **P1** — pack pointers resolve to I1/B1/P1 artifacts and related Stage 27 S1 / Stage 314 / Stage 313 / Stage 210 docs.
4. **D1** — fidelity cites present in required docs; honesty flags false.
5. Automated tests: `pytest tests/test_stage315_*.py` green.
6. Frontend: `npm run build` succeeds (no Stage-315 UI claim of live security-scan Completes).

## Explicit non-exit

- Live security-scan / live ZAP / vendor pen-test purchased / ZAP CI wired Complete
- Go-live Complete
- Reopening frozen Stages 1–314 (including Stage 27 S1 / Stage 314 / Stage 313 / Stage 210)
