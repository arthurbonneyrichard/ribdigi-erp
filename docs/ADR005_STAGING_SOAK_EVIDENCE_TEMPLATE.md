# ADR-005 / membership-scope staging soak — evidence template

**Purpose:** Fillable operator evidence pack for staging enable of
`STORE_MEMBERSHIP_SCOPE_ENABLED=true`.

**Parent runbook:** [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)  
**Complete criteria (still MISSING):** [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md)  
**Go-live pack:** [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md) §3C

**Honesty — checking boxes / attaching evidence here does NOT alone claim:**

| Claim | Status after soak |
|-------|-------------------|
| ADR-005 membership Complete | Already **Complete** (enable ≠ reopen) |
| Store-scoped RBAC Complete | Still **MISSING** |
| Offline Complete / 7-day VERIFIED | Still **MISSING** |
| Go-live / attestation | Still **MISSING** |
| Paid billing Complete | Still **MISSING** |
| Overall RBAC Complete | Still **MISSING** / readiness **PARTIAL** |

Product ALLOW sign-off (logo binary GET; `/auth/sessions`; `/notifications/settings`)
is a **separate** gate — see remaining checklist item 6. This soak does **not**
substitute for that sign-off.

---

## Cover sheet

| Field | Value |
|-------|-------|
| Staging tenant / company | |
| Operator name | |
| Date / window | |
| Tip / build SHA under test | |
| Staging API URL | |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` before soak | `false` (expected) |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` during soak | `true` |
| Rollback verified? (Y/N) | |

**Verdict after run (circle one):** NOT RUN · IN PROGRESS · FAIL · PASS (evidence attached)

**Store-scoped RBAC Complete claim authorized?** ☐ **No** (default — soak alone never flips)  
**Prod default ON approved?** ☐ No (default) ☐ Yes — only after product + ops sign-off below

---

## Actor inventory (staging, non-demo)

| Role | User email / id | Notes |
|------|-----------------|-------|
| Company / tenant admin | | Assigns memberships; grants elevation |
| store_manager (managed Store A via `manager_id`) | | Union scope target |
| cashier with membership (Store A only) | | POS bind / fail-closed foreign |
| cashier **without** membership | | Empty visibility expected |
| Optional: store_manager + membership-only Store B | | Union = manager_id ∪ membership |

| Store | Code / id | `manager_id` | Memberships to assign |
|-------|-----------|--------------|------------------------|
| Store A (managed) | | store_manager | cashier-with-membership |
| Store B (foreign / membership-only) | | other or null | optional manager membership |
| Store C (unassigned foreign) | | other | none for soak cashiers |

---

## Step results (Pass / Fail + evidence link)

| # | Step | Expected | Pass/Fail | Evidence link (API JSON / screenshot / HAR) |
|---|------|----------|-----------|-----------------------------------------------|
| 0 | Preflight: flag OFF smoke (optional) | Legacy `manager_id` / company-wide cashier POS | | |
| 1 | Set `STORE_MEMBERSHIP_SCOPE_ENABLED=true`; restart API | Health green; flag readable | | |
| 2 | Admin assigns memberships (`/stores#memberships` or API) | 200; rows listed | | |
| 3 | Manager union | Sees Store A ∪ membership stores only; Store C excluded | | |
| 4 | Cashier **with** membership | Store A only; foreign POS → `STORE_SCOPE_DENIED` | | |
| 5 | Cashier **without** membership | Empty store list; POS denied (fail-closed) | | |
| 6 | POS bind | `/me/store-memberships` → `pos_store_bind_required=true`; picker binds assigned store; foreign denied | | |
| 7 | Temp membership `expires_at` | Future OK; past → excluded from scope / denied | | |
| 8 | Elevation / break-glass | Grant with reason + ≤24h `expires_at`; audit; early revoke or post-expiry deny; store_manager cannot grant | | |
| 9 | Admin bypass + SM deny admin APIs | Admin all stores; SM cannot assign/revoke memberships or elevations | | |
| 10 | Honesty payload | `adr005_complete_claimed`/`scope_wired_to_membership` **true**; `store_scoped_rbac_complete_claimed` **false**; `temp_membership_expires_at_claimed` / `elevation_break_glass_claimed` **true** | | |
| 11 | Intentional ALLOWs (observe only) | Logo binary GET; caller `/auth/sessions`; `/notifications/settings` still reachable for SM — **do not deny** without product sign-off | | |
| 12 | Rollback flag `false` | Legacy scope returns; membership **rows retained** | | |

---

## Honesty payload capture (`GET /api/v1/me/store-memberships`)

Paste or link response excerpt (flag ON):

| Field | Expected | Observed |
|-------|----------|----------|
| `store_membership_scope_enabled` | `true` | |
| `adr005_complete_claimed` | `true` | |
| `scope_wired_to_membership` | `true` | |
| `store_scoped_rbac_complete_claimed` | `false` | |
| `pos_store_bind_required` | `true` | |
| `temp_membership_expires_at_claimed` | `true` | |
| `elevation_break_glass_claimed` | `true` | |

---

## Intentional product ALLOWs (sign-off tracker — not soak Pass/Fail)

These remain **intentional ALLOWs** until product accepts or rejects them.
Soak operators **must not** treat “still allowed” as a defect or flip Completes.

| Surface | Product decision | Owner | Date | Notes |
|---------|------------------|-------|------|-------|
| Company/tenant logo binary GET | ☐ Accept ALLOW · ☐ Change (ticket) · ☐ Deferred | | | Workspace chrome |
| `GET/… /auth/sessions` (caller-scoped) | ☐ Accept ALLOW · ☐ Change · ☐ Deferred | | | Self-service sessions |
| `/notifications/settings` (caller-scoped) | ☐ Accept ALLOW · ☐ Change · ☐ Deferred | | | Self-service prefs |

**Store-scoped RBAC Complete requires** product ACCEPT on remaining ALLOWs **and**
engineering residual empty **and** this soak PASS — none of those alone suffices.

---

## Sign-off

| Role | Name | Date | Signature / ack |
|------|------|------|-----------------|
| Staging operator | | | |
| Product (ALLOW sign-off — optional this run) | | | |
| Engineering (review evidence only) | | | |

**Prod `STORE_MEMBERSHIP_SCOPE_ENABLED=true` default?** ☐ Not approved (default)  
Enabling prod default is a separate ops cutover after product readiness — it does
**not** reopen ADR-005 Complete and does **not** claim store-scoped RBAC Complete.
