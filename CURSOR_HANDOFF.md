# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 330 froze Tenant MVP Offline Materials Pack Remaining-Gate Index Fidelity (ADR-668) — `OFFLINE_MATERIALS_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 190/329/328/FAQ offline POS pointers, explicit Offline-Complete / browser-E2E / attestation / live-training / go-live non-claim (≠ Stage 190 `OFFLINE_MATERIALS_REMAINING_GATE_*`; ≠ Stage 190 P1 `OFFLINE_MATERIALS_PACK_POINTERS_MVP.md`). Offline Complete remains MISSING. Next recommended distinct outline: Tenant MVP Support SLA Boundary Pack Remaining-Gate Index Fidelity (packaged support SLA boundary remaining-gate materials non-claim as live support SLA Completes — use prefixed `SUPPORT_SLA_BOUNDARY_PACK_*` if needed; ≠ Stage 330 Offline materials pack / `SUPPORT_SLA_BOUNDARY_REMAINING_GATE_*` / `SUPPORT_SLA_BOUNDARY_RG_POINTERS_MVP.md`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 331+ after CONTINUE/NEXT. Prior Stage 329 froze Offline Complete Pack Remaining-Gate Index Fidelity (ADR-666).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
