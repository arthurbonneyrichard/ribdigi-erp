# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 353 froze Tenant MVP Store Close Drain Pack Remaining-Gate Index Fidelity (ADR-714) — `STORE_CLOSE_DRAIN_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 174/352/341/329 pointers, explicit Offline-Complete / support-SLA / attestation / empty-queue / go-live non-claim (≠ Stage 174 `STORE_CLOSE_DRAIN_MVP.md`; ≠ Stage 352 `MIGRATION_GATE_PACK_*`; ≠ Stage 341 `STORE_CLOSE_CHECKLIST_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live store-close drain Complete remains MISSING. Next recommended distinct outline: Tenant MVP Store Open Health Pack Remaining-Gate Index Fidelity (packaged `STORE_OPEN_HEALTH_MVP.md` materials non-claim as live store-open health Completes — use prefixed `STORE_OPEN_HEALTH_PACK_*` if needed; ≠ Stage 353 store close drain pack / `STORE_OPEN_HEALTH_MVP.md` / Stage 340 `STORE_OPEN_CHECKLIST_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 354+ after CONTINUE/NEXT. Prior Stage 352 froze Migration Gate Pack Remaining-Gate Index Fidelity (ADR-712). Prior Stage 351 froze Quarterly POS Ops Gates Pack Remaining-Gate Index Fidelity (ADR-710).











## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
