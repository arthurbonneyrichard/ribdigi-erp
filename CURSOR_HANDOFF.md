# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 261 froze Tenant MVP Preflight Verification Pack Remaining-Gate Index Fidelity (ADR-530) — `PREFLIGHT_VERIFICATION_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 69/260/259/201 pointers, explicit sections-1-3 / preflight-verified / go-live / attestation non-claim (≠ Stage 69 V1 / Stage 201 `PREFLIGHT_VERIFICATION_*`). §§1–3 verified Complete and go-live Complete remain MISSING. Next recommended distinct outline: Tenant MVP Production Launch Pack Remaining-Gate Index Fidelity (packaged Stage 66 L1 production-launch materials non-claim as live cutover / go-live Complete — use prefixed `PRODUCTION_LAUNCH_PACK_*` if needed; ≠ Stage 202 `PRODUCTION_LAUNCH_*`) — Stage 262+. Do not claim live incident drill, live support SLA, hosted PagerDuty, live go-live evidence, certified 1000-VU, live offsite backup, live PITR drill, production sign-off, or CI replay certificate Complete. Do not weaken tenant isolation, RBAC, audit logging, or financial double-entry requirements. Do not fabricate MRR/billing Completes (ADR-002).


## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
