# ERP Completion Status

**Last updated:** 2026-09-15 (Cash/bank store skip + Reports warehouse↔header store parity)  
**Overall estimate:** ~90%

## This session

### Cash / bank / reconcile — skip (honest)

`Account` / `BankStatement` / `BankStatementLine` / `CashTransfer` have **no `store_id`**. Liquid accounts and bank feeds are company (tenant) books; cash transfers move between liquid GL accounts only. Adding API `store_id` would invent a filter that cannot be applied without lying. **Not wired** to Accounting Cash & Bank / Reconcile `useStoreContext`.

### Reports warehouse filter parity (shipped instead)

- Inventory + Purchases warehouse `<select>` options filter by **`effectiveStoreId = page store || header store`**, so a header-only store selection still scopes warehouse pickers.
- Selecting a warehouse with `store_id` syncs page store **and** shell header (`setCtxStoreId`) on Inventory and Purchases.
- Clearing / changing to a store that does not own the selected warehouse clears `warehouseId`.

## Prior (this branch)

- Dashboard KPI `store_id`; Accounting P&L / TB / BS / CF honor header store; Reports empty page store falls back to header in `qs` / BS / TB.

## Known gaps (honest)

- Cash / bank / reconcile remain **tenant-wide** (by design until liquid accounts gain store attribution).
- Branch / department page filters still separate from header store where UIs expose them.
- Expense / AI analysis store filters where APIs already support `store_id` but UI is incomplete.

## Next recommended gaps

1. Branch / department filter consistency with header store on Reports / Accounting where APIs exist.
2. Expense / AI store filter UI where APIs already accept `store_id`.
3. Store-attributed liquid accounts (schema) if product wants cash/bank by store — not a fake query param.
