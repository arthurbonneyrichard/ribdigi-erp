# Market-ready launch pack (Commercial MVP — conditional)

**Product:** RIBDIGI BUSINESS ERP — Commercial MVP v1.0  
**Verdict:** **Market-ready with conditions** (commercial MVP packaging)  
**Not:** go-live Complete · Offline Complete · 7-day VERIFIED · paid billing Complete  

This is the single operator entrypoint for sales demos, staging flag enable, and
honest Completes status. Deep runbooks stay linked — do not duplicate dumps here.

| Surface | Path |
|---------|------|
| Demo account seed | [`DEMO_ACCOUNT.md`](DEMO_ACCOUNT.md) |
| Go-live ops gates | [`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md) |
| Store-scoped RBAC Complete | [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md) |
| Intentional ALLOWs (accepted) | [`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md) |
| Local soak evidence | [`STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md`](STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md) |
| Commercial readiness | [`COMMERCIAL_READINESS_REPORT_2026-08-23.md`](COMMERCIAL_READINESS_REPORT_2026-08-23.md) |
| Launch hygiene smoke | [`LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md) |

---

## 1. Completes honesty (customer-facing readiness)

| Claim | Status | Notes |
|-------|--------|-------|
| Security M1–M5 + L2 | **FIXED** / **HARDENED** | Cookie flag default OFF = ops cutover |
| ADR-005 membership | **Complete** | Flag default OFF |
| Store-scoped RBAC | **Complete** | Flag default OFF; ALLOWs product-accepted |
| Continuum safe dump backlog | **NONE** | Do not resume dump spam |
| Overall RBAC | **PARTIAL** / Complete **MISSING** | Approval hardening landed ≠ overall Complete |
| Offline / push | **PARTIAL** | Poll-path engineering-ready; push + Complete ops-blocked |
| Offline Complete + 7-day VERIFIED | **MISSING** | Ops physical matrix + attestation |
| Paid billing | **PARTIAL** | Mock soak ready; live Stripe Complete ops-blocked |
| Go-live / attestation | **MISSING** | Staging cutovers below |
| **Commercial MVP market-ready** | **Conditional** | Ship demos + pilots with staging cutovers listed |

**Market-ready with conditions** means: engineering Completes required for a
commercial MVP demo / controlled pilot are landed; revenue go-live and Offline
endurance Completes remain ops-blocked and must not be sold as finished.

---

## 2. How to run a sales demo

### 2A. Seed the demo tenant

Follow [`DEMO_ACCOUNT.md`](DEMO_ACCOUNT.md). From `backend/` (migrations applied):

```bash
ALLOW_DEMO_TENANT_SEED=true \
  DEMO_OWNER_PASSWORD='YourStrongPass1!' \
  DEMO_CASHIER_PASSWORD='YourStrongPass1!' \
  python -m scripts.seed_demo_tenant
```

Docker Compose:

```bash
docker compose exec -e ALLOW_DEMO_TENANT_SEED=true \
  -e DEMO_OWNER_PASSWORD='YourStrongPass1!' \
  -e DEMO_CASHIER_PASSWORD='YourStrongPass1!' \
  backend python -m scripts.seed_demo_tenant
```

### 2B. Credentials artifact (ops only — never commit)

Write operator copies to:

`/opt/cursor/artifacts/demo_account_credentials.md`

Include tenant slug `demo`, owner/cashier emails, and the passwords you set via
env. Do **not** commit plaintext passwords to git.

### 2C. Login path

1. Open the app login page (`FRONTEND_URL`).
2. Tenant slug: `demo`
3. Owner: `owner@demo.ribdigi.app` (full ERP + POS) or cashier: `cashier@demo.ribdigi.app`
4. Password: from the ops credentials artifact

Sample catalog (`DEMO-001`…), Demo Walk-in Customer, and an open POS shift for
the cashier are included when seed defaults are left on.

### 2D. Optional: membership-scope demo

For demos that show cashier fail-closed / manager union:

1. Set `STORE_MEMBERSHIP_SCOPE_ENABLED=true` on the **demo/staging** API only.
2. Restart API; confirm health.
3. Demo seed already creates `user_store_memberships` for owner + cashier.
4. Rollback: set flag `false` (membership rows retained).

Prod templates keep the flag **false**. Enabling it is an ops cutover — Completes
already claimed; enable ≠ reopen.

---

## 3. Staging flag cutovers (ops-blocked Completes)

| Flag | Template default | When to enable |
|------|------------------|----------------|
| `AUTH_HTTPONLY_COOKIES_ENABLED` | `false` | After SEC-M2 staging soak |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` | `false` | After ADR-005 staging soak pack |
| `OFFLINE_PUSH_ENABLED` + VAPID keys | `false` / empty | After real till-browser wipe proof |
| `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` | `false` | After live Stripe mirror→access soak |
| `BILLING_PROVIDER*` / checkout | empty / `false` | Live Stripe keys in secrets (never git) |
| `ALLOW_DEMO_TENANT_SEED` | `false` | Local/staging demos only — **never** production |
| `ALLOW_PUBLIC_TENANT_SIGNUP` | `false` | Keep false for production MVP |

Runbooks:

- Cookies: `sec_m2_staging_soak_checklist.md`
- Membership: `adr005_staging_soak_checklist.md` + evidence template
- Offline push: `offline_wipe_push_staging_checklist.md` (poll alternative: `OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md`)
- 7-day: `OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`
- Billing: `PAID_BILLING_PROVIDER_OPS.md` + `paid_billing_staging_soak_checklist.md`

---

## 4. Customer-facing readiness language (approved)

Use:

> RIBDIGI BUSINESS ERP Commercial MVP is **market-ready with conditions**:
> core ERP, store entitlements, ADR-005 membership, and store-scoped RBAC are
> Complete in engineering (membership-scope flag defaults OFF until staging
> enable). Offline endurance Completes, live Stripe billing Completes, and
> go-live attestation remain **ops cutovers** on staging — not unfinished
> product placeholders.

Do **not** say: Offline Complete, 7-day VERIFIED, paid billing Complete, or
go-live Complete.

---

## 5. Pre-demo / pre-pilot smoke

From [`LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md) §§1–3 on the target env:

- [ ] Health deep checks green; Alembic head
- [ ] Demo seed only on non-production; prod keeps seed flags false
- [ ] Core path: inventory → sale → payment on demo or staging tenant
- [ ] If membership flag ON: cashier assigned store only; foreign POS denied

Checking these boxes does **not** authorize go-live Completes.

---

## 6. Remaining ops conditions (block full go-live)

1. Staging ADR-005 flag-ON soak on a **non-demo** tenant + filled evidence
2. SEC-M2 cookie staging enable when ready
3. Live Stripe keys + signed webhook soak; entitlement gate only after mirror health
4. Real till-browser wipe-via-push (or accept poll-path only for pilot Offline)
5. 7-day physical offline matrix + Offline Complete attestation
6. Production cutover + LAUNCH §7 sign-off

Until §6 is done, ship as **commercial MVP market-ready (conditional)** — not
go-live Complete.
