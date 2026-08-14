# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 370 froze Tenant MVP Permission Alias Pack Remaining-Gate Index Fidelity (ADR-748) — `PERMISSION_ALIAS_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 369/ADR-004/275/329 pointers, explicit permission-rename / products-stock alias-map / Offline-Complete / go-live / attestation non-claim (≠ Stage 369 `SYNC_CONFLICT_UX_PACK_*`; ≠ ADR-004 Completes; ≠ Stage 275 `MENU_PERMISSIONS_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Authoritative audit: `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md` P2. Permission-rename Completes remain MISSING. Next recommended distinct outline: Tenant MVP Business Metrics Pack Remaining-Gate Index Fidelity (packaged `BUSINESS_METRICS_MVP.md` materials non-claim as live business-metrics Completes — use prefixed `BUSINESS_METRICS_PACK_*` if needed; ≠ Stage 370 permission alias pack / `BUSINESS_METRICS_MVP.md` / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`). Stages 1–370 feature scopes remain frozen under their freeze ADRs. Main `ci.yml` remains deploy-free (Stage 18 C1).

## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
