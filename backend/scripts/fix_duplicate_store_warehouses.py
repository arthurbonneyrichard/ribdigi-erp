"""Find stores that have more than one linked warehouse and unlink the extras.

POS reads one warehouse per store (`stores.warehouse_for_store`). Creating or
editing a warehouse now refuses a second link, but older data can still have
two. This keeps the warehouse POS already uses and clears `store_id` on the
others. Stock stays in the unlinked warehouse; move it with a stock transfer
if it should be sold at the till.

Dry run by default. Pass --apply to write.

Usage:
  docker compose exec backend python scripts/fix_duplicate_store_warehouses.py
  docker compose exec backend python scripts/fix_duplicate_store_warehouses.py --apply
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import func, select

from app import models as m
from app.db import SessionLocal
from app.stores import warehouse_for_store


async def main(apply: bool) -> int:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(m.Warehouse).where(m.Warehouse.store_id.is_not(None)).order_by(m.Warehouse.tenant_id, m.Warehouse.code)
            )
        ).scalars().all()
        by_store: dict[tuple[str, str], list[m.Warehouse]] = defaultdict(list)
        for wh in rows:
            by_store[(wh.tenant_id, wh.store_id)].append(wh)

        changed = 0
        for (tenant_id, store_id), whs in by_store.items():
            if len(whs) < 2:
                continue
            keep = await warehouse_for_store(db, tenant_id, store_id)
            for wh in whs:
                if wh.id == keep.id:
                    continue
                qty = (
                    await db.execute(
                        select(func.coalesce(func.sum(m.WarehouseStock.quantity), 0)).where(
                            m.WarehouseStock.warehouse_id == wh.id
                        )
                    )
                ).scalar_one()
                print(f"tenant {tenant_id} store {store_id}: keep {keep.code}, unlink {wh.code} (stock on hand {qty})")
                if apply:
                    wh.store_id = None
                changed += 1
        if apply:
            await db.commit()
        print(f"{changed} warehouse link(s) {'removed' if apply else 'would be removed (dry run; pass --apply)'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--apply" in sys.argv[1:])))
