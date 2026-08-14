# Cursor AI Handoff

Start by reading `README.md`, then `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md` (latest product-update audit), then `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md`, `docs/ARCHITECTURE_DOCUMENTS.md`, `docs/DATABASE_DOCUMENTATION.md`, `docs/API_DOCUMENTATION.md`, `docs/SECURITY_GUIDE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

Do **not** restart the project. Preserve working engines. Stage 368 froze Tenant MVP Sync Idempotency Replay Pack Remaining-Gate Index Fidelity (ADR-744) — `SYNC_IDEMPOTENCY_REPLAY_PACK_*` remaining-gate hub (`_REMAINING_GATE` / `_RG_*`), blocker matrix, Stage 367/164/329/CHANGE_IMPACT pointers, explicit Offline-Complete / sync-hardening / duplicate-sale-on-replay / go-live / attestation non-claim (≠ Stage 367 `MVP_PRODUCT_UPDATE_PACK_*`; ≠ Stage 164 Completes; ≠ skipped `CONNECTIVITY_SYNC_STATUS_PACK_*`; ≠ Stage 329 `OFFLINE_COMPLETE_PACK_*`). Authoritative audit: `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md` P1. Offline Complete remains MISSING. Next recommended distinct outline: Tenant MVP Sync Conflict UX Pack Remaining-Gate Index Fidelity (manager conflict review / reconciliation chrome non-claim as Offline Complete — use prefixed `SYNC_CONFLICT_UX_PACK_*` if needed; ≠ Stage 368 sync idempotency replay pack / Stage 164 conflicts / Stage 329 `OFFLINE_COMPLETE_PACK_*`; do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`). Stages 1–368 feature scopes remain frozen under their freeze ADRs. Main `ci.yml` remains deploy-free (Stage 18 C1).

## COMMERCIAL PRODUCT / NO-DEMO RULE

RIBDIGI ERP is being developed as a market product, not a demo. Do not introduce or preserve demo tenants, fake production data, prefilled passwords, mocked success responses, placeholder business logic, or UI that pretends an unfinished feature works. Local development fixtures are allowed only when explicitly marked local/test-only and technically blocked from production.

Before declaring any module complete, compare it against `PRODUCTION_READINESS.md` and the authoritative `/docs` acceptance criteria. Report gaps as COMPLETE / PARTIAL / MISSING / BROKEN. Never change a status to COMPLETE merely because a page or endpoint exists.
