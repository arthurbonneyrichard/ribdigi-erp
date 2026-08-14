# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 273 froze Tenant MVP Store Membership Pack Remaining-Gate Index Fidelity (ADR-554) — `STORE_MEMBERSHIP_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, ADR-005/272/271/182 pointers, explicit store-membership-live / users-store-id / billing-complete / go-live non-claim (≠ ADR-005 / Stage 182 `MEMBERSHIP_*`; ADR-005 in force). Live store-membership Complete and `users.store_id` Complete remain MISSING. Next recommended distinct outline: Tenant MVP Language I18n Pack Remaining-Gate Index Fidelity (packaged ADR-006 language/i18n materials non-claim as full locale Completes — use prefixed `LANGUAGE_I18N_PACK_*` if needed; ≠ Stage 273 store membership / ADR-006 decision text) — Stage 274+. Do not claim live incident drill, live support SLA, hosted PagerDuty, live go-live evidence, certified 1000-VU, live offsite backup, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
