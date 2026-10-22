# DBA stamp notes — unique 0122–0126 after hotel 0121

Do **not** wipe Postgres. Do **not** rewrite pre-0105 migrations.
This is **not** a go-live Complete.

## Target graph (single head)

`…` → `20260920_0115` → `20260928_0116` → … → `20260928_0121` (hotel events)
→ **`20260928_0122`** → **`20260928_0123`** → **`20260928_0124`** → **`20260928_0125`**
→ **`20260930_0126`**

| File | Revision | Schema |
|------|----------|--------|
| `20260928_0122_product_minimum_stock.py` | `20260928_0122` | `products.minimum_stock`, `warehouse_stocks.minimum_stock` |
| `20260928_0123_coupons_income_product_created.py` | `20260928_0123` | `products.created_by`, coupon + other_income tables |
| `20260928_0124_sales_invoice_coupon_id.py` | `20260928_0124` | `sales_invoices.coupon_id` + same tables IF MISSING |
| `20260928_0125_printer_routing.py` | `20260928_0125` | printers / print agents / jobs |
| `20260930_0126_perf_indexes.py` | `20260930_0126` | `ix_products_tenant_id_is_active`, `ix_auth_sessions_tenant_id_user_id_revoked_at` (IF NOT EXISTS) |

`20260917_0106` is POS `client_request_id`, not `20260928_0106`.
`20260816_0106` was a colliding page-speed index file (revising `20260816_0105`); indexes now live on **0126**. Printer routing is **0125**, not 0106.

## Inspect

```sql
SELECT version_num FROM alembic_version;

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'sales_invoices' AND column_name = 'coupon_id';

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'products'
  AND column_name IN ('minimum_stock', 'created_by');

SELECT to_regclass('public.sales_coupons') AS coupons,
       to_regclass('public.printers') AS printers,
       to_regclass('public.ix_products_tenant_id_is_active') AS products_active_idx;
```

Fresh DB: `alembic upgrade head`.

## Already ALTERed `sales_invoices.coupon_id`

0124 is IF NOT EXISTS. If the column (and optional index `ix_sales_invoices_coupon_id`) already exists, 0124 will not re-ADD it.

- If `alembic_version` is still `20260928_0121` or earlier on the linear chain: `alembic upgrade head`.
- If version is a **removed** id (`20260928_0106`, bogus `20260816_0106` index revision, or an old duplicate `20260928_0122` that meant coupons, not minimum_stock), **do not** `upgrade` until you stamp a proven ancestor (usually `20260928_0121` if at the hotel tail, or `20260816_0105` if stuck on the speed-agent 0106), then `upgrade head`. Idempotent steps skip existing objects. If indexes already exist, 0126 is IF NOT EXISTS.

### Old meaning of `20260928_0122` (coupon IF MISSING, from an earlier linearize)

If you stamped `20260928_0122` when that revision **was** coupon tables + `coupon_id` (not `minimum_stock`):

1. Confirm `coupon_id` / `sales_coupons` exist.
2. Stamp hotel head, apply min-stock, skip coupon revisions, then printers:

```text
alembic stamp 20260928_0121
alembic upgrade 20260928_0122
alembic stamp 20260928_0124
alembic upgrade head
```

If `minimum_stock` already exists, stamp `20260928_0124` then `upgrade head` (0125 then 0126).

### Old meaning of `20260928_0123` (printer)

If you stamped `20260928_0123` when that revision **was** printer routing:

```text
alembic stamp 20260928_0121
alembic upgrade 20260928_0124
alembic stamp 20260928_0125
alembic upgrade head
```

(`upgrade 0124` applies min-stock + coupons + coupon_id; 0125 is a no-op if printers exist; `upgrade head` applies 0126 indexes IF NOT EXISTS.)

### Bogus `20260928_0106` (coupon vs printer)

Same as before: use `sales_coupons` vs `printers` to see which sibling ran, stamp `20260928_0121`, `upgrade head` (idempotent).

### Bogus `20260816_0106` (page-speed indexes)

That file forked `20260816_0105` (real next rev is `20260917_0105`). If `alembic_version` is `20260816_0106`:

1. Confirm indexes: `to_regclass('public.ix_products_tenant_id_is_active')`.
2. Stamp `20260816_0105`, then `alembic upgrade head`. 0126 will skip existing indexes.

Never `DROP DATABASE`.
