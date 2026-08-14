# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 344 froze Tenant MVP Weekly POS Ops Review Pack Remaining-Gate Index Fidelity (ADR-696) — `WEEKLY_POS_OPS_REVIEW_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 176/343/342/329 pointers, explicit Offline-Complete / support-SLA / attestation / fabricated-weekly-green / go-live non-claim (≠ Stage 176 `WEEKLY_POS_OPS_REVIEW_MVP.md`; ≠ Stage 343 `WEEKLY_POS_OPS_ADHERENCE_PACK_*`; ≠ Stage 342 `SHIFT_HANDOVER_CHECKLIST_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live weekly POS ops review Complete remains MISSING. Next recommended distinct outline: Tenant MVP Weekly POS Ops Signals Pack Remaining-Gate Index Fidelity (packaged Stage 176 weekly POS ops signals materials non-claim as live weekly POS ops signals Completes — use prefixed `WEEKLY_POS_OPS_SIGNALS_PACK_*` if needed; ≠ Stage 344 weekly POS ops review pack / `WEEKLY_POS_OPS_SIGNALS_MVP.md` / Stage 343 `WEEKLY_POS_OPS_ADHERENCE_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 345+ after CONTINUE/NEXT. Prior Stage 343 froze Weekly POS Ops Adherence Pack Remaining-Gate Index Fidelity (ADR-694). Prior Stage 342 froze Shift Handover Checklist Pack Remaining-Gate Index Fidelity (ADR-692).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
