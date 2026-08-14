# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 371 froze Tenant MVP Business Metrics Pack Remaining-Gate Index Fidelity (ADR-750) — `BUSINESS_METRICS_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 370/58/billing-deferred/329 pointers, explicit measured-MRR / paying-customers / NRR·GRR / program-live / go-live non-claim (≠ Stage 370 `PERMISSION_ALIAS_PACK_*`; ≠ Stage 58 `BUSINESS_METRICS_MVP.md`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Authoritative source: `docs/BUSINESS_METRICS_MVP.md`. Measured MRR Completes remain MISSING. Next recommended distinct outline: Tenant MVP Store Membership Pack Remaining-Gate Index Fidelity (ADR-005 user↔store assignment materials non-claim as store membership Completes — use prefixed `STORE_MEMBERSHIP_PACK_*` if needed; ≠ Stage 371 business metrics pack / ADR-005 deferred Completes / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`). Stages 1–371 feature scopes remain frozen under their freeze ADRs. Main `ci.yml` remains deploy-free (Stage 18 C1).

## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
