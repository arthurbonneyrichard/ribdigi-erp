# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 328 froze Tenant MVP Loadtest Baseline Pack Remaining-Gate Index Fidelity (ADR-664) — `LOADTEST_BASELINE_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 225/327/326/5 pointers, explicit certified-load / live-load-capacity / operator-1000VU / load-cert / go-live non-claim (≠ Stage 225 `LOADTEST_BASELINE_REMAINING_GATE_*`; ≠ `LOADTEST_BASELINE_RG_POINTERS_MVP.md`; ≠ Stage 234 `LOAD_CAPACITY_PACK_*`). Certified load Complete remains MISSING. Next recommended distinct outline: Tenant MVP Offline Complete Pack Remaining-Gate Index Fidelity (packaged Offline Complete remaining-gate materials non-claim as live Offline Completes — use prefixed `OFFLINE_COMPLETE_PACK_*` if needed; ≠ Stage 328 loadtest baseline pack / `OFFLINE_COMPLETE_REMAINING_GATE_*` / `OFFLINE_COMPLETE_PACK_POINTERS_MVP.md`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 329+ after CONTINUE/NEXT. Prior Stage 327 froze Ops Monitoring Pack Remaining-Gate Index Fidelity (ADR-662).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
