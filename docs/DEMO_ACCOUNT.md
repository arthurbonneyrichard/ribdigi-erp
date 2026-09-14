# Live customer-demo account (ops)

**Status:** Opt-in seed packaging — **not** Offline Complete, go-live Complete, paid billing Complete, store-scoped RBAC Complete, or 7-day VERIFIED.

Repeatable seed for a **live customer demo** tenant: one company, one store, company-admin “owner” login, optional cashier, light sample catalog, and an open POS shift for the cashier so demos are not empty.

## Security posture

| Flag | Production | Demo seed |
|------|------------|-----------|
| `ALLOW_PUBLIC_TENANT_SIGNUP` | **false** (unchanged) | Not required / not flipped by this seed |
| `ALLOW_DEMO_TENANT_SEED` | **false** | Must be `true` explicitly on local/staging |
| `ALLOW_DEVELOPMENT_SEED` | **false** | Separate local-dev seed (`scripts/seed.py`); not used here |
| `APP_ENV=production` | — | Seed **refuses** to run |

Do **not** commit plaintext demo passwords to git. Override with env vars and store operator copies only in local/ops artifacts (e.g. `/opt/cursor/artifacts/demo_account_credentials.md`).

## Defaults (identifiers safe to document)

| Field | Default |
|-------|---------|
| Tenant slug | `demo` |
| Company | `Ribdigi Demo` (`DEMO`) |
| Branch | `Demo HQ` (`HQ`) |
| Store | `Demo Store` (`DEMO-01`) |
| Warehouse | `Demo Warehouse` (`DEMO-WH`) |
| Owner email | `owner@demo.ribdigi.app` |
| Owner role | `company_admin` |
| Cashier email | `cashier@demo.ribdigi.app` |
| Cashier role | `cashier` |

Password defaults (change after first login; override via env):

- `DEMO_OWNER_PASSWORD` → default `DemoOwner-ChangeMe1!`
- `DEMO_CASHIER_PASSWORD` → default `DemoCashier-ChangeMe1!`

## How to create / reset

From `backend/` (Compose service or local venv with `DATABASE_URL` pointed at the target DB).
Apply migrations first (`alembic upgrade head`) so schema matches models (e.g. membership columns).

```bash
# Plan only (no writes)
ALLOW_DEMO_TENANT_SEED=true python -m scripts.seed_demo_tenant --dry-run

# Create or refresh (idempotent)
ALLOW_DEMO_TENANT_SEED=true \
  DEMO_OWNER_PASSWORD='YourStrongPass1!' \
  DEMO_CASHIER_PASSWORD='YourStrongPass1!' \
  python -m scripts.seed_demo_tenant

# Reset passwords on an existing demo tenant
ALLOW_DEMO_TENANT_SEED=true \
  DEMO_FORCE_PASSWORD=1 \
  DEMO_OWNER_PASSWORD='YourStrongPass1!' \
  DEMO_CASHIER_PASSWORD='YourStrongPass1!' \
  python -m scripts.seed_demo_tenant
```

Docker Compose example:

```bash
docker compose exec -e ALLOW_DEMO_TENANT_SEED=true \
  -e DEMO_OWNER_PASSWORD='YourStrongPass1!' \
  -e DEMO_CASHIER_PASSWORD='YourStrongPass1!' \
  backend python -m scripts.seed_demo_tenant
```

### Useful env overrides

| Env | Purpose |
|-----|---------|
| `DEMO_TENANT_SLUG` | Tenant slug (default `demo`) |
| `DEMO_COMPANY_NAME` / `DEMO_STORE_NAME` | Display names |
| `DEMO_OWNER_EMAIL` / `DEMO_CASHIER_EMAIL` | Login emails |
| `DEMO_SEED_SAMPLE_DATA` | `true`/`false` — products, VAT, GL stubs, parties (default true) |
| `DEMO_SEED_OPEN_SHIFT` | `true`/`false` — open POS session for cashier (default true) |
| `DEMO_FORCE_PASSWORD` | `1` to rewrite password hashes on re-run |
| `DEMO_CURRENCY` | Default `GHS` |

## Login

1. Open the app login page.
2. Tenant: `demo` (slug).
3. Email: `owner@demo.ribdigi.app` (full ERP + POS) or `cashier@demo.ribdigi.app` (cashier path).
4. Password: value from env / ops artifact (not from git).

## Sample data included

When `DEMO_SEED_SAMPLE_DATA=true` (default):

- VAT 15% (default tax)
- GL stubs: Cash `1000`, Bank `1100`, Sales Revenue `4000`
- Products: `DEMO-001` Rice 5kg, `DEMO-002` Cooking Oil 1L, `DEMO-003` Soft Drink 500ml (with warehouse stock)
- Parties: Demo Walk-in Customer, Demo Supplier
- In-app notification “Demo tenant ready”

When `DEMO_SEED_OPEN_SHIFT=true` (default): one **open** POS session for the cashier on Demo Store (`opening_cash=200`) so POS can be shown immediately. Re-runs reuse an existing open session.

Also creates optional `user_store_memberships` rows for owner + cashier (helpful if `STORE_MEMBERSHIP_SCOPE_ENABLED` is on). That does **not** claim ADR-005 / store-scoped RBAC Complete.

## Honesty

This seed is an **ops/demo convenience**. Packaging it does **not** claim:

- Offline Complete / 7-day VERIFIED
- Go-live / attestation Complete
- Paid billing / checkout Complete
- Store-scoped RBAC Complete
- Public signup as a production path

Keep `ALLOW_PUBLIC_TENANT_SIGNUP=false` in production templates.

## Related code

| Piece | Path |
|-------|------|
| Seed logic | `backend/app/demo_tenant_seed.py` |
| CLI | `backend/scripts/seed_demo_tenant.py` |
| Local-dev seed (different) | `backend/scripts/seed.py` (`ALLOW_DEVELOPMENT_SEED`) |
| Tests | `backend/tests/test_seed_demo_tenant.py` |
