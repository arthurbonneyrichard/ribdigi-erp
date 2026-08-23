# RIBDIGI ERP — Commercial Readiness Report (2026-08-23)

**Mode:** Audit synthesis + first code hardening pass. **Packaging ≠ product Completes.**

**Authoritative audit spines:** `PRODUCTION_READINESS.md`, `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md`, `docs/LAUNCH_CHECKLIST.md` + `ops/launch/checklist-map.json`.

---

## Verdict summary (Section 60)

| Area | Status |
|------|--------|
| Architecture (shared-schema tenancy) | **PASS** (runtime) — doc drift **NEEDS HARDENING** |
| Tenant isolation | **PASS** (MVP automated tests) |
| Multi-company | **PARTIAL** |
| Company entitlement | **PARTIAL** (`max_companies` enforced; not plan-synced) |
| Store entitlement | **COMPLETE** (MVP) |
| User ↔ Store assignment | **MISSING** (ADR-005 POST-MVP) |
| RBAC / store scope | **PARTIAL** — **NEEDS HARDENING** |
| Inventory / Purchasing / Sales / Accounting / Tax / Credit | **PASS** (MVP gates in `PRODUCTION_READINESS.md`) |
| POS (online) | **PASS** (MVP) |
| Offline foundation | **PARTIAL** — queue/catalog/sync MVP; no 7-day envelope |
| 7-Day offline | **MISSING** / **NOT RUN** (physical) |
| Offline recovery / lockdown / owner dashboard | **MISSING** |
| Paid billing | **DEFERRED** (ADR-002) |
| Backup (logical) | **PASS** (MVP tests) |
| Restore / PITR / load / pen test (live) | **NOT RUN** (operator/external) |
| Production deployment | **NOT READY** (cutover not executed) |
| Documentation | **DRIFT EXISTS** (being corrected) |
| **Go-live** | **NOT READY** |

---

## Launch blockers (code + operator)

1. **Go-live not executed** — `go_live_claimed: false`; LAUNCH §1–3 unchecked; §7 unsigned.
2. **Paid billing missing** — ADR-002; blocks revenue launch.
3. **Production cutover not performed** — `production_cutover_claimed: false`.
4. **Live PITR / restore drill** — packaged runbooks only; `operator_pitr_drill_executed: false`.
5. **Architecture doc drift** — **partially fixed** 2026-08-23 (`DATABASE_DOCUMENTATION.md`, `ARCHITECTURE_DOCUMENTS.md`); audit remaining top-level docs.
6. **`max_users` not enforced** on user create (catalog display only).
7. **Default store on company create** — **implemented** 2026-08-23 when store capacity allocated.
8. **ADR-005 user↔store membership** — POST-MVP if product requires cashier store lists.
9. **Store RBAC** — not enforced on all operational APIs.
10. **7-day offline POS** — **MISSING** (catalog TTL ~4h; no `offline_valid_until` envelope; idempotency at API layer only). See offline audit §13–14.
11. **Offline owner dashboard + alerts + recovery** — MISSING (queue MVP exists; monitoring/alerts/export not shipped).
12. **Scale / pen test on prod infra** — operator/external.

---

## Code changes this pass (not documentation packs)

- **Default Main Store on company create** when `create_main_store` (default when company has `store_limit ≥ 1`); blocks explicit request without allocation (`STORE_LIMIT_REQUIRED`). Tests: `test_company_create_creates_main_store_when_capacity_allocated`, `test_company_create_blocks_main_store_without_allocation`.
- **UI:** Companies page checkbox “Create Main Store automatically”.
- **Docs:** Mark schema-per-tenant as SUPERSEDED; point to `docs/ADR_001_TENANCY.md`.

---

## ACTION REQUIRED FROM OWNER

1. LAUNCH §1–3 verification (secrets, CORS, Redis, SMTP, no demo creds).
2. Staging → production cutover on target VPS/domain/HTTPS.
3. Execute PITR + restore drill in staging/prod; retain evidence.
4. Physical POS offline tests (Windows/Android/iPad/macOS) per master prompt §51–52.
5. Production load test (~1000 VU) on sized infra.
6. Vendor penetration test engagement.
7. Decide billing provider integration timeline (ADR-002).
8. Sign LAUNCH §7 after evidence review.

---

*Offline POS deep audit (sections 13–38) was in progress at report time; update this file when that audit completes.*
