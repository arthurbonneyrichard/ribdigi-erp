# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 337 froze Tenant MVP FAQ Offline POS Pack Remaining-Gate Index Fidelity (ADR-682) — `FAQ_OFFLINE_POS_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 171/336/335/329 pointers, explicit Offline-Complete / hosted-KB-SaaS / attestation / fabricated-FAQ-SLA / go-live non-claim (≠ Stage 171 `FAQ_OFFLINE_POS_MVP.md`; ≠ Stage 336 `OFFLINE_SYNC_RUNBOOK_PACK_*`; ≠ Stage 335 `OFFLINE_SYNC_ESCALATION_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live FAQ offline POS Complete remains MISSING. Next recommended distinct outline: Tenant MVP Troubleshooting Index Pack Remaining-Gate Index Fidelity (packaged Stage 171 troubleshooting index materials non-claim as live troubleshooting index Completes — use prefixed `TROUBLESHOOTING_INDEX_PACK_*` if needed; ≠ Stage 337 FAQ offline POS pack / `TROUBLESHOOTING_INDEX_MVP.md` / Stage 336 `OFFLINE_SYNC_RUNBOOK_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 338+ after CONTINUE/NEXT. Prior Stage 336 froze Offline Sync Runbook Pack Remaining-Gate Index Fidelity (ADR-680).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
