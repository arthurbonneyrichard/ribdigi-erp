# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 232 froze Tenant MVP Accounts Receivable & Payable Accounting Surface Discoverability (ADR-471) — `AR_AP_SURFACE_*` Shell Accounts Receivable / Payable, `/accounting/receivables|payables` routes, Credit titles + Accounting cross-links; Stage 22 Credit remains AR/AP authority (`new_ar_ap_engine_claimed` false). Next recommended distinct outline: Tenant MVP WAL Offsite Remaining-Gate Index Fidelity (packaged Stage 26 W1 / Stage 27 B1 auto-`.ribbak` materials non-claim as live offsite backup Complete — explicit non-claim) — Stage 233+. Do not claim a new AR/AP engine, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
