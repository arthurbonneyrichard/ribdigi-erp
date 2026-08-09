# ADR-007: Audit Log Retention and Cold Archive

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-17.2 requires:

- Tamper-proof append-only audit storage (already hash-chained)
- Retention of at least **7 years** for financial/audit records
- Cold storage archive for long-term retention

Deleting hot audit rows would break the integrity chain and violate commercial MVP honesty if presented as “archived” without a real copy.

## Decision

For Stage 1 / Commercial MVP:

1. **Retention minimum is 7 years** (`AUDIT_RETENTION_YEARS`, never below 7).
2. **No purge API** — `DELETE`/`PATCH` on audit logs remain blocked (`reject_mutation`).
3. **Cold archive** copies aged rows (default older than `AUDIT_COLD_ARCHIVE_AFTER_DAYS`, 365) to tenant-scoped object storage as checksummed JSONL (`{tenant}/audit-cold/...jsonl`).
4. Archived rows receive `archived_at` but **remain queryable** in the hot table; the hash chain stays intact.
5. Manifest rows are stored in `audit_cold_archives` (key, sha256, counts, range).
6. Operators trigger archive via `POST /audit-logs/archive-cold` or Celery `archive_cold_audit_logs`.
7. Physical deletion of hot rows (even after 7 years) is **out of Stage 1**.

## Consequences

- BR-17.2 retention is COMPLETE for MVP policy + cold copy; long-term hot-table pruning remains post-MVP.
- Storage growth is expected; cold copies use the same `STORAGE_BACKEND` as media (local or S3).
- HTTP mutation middleware (ADR companion G19) continues to append to the same chain.
