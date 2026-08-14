# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 329 froze Tenant MVP Offline Complete Pack Remaining-Gate Index Fidelity (ADR-666) — `OFFLINE_COMPLETE_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 179/328/327/190 pointers, explicit Offline-Complete / browser-E2E / attestation / product-acceptance / go-live non-claim (≠ Stage 179 `OFFLINE_COMPLETE_REMAINING_GATE_*`; ≠ Stage 179 P1 `OFFLINE_COMPLETE_PACK_POINTERS_MVP.md`). Offline Complete remains MISSING. Next recommended distinct outline: Tenant MVP Offline Materials Pack Remaining-Gate Index Fidelity (packaged Stage 190 Offline materials remaining-gate materials non-claim as live Offline Completes — use prefixed `OFFLINE_MATERIALS_PACK_*` if needed; ≠ Stage 329 Offline Complete pack / `OFFLINE_MATERIALS_REMAINING_GATE_*` / `OFFLINE_MATERIALS_PACK_POINTERS_MVP.md`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 330+ after CONTINUE/NEXT. Prior Stage 328 froze Loadtest Baseline Pack Remaining-Gate Index Fidelity (ADR-664).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
