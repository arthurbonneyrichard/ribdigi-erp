# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 341 froze Tenant MVP Store Close Checklist Pack Remaining-Gate Index Fidelity (ADR-690) — `STORE_CLOSE_CHECKLIST_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 174/340/339/329 pointers, explicit Offline-Complete / live-DR / attestation / fabricated-store-closed-green / go-live non-claim (≠ Stage 174 `STORE_CLOSE_CHECKLIST_MVP.md`; ≠ Stage 340 `STORE_OPEN_CHECKLIST_PACK_*`; ≠ Stage 339 `CASHIER_QUICKSTART_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Live store close checklist Complete remains MISSING. Next recommended distinct outline: Tenant MVP Shift Handover Checklist Pack Remaining-Gate Index Fidelity (packaged Stage 175 shift handover checklist materials non-claim as live shift handover checklist Completes — use prefixed `SHIFT_HANDOVER_CHECKLIST_PACK_*` if needed; ≠ Stage 341 store close checklist pack / `SHIFT_HANDOVER_CHECKLIST_MVP.md` / Stage 340 `STORE_OPEN_CHECKLIST_PACK_*` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 342+ after CONTINUE/NEXT. Prior Stage 340 froze Store Open Checklist Pack Remaining-Gate Index Fidelity (ADR-688).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
