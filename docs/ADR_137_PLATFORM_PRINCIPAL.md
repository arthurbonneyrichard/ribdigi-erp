# ADR-137: Platform Principal Separation

**Status:** Accepted  
**Date:** 2026-08-11  
**Related:** [ADR-001](ADR_001_TENANCY.md), [ADR-002](ADR_002_BILLING_DEFERRED.md)

## Context

Commercial MVP requires a Ribdigi House **Platform Owner** console distinct from each customer **Tenant** ERP. The prior model used a tenant-scoped `super_admin` role for a few cross-tenant lifecycle APIs, which conflates SaaS administration with customer tenancy and risks operator lockout when a home tenant is suspended.

## Decision

1. **Reserved platform tenant** `ribdigi-platform` (id + slug) represents Ribdigi House under ADR-001 shared-schema + `tenant_id`.
2. Platform staff are `users` on that tenant with roles `platform_super_admin` / `platform_admin` (MVP). JWT includes `principal: "platform" | "tenant"`.
3. Platform APIs live under `/api/v1/platform/*` and require platform principal + platform module permission.
4. Tenant ERP APIs remain tenant-scoped; platform principals cannot use them for business modules (allowlist: `/me`, auth, security enrollment).
5. Customer registration cannot claim slug/id `ribdigi-platform`.
6. **ADR-002** remains: no fake MRR/payments; platform billing cards show deferred until a provider ships.
7. Legacy customer-tenant `super_admin` cross-tenant `/tenants` list/suspend/activate endpoints are **retired** (HTTP 410 → `/api/v1/platform/*`). Tenant self-service remains on `/tenants/me`.
8. Platform settings (`GET/PATCH /api/v1/platform/settings`) cover House idle timeout and support contacts on the reserved tenant row only.

## Consequences

- Platform operators are not tied to a customer tenant lifecycle.
- Frontend redirects platform principals to `/platform/dashboard` and tenant users to `/dashboard`.
- Security tests must prove tenant roles cannot call platform APIs and platform roles cannot read other tenants’ business rows via tenant APIs.
- The reserved platform tenant cannot be suspended or listed as a customer tenant (legacy `/tenants*` and `/platform/*`).
- Platform principals are allowlisted to `/api/v1/platform/*`, `/me`, and auth/security paths only (enforced in `current_claims`).
- Platform staff management lives under `/api/v1/platform/users`; plan_code edits are metadata-only under `/platform/tenants/{id}/plan`.
- Legacy `GET/POST /tenants` cross-tenant lifecycle returns **410** with `migrate_to` pointing at `/api/v1/platform/*`.
- Platform settings are House-scoped only (`/api/v1/platform/settings`).
