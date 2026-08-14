# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 324 froze Tenant MVP Customer Assurance Pack Remaining-Gate Index Fidelity (ADR-656) — `CUSTOMER_ASSURANCE_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 195/323/322/196 pointers, explicit customer-assurance / assurance / evidence-chain-live / residual-risks-closed / go-live non-claim (≠ Stage 195 `CUSTOMER_ASSURANCE_REMAINING_GATE_*`; ≠ Stage 297 `COMMERCIAL_ASSURANCE_PACK_*`; ≠ `ASSURANCE_EVIDENCE_PACK_*`). Customer assurance Complete and assurance Complete remain MISSING. Next recommended distinct outline: Tenant MVP GoLive Pack Remaining-Gate Index Fidelity (packaged go-live remaining-gate materials non-claim as live go-live Completes — use prefixed `GOLIVE_PACK_*` if needed; ≠ Stage 324 customer assurance pack / `GOLIVE_REMAINING_GATE_*` / `COMMERCIAL_GOLIVE_CLOSEOUT_PACK_*` / `FIRST_TENANT_GOLIVE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*`) — Stage 325+ after CONTINUE/NEXT. Prior Stage 323 froze First Tenant Live Onboarding Pack Remaining-Gate Index Fidelity (ADR-654).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
