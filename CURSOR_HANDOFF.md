# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 356 froze Tenant MVP Store Open Lowstock Pack Remaining-Gate Index Fidelity (ADR-720) — `STORE_OPEN_LOWSTOCK_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 173/355/354/329 pointers, explicit Offline-Complete / attestation / auto-PO / authoritative-offline-stock / go-live non-claim (≠ Stage 173 `STORE_OPEN_LOWSTOCK_MVP.md`; ≠ Stage 355 `STORE_CLOSE_TRIAGE_PACK_*`; ≠ Stage 354 `STORE_OPEN_HEALTH_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live store-open lowstock Complete remains MISSING. Next recommended distinct outline: Tenant MVP Cashier Bind Catalog Pack Remaining-Gate Index Fidelity (packaged `CASHIER_BIND_CATALOG_MVP.md` materials non-claim as live cashier bind catalog Completes — use prefixed `CASHIER_BIND_CATALOG_PACK_*` if needed; ≠ Stage 356 store open lowstock pack / `CASHIER_BIND_CATALOG_MVP.md` / Stage 354 `STORE_OPEN_HEALTH_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 357+ after CONTINUE/NEXT. Prior Stage 355 froze Store Close Triage Pack Remaining-Gate Index Fidelity (ADR-718). Prior Stage 354 froze Store Open Health Pack Remaining-Gate Index Fidelity (ADR-716).




















## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
