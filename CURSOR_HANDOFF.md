# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 336 froze Tenant MVP Offline Sync Runbook Pack Remaining-Gate Index Fidelity (ADR-680) — `OFFLINE_SYNC_RUNBOOK_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 169/335/334/329 pointers, explicit Offline-Complete / attestation / browser-E2E / fabricated-sync / go-live non-claim (≠ Stage 169 `OFFLINE_SYNC_RUNBOOK_MVP.md`; ≠ Stage 335 `OFFLINE_SYNC_ESCALATION_PACK_*`; ≠ Stage 334 `INCIDENT_SEVERITY_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live offline sync runbook Complete remains MISSING. Next recommended distinct outline: Tenant MVP FAQ Offline POS Pack Remaining-Gate Index Fidelity (packaged Stage 171 FAQ offline POS materials non-claim as live FAQ offline POS Completes — use prefixed `FAQ_OFFLINE_POS_PACK_*` if needed; ≠ Stage 336 offline sync runbook pack / `FAQ_OFFLINE_POS_MVP.md` / Stage 335 `OFFLINE_SYNC_ESCALATION_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 337+ after CONTINUE/NEXT. Prior Stage 335 froze Offline Sync Escalation Pack Remaining-Gate Index Fidelity (ADR-678).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
