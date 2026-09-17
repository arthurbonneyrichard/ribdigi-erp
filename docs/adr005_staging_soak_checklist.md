# ADR-005 staging / ops membership-scope soak checklist

**Status:** ADR-005 is **Complete** in code via automated flag-ON soak
(`backend/tests/test_adr005_membership_scope_soak.py`). This checklist is the
**operator** staging enable step — flag default remains
`STORE_MEMBERSHIP_SCOPE_ENABLED=false` in `.env.example` and
`.env.production.example`.

**Evidence template (fillable):** [`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md)  
**Store-scoped Complete remaining:** [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md)  
**Go-live pack:** [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md) §3C  
**Living matrix:** [`STORE_SCOPED_RBAC_TEST_MATRIX.md`](STORE_SCOPED_RBAC_TEST_MATRIX.md)  
**Design:** [`ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md`](ADR_005_MEMBERSHIP_SCOPE_CUTOVER.md)

## Honesty — soak does **not** alone claim Completes

| Claim | After this soak |
|-------|-----------------|
| ADR-005 membership Complete | Already **Complete** (staging enable ≠ reopen) |
| Store-scoped RBAC Complete | Already **Complete** (engineering + ALLOW accept + automated/local soak; staging enable ≠ reopen) |
| Offline Complete / 7-day VERIFIED | Still **MISSING** |
| Go-live / attestation | Still **MISSING** |
| Paid billing Complete | Still **MISSING** |
| Overall RBAC Complete | Still **MISSING** / readiness **PARTIAL** |

Automated soak **=** ADR-005 + store-scoped Complete evidence (SEC-M2 parallel). Do **not** flip
production default to ON from this checklist alone. Leaving the flag OFF does
**not** reopen Completes.

Intentional product ALLOWs (logo binary GET; caller-scoped `/auth/sessions` +
`/notifications/settings`) are **product-accepted** —
[`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md).
Observe in soak; do **not** deny without a product ticket.

---

## Automated evidence (already landed)

| Check | Coverage |
|-------|----------|
| Flag default OFF | `test_adr005_soak_flag_still_defaults_off_ops_enable` |
| Honesty Complete flags | `test_adr005_soak_honesty_complete_flags` |
| Flag OFF legacy | `test_adr005_soak_flag_off_legacy_manager_and_cashier` |
| Flag ON manager union | `test_adr005_soak_flag_on_store_manager_union_scope` |
| Flag ON manager membership-only | `test_adr005_soak_flag_on_store_manager_membership_only` |
| Flag ON cashier with membership | `test_adr005_soak_flag_on_cashier_with_membership_only_assigned` |
| Flag ON cashier empty/denied | `test_adr005_soak_flag_on_cashier_without_membership_empty_denied` |
| Flag ON admin bypass | `test_adr005_soak_flag_on_admin_unaffected` |
| `/me` visibility flag ON | `test_adr005_soak_me_memberships_honesty_and_visibility_flag_on` |
| `/me` no bind flag OFF | `test_adr005_soak_me_memberships_visibility_flag_off_no_bind` |
| Docs present | `test_adr005_soak_docs_and_checklist_present` |
| Temp `expires_at` | `tests/test_membership_expires_at.py` |
| Elevation / break-glass | `tests/test_rbac_elevation_break_glass.py` |
| Living matrix spine | `tests/test_store_scope_rbac_matrix.py` (`-m store_scope`) |

```bash
cd backend && .venv/bin/pytest \
  tests/test_adr005_membership_scope_soak.py \
  tests/test_store_membership_scaffold.py \
  tests/test_membership_expires_at.py \
  tests/test_rbac_elevation_break_glass.py \
  tests/test_store_scope_rbac_matrix.py -q
cd frontend && node --test lib/storeMembershipAdmin.test.mjs lib/posStoreBinding.test.mjs
```

---

## Operator staging enable — step-by-step

Use a **real staging tenant** (no demo seed). Copy
[`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md)
into the ops evidence folder for this run and fill Pass/Fail + links.

### 0. Preflight (optional baseline)

- [ ] Confirm prod/staging template default: `STORE_MEMBERSHIP_SCOPE_ENABLED=false`
- [ ] Optional: with flag OFF, note legacy store_manager (`manager_id` only) and
      cashier company-wide POS behavior for rollback comparison
- **Pass:** defaults fail-closed OFF · **Fail:** flag already ON without change control

### 1. Enable flag

- [ ] Set `STORE_MEMBERSHIP_SCOPE_ENABLED=true` in staging secrets / env
- [ ] Restart API; confirm health green
- **Pass:** process up · **Fail:** boot error / wrong env file

### 2. Assign memberships

- [ ] As company/tenant admin, open `/stores#memberships` (or
      `POST /api/v1/stores/{id}/memberships`)
- [ ] Assign cashier → Store A (permanent or future `expires_at`)
- [ ] Optionally assign store_manager → membership-only Store B
- [ ] Confirm store_manager **cannot** call membership assign/revoke APIs
- **Pass:** 200 + rows visible to admin · **Fail:** SM can mutate memberships; 5xx

### 3. store_manager union scope

- [ ] Login as store_manager with `manager_id` on Store A (+ optional membership B)
- [ ] List stores / scoped commerce: **only** `manager_id` ∪ active memberships
- [ ] Foreign Store C excluded from lists; foreign write → `STORE_SCOPE_DENIED`
- **Pass:** union only · **Fail:** sees all company stores or misses managed store

### 4. Cashier fail-closed (with membership)

- [ ] Cashier with Store A membership: store list = assigned only
- [ ] POS / store-scoped write on Store A allowed
- [ ] Foreign store POS / bind → `STORE_SCOPE_DENIED` (or empty picker)
- **Pass:** assigned only + foreign denied · **Fail:** company-wide visibility

### 5. Cashier fail-closed (without membership)

- [ ] Cashier with **no** membership rows: empty store visibility
- [ ] POS open / bind denied (fail-closed — not legacy company-wide)
- **Pass:** empty + denied · **Fail:** any company store still usable

### 6. POS bind

- [ ] `GET /api/v1/me/store-memberships` → `pos_store_bind_required=true` (flag ON)
- [ ] POS store picker requires bind to an assigned membership store
- [ ] Bind Store A succeeds; bind foreign fails
- **Pass:** bind required + assigned only · **Fail:** unbound POS or foreign bind OK

### 7. Temp membership expiry (`expires_at`)

- [ ] Assign membership with future `expires_at` (≤ staging window) → in scope
- [ ] Assign / backdate past `expires_at` (or wait) → row `is_expired`; **excluded**
      from scope; POS/store lists deny that store
- [ ] Clear `expires_at` (null) → permanent again
- [ ] Honesty: `temp_membership_expires_at_claimed=true`
- **Pass:** future in / past out · **Fail:** expired row still grants scope

### 8. Elevation / break-glass (related MVP — not store-scope Complete)

- [ ] Admin `POST /api/v1/users/{id}/elevations` with **required** `reason` +
      future `expires_at` ≤ 24h + permissions within grantor subset
- [ ] Missing reason / missing expiry / >24h / past expiry → **400**
- [ ] Effective grant merges permissions; audit on grant
- [ ] Early revoke **or** wait until expiry → elevated action denied after
- [ ] store_manager **cannot** list/grant elevations
- [ ] Honesty: `elevation_break_glass_claimed=true`;
      `store_scoped_rbac_complete_claimed=false`
- **Pass:** grant/deny/expiry as above · **Fail:** open-ended grant or SM can elevate

### 9. Admin bypass

- [ ] Company/tenant admin still sees all company stores; can assign/revoke
- **Pass:** admin unrestricted for membership admin · **Fail:** admin fail-closed

### 10. Honesty payload (required capture)

`GET /api/v1/me/store-memberships` (flag ON) must show:

| Field | Expected |
|-------|----------|
| `store_membership_scope_enabled` / equivalent flag signal | true |
| `adr005_complete_claimed` | **true** |
| `scope_wired_to_membership` | **true** |
| `store_scoped_rbac_complete_claimed` | **false** |
| `pos_store_bind_required` | **true** |
| `temp_membership_expires_at_claimed` | **true** |
| `elevation_break_glass_claimed` | **true** |

- **Pass:** all rows match · **Fail:** any Complete flipped true for store-scoped /
  Offline / billing / go-live — **stop and escalate**

### 11. Intentional ALLOWs (observe — do not “fix” by denying)

- [ ] store_manager can still `GET` company/tenant **logo binary** (workspace chrome)
- [ ] Caller can use `/auth/sessions` and `/notifications/settings` (self-service)
- Record observations on the evidence template ALLOW tracker; product sign-off
  is **out of band** for Completing store-scoped RBAC
- **Pass:** still allowed (current product posture) · **Fail:** unexpected 403
  without product change ticket (regression)

### 12. Rollback

- [ ] Set `STORE_MEMBERSHIP_SCOPE_ENABLED=false`; restart
- [ ] Legacy scope returns (`manager_id` / legacy cashier)
- [ ] Membership **rows retained** (never delete business data for flag flip)
- **Pass:** legacy restored + rows kept · **Fail:** data wiped or flag stuck ON

### 13. Production enable (separate cutover)

- [ ] Only after staging PASS + product readiness: enable prod default ON under
      change control
- Production enable does **not** reopen ADR-005 Complete
- Production enable does **not** claim store-scoped RBAC Complete

---

## Expected Pass / Fail summary

| Scenario | Pass | Fail |
|----------|------|------|
| Flag ON manager | Union of `manager_id` ∪ memberships only | Company-wide dump |
| Flag ON cashier + membership | Assigned stores only | Sees foreign stores |
| Flag ON cashier empty | Empty + POS denied | Any usable store |
| POS bind | Required; assigned only | Unbound or foreign OK |
| `expires_at` past | Out of scope | Still scoped |
| Elevation | Reason + ≤24h; deny after expiry/revoke | Permanent elevate |
| Honesty | store-scoped Complete **false** | Accidental Complete true |
| Rollback | Legacy + rows kept | Data loss / stuck ON |

---

## Evidence capture

1. Copy [`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md)
2. Fill cover sheet (tenant, SHA, dates)
3. Attach API JSON / screenshots / HAR per step row
4. Paste honesty payload excerpt
5. Leave Complete claim boxes **No** unless product + remaining checklist
   explicitly authorize (they do **not** today)

Minimum evidence for a PASS soak: steps **1–7**, **9–10**, **12** with links.
Steps **8** and **11** recommended; **11** feeds product ALLOW sign-off, not soak Pass.

---

## Explicit non-claims

Do **not** mark from this checklist or a green soak alone:

- Store-scoped RBAC Complete
- Offline Complete / 7-day VERIFIED
- Go-live / attestation
- Paid billing Complete / `payment_success`
- Overall RBAC Complete
- Prod default `STORE_MEMBERSHIP_SCOPE_ENABLED=true` without separate change control

ADR-005 remains **Complete** with automated soak; staging enable is ops cutover only.
