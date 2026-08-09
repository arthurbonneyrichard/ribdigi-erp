# ADR-013: Stage 4 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-09  
**Supersedes (in part):** ADR-012 clause that blocked opening Stage 4 until explicit sign-off

## Context

Stage 3 Sales, POS & Financials hardening exit criteria are met (`docs/STAGE_3_EXIT_CRITERIA.md`) and Stage 3 feature scope remains frozen (ADR-012). Product owner approved opening Stage 4 (Intelligence, Multi-Store & Scale hardening) as the next delivery track via CONTINUE after Stage 3 freeze.

Roadmap Phase 4 features 4.1–4.22 are largely already in the codebase (stores, transfers, reports, notifications, rule-based AI). Remaining work is BR acceptance holes — not greenfield modules or Prophet/LLM upgrades.

## Decision

1. **Stage 4 delivery track is open** per `docs/STAGE_4_PLAN.md`.
2. **Stage 1–3 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 4 **one workstream at a time** (T1 → …) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: Prophet/ML upgrade, optional external LLM provider, WebSocket push, materialized views / load tests (Phase 5), FIFO/LIFO layer costing, multi-bin locations, user↔store membership (ADR-005), paid billing (ADR-002), schema-per-tenant (ADR-001), AI document auto-write, pg_dump/WAL DR.

## Consequences

- Agents may implement Stage 4 plan items without reopening Stage 1–3 feature scope.
- Stage 4 exit requires `docs/STAGE_4_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned P0 workstreams.
