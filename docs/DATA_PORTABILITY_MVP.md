# Data Portability MVP — Data Subject Access / Portability Honesty Packaging

**Status:** Complete (MVP) — Stage 37 P1  
**Evidence:** `backend/tests/test_data_portability_p1.py` · `/opt/cursor/artifacts/launch/stage37_p1_data_portability.json`  
**Register:** `ops/mvp/data-portability.json`  
**Related:** [DR_LOGICAL_BACKUP_RUNBOOK.md](DR_LOGICAL_BACKUP_RUNBOOK.md) · [COMPLIANCE_QUESTIONNAIRE_MVP.md](COMPLIANCE_QUESTIONNAIRE_MVP.md) · [COMPLIANCE_READINESS_MVP.md](COMPLIANCE_READINESS_MVP.md) · [SECURITY_GUIDE.md](SECURITY_GUIDE.md) · [STAGE_37_PLAN.md](STAGE_37_PLAN.md) · [ADR_079_STAGE37_OPEN.md](ADR_079_STAGE37_OPEN.md)

This is the **MVP data subject access / portability packaging surface**: a customer/procurement-facing honesty boundary consolidating existing tenant-scoped export and backup surfaces (logical `.ribbak` download, report CSV/PDF/XLSX export, audit-log export) against BRD GDPR-ready portability themes. It extends Stage 18 backup / Stage 22–23 report export / Stage 33–34 compliance privacy themes — it does **not** claim GDPR certification Complete, a live DSAR portal Complete, consent-management SaaS Complete, or that an automated subject-request workflow already runs in production.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Portability step indexed to Complete (MVP) product / packaging surfaces |
| `remaining` | Live DSAR portal / GDPR certification / automated workflow still required |

Every step keeps `done: false`. Top-level `gdpr_complete_claimed: false` / `dsar_portal_claimed: false` / `live_portability_workflow_claimed: false` / `consent_management_claimed: false`.

## Register scope

1. Tenant-scoped logical backup download (`.ribbak`) access path.
2. Report export surfaces (`GET /reports/export` CSV/PDF/XLSX).
3. Audit log export (`GET /audit-logs/export`).
4. Catalog / list packaging honesty (CSV import Complete; dedicated catalog CSV export deferred).
5. Tenant isolation on backup download / export paths.
6. Compliance questionnaire privacy / GDPR theme linkage.
7. SECURITY_GUIDE GDPR / data-protection theme linkage.
8. BRD GDPR-ready portability theme honesty (packaging ≠ certification).
9. Live DSAR portal Remaining.
10. GDPR / privacy certification Remaining.

## Automation hooks

1. Maintain `ops/mvp/data-portability.json` (synced by `test_data_portability_p1.py`).
2. Align honesty with Stage 33–34 compliance privacy themes and Stage 18 backup export surfaces.
3. CI proves packaging honesty only — never forges GDPR certification or live DSAR Complete.

## Explicitly not claimed

- GDPR / privacy regulation certification Complete because Stage 37 P1 packaging exists
- Live DSAR portal / automated subject-request workflow Complete
- Consent-management SaaS Complete
- Hard-delete archival / erasure Complete (Stage 37 E1 / ADR-003 Remaining)
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 18–34 backup/export/compliance packs as new runtime Complete

## Sign-off

Stage 37 P1 is met when this doc + register JSON + evidence JSON exist, `test_data_portability_p1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 37 P1 without inventing GDPR or live DSAR Complete.
