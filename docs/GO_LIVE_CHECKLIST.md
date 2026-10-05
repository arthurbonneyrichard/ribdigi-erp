# RIBDIGI ERP — GO-LIVE CHECKLIST (authoritative)

**2026-10-05 audit status: Not ready for market.** The full backend suite is green. Isolated sqlite restore is proven. An isolated Postgres restore was not run. Browser sign-in was not completed. Offline POS is the only offline surface; the rest of the ERP is online-only. `offline_complete_claimed` stays false.

## Audit 2026-10-05 (local production tree, not deployed)

| Gate | Status | Evidence |
|------|--------|----------|
| Full backend pytest | PASS | Before: **112 failed, 2743 passed, 1 skipped**, ended 2026-10-04T23:25:55Z. Mid: **1 failed, 2854 passed, 1 skipped**, ended 2026-10-05T04:53:20Z (login p95 2526.3ms > 2000ms). After moving bcrypt `verify_password` off the event loop with `asyncio.to_thread` (cost factor 12 unchanged, 2000ms target unchanged): `PYTHONPATH=.` and `python -m pytest -q --tb=line` from `backend` on Python 3.12.10: **2855 passed, 1 skipped**, 36257 warnings, 4345.20s (1:12:25), exit 0. Log `%TEMP%\ribdigi-pytest-final3.txt`, ended 2026-10-05T10:09:14Z. |
| Targeted behavioral slice | PASS | 38 passed, 436 warnings, 58.86s, exit 0, ended 2026-10-04T23:59:14Z. Terminal record 506824. Not re-run after later edits. |
| Isolated sqlite restore | PASS | 2 passed, 5.44s. Not an operator Postgres restore. |
| Isolated Postgres restore | BLOCKED | 127.0.0.1:5432 is Docker `ribdigi-erp-postgres-1`. Only application database is `ribdigi_erp`. `/data/backups` in `ribdigi-erp-backend-1` is empty. No `.ribbak` in the tree. No restore was attempted. Operator action is in `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`. |
| Browser retail and pharmacy walkthrough | BLOCKED | `http://127.0.0.1:3000/` shows Login tenant, Login email, Login password, and Sign in. `/login` is 404. The page is served by container `ribdigi-erp-frontend-1`, not this uncommitted tree. Automation did not type the password. API walkthroughs of `walk-retail-one`, `walk-retail-multi`, `walk-pharm-one`, and `walk-pharm-multi` are not this gate. Missing prerequisite: an operator signs in and checks on-screen receipt preview for retail and pharmacy, single-store and multi-store, transfer absence and presence, pharmacy lots, batches, prescriptions, and expiry, a valid dispense, an expired or quarantined block, and POS checkout with receipt preview. |
| Frontend production build | PASS with warning | `npm run build` in `frontend` after the UI edits. Next.js 14.2.35, 44/44 pages, exit 0, ended 2026-10-05T02:25:52Z. `themeColor` warning is gone; brand `#4AB012` stays on `viewport` and the manifest. `metadataBase` is still unset (15 warnings). Next used `http://localhost:3000` while generating pages. No public origin is configured, so a production host was not invented. |
| Owner tasks | INCOMPLETE | Production HTTPS, secrets, workers, load certification, and physical POS checks stay open. |

Pharmacy stays on the main dashboard. Retail keeps shared sales, inventory, and POS. A single-store company cannot create a transfer. Hotel and FMCG are not selectable for new companies. Mobile Money is a recorded tender only. Staff guides stay industry-specific. An unmapped AI prompt is not shown as a completed report.

### Signed-in browser steps (operator, still open)

Do this in a browser against a build of this tree, not only the Docker image on port 3000. Do not treat API checks as this gate.

1. Sign in to a retail single-store company. Confirm transfer controls are absent. Complete a POS checkout and open the on-screen receipt preview.
2. Sign in to a retail multi-store company. Confirm a transfer can be started only where the user is allowed.
3. Sign in to a pharmacy single-store company. Check lots, batches, prescriptions, and expiry. Dispense a valid item. Confirm an expired or quarantined item is blocked. Complete POS checkout and open the receipt preview.
4. Repeat the pharmacy checks on a multi-store company, including transfer presence only when authorized.


**Date:** 2026-09-17 (historical snapshot below)  
**Branch evidence:** commercial readiness work on the production release branch  
**Rule:** Evidence required. Docs ≠ implementation. Local Docker ≠ production.

## Audit 2026-10-04 (local, not deployed)

Supported new-company industries: Retail, Pharmacy, Wholesale, Retail + Wholesale, and Hospital. Hotel and FMCG are rejected on create and on a business-type change. A company that already stores Hotel or FMCG keeps that value and its records. Offline Complete, paid checkout, and a hospital information system are not claimed.

| Area | Status | Evidence |
|------|--------|----------|
| Hotel / FMCG removed from new selection | PASS | `assert_industry_selectable`; `tests/test_business_type_locked_b1.py::test_hotel_and_fmcg_are_not_selectable_for_new_companies` |
| Single-store transfer API | PASS | `stores.create_transfer` returns 403 when entitlement is 1 store; `test_single_store_company_cannot_create_a_transfer` |
| Paid expenses list | PASS (code) | Expenses page shows the register under the title, with a Categories jump |
| Staff guide by industry | PASS (code) | `staff_guide.py` steps differ for retail, pharmacy, wholesale, and retail+wholesale |
| Mobile Money recorded settlement | PASS | Expenses, credit repayments, and other income accept `mobile_money` (`momo` alias). Posts to bank GL 1010. Does not collect or settle funds. |
| Pharmacy and wholesale nav labels | PASS (code) | Sidebar groups are Pharmacy and Wholesale. Pharmacy work stays on `/dashboard` plus inventory and prescriptions. |
| Tenant isolation matrix (SQLite) | PASS | Prior local slice; not re-run in this pass |
| Isolated logical restore (sqlite pytest) | PASS | `python -m pytest tests/test_backup_restore_isolation_r1.py -q --tb=short` from `backend` on Python 3.12: **2 passed** in 5.44s (2026-10-04, after store, warehouse, dry-run, and failed-store checks). See the procedure below. Production data was not restored. |
| Operator backup restore of a production database | BLOCKED | Not run. Do not treat the sqlite drill as a production restore. |
| Signed-in retail and pharmacy walkthrough | PASS (API) | Local companies `walk-retail-one`, `walk-retail-multi`, `walk-pharm-one`, `walk-pharm-multi` on `http://127.0.0.1:8000`. Industry and store mode verified from `/me` and `/stores/entitlement`. See the walkthrough section. Browser password entry was not driven. |
| Frontend production build | PASS | `npm run build` in `frontend` (clean, Next.js 14.2.35, 44/44 static pages). Exit 0. Ended 2026-10-04T21:59:44Z. Warnings only: `metadataBase` and `themeColor`. |
| Full backend suite | FAIL | `python -m pytest -q --tb=line` from `backend` with `PYTHONPATH=.` on Python 3.12. Exit 1. **112 failed, 2743 passed, 1 skipped, 35745 warnings** in 3631.66s (ended 2026-10-04T23:25:55Z). Sqlite in-process tests. Failures are assertions, not missing Redis, Postgres, or RabbitMQ. Sampled failures also fail against unchanged HEAD files (see the note below). |
| Alembic against a staging database | BLOCKED | Not run in this pass |

Legend: **PASS** | **FAIL** | **BLOCKED** | **NOT REQUIRED FOR MVP**

### Isolated restore procedure (sqlite, 2026-10-04)

Production data was not restored. Command from `backend` (Python 3.12.10):

```
python -m pytest tests/test_backup_restore_isolation_r1.py -q --tb=short
```

Result: **2 passed** in 5.44s (exit 0). An earlier run of the same file, before the store and failed-store assertions, was 2 passed in 8.25s. The database is the pytest in-memory sqlite engine. `BACKUP_DIR` is a temp directory. Warnings were deprecations only.

Checks that passed:

- `POST /backup`, then dry-run `POST /backup/{id}/restore` with `dry_run: true`: `valid` true, `applied` false, source tenant id and company name `Alpha Co`, and record counts for stores and transactions.
- Apply with `confirm_text` `RESTORE` returns `applied` and `proof.ok`. `POST /backup/{id}/verify` with `sample_limit` 100 also returns `proof.ok`.
- The other tenant's product, invoice, store, company name, company id, and audit count stay unchanged, including `tenant_id`.
- A POS sale, `mobile_money` tender, stock movement, and audit row on the restored tenant return to the backup values and keep `tenant_id`. The payment stays linked to the sale.
- Store `Alpha Main` (`AMAIN`) and warehouse `Alpha WH` return to the backup names, stay on the source tenant, and the warehouse `store_id` is restored. The other tenant's store stays `Beta Main`.
- Company names and tenant ids are unchanged. Restore does not rewrite the tenant row; ownership is the restored rows' `tenant_id` plus the unchanged company record.
- Queued offline conflicts created before and after the backup remain and are still listed. Dismissing one returns 200. Restore does not delete the queue.
- A forced integrity failure after writing sentinel product and store names returns 409. Those names stay at the pre-restore corrupt values. The partial names are not left committed. The other tenant is unchanged.

Offline scope: POS only. The rest of the ERP stays online-only.

### Signed-in walkthrough (API, 2026-10-04)

Disposable local companies on the running API at `http://127.0.0.1:8000`, which bind-mounts this production tree. Accounts are the company admin for each slug. Passwords and tokens are not recorded here.

Industry and store mode were read after create (`/me` industry, `/stores/entitlement`):

| Slug | Industry | Store mode | Stores |
|------|----------|------------|--------|
| walk-retail-one | retail | single (`multi_store` false, effective limit 1) | 1 |
| walk-retail-multi | retail | multi (`multi_store` true, effective limit 2) | 2 |
| walk-pharm-one | pharmacy | single | 1 |
| walk-pharm-multi | pharmacy | multi | 2 |

Each company signed in (HTTP 200, role `company_admin`). `GET /dashboard` has `pharmacy_desk` for both pharmacy companies and omits it for both retail companies. `GET /reports/sales/daily` returned 200 for all four.

POS: `POST /pos/sessions/open` (or an already open shift) returned 200. `POST /pos/sales` with `payment_method` `mobile_money` and no client tender amount let the server record the full total. `pos_payments` stored `mobile_money` for each sale (totals 5.75, 13.80, 9.20, and 4.60). `GET /pos/sales/{id}/receipt` returned 200 with line items. An earlier sale attempt that sent only the shelf price returned 400 `Payment tenders must sum to sale total` because tax was excluded. That attempt is not a pass.

Transfers: both single-store companies returned 403 `This company is single-store. Branch and warehouse transfers are not available.` Both multi-store companies created transfer `TR-2026-0001` (HTTP 200).

Pharmacy lots: a sellable lot dispensed (HTTP 200). An expired lot returned 409 `Lot has expired and cannot be sold` on both pharmacy companies. A quarantined lot returned 409 `Lot is quarantined or recalled` on both. The first attempts returned 409 `Open a POS shift before recording sales` because `POST /pos/sessions` is not the open route (405). Those attempts are not a pass. The block above is the result after `POST /pos/sessions/open`.

The on-screen login form was not completed. Browser automation refused to type the password. The signed-in evidence is the API session above.

There is no separate Pharmacy Management page. Pharmacy figures stay on the main dashboard.

### Full backend suite (2026-10-04)

Command from `backend`:

```
$env:PYTHONPATH = "."
python -m pytest -q --tb=line
```

Result: **112 failed, 2743 passed, 1 skipped, 35745 warnings** in 3631.66s. Exit code 1. Ended 2026-10-04T23:25:55Z. The quiet run did not name the single skip. Warnings are deprecations (`on_event`, `datetime.utcnow`), not missing services. No failure in the short traceback is a connection error to Redis, Postgres, or RabbitMQ. The suite uses the pytest sqlite engine.

Sampled failures are already present on clean `HEAD` of this branch:

- UI strings such as `Drawer reason (required)`, `POS receipt override to`, `shiftManageFilter`, `Report financial store filter`, `Expense reject reason`, and `Show receivables aging` are absent from both `HEAD` and the working copies of those pages.
- `normalize_payment_method("MoMo")` already returns `mobile_money` on `HEAD`. The committed test still expects `wallet`. The uncommitted diff does not change that alias.
- Customer create returns the generic 500 from `customers.py`, which is not in the working-tree diff. Product create opening-stock doubling (`stock_qty` 24 vs 12) is in `api.py` lines that the working-tree diff does not change.

`offline_complete_claimed` stays false. Offline POS is the only offline surface. The rest of the ERP is online-only.

| Category | Item | Status | Evidence / notes |
|----------|------|--------|------------------|
| Architecture | Shared schema + `tenant_id` | PASS | `docs/ADR_001_TENANCY.md`; models |
| Architecture | Tenant == Company (1:1 MVP) | PASS | `store_entitlements.py`; multi-company under one tenant = POST-MVP |
| Database | Migrations apply | PASS | Alembic tree incl. `20260917_0105`–`0107` (membership, client_request_id, pos_devices) |
| Tenant Isolation | JWT + query filters | PASS | `security.py`, isolation tests |
| Company Isolation | Multi-company child orgs | NOT REQUIRED FOR MVP | Company profile = Tenant; no second Company entity |
| Store Isolation | Entitlement + membership | PASS | `store_entitlements.py`; `store_access.py`; POS filter |
| RBAC | Module permissions | PASS | `rbac.py`, role nav |
| Inventory | Core stock flows | PASS | Existing inventory APIs/UI |
| Purchasing | PO / GRN / invoices | PASS | Existing purchasing module |
| Sales | Invoices / orders | PASS | Existing sales module |
| POS | Online shift + sale | PASS | `pos.py`, `/pos` UI |
| Accounting | CoA / journals / P&L | PASS | Accounting module |
| Tax | Tax rates / reports | PASS | Tax module |
| Credit | Customer credit | PASS | Credit module |
| Offline | Server grant, device allocation, encrypted queue | PARTIAL | New sales block when the grant expires; queued sales still sync after an online sign-in. Browser-restart endurance NOT RUN. Offline Complete is not claimed. |
| POS Devices | Heartbeat / lockdown | PARTIAL | Heartbeat API + `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`; physical kiosk NOT VERIFIED |
| Backup | Logical backup API | PASS | `/backup`, DR runbook |
| Restore | Logical restore tested in CI | PASS | `test_logical_dr_drill_b1.py` |
| Security | Internal isolation/RBAC tests | PASS | Backend test suite |
| Performance | Live load certification | BLOCKED | Scripts exist; live VPS run = OWNER |
| Monitoring | Prod scrape/alerts | BLOCKED | OWNER / ops |
| Deployment | Prod HTTPS + secrets | BLOCKED | OWNER |
| Documentation | Tenancy drift marked | PASS | `ORIGINAL_README.md` SUPERSEDED notes |
| Support | Paid billing gateway | NOT REQUIRED FOR MVP | Platform assigns packages; truthful “Contact Ribdigi” |
| Rollback | Deploy rollback plan | BLOCKED | OWNER runbook |

## Launch blockers (must close or explicitly defer marketing)

1. **Production deployment** (OWNER) — domain, TLS, secrets, Postgres, workers  
2. **Offline POS marketing** — foundation **PARTIAL** in code (queue + recovery JSON + heartbeat); do not claim certified 7-day endurance until physical tests + alert UX  
3. **Physical POS verification** (OWNER) — Windows/Android devices  
4. **Staging restore + load drill** (OWNER)  
5. **External pen test** (EXTERNAL)

## Post-MVP (do not block launch if not marketed)

- Multi-company under one Tenant  
- User↔POS terminal binding (`ASSIGNED_POS_ONLY`)  
- Offline endurance certification, device alert dashboard (beyond last-seen table)  
- Physical kiosk verification per `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`  
- PITR live drill, paid payment provider  
- HR / MRP / Open Banking  
