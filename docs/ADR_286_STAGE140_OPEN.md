# ADR-286: Stage 140 Open — Tenant MVP Storage Settings CSV, Notification Preferences CSV & Backup Settings CSV Export Fidelity

**Status:** Accepted  
**Date:** 2026-08-12  
**Related:** [ADR-285](ADR_285_STAGE139_FREEZE.md), [STAGE_140_PLAN.md](STAGE_140_PLAN.md)

## Context

Stage 139 closed finance ops-list CSVs under ADR-285.
Operators can view **storage backend status**, **notification channel preferences**, and **backup schedule settings**, but cannot export those settings as CSV (named deferred after Stage 139). Inbox/job list CSVs already ship (Stage 129).

## Decision

Open **Stage 140 — Tenant MVP Storage Settings CSV, Notification Preferences CSV & Backup Settings CSV Export Fidelity** with packs:

| Pack | Scope |
|------|--------|
| **S1** | Storage settings CSV: `GET /settings/storage/export` + Company Export storage settings CSV |
| **N1** | Notification preferences CSV: `GET /notifications/settings/export` + Notifications Export preferences CSV |
| **B1** | Backup settings CSV: `GET /backup/settings/export` + Backup Export backup settings CSV |
| **D1 / H140x** | Fidelity cite sync + Stage 140 exit; freeze as **ADR-287** |

## Consequences

- Completes the ops settings CSV trio deferred after Stage 139.
- Does **not** reopen Stages 1–139; does **not** claim ADR-002/005, ADR-003 hard-delete Complete, impersonation, payment allocation dumps, or main `ci.yml` deploy.
- Storage export is secret-free (no S3 access/secret keys); backup export excludes archive bytes/credentials.
