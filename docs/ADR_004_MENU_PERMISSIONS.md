# ADR-004: Menu Permissions Equal Module Permissions

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-3.3 requires three permission layers: module, menu/submenu, and record scope. The Shell already filters navigation items by the user's **module** permissions (`read` / `write` / `*`). A parallel menu-permission matrix would duplicate RBAC, drift from API gates, and add Stage 1 complexity without new security.

## Decision

For Stage 1 / Commercial MVP:

1. **Menu visibility = module permission.** A nav item with module key `M` is shown when the user has `M:read`, `M:write`, or `M:*` (or global `*:*`).
2. **No separate menu/submenu permission store** or UI matrix in Stage 1.
3. API authorization continues to use `require_permission(module, action)` independently of the Shell.
4. Record scope (own / department / branch / all) remains the third BR-3.3 dimension and is unchanged.
5. Fine-grained submenu flags (hide a tab inside a module while keeping module access) are **post-MVP** if product needs them.

## Consequences

- One permission source of truth for nav and APIs.
- BR-3.3 “Menu Permissions” is satisfied for Stage 1 as *module-gated menus* (this ADR).
- Custom roles edited on Users page continue to drive both API access and Shell menus.
