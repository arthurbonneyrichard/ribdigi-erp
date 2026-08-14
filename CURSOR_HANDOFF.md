# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 278 froze Tenant MVP Data Portability Pack Remaining-Gate Index Fidelity (ADR-564) — `DATA_PORTABILITY_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 37/277/276/37E1 pointers, explicit gdpr-complete / dsar-portal / billing-complete / go-live non-claim (≠ Stage 37 P1 `DATA_PORTABILITY_MVP.md`). GDPR Complete and live DSAR portal Complete remain MISSING. Next recommended distinct outline: Tenant MVP Compliance Questionnaire Pack Remaining-Gate Index Fidelity (packaged Stage 33–34 / Stage 37 compliance questionnaire materials non-claim as live compliance / certification Completes — use prefixed `COMPLIANCE_QUESTIONNAIRE_PACK_*` if needed; ≠ Stage 278 data portability / Stage 33–34 packaging) — Stage 279+. Do not claim live incident drill, live support SLA, hosted PagerDuty, live go-live evidence, certified 1000-VU, live offsite backup, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
