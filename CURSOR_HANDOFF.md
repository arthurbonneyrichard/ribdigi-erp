# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 358 froze Tenant MVP Cashier POS Dayone Pack Remaining-Gate Index Fidelity (ADR-724) — `CASHIER_POS_DAYONE_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 172/357/339/329 pointers, explicit Offline-Complete / support-SLA / attestation / fabricated-conflict-free / go-live non-claim (≠ Stage 172 `CASHIER_POS_DAYONE_MVP.md`; ≠ Stage 357 `CASHIER_BIND_CATALOG_PACK_*`; ≠ Stage 339 `CASHIER_QUICKSTART_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live cashier POS day-one Complete remains MISSING. Next recommended distinct outline: Tenant MVP Shift Handover Snapshot Pack Remaining-Gate Index Fidelity (packaged `SHIFT_HANDOVER_SNAPSHOT_MVP.md` materials non-claim as live shift handover snapshot Completes — use prefixed `SHIFT_HANDOVER_SNAPSHOT_PACK_*` if needed; ≠ Stage 358 cashier POS dayone pack / `SHIFT_HANDOVER_SNAPSHOT_MVP.md` / Stage 342 `SHIFT_HANDOVER_CHECKLIST_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 359+ after CONTINUE/NEXT. Prior Stage 357 froze Cashier Bind Catalog Pack Remaining-Gate Index Fidelity (ADR-722). Prior Stage 356 froze Store Open Lowstock Pack Remaining-Gate Index Fidelity (ADR-720).


























## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
