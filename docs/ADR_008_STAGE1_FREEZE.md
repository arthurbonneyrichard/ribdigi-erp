# ADR-008: Stage 1 Scope Freeze

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Stage 1 (Foundation & Platform Core) delivered auth, tenancy, org UX, users/RBAC, settings, dashboard/notifications, and audit workstreams (A–G). Opening Stage 2 feature expansion before Stage 1 exit criteria are recorded risks unfinished foundation gaps and parallel stacks.

## Decision

1. **Stage 1 is frozen for new feature scope.** Further Stage 1 work is limited to bugfixes, security patches, test hardening, and documentation corrections against accepted ACs / ADRs.
2. **Do not open Stage 2 as the next delivery track** until `docs/STAGE_1_EXIT_CRITERIA.md` remains accurate and any CRITICAL Stage 1 failures are closed.
3. Deferred items already captured in ADRs remain deferred (billing provider, multi-language packs, user↔store membership, hard-delete users, hot audit prune).
4. Existing later-stage code already in the repo (inventory/sales/etc.) may receive bugfixes; new Stage 2 epics require an explicit Stage 2 plan approval after Stage 1 exit sign-off.

## Consequences

- Agents and engineers treat Stage 1 A–H as closed unless fixing a regression.
- `PRODUCTION_READINESS.md` continues to track module-level Partial/Complete for the whole commercial MVP, distinct from Stage 1 foundation exit.
