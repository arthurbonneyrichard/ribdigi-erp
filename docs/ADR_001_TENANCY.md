# ADR-001: Tenant Isolation for Commercial MVP

**Status:** Accepted  
**Date:** 2026-08-08

## Context

Architecture docs specify schema-per-tenant. The running codebase uses shared tables with `tenant_id`. Schema-per-tenant is the long-term target, but rewriting isolation before auth, RBAC, and transactional inventory would delay a usable commercial MVP.

## Decision

For MVP implementation, use **shared-schema multi-tenancy** with:

1. Every tenant-owned row includes `tenant_id`
2. JWT always carries `tenant_id`; `X-Tenant-ID` must match when present
3. All queries filter by `tenant_id` from the authenticated session (never from client body alone)
4. Cross-tenant isolation automated tests are mandatory for new resource endpoints
5. Schema-per-tenant remains a post-MVP migration path (documented in PRODUCTION_READINESS)

## Consequences

- Faster delivery of auth, RBAC, inventory, and financial workflows
- Isolation bugs are application-layer risks — mitigated by tests and review
- Backup/restore is database-wide until schema-per-tenant lands

See also Stage 185 schema-per-tenant remaining-gate index: [`SCHEMA_PER_TENANT_REMAINING_GATE_MVP.md`](SCHEMA_PER_TENANT_REMAINING_GATE_MVP.md) (schema-per-tenant remains deferred; not Complete).
