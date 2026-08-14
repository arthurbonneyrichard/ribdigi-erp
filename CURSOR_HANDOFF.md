# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 347 froze Tenant MVP Monthly POS Ops Trends Pack Remaining-Gate Index Fidelity (ADR-702) — `MONTHLY_POS_OPS_TRENDS_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 177/346/345/329 pointers, explicit Offline-Complete / Hold-SLA / attestation / fabricated-trend-dashboard / go-live non-claim (≠ Stage 177 `MONTHLY_POS_OPS_TRENDS_MVP.md`; ≠ Stage 346 `MONTHLY_POS_OPS_REVIEW_PACK_*`; ≠ Stage 345 `WEEKLY_POS_OPS_SIGNALS_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live monthly POS ops trends Complete remains MISSING. Next recommended distinct outline: Tenant MVP Monthly POS Ops Pointers Pack Remaining-Gate Index Fidelity (packaged Stage 177 monthly POS ops pointers materials non-claim as live monthly POS ops pointers Completes — use prefixed `MONTHLY_POS_OPS_POINTERS_PACK_*` if needed; ≠ Stage 347 monthly POS ops trends pack / `MONTHLY_POS_OPS_POINTERS_MVP.md` / Stage 346 `MONTHLY_POS_OPS_REVIEW_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 348+ after CONTINUE/NEXT. Prior Stage 346 froze Monthly POS Ops Review Pack Remaining-Gate Index Fidelity (ADR-700). Prior Stage 345 froze Weekly POS Ops Signals Pack Remaining-Gate Index Fidelity (ADR-698).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
