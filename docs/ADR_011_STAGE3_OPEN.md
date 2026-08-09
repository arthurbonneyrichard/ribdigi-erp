# ADR-011: Stage 3 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-09  
**Supersedes (in part):** ADR-010 clause that blocked opening Stage 3 until explicit sign-off

## Context

Stage 2 Inventory & Supply Chain hardening exit criteria are met (`docs/STAGE_2_EXIT_CRITERIA.md`) and Stage 2 feature scope remains frozen (ADR-010). Product owner approved opening Stage 3 (Sales, POS & Financials hardening) as the next delivery track.

Roadmap Phase 3 features 3.1–3.21 are largely already in the codebase. Remaining work is BR acceptance holes (journal unpost, COA CRUD depth, report date ranges, POS split tender, credit-limit override audit) — not greenfield modules.

## Decision

1. **Stage 3 delivery track is open** per `docs/STAGE_3_PLAN.md`.
2. **Stage 1 and Stage 2 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 3 **one workstream at a time** (A1 → …) with tests, commit, push, and PR update after each feature.
4. Explicitly out of MVP for this pass: native Open Banking/Plaid adapters, tax portal e-file, vendor USB/serial POS drivers beyond existing bridges.

## Consequences

- Agents may implement Stage 3 plan items without reopening Stage 1/2 feature scope.
- Stage 3 exit requires `docs/STAGE_3_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned P0 workstreams.
