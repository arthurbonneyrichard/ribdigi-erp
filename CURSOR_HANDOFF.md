# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 332 froze Tenant MVP Support SLA Pack Remaining-Gate Index Fidelity (ADR-672) — `SUPPORT_SLA_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 188/331/330/36 pointers, explicit support-SLA / PagerDuty-hosted / on-call-rota / incident-drill / go-live non-claim (≠ Stage 188 `SUPPORT_SLA_REMAINING_GATE_*`; ≠ Stage 188 P1 `SUPPORT_SLA_PACK_POINTERS_MVP.md`; ≠ Stage 331 `SUPPORT_SLA_BOUNDARY_PACK_*`). Live support-SLA Complete remains MISSING. Next recommended distinct outline: Tenant MVP Support Readiness Pack Remaining-Gate Index Fidelity (packaged Stage 170 support readiness materials non-claim as live support readiness Completes — use prefixed `SUPPORT_READINESS_PACK_*` if needed; ≠ Stage 332 support SLA pack / `SUPPORT_READINESS_MVP.md` / Stage 331 `SUPPORT_SLA_BOUNDARY_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`) — Stage 333+ after CONTINUE/NEXT. Prior Stage 331 froze Support SLA Boundary Pack Remaining-Gate Index Fidelity (ADR-670).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
