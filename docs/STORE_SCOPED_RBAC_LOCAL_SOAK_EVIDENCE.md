# Store-scoped RBAC — local membership-scope soak evidence

**Status:** **PASS** (engineering local / automated evidence)  
**Does not:** flip production `STORE_MEMBERSHIP_SCOPE_ENABLED` default; claim Offline / go-live / paid billing Completes  
**Parent:** [`STORE_SCOPED_RBAC_COMPLETE_REMAINING.md`](STORE_SCOPED_RBAC_COMPLETE_REMAINING.md)  
**Product ALLOWs:** [`STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md`](STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md)  
**Operator staging (separate):** [`adr005_staging_soak_checklist.md`](adr005_staging_soak_checklist.md)

## Honesty

| Claim | After this local soak |
|-------|------------------------|
| ADR-005 membership Complete | Already **Complete** |
| Store-scoped RBAC Complete | **Complete** when combined with empty residual + ALLOW accept + living matrix (this soak is membership-scope evidence) |
| Prod flag default ON | Still **false** (ops cutover) |
| Offline / 7-day / go-live / paid billing | Still **MISSING** / PARTIAL |

Local automated soak parallels ADR-005 Phase E and SEC-M2: **Complete ≠ production default ON**.

## Automated evidence commands

```bash
cd backend && .venv/bin/pytest -q \
  tests/test_adr005_membership_scope_soak.py \
  tests/test_store_scope_rbac_matrix.py \
  tests/test_store_membership_scaffold.py \
  tests/test_membership_expires_at.py \
  tests/test_rbac_elevation_break_glass.py \
  tests/test_seed_demo_tenant.py \
  tests/test_store_scoped_rbac_demo_soak.py \
  -m "store_scope or not store_scope"

# Focused Completes spine:
cd backend && PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_adr005_membership_scope_soak.py \
  tests/test_store_scope_rbac_matrix.py \
  tests/test_store_scoped_rbac_demo_soak.py
```

Frontend membership admin / POS bind:

```bash
cd frontend && node --test lib/storeMembershipAdmin.test.mjs lib/posStoreBinding.test.mjs
```

## Demo-seed local soak (optional DB)

Uses the opt-in demo tenant (`docs/DEMO_ACCOUNT.md`). Requires
`ALLOW_DEMO_TENANT_SEED=true` and a non-production `APP_ENV`.

```bash
# From backend/ with DATABASE_URL set
ALLOW_DEMO_TENANT_SEED=true \
  DEMO_OWNER_PASSWORD='DemoOwner-ChangeMe1!' \
  DEMO_CASHIER_PASSWORD='DemoCashier-ChangeMe1!' \
  python -m scripts.seed_demo_tenant

# Then run demo soak pytest (flag ON via monkeypatch; does not mutate .env defaults)
PYTHONPATH=. .venv/bin/pytest -q tests/test_store_scoped_rbac_demo_soak.py
```

Credentials artifact path for sales demos (ops only — **not** committed):
`/opt/cursor/artifacts/demo_account_credentials.md`

## Cover sheet (local run)

| Field | Value |
|-------|-------|
| Environment | Local / CI pytest (+ optional demo seed DB) |
| `STORE_MEMBERSHIP_SCOPE_ENABLED` in templates | `false` (expected) |
| Flag during soak | `true` (monkeypatch / test settings only) |
| Product ALLOW policy | Accepted — `STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md` |
| Residual dump backlog | NONE |
| Verdict | **PASS** |

## Checks covered

| Check | Evidence |
|-------|----------|
| Flag default OFF | `test_adr005_soak_flag_still_defaults_off_ops_enable` / matrix flag default |
| Honesty Complete flags | soak + matrix + demo soak (`store_scoped_rbac_complete_claimed=true`) |
| Manager union flag ON | soak + matrix living case |
| Cashier fail-closed empty / assigned | soak + matrix |
| Intentional ALLOWs still allowed | matrix `intentional_allow` + ops hardening tests |
| Demo seed memberships + flag-ON visibility | `test_store_scoped_rbac_demo_soak.py` |
| Living matrix spine | `test_store_scope_rbac_matrix.py` |

## Staging note

Fill [`ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md`](ADR005_STAGING_SOAK_EVIDENCE_TEMPLATE.md)
on a **real staging tenant** before enabling the flag in staging/prod secrets.
That ops run does **not** reopen store-scoped RBAC Complete.
