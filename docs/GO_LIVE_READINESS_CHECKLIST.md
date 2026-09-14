# Go-live readiness checklist (operator pack)

**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Audience:** Staging / production operators (not continuum dump authors)  
**As of engineering tip ancestry:** paid billing entitlement gate + ADR-005 soak +
offline wipe-via-push automation (see `AGENTS.md` tip SHA after merge).

**Engineering → Complete path: ops-blocked.** Landed code + automated suites do
**not** advance Offline / push-delivery / 7-day VERIFIED / go-live / paid billing /
ADR-005 / store-scoped RBAC Completes. Cloud-agent Chrome could not finish
`PushManager.subscribe` (no FCM endpoint) — that attempt is a **blocker note**,
not proof. Remaining work is **ops-only** (staging keys, real till browser,
soaks, physical matrix). Do **not** resume continuum RBAC dumps.

**Honesty — do not claim from this document alone:**

| Claim | Status |
|-------|--------|
| Offline Complete | **MISSING** |
| 7-day physical VERIFIED | **MISSING** (matrix not run) |
| Go-live / attestation Complete | **MISSING** |
| Paid billing Complete / payment_success | **MISSING** |
| ADR-005 Complete | **MISSING** |
| Store-scoped RBAC Complete | **MISSING** |

This pack consolidates FIXED vs PARTIAL vs MISSING gates and the **exact ops
steps** for staging soaks. Engineering automation is already landed; Completes
that need staging keys, real browsers, or multi-day physical evidence stay open.

Related deep runbooks (do not duplicate dumps here):

- Security cookie cutover: [`sec_m2_staging_soak_checklist.md`](sec_m2_staging_soak_checklist.md)
- ADR-005 membership: [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)
- Offline wipe + VAPID browser: [`offline_wipe_push_staging_checklist.md`](offline_wipe_push_staging_checklist.md)
- Offline 7-day matrix: [`OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`](OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md)
- Paid billing provider: [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md)
  · staging soak [`paid_billing_staging_soak_checklist.md`](paid_billing_staging_soak_checklist.md)
- Commercial honesty: [`COMMERCIAL_READINESS_REPORT_2026-08-23.md`](COMMERCIAL_READINESS_REPORT_2026-08-23.md)
- Classic launch hygiene: [`LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md) (config/smoke; does **not** override honesty below)

---

## 1. Status summary (FIXED / PARTIAL / MISSING)

| Gate | Status | Engineering evidence | Ops still required |
|------|--------|----------------------|--------------------|
| Security Mediums SEC-M1…M5 + L2 | **FIXED** / overall ✅ **HARDENED** | Automated cookie soak Phase E; flag defaults OFF intentional | Staging cookie enable per SEC-M2 checklist (ops cutover ≠ reopen finding) |
| Offline remote wipe scaffold | **PARTIAL** | Alembic `20260914_0111`; request/ack + IndexedDB clear | — |
| Offline Web Push wipe delivery | **PARTIAL** (ops-blocked for Complete) | Alembic `20260914_0112`; VAPID dispatch; automated wipe-via-push suite; cloud-agent subscribe **blocked** | Staging VAPID keys + **real till browser** proof (not cloud agent) |
| Offline Complete attestation | **MISSING** | Explicitly not claimed (`OFFLINE_COMPLETE_ATTESTATION.md`) | Product attestation after endurance + push Complete |
| 7-day offline physical VERIFIED | **MISSING** | Envelope + client gate shipped only | Execute platform matrix runbook (unchecked) |
| ADR-005 membership scaffold + UI + flag scope | **PARTIAL** | Assign/list/revoke; flag-gated union scope; cashier fail-closed; automated flag-ON soak | Staging `STORE_MEMBERSHIP_SCOPE_ENABLED=true` soak |
| ADR-005 Complete / store-scoped RBAC Complete | **MISSING** | Flag default **OFF** in prod examples | Product sign-off after soak; do **not** flip prod default from soak alone |
| Paid billing scaffold (portal/checkout/webhooks) | **PARTIAL** (engineering mock soak ready) | ADR-002 tables; HMAC webhooks; portal + checkout create (503 unconfigured; mock CI); lifecycle + `invoice.paid` non-Complete; `test_paid_billing_soak.py` | Live Stripe keys + staging soak |
| Paid billing entitlement gate | **PARTIAL** | `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` default **OFF**; when ON gates only `POST /sales` + `PATCH /companies/{id}`; mock gate-ON soak proven | Staging mirror→access evidence before any prod enable |
| Paid billing Complete / go-live | **MISSING** (ops-blocked) | No `Tenant.plan_code` mutation from Checkout/webhooks; no fabricated MRR; `paid_billing_complete_ops_blocked=true` | Live Stripe cutover + commercial acceptance |

---

## 2. Production / staging flag posture (fail-closed defaults)

Confirm in secrets manager / deploy env (templates: `.env.example`,
`.env.production.example`):

| Variable | Prod template default | Meaning |
|----------|----------------------|---------|
| `AUTH_HTTPONLY_COOKIES_ENABLED` | `false` | SEC-M2 FIXED; ops enable after cookie soak |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `false` | ADR-005 PARTIAL; legacy `manager_id` when OFF |
| `OFFLINE_PUSH_ENABLED` | `false` | Wipe still queues; push skipped until VAPID + enable |
| `OFFLINE_PUSH_VAPID_PUBLIC_KEY` / `_PRIVATE_KEY` | empty | Fail-closed when empty |
| `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` | `false` | Trial/grace/suspend authoritative when OFF |
| `BILLING_PROVIDER*` / `BILLING_CHECKOUT_ENABLED` | empty / `false` | Portal/checkout **503** when unconfigured (no fake success) |

Do **not** treat “flag still false in prod” as unfinished engineering wire after
the automated soaks — wire is flag-gated; Completes remain MISSING until ops
evidence + product sign-off.

---

## 3. Staging soak runbooks (exact ops steps)

Execute on **staging** tenants only. Capture evidence packs (API JSON, screenshots,
HAR, change-log). Completing a soak does **not** by itself mark the related Complete.

### 3A. SEC-M2 httpOnly cookie cutover (security FIXED — ops enable)

Follow [`sec_m2_staging_soak_checklist.md`](sec_m2_staging_soak_checklist.md):

1. Set `AUTH_HTTPONLY_COOKIES_ENABLED=true`; restart API.
2. Login / refresh / 2FA: JSON access tokens null; `Set-Cookie` httpOnly present.
3. Cookie-only authenticated GETs work without Bearer; mutating calls require CSRF.
4. Logout + idle-logout clear cookies and revoke server sessions.
5. Rollback: set flag `false` and restart.

### 3B. Paid billing provider + entitlement gate (PARTIAL / Complete ops-blocked)

Follow [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) and
[`paid_billing_staging_soak_checklist.md`](paid_billing_staging_soak_checklist.md):

1. Set `BILLING_PROVIDER=stripe` + secret key + webhook secret (secrets manager; never git).
2. Set `BILLING_PROVIDER_MODE=live` (or auto with non-mock secret).
3. Set `BILLING_PROVIDER_PRICE_IDS` JSON (or pass `price_id` per request) + portal/checkout return URLs.
4. Point provider webhook to `POST /api/v1/billing/webhooks/provider`.
5. Confirm signed event → `billing_webhook_events.signature_valid=true`.
6. Confirm portal + checkout sessions return real URLs; Company UI navigates; **503** when keys cleared.
7. Confirm Checkout / `invoice.paid` does **not** mutate `Tenant.plan_code` and never claims `payment_success`.
8. Confirm `GET /api/v1/billing/status` reports `paid_billing_complete_claimed=false` and `paid_billing_complete_ops_blocked=true`.
9. **Only after** mirror is healthy: staging-enable `PAID_BILLING_ENTITLEMENT_GATE_ENABLED=true`.
10. Gate ON checks on allowlist only:
    - Allow when subscription mirror `active` or `trialing`: `POST /api/v1/sales`, `PATCH /api/v1/companies/{id}`.
    - Deny missing / `past_due` / `canceled` / `cancelled` → `403 PAID_BILLING_ENTITLEMENT_DENIED`.
11. Rollback: set gate `false`; legacy trial/grace/suspend returns immediately.
12. Do **not** enable the gate in production from this checklist alone; paid billing Complete stays **MISSING** (ops-blocked on live Stripe).

CI already proves the mock path via `test_paid_billing_soak.py` (engineering ready ≠ Complete).

### 3C. ADR-005 membership scope (PARTIAL)

Follow [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md):

1. Set `STORE_MEMBERSHIP_SCOPE_ENABLED=true`; restart API.
2. Ensure membership rows for cashiers who must open POS (`/stores#memberships`).
3. **store_manager:** sees `manager_id` ∪ membership stores only.
4. **cashier with membership:** assigned stores only; foreign POS → `STORE_SCOPE_DENIED`.
5. **cashier without membership:** empty store list; POS denied.
6. **company/tenant admin:** all company stores; can assign/revoke; store_manager cannot call membership admin APIs.
7. `/me/store-memberships`: `store_membership_scope_enabled: true` while
   `adr005_complete_claimed` / `scope_wired_to_membership` remain **false**.
8. Rollback: set flag `false`; legacy scope returns (membership rows retained).
9. Product sign-off required before any production default ON — still **not** ADR-005 Complete.

### 3D. Offline wipe-via-push real-browser (PARTIAL)

Follow [`offline_wipe_push_staging_checklist.md`](offline_wipe_push_staging_checklist.md)
and [`OFFLINE_WEB_PUSH_VAPID_OPS.md`](OFFLINE_WEB_PUSH_VAPID_OPS.md):

- [ ] Generate VAPID keypair into secrets manager (never commit private key).
- [ ] Staging: set public/private/subject keys; `OFFLINE_PUSH_ENABLED=true`; restart.
- [ ] `GET /api/v1/offline/push/vapid-public-key` → `configured: true`, `enabled: true`;
      honesty Complete flags remain **false**.
- [ ] Staging till browser: register/bind device → **Bind browser** (PushManager subscribe).
- [ ] Admin `POST /api/v1/offline/devices/{id}/wipe` → pending + push `delivered` (or honest skip/fail).
- [ ] SW receives `remote_wipe`; IndexedDB cleared; wipe ack succeeds.
- [ ] Optional 410 revoke → subscription revoked; rebind; poll fallback until ack.
- [ ] Rollback: `OFFLINE_PUSH_ENABLED=false` or clear keys — wipe still queues via poll.
- [ ] Evidence pack required for any future push-delivery Complete — **not** Offline Complete.

**Cloud-agent local attempt (2026-09-15):** stack + VAPID endpoint + device bind
proven; **PushManager.subscribe blocked** (timeout / no FCM endpoint). Leave all
boxes above unchecked. See
`/opt/cursor/artifacts/local_vapid_wipe_browser_proof_blocker.md`. Push + Offline
remain **PARTIAL**; Completes stay **MISSING**.

### 3E. Seven-day physical offline matrix (MISSING / NOT RUN)

Follow [`OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`](OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md):

1. Fill platform matrix rows (Windows / Android / iPad / macOS) — currently unchecked.
2. Day 0 bind + catalog; Days 1–6 offline sales with envelope gate; Day 7 renew + sync flush.
3. Record Pass/Fail + evidence links per platform.
4. Passing the matrix is required before any **7-day VERIFIED** claim; Offline Complete remains a separate attestation.

---

## 4. Pre-promote smoke (does not flip Completes)

Use [`LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md) §§1–3 for config/secrets, identity,
and integrations on the **target** environment with real (non-demo) data:

- [ ] `APP_ENV=production`, `DEBUG=false`, strong secrets, CORS whitelist, Alembic head
- [ ] Health deep checks green; no demo tenants / seed passwords
- [ ] Core ERP smoke on a real staging tenant (inventory → sale → payment path)

Checking these boxes does **not** authorize Offline Complete, paid billing Complete,
ADR-005 Complete, store-scoped RBAC Complete, 7-day VERIFIED, or go-live attestation.

---

## 5. Sign-off table (leave blank until ops evidence exists)

| Gate | Owner | Staging evidence link | Prod enable approved? | Complete claimed? |
|------|-------|----------------------|----------------------|-------------------|
| SEC-M2 cookies | | | [ ] | N/A (FIXED; enable ≠ reopen) |
| Paid billing provider soak | | | [ ] | **No** — Complete MISSING |
| Entitlement gate ON | | | [ ] | **No** — Complete MISSING |
| ADR-005 scope ON | | | [ ] | **No** — Complete MISSING |
| Wipe-via-push browser | | | [ ] | **No** — push Complete MISSING |
| 7-day physical matrix | | | [ ] | **No** — VERIFIED MISSING |
| Go-live / Offline Complete | | | [ ] | **No** — MISSING |

---

## 6. Remaining ops-only next steps (Completes path)

No further engineering slices are required to unlock Completes for these gates —
only operator evidence on staging/real tills:

1. Staging VAPID secrets + **real till browser** wipe-via-push proof
   (`offline_wipe_push_staging_checklist.md`, `OFFLINE_WEB_PUSH_VAPID_OPS.md`).
   Do **not** re-attempt in cloud-agent Chrome (PushManager/FCM blocked).
2. Operator 7-day physical offline matrix
   (`OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`) — required before any
   **7-day VERIFIED** claim; Offline Complete remains a separate attestation.
3. Staging: real billing provider keys + price map + signed webhook soak
   (`PAID_BILLING_PROVIDER_OPS.md`); entitlement gate ON only after
   mirror→access evidence on the allowlist.
4. Staging ADR-005 `STORE_MEMBERSHIP_SCOPE_ENABLED=true` soak
   (`adr005_staging_soak_checklist.md`); product sign-off before any prod default ON.
5. SEC-M2 cookie staging enable when ready (`sec_m2_staging_soak_checklist.md`)
   — FIXED finding; enable is ops cutover only.
6. Do **not** resume continuum RBAC dumps. Do **not** claim Offline Complete /
   7-day VERIFIED / go-live / paid billing Complete / ADR-005 Complete /
   store-scoped RBAC Complete from this checklist or flag flips alone.
