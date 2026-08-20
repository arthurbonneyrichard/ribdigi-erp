# ADR-002: Local / Offline Synchronization (alongside the ERP)

**Status:** Proposed  
**Date:** 2026-08-20

## Context

Retail, mart, pharmacy, and restaurant POS terminals need to keep selling when the cloud API is unreachable. No IndexedDB, service worker, or sync queue exists in this repository today. Completing core ERP workflows (stock, purchasing, accounting, launch gates) must not wait on a full offline client.

## Decision

Treat **offline sync as a parallel subsystem**, not a rewrite of posting rules:

1. **Cloud remains the system of record.** Inventory, AR/AP, tax, and journals post only on the FastAPI + PostgreSQL path already used by the ERP.
2. **The first offline client is POS-scoped.** Catalog snapshot + queued sales/payments. Do not replicate the full ERP schema to the browser.
3. **Sync is append-only and idempotent.** Each offline document has a client-generated UUID. The server rejects duplicates via `external_ref` / unique `(tenant_id, client_id)`.
4. **Conflicts never silently overwrite stock or money.** Out-of-stock or credit-limit failures return a sync error for the cashier to resolve; they do not invent negative stock.
5. **New tables (when implemented) live beside existing ones:** `offline_devices`, `offline_sync_batches`, `offline_client_ops` with `tenant_id`. No change to current `stock_movements` / journal posting functions except an optional `external_ref` argument.
6. **Do not block Phase 2–5 ERP work** on this subsystem. This ADR is the contract so a later agent can implement it without forking inventory or accounting.

## Out of scope for this ADR

- Shipping a PWA or IndexedDB implementation now
- Multi-master warehouse replication
- Offline purchasing, payroll, or bank reconciliation

## Consequences

- POS can later work locally without changing today’s checkout API contract much (add idempotency keys).
- Core ERP completion stays on the current architecture.
- A future migration will add the sync tables; until then the product is **online-only**.
