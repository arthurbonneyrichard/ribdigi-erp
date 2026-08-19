# ADR-017: Stage 6 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-09  
**Supersedes (in part):** ADR-016 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 5 Polish, Security & Launch hardening exit criteria are met (`docs/STAGE_5_EXIT_CRITERIA.md`) and Stage 5 feature scope remains frozen (ADR-016). Product owner approved opening Stage 6 (Integrations, Onboarding & Performance) as the next delivery track via CONTINUE after Stage 5 freeze.

Remaining commercial-MVP gaps from Phase 5 / BR-18 include tenant API keys, webhooks, onboarding checklist UX, and Redis app-data caching. Greenfield Kubernetes, WAL/PITR, vendor pen test, and paid billing stay deferred.

## Decision

1. **Stage 6 delivery track is open** per `docs/STAGE_6_PLAN.md`.
2. **Stage 1–5 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 6 **one workstream at a time** (K1 → …) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: Kubernetes/Helm, full Prometheus/Grafana stack, pg_dump/WAL/S3 PITR, vendor penetration test, paid billing (ADR-002), schema-per-tenant (ADR-001), i18n packs (ADR-006), certified 1000-VU ops run.

## Consequences

- Agents may implement Stage 6 plan items without reopening Stage 1–5 feature scope.
- Stage 6 exit requires `docs/STAGE_6_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned P0 workstreams.

## Amendment (2026-08-09)

Stage 6 exit criteria are **met** and feature scope is **frozen** under [ADR-018](ADR_018_STAGE6_FREEZE.md) / `docs/STAGE_6_EXIT_CRITERIA.md`. This open ADR remains historical for the delivery track.
