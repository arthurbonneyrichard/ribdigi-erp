# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 349 froze Tenant MVP Quarterly POS Ops Review Pack Remaining-Gate Index Fidelity (ADR-706) — `QUARTERLY_POS_OPS_REVIEW_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 178/348/347/329 pointers, explicit Offline-Complete / support-SLA / attestation / live-migration / go-live non-claim (≠ Stage 178 `QUARTERLY_POS_OPS_REVIEW_MVP.md`; ≠ Stage 348 `MONTHLY_POS_OPS_POINTERS_PACK_*`; ≠ Stage 347 `MONTHLY_POS_OPS_TRENDS_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live quarterly POS ops review Complete remains MISSING. Next recommended distinct outline: Tenant MVP Quarterly POS Ops Rollup Pack Remaining-Gate Index Fidelity (packaged Stage 178 quarterly POS ops rollup materials non-claim as live quarterly POS ops rollup Completes — use prefixed `QUARTERLY_POS_OPS_ROLLUP_PACK_*` if needed; ≠ Stage 349 quarterly POS ops review pack / `QUARTERLY_POS_OPS_ROLLUP_MVP.md` / Stage 348 `MONTHLY_POS_OPS_POINTERS_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 350+ after CONTINUE/NEXT. Prior Stage 348 froze Monthly POS Ops Pointers Pack Remaining-Gate Index Fidelity (ADR-704). Prior Stage 347 froze Monthly POS Ops Trends Pack Remaining-Gate Index Fidelity (ADR-702).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
