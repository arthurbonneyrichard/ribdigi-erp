# DBA stamp notes — unique 0122–0125 after hotel 0121

Do **not** wipe Postgres. Do **not** rewrite pre-0105 migrations.
This is **not** a go-live Complete.

## Target graph (single head)

`…` → `20260920_0115` → `20260928_0116` → … → `20260928_0121` (hotel events)
→ **`20260928_0122`** → **`20260928_0123`** → **`20260928_0124`** → **`20260928_0125`**

| File | Revision | Schema |
|------|----------|--------|
| `20260928_0122_product_minimum_stock.py` | `20260928_0122` | `products.minimum_stock`, `warehouse_stocks.minimum_stock` |
| `20260928_0123_coupons_income_product_created.py` | `20260928_0123` | `products.created_by`, coupon + other_income tables |
| `20260928_0124_sales_invoice_coupon_id.py` | `20260928_0124` | `sales_invoices.coupon_id` + same tables IF MISSING |
| `20260928_0125_printer_routing.py` | `20260928_0125` | printers / print agents / jobs |

`20260917_0106` is POS `client_request_id`, not `20260928_0106`.

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
       to_regclass('public.printers') AS printers;
```

Fresh DB: `alembic upgrade head`.

## Already ALTERed `sales_invoices.coupon_id`

0124 is IF NOT EXISTS. If the column (and optional index `ix_sales_invoices_coupon_id`) already exists, 0124 will not re-ADD it.

- If `alembic_version` is still `20260928_0121` or earlier on the linear chain: `alembic upgrade head`.
- If version is a **removed** id (`20260928_0106` or an old duplicate `20260928_0122` that meant coupons, not minimum_stock), **do not** `upgrade` until you stamp a proven ancestor (usually `20260928_0121`), then `upgrade head`. Idempotent steps skip existing objects.

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

If `minimum_stock` already exists, stamp `20260928_0124` then `upgrade head` (0125).

### Old meaning of `20260928_0123` (printer)

If you stamped `20260928_0123` when that revision **was** printer routing:

```text
alembic stamp 20260928_0121
alembic upgrade 20260928_0124
alembic stamp 20260928_0125
```

(`upgrade 0124` applies min-stock + coupons + coupon_id; 0125 is a no-op if printers exist.)

### Bogus `20260928_0106` (coupon vs printer)

Same as before: use `sales_coupons` vs `printers` to see which sibling ran, stamp `20260928_0121`, `upgrade head` (idempotent).

Never `DROP DATABASE`.
