# ADR-010: Stage 2 Scope Freeze

**Status:** Accepted  
**Date:** 2026-08-09  
**Related:** [ADR-009](ADR_009_STAGE2_OPEN.md), [STAGE_2_EXIT_CRITERIA.md](STAGE_2_EXIT_CRITERIA.md)

## Context

Stage 2 Inventory & Supply Chain hardening (I1–I6) delivered opening stock, ops scan/reasons, dual-threshold low stock, count variance export, movement audit integrity, and catalog harden (UoM conversion, brand logo, weight/dimensions). Opening Stage 3 feature expansion before recording Stage 2 exit risks unfinished ACs.

## Decision

1. **Stage 2 is frozen for new feature scope.** Further Stage 2 work is limited to bugfixes, security patches, test hardening, and documentation corrections against accepted ACs / ADRs.
2. **Do not open Stage 3 as the next delivery track** until `docs/STAGE_2_EXIT_CRITERIA.md` remains accurate and any CRITICAL Stage 2 failures are closed.
3. Deferred items (P1 multi-line return UI, P2 Kanban, M1 multi-bin) remain deferred.
4. Existing later-stage code may receive bugfixes; new Stage 3 epics require explicit plan approval after Stage 2 exit sign-off.

## Consequences

- Agents treat Stage 2 I1–I6 as closed unless fixing a regression.
- `PRODUCTION_READINESS.md` continues to track module-level Partial/Complete for the whole commercial MVP.

## Amendment (2026-08-09)

Stage 3 delivery track was **explicitly approved** and opened under [ADR-011](ADR_011_STAGE3_OPEN.md) / `docs/STAGE_3_PLAN.md`. Stage 2 freeze above still applies to Inventory & Supply Chain I1–I6 scope.
