# ADR-630: Stage 311 Scope Freeze

**Status:** Accepted  
**Date:** 2026-08-14  
**Related:** [ADR-629](ADR_629_STAGE311_OPEN.md), [STAGE_311_EXIT_CRITERIA.md](STAGE_311_EXIT_CRITERIA.md), [STAGE_311_FIDELITY.md](STAGE_311_FIDELITY.md), [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md)

## Context

Stage 311 Tenant MVP Service Credit Warranty Pack Remaining-Gate Index Fidelity delivered service credit warranty pack remaining-gate hub (I1), blocker matrix (B1), Stage 46 W1 / Stage 310 / Stage 309 / Stage 40 U1 pointers (P1), fidelity sync (D1), and exit (H311x). Prior Stage 310 remains frozen under ADR-628.

## Decision

1. **Stage 311 is frozen for new feature scope** (bugfixes / test hardening / doc corrections only).
2. **Do not open Stage 312** until CONTINUE/NEXT with a distinct outline is approved.
3. Deferred items in Stage 311 exit criteria remain deferred.
4. **Stage 1–310 freezes remain in force**.
5. Honesty flags stay false including `service_credits_live`, `warranty_live_claimed`, `uptime_credit_claimed`, `remedy_schedule_live`, `go_live_claimed`, plus prior Stage 310 honesty flags.
6. Do **not** claim live service credits Completes, warranty Completes, uptime credit Completes, remedy schedule live Completes, or go-live Completes (ADR-002 remain in force).

## Consequences

- Agents treat Stage 311 I1 / B1 / P1 / D1 / H311x as closed unless fixing a regression.
- Main `ci.yml` remains deploy-free (**Stage 18 C1**).

## Next stage

Stage 312 requires CONTINUE/NEXT with a distinct product outline after this freeze. Stage 311 feature scope remains frozen.

**Runner-up outline (not opened):** Tenant MVP Status Uptime Pack Remaining-Gate Index Fidelity — single index of status-uptime-pack blockers (packaged Stage 40 U1 status uptime materials non-claim as live status-page / measured-uptime Completes) with explicit non-claim. Prefixed `STATUS_UPTIME_PACK_*` if a prior remaining-gate exists. Distinct from Stage 311 service credit warranty pack remaining-gate, Stage 310 liability indemnity pack remaining-gate, and `STATUS_UPTIME_MVP.md` packaging. Source: `STATUS_UPTIME_MVP.md`.

## Non-claims

Packaging ≠ live Completes for live service credits, warranty, uptime credit, remedy schedule live, or go-live.
