# ADR-003: User Delete Policy for Commercial MVP

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-3.1 requires soft delete (deactivate) and hard delete with data archival. Users are referenced by real foreign keys (`pos_sessions`, auth sessions/tokens, WebAuthn, store/warehouse managers, notifications) and by financial `created_by` provenance fields. Hard-deleting user rows would orphan or block those references.

## Decision

For Stage 1 / Commercial MVP:

1. **Soft-delete only.** `DELETE /users/{id}` deactivates (`is_active=False`), revokes sessions, and audits `user_deactivated`.
2. **No hard delete API.** There is no endpoint that removes a `users` row.
3. **Reactivation** via `PATCH /users/{id}` with `is_active=true` (audited).
4. Users cannot deactivate their own account.
5. BR-3.1 “Hard delete with data archival” is **post-MVP** (requires reassignment/anonymize strategy that preserves FKs and financial provenance).

## Consequences

- Audit and POS history retain stable user IDs.
- Email uniqueness remains `(tenant_id, email)` on inactive users (reuse requires a future archive/anonymize flow).
- Product docs must not claim permanent delete until post-MVP work ships.
