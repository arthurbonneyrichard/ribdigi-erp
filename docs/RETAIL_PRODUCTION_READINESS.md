# Retail production readiness

**Date:** 30 October 2026 UTC. Supersedes the 17 October gate table.

**Verdict: Ready to sell to retailers. Verified by evidence, not certified.** Two owner actions remain before anyone may call it certified (external penetration test, production restore drill).

Feature audit Status rows: **64 / 64 complete** (API/source proof).

| Gate | Status | Evidence |
| --- | --- | --- |
| Feature audit matrix | complete | `RETAIL_COMPLETE_FEATURE_AUDIT.md` |
| Full backend suite | pass | CI on `52e232ef67`, fully green (29 Oct run on `15fe81aba9`: 3283 passed, 1 skipped) |
| Frontend production build | pass | CI frontend job green on `52e232ef67` |
| Signed-in browser walkthroughs | pass | 51 owner how-to guides recorded on the live interface (`demo-mart-rec`) |
| Migrations on production | pass | Production deployed at `52e232ef67` on 30 Oct; health and auth checks OK |
| Restore drill (local copy) | pass | Row counts matched, 0 orphan rows, 0 rows crossing companies (29 Oct) |
| Live security headers | pass | HSTS, nosniff, Referrer-Policy, Permissions-Policy, X-Frame-Options, CSP baseline; no Server header; `/_next/image` 404; metrics need `METRICS_TOKEN` |
| Restore drill on production (RPO/RTO) | owner | Not done |
| External penetration test | owner | Not done |

| Area | Feature Status |
| --- | --- |
| Retail ERP API rules | complete |
| POS / Offline supported scope | complete |
| Purchasing / GRN | complete |
| Inventory / Sales / Finance / Reports | complete |
| Security / Isolation / AI fail-closed | complete |
| Production deployment | live |

## Known limits to tell customers

- Card, Mobile Money and bank tenders are recorded, not charged through a gateway.
- Offline till works for the supported scope; `offline_complete_claimed` stays false.
- AI chat stays off (503) until a provider and key are approved; rule-based insights work without it.

## Security items still open (not blockers for retail sales)

From `SECURITY_AUDIT_2026-10-29.md`: O1 Next 16 upgrade (own tested release), O2 dedicated encryption key with re-encryption migration, O3 switch the full CSP from report-only to enforcing, O9 pentest and production restore drill.
