# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 271 froze Tenant MVP Billing Deferred Pack Remaining-Gate Index Fidelity (ADR-550) — `BILLING_DEFERRED_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, ADR-002/36/270/269/266 pointers, explicit billing-complete / payment-provider / checkout-success / go-live non-claim (≠ Stage 36 B1 / ADR-002 decision text; ADR-002 in force). Paid billing Complete and payment provider Complete remain MISSING. Next recommended distinct outline: Tenant MVP Subscription Renewal Pack Remaining-Gate Index Fidelity (packaged Stage 52 R1 subscription-renewal materials non-claim as paid billing / live subscriptions Completes — use prefixed `SUBSCRIPTION_RENEWAL_PACK_*` if needed; ≠ Stage 271 billing deferred / Stage 52 R1 packaging) — Stage 272+. Do not claim live incident drill, live support SLA, hosted PagerDuty, live go-live evidence, certified 1000-VU, live offsite backup, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
