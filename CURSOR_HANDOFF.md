# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 270 froze Tenant MVP Shared-Schema Tenancy Pack Remaining-Gate Index Fidelity (ADR-548) — `SHARED_SCHEMA_TENANCY_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, ADR-001/269/268/185 pointers, explicit billing-complete / schema-per-tenant / live-multitenant / go-live non-claim (≠ ADR-001 / Stage 185 `SCHEMA_PER_TENANT_*`; ADR-002 in force). Paid billing Complete and schema-per-tenant Complete remain MISSING. Next recommended distinct outline: Tenant MVP Billing Deferred Pack Remaining-Gate Index Fidelity (packaged ADR-002 / Stage 36 billing-deferred honesty materials non-claim as paid billing / payment-provider Completes — use prefixed `BILLING_DEFERRED_PACK_*` if needed; ≠ Stage 270 tenancy / Stage 36 B1 packaging) — Stage 271+. Do not claim live incident drill, live support SLA, hosted PagerDuty, live go-live evidence, certified 1000-VU, live offsite backup, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
