# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 327 froze Tenant MVP Ops Monitoring Pack Remaining-Gate Index Fidelity (ADR-662) — `OPS_MONITORING_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 221/326/325/26 pointers, explicit live-ops-monitoring / live-monitoring / hosted-Grafana / paging / go-live non-claim (≠ Stage 221 `OPS_MONITORING_REMAINING_GATE_*`; ≠ `OPS_MONITORING_RG_POINTERS_MVP.md`; ≠ Stage 26 M1 `OPS_MONITORING_MVP.md`). Live ops monitoring Complete remains MISSING. Next recommended distinct outline: Tenant MVP Loadtest Baseline Pack Remaining-Gate Index Fidelity (packaged Stage 225 loadtest baseline materials non-claim as live certified load Completes — use prefixed `LOADTEST_BASELINE_PACK_*` if needed; ≠ Stage 327 ops monitoring pack / `LOADTEST_BASELINE_REMAINING_GATE_*` / `LOADTEST_BASELINE_RG_POINTERS_MVP.md`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 328+ after CONTINUE/NEXT. Prior Stage 326 froze Hosted FAQ SaaS Pack Remaining-Gate Index Fidelity (ADR-660).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
