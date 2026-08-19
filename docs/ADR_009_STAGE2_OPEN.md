# ADR-009: Stage 2 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-09  
**Supersedes (in part):** ADR-008 clause that blocked opening Stage 2 until explicit sign-off

## Context

Stage 1 foundation exit criteria are met (`docs/STAGE_1_EXIT_CRITERIA.md`) and Stage 1 feature scope remains frozen (ADR-008). Product owner approved opening Stage 2 (Inventory & Supply Chain hardening) as the next delivery track.

Roadmap Phase 2 features 2.1–2.17 are largely already in the codebase. Remaining work is BR AC holes and UX hardening, not greenfield modules.

## Decision

1. **Stage 2 delivery track is open** per `docs/STAGE_2_PLAN.md`.
2. **Stage 1 freeze remains** for foundation A–H: bugfixes / security / tests / docs only.
3. Deliver Stage 2 **one workstream at a time** (I1 → …) with tests, commit, push, and PR update after each feature.
4. Purchasing 2.10–2.16 are treated as MVP-complete; optional polish (P1–P2) is not a blocker for Stage 2 exit.
5. Multi-bin locations (M1) stay under multi-store Remaining and are out of the first Stage 2 hardening pass unless explicitly pulled in.

## Consequences

- Agents may implement Stage 2 plan items without reopening Stage 1 scope.
- Stage 2 exit requires `docs/STAGE_2_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.
