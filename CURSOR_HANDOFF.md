# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 172 froze Cashier Quickstart Fidelity (ADR-351) — day-one bind/catalog, Hold/flush/accept-client. Offline Complete / live training / go-live remain MISSING. Next recommended distinct outline: Tenant MVP store-open checklist fidelity (store select, low-stock glance, Hold expiry, offline device health, sync conflict queue) — Stage 173+. Do not claim Offline Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
