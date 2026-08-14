# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 355 froze Tenant MVP Store Close Triage Pack Remaining-Gate Index Fidelity (ADR-718) — `STORE_CLOSE_TRIAGE_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 174/354/353/329 pointers, explicit Offline-Complete / live-DR / attestation / fabricated-conflict-free / go-live non-claim (≠ Stage 174 `STORE_CLOSE_TRIAGE_MVP.md`; ≠ Stage 354 `STORE_OPEN_HEALTH_PACK_*`; ≠ Stage 353 `STORE_CLOSE_DRAIN_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live store-close triage Complete remains MISSING. Next recommended distinct outline: Tenant MVP Store Open Lowstock Pack Remaining-Gate Index Fidelity (packaged `STORE_OPEN_LOWSTOCK_MVP.md` materials non-claim as live store-open lowstock Completes — use prefixed `STORE_OPEN_LOWSTOCK_PACK_*` if needed; ≠ Stage 355 store close triage pack / `STORE_OPEN_LOWSTOCK_MVP.md` / Stage 354 `STORE_OPEN_HEALTH_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 356+ after CONTINUE/NEXT. Prior Stage 354 froze Store Open Health Pack Remaining-Gate Index Fidelity (ADR-716). Prior Stage 353 froze Store Close Drain Pack Remaining-Gate Index Fidelity (ADR-714).

















## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
