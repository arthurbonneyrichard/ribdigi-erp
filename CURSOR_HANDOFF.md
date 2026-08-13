# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 185 froze Tenant MVP Schema-Per-Tenant Remaining-Gate Index Fidelity (ADR-377) — schema-per-tenant remaining-gate hub, blocker matrix, ADR-001/deferred ADR/readiness pointers, explicit schema-per-tenant non-claim. Schema-per-tenant / database-per-tenant Completes remain MISSING. Next recommended distinct outline: Tenant MVP audit-retention remaining-gate index fidelity (ADR-007 / hot-table pruning blockers — MVP cold-archive Completes non-claim as infinite retention / purge Complete — explicit non-claim) — Stage 186+. Do not claim schema-per-tenant Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
