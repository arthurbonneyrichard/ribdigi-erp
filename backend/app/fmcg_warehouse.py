"""FMCG warehouse layout: zones, bins, put-away, moves, bin counts and pick guidance.

Bins are a location layer over consolidated stock (``products.stock_qty``). Putting stock into a
bin, moving it or counting it never changes how much stock the company has, so none of it posts to
the books. Stock leaving through FMCG delivery, batch write-off and van losses is taken out of the
bins too (``consume``), earliest pick order first. Stock that leaves by another route (for example a
retail sale) can leave a bin over-stated; the warehouse report lists those products so a count can
correct them.

Rules: a held or expired batch may only sit in a quarantine zone, and a quarantine zone takes
nothing else. A bin cannot hold more than its capacity. Stock is never picked from a quarantine zone.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import pharmacy as pharmacy_svc
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

ZONE_TYPES = ("ambient", "cold", "bulk", "quarantine", "receiving", "dispatch", "returns")
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,29}$")


def _qty(value) -> float:
    return money_json(round(float(value or 0), 3))


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_location", entity_id=entity_id, details=details,
    )


# ---------------------------------------------------------------- locations

async def _warehouse(db, tenant_id: str, warehouse_id: str) -> m.Warehouse:
    row = (
        await db.execute(select(m.Warehouse).where(m.Warehouse.id == warehouse_id, m.Warehouse.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return row


async def _location(db, tenant_id: str, location_id: str, *, lock: bool = False) -> m.FmcgLocation:
    stmt = select(m.FmcgLocation).where(m.FmcgLocation.id == location_id, m.FmcgLocation.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return row


async def create_location(
    db, *, tenant_id: str, warehouse_id: str, kind: str, code: str, name: str, parent_id: str | None,
    zone_type: str | None, capacity: float | None, pick_order: int, user_id,
) -> dict:
    await _warehouse(db, tenant_id, warehouse_id)
    clean = (code or "").strip().upper()
    if not CODE_RE.match(clean):
        raise HTTPException(status_code=422, detail="Code is letters, numbers, dots, dashes, up to 30 characters")
    label = require_honest_narrative(name, label="name", max_length=120)
    if kind == "zone":
        if zone_type not in ZONE_TYPES:
            raise HTTPException(status_code=422, detail=f"A zone needs a type: {', '.join(ZONE_TYPES)}")
        if parent_id or capacity is not None:
            raise HTTPException(status_code=422, detail="A zone has no parent and no capacity; set capacity on bins")
    elif kind == "bin":
        if not parent_id:
            raise HTTPException(status_code=422, detail="A bin sits inside a zone")
        zone = await _location(db, tenant_id, parent_id)
        if zone.kind != "zone" or zone.warehouse_id != warehouse_id or not zone.is_active:
            raise HTTPException(status_code=409, detail="Pick an active zone in the same warehouse")
        if zone_type:
            raise HTTPException(status_code=422, detail="A bin takes its type from its zone")
    else:
        raise HTTPException(status_code=422, detail="kind must be zone or bin")
    clash = (
        await db.execute(
            select(m.FmcgLocation.id).where(
                m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.warehouse_id == warehouse_id,
                m.FmcgLocation.code == clean,
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="That code is already used in this warehouse")
    row = m.FmcgLocation(
        tenant_id=tenant_id, warehouse_id=warehouse_id, parent_id=parent_id, kind=kind, code=clean, name=label,
        zone_type=zone_type if kind == "zone" else None, capacity=capacity, pick_order=pick_order,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_location_created", row.id, {"kind": kind, "code": clean})
    return await _present(db, row)


async def _bin_total(db, tenant_id: str, bin_id: str) -> float:
    return _qty(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.FmcgBinStock.quantity), 0)).where(
                    m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.bin_id == bin_id
                )
            )
        ).scalar_one()
    )


async def _present(db, row: m.FmcgLocation) -> dict:
    data = {
        "id": row.id, "warehouse_id": row.warehouse_id, "parent_id": row.parent_id, "kind": row.kind,
        "code": row.code, "name": row.name, "zone_type": row.zone_type, "pick_order": row.pick_order,
        "capacity": money_json(row.capacity) if row.capacity is not None else None, "is_active": row.is_active,
    }
    if row.kind == "bin":
        used = await _bin_total(db, row.tenant_id, row.id)
        data["used"] = used
        data["utilisation_pct"] = round(100 * used / float(row.capacity), 1) if row.capacity else None
    return data


async def set_active(db, *, tenant_id: str, location_id: str, is_active: bool, user_id) -> dict:
    row = await _location(db, tenant_id, location_id, lock=True)
    if not is_active:
        if row.kind == "bin" and await _bin_total(db, tenant_id, row.id) > 0:
            raise HTTPException(status_code=409, detail="Move the stock out of this bin first")
        if row.kind == "zone":
            held = (
                await db.execute(
                    select(func.coalesce(func.sum(m.FmcgBinStock.quantity), 0))
                    .join(m.FmcgLocation, m.FmcgLocation.id == m.FmcgBinStock.bin_id)
                    .where(m.FmcgBinStock.tenant_id == tenant_id, m.FmcgLocation.parent_id == row.id)
                )
            ).scalar_one()
            if float(held or 0) > 0:
                raise HTTPException(status_code=409, detail="This zone still has stock in its bins")
    row.is_active = is_active
    await _audit(db, tenant_id, user_id, "fmcg_location_active", row.id, {"code": row.code, "is_active": is_active})
    await db.flush()
    return await _present(db, row)


async def list_tree(db, *, tenant_id: str, warehouse_id: str) -> list[dict]:
    await _warehouse(db, tenant_id, warehouse_id)
    rows = (
        await db.execute(
            select(m.FmcgLocation)
            .where(m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.warehouse_id == warehouse_id)
            .order_by(m.FmcgLocation.pick_order, m.FmcgLocation.code)
        )
    ).scalars().all()
    used = dict(
        (
            await db.execute(
                select(m.FmcgBinStock.bin_id, func.coalesce(func.sum(m.FmcgBinStock.quantity), 0))
                .where(m.FmcgBinStock.tenant_id == tenant_id)
                .group_by(m.FmcgBinStock.bin_id)
            )
        ).all()
    )
    zones = []
    for z in [r for r in rows if r.kind == "zone"]:
        bins = []
        for b in [r for r in rows if r.parent_id == z.id]:
            u = _qty(used.get(b.id, 0))
            bins.append(
                {
                    "id": b.id, "code": b.code, "name": b.name, "is_active": b.is_active, "used": u,
                    "capacity": money_json(b.capacity) if b.capacity is not None else None,
                    "utilisation_pct": round(100 * u / float(b.capacity), 1) if b.capacity else None,
                }
            )
        zones.append(
            {
                "id": z.id, "code": z.code, "name": z.name, "zone_type": z.zone_type, "is_active": z.is_active,
                "pick_order": z.pick_order, "bins": bins, "used": _qty(sum(b["used"] for b in bins)),
            }
        )
    return zones


async def contents(db, *, tenant_id: str, bin_id: str, blind: bool = False) -> dict:
    loc = await _location(db, tenant_id, bin_id)
    if loc.kind != "bin":
        raise HTTPException(status_code=422, detail="That is a zone, not a bin")
    rows = (
        await db.execute(
            select(m.FmcgBinStock, m.Product, m.ProductBatch)
            .join(m.Product, m.Product.id == m.FmcgBinStock.product_id)
            .outerjoin(m.ProductBatch, m.ProductBatch.id == m.FmcgBinStock.batch_id)
            .where(m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.bin_id == bin_id, m.FmcgBinStock.quantity > 0)
            .order_by(m.Product.name)
        )
    ).all()
    items = []
    for stock, product, batch in rows:
        item = {
            "product_id": product.id, "product_name": product.name, "batch_id": stock.batch_id,
            "batch_number": batch.batch_number if batch else None,
            "expiry_date": batch.expiry_date.date().isoformat() if batch and batch.expiry_date else None,
        }
        if not blind:
            item["quantity"] = _qty(stock.quantity)
        items.append(item)
    data = await _present(db, loc)
    data["items"] = items
    data["blind"] = blind
    if blind:
        data.pop("used", None)
        data.pop("utilisation_pct", None)
    return data


async def scan(db, *, tenant_id: str, code: str) -> dict:
    clean = (code or "").strip().upper()
    rows = (
        await db.execute(
            select(m.FmcgLocation).where(
                m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.code == clean, m.FmcgLocation.kind == "bin"
            )
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No bin with that code")
    if len(rows) > 1:
        raise HTTPException(status_code=409, detail="That code exists in more than one warehouse. Pick the warehouse first")
    return await contents(db, tenant_id=tenant_id, bin_id=rows[0].id)


# ---------------------------------------------------------------- stock in bins

async def _unplaced(db, tenant_id: str, product_id: str, batch_id: str | None) -> float:
    """Stock on hand that is not yet in any bin. For a batch, that batch's quantity less what is binned."""
    if batch_id:
        batch = (
            await db.execute(
                select(m.ProductBatch).where(m.ProductBatch.id == batch_id, m.ProductBatch.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if batch is None or batch.product_id != product_id:
            raise HTTPException(status_code=404, detail="Batch not found for that product")
        total = float(batch.quantity or 0)
        binned = (
            await db.execute(
                select(func.coalesce(func.sum(m.FmcgBinStock.quantity), 0)).where(
                    m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.batch_id == batch_id
                )
            )
        ).scalar_one()
        return _qty(total - float(binned or 0))
    product = (
        await db.execute(select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    binned = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgBinStock.quantity), 0)).where(
                m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.product_id == product_id
            )
        )
    ).scalar_one()
    return _qty(float(product.stock_qty or 0) - float(binned or 0))


async def _stock_row(db, tenant_id: str, bin_id: str, product_id: str, batch_id: str | None, *, create: bool):
    stmt = select(m.FmcgBinStock).where(
        m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.bin_id == bin_id, m.FmcgBinStock.product_id == product_id,
        (m.FmcgBinStock.batch_id == batch_id) if batch_id else m.FmcgBinStock.batch_id.is_(None),
    ).with_for_update()
    row = (await db.execute(stmt)).scalars().first()
    if row is None and create:
        row = m.FmcgBinStock(tenant_id=tenant_id, bin_id=bin_id, product_id=product_id, batch_id=batch_id, quantity=0)
        db.add(row)
        await db.flush()
    return row


async def _check_destination(db, tenant_id: str, target: m.FmcgLocation, product_id: str, batch_id: str | None, qty: float):
    if target.kind != "bin" or not target.is_active:
        raise HTTPException(status_code=409, detail="Pick an active bin")
    zone = await db.get(m.FmcgLocation, target.parent_id)
    quarantine = zone is not None and zone.zone_type == "quarantine"
    bad = False
    if batch_id:
        batch = await db.get(m.ProductBatch, batch_id)
        held = await pharmacy_svc.open_hold_batch_ids(db, tenant_id, [batch_id])
        expired = bool(batch and batch.expiry_date and batch.expiry_date.date() < date.today())
        bad = batch_id in held or expired
    if bad and not quarantine:
        raise HTTPException(
            status_code=409,
            detail={"code": "QUARANTINE_ONLY", "message": "A held or expired batch can only go in a quarantine zone"},
        )
    if quarantine and not bad:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_QUARANTINED", "message": "A quarantine zone only takes held or expired stock"},
        )
    if target.capacity is not None:
        room = _qty(float(target.capacity) - await _bin_total(db, tenant_id, target.id))
        if qty > room + 0.0005:
            raise HTTPException(
                status_code=409, detail={"code": "BIN_FULL", "message": f"Only {room:g} more fits in {target.code}"}
            )


async def put_away(db, *, tenant_id: str, bin_id: str, product_id: str, batch_id: str | None, quantity: float, user_id) -> dict:
    qty = _qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero")
    target = await _location(db, tenant_id, bin_id, lock=True)
    free = await _unplaced(db, tenant_id, product_id, batch_id)
    if qty > free + 0.0005:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_ENOUGH_UNPLACED", "message": f"Only {max(free, 0):g} is waiting to be put away"},
        )
    await _check_destination(db, tenant_id, target, product_id, batch_id, qty)
    row = await _stock_row(db, tenant_id, bin_id, product_id, batch_id, create=True)
    row.quantity = _qty(float(row.quantity) + qty)
    row.updated_at = datetime.utcnow()
    await _audit(
        db, tenant_id, user_id, "fmcg_bin_put_away", bin_id,
        {"product_id": product_id, "batch_id": batch_id, "quantity": qty},
    )
    await db.flush()
    return await contents(db, tenant_id=tenant_id, bin_id=bin_id)


async def move(
    db, *, tenant_id: str, from_bin: str, to_bin: str, product_id: str, batch_id: str | None, quantity: float, user_id
) -> dict:
    qty = _qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero")
    if from_bin == to_bin:
        raise HTTPException(status_code=422, detail="Pick two different bins")
    first, second = sorted([from_bin, to_bin])
    await _location(db, tenant_id, first, lock=True)
    await _location(db, tenant_id, second, lock=True)
    src = await _location(db, tenant_id, from_bin)
    dst = await _location(db, tenant_id, to_bin)
    if src.warehouse_id != dst.warehouse_id:
        raise HTTPException(status_code=409, detail="Bins are in different warehouses. Use a stock transfer instead")
    have = await _stock_row(db, tenant_id, from_bin, product_id, batch_id, create=False)
    if have is None or float(have.quantity) + 0.0005 < qty:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_IN_BIN", "message": f"Only {_qty(have.quantity) if have else 0:g} in {src.code}"},
        )
    await _check_destination(db, tenant_id, dst, product_id, batch_id, qty)
    have.quantity = _qty(float(have.quantity) - qty)
    have.updated_at = datetime.utcnow()
    there = await _stock_row(db, tenant_id, to_bin, product_id, batch_id, create=True)
    there.quantity = _qty(float(there.quantity) + qty)
    there.updated_at = datetime.utcnow()
    await _audit(
        db, tenant_id, user_id, "fmcg_bin_move", to_bin,
        {"from": src.code, "to": dst.code, "product_id": product_id, "batch_id": batch_id, "quantity": qty},
    )
    await db.flush()
    return {"from": await contents(db, tenant_id=tenant_id, bin_id=from_bin), "to": await contents(db, tenant_id=tenant_id, bin_id=to_bin)}


async def consume(db, tenant_id: str, product_id: str, batch_id: str | None, quantity: float) -> float:
    """Take stock that has left the company out of the bins, earliest pick order first. Never raises.

    Returns how much was found in bins; any rest was never binned. Quarantine zones are not drawn on.
    """
    left = _qty(quantity)
    if left <= 0:
        return 0.0
    taken_total = 0.0
    # Load the candidate rows, then order in Python by zone pick order and bin code.
    rows = (
        await db.execute(
            select(m.FmcgBinStock, m.FmcgLocation)
            .join(m.FmcgLocation, m.FmcgLocation.id == m.FmcgBinStock.bin_id)
            .where(
                m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.product_id == product_id,
                m.FmcgBinStock.quantity > 0,
            )
            .with_for_update(of=m.FmcgBinStock)
        )
    ).all()
    zones = {
        z.id: z
        for z in (
            await db.execute(
                select(m.FmcgLocation).where(
                    m.FmcgLocation.id.in_(list({b.parent_id for _, b in rows if b.parent_id}) or [""])
                )
            )
        ).scalars().all()
    }
    usable = [(s, b) for s, b in rows if not (zones.get(b.parent_id) and zones[b.parent_id].zone_type == "quarantine")]

    def order(item):
        s, b = item
        zone = zones.get(b.parent_id)
        exact = 0 if (batch_id and s.batch_id == batch_id) else 1
        return (exact, zone.pick_order if zone else 999, b.pick_order, b.code)

    for stock, _bin in sorted(usable, key=order):
        if left <= 0:
            break
        if batch_id and stock.batch_id not in (batch_id, None):
            continue
        take = min(_qty(stock.quantity), left)
        stock.quantity = _qty(float(stock.quantity) - take)
        stock.updated_at = datetime.utcnow()
        left = _qty(left - take)
        taken_total += take
    return _qty(taken_total)


# ---------------------------------------------------------------- counting

async def count_bin(db, *, tenant_id: str, bin_id: str, lines: list[dict], note: str | None, user_id) -> dict:
    """Set a bin to what was physically counted. Stock totals are untouched; only where it sits changes."""
    loc = await _location(db, tenant_id, bin_id, lock=True)
    if loc.kind != "bin":
        raise HTTPException(status_code=422, detail="Count a bin, not a zone")
    current = {
        (s.product_id, s.batch_id): s
        for s in (
            await db.execute(
                select(m.FmcgBinStock).where(m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.bin_id == bin_id).with_for_update()
            )
        ).scalars().all()
    }
    counted: dict[tuple, float] = {}
    for line in lines:
        key = (line["product_id"], line.get("batch_id"))
        if key in counted:
            raise HTTPException(status_code=422, detail="Each product and batch can be counted once")
        counted[key] = _qty(line["counted"])
    for key, stock in current.items():
        counted.setdefault(key, 0.0)  # in the system but not found: counted as zero
    variances = []
    for (product_id, batch_id), qty in counted.items():
        stock = current.get((product_id, batch_id))
        expected = _qty(stock.quantity) if stock else 0.0
        diff = _qty(qty - expected)
        if abs(diff) < 0.0005:
            continue
        variances.append((product_id, batch_id, expected, qty, diff, stock))
    text = None
    if variances:
        text = require_honest_narrative(note, label="reason for the difference", max_length=500)
    else:
        text = optional_honest_narrative(note, label="note", max_length=500)
    for product_id, batch_id, expected, qty, diff, stock in variances:
        if diff > 0:
            free = await _unplaced(db, tenant_id, product_id, batch_id)
            if diff > free + 0.0005:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "MORE_THAN_STOCK",
                        "message": f"You found {diff:g} more than the system has unplaced ({max(free, 0):g}). Fix the stock level first",
                    },
                )
            await _check_destination(db, tenant_id, loc, product_id, batch_id, diff)
        if stock is None:
            stock = m.FmcgBinStock(tenant_id=tenant_id, bin_id=bin_id, product_id=product_id, batch_id=batch_id, quantity=0)
            db.add(stock)
        stock.quantity = qty
        stock.updated_at = datetime.utcnow()
        db.add(
            m.FmcgBinCount(
                tenant_id=tenant_id, bin_id=bin_id, product_id=product_id, batch_id=batch_id, expected_qty=expected,
                counted_qty=qty, variance_qty=diff, note=text, counted_by=user_id,
            )
        )
    await _audit(db, tenant_id, user_id, "fmcg_bin_counted", bin_id, {"variances": len(variances), "note": text})
    await db.flush()
    result = await contents(db, tenant_id=tenant_id, bin_id=bin_id)
    result["variances"] = [
        {"product_id": p, "batch_id": b, "expected": e, "counted": c, "variance": d} for p, b, e, c, d, _ in variances
    ]
    return result


# ---------------------------------------------------------------- guidance and reports

async def suggest_bins(db, *, tenant_id: str, product_id: str, batch_id: str | None, quantity: float) -> list[dict]:
    """Where to put stock away: bins already holding this product with room, then empty bins."""
    qty = _qty(quantity)
    bins = (
        await db.execute(
            select(m.FmcgLocation).where(
                m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.kind == "bin", m.FmcgLocation.is_active.is_(True)
            )
        )
    ).scalars().all()
    zones = {
        z.id: z
        for z in (
            await db.execute(select(m.FmcgLocation).where(m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.kind == "zone"))
        ).scalars().all()
    }
    has = {
        r[0] for r in (
            await db.execute(
                select(m.FmcgBinStock.bin_id).where(
                    m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.product_id == product_id, m.FmcgBinStock.quantity > 0
                )
            )
        ).all()
    }
    out = []
    for loc in bins:
        zone = zones.get(loc.parent_id)
        try:
            await _check_destination(db, tenant_id, loc, product_id, batch_id, qty)
        except HTTPException:
            continue
        out.append(
            (0 if loc.id in has else 1, zone.pick_order if zone else 999, loc.code,
             {"bin_id": loc.id, "code": loc.code, "zone": zone.code if zone else None, "already_holds_product": loc.id in has})
        )
    return [x[3] for x in sorted(out, key=lambda t: t[:3])[:5]]


async def pick_list(db, *, tenant_id: str, order_id: str) -> dict:
    """Where to pick each line of an order from: earliest expiry first, never from quarantine."""
    from app import fmcg_orders as orders

    order = await orders._order(db, tenant_id, order_id)
    out = []
    for line in await orders._lines(db, order.id):
        rows = (
            await db.execute(
                select(m.FmcgBinStock, m.FmcgLocation, m.ProductBatch)
                .join(m.FmcgLocation, m.FmcgLocation.id == m.FmcgBinStock.bin_id)
                .outerjoin(m.ProductBatch, m.ProductBatch.id == m.FmcgBinStock.batch_id)
                .where(
                    m.FmcgBinStock.tenant_id == tenant_id, m.FmcgBinStock.product_id == line.product_id,
                    m.FmcgBinStock.quantity > 0, m.FmcgLocation.is_active.is_(True),
                )
            )
        ).all()
        zones = {z.id: z for z in (await db.execute(select(m.FmcgLocation).where(m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.kind == "zone"))).scalars().all()}
        held = await pharmacy_svc.open_hold_batch_ids(db, tenant_id, [s.batch_id for s, _, _ in rows if s.batch_id])
        today = date.today()
        usable = []
        for stock, loc, batch in rows:
            zone = zones.get(loc.parent_id)
            if zone and zone.zone_type == "quarantine":
                continue
            if stock.batch_id and stock.batch_id in held:
                continue
            if batch and batch.expiry_date and batch.expiry_date.date() < today:
                continue
            usable.append((batch.expiry_date if batch and batch.expiry_date else datetime.max, zone.pick_order if zone else 999, loc.code, stock, loc, batch))
        usable.sort(key=lambda t: t[:3])
        need = _qty(line.quantity)
        steps = []
        for _, _, _, stock, loc, batch in usable:
            if need <= 0:
                break
            take = min(_qty(stock.quantity), need)
            steps.append(
                {"bin_id": loc.id, "bin": loc.code, "batch_number": batch.batch_number if batch else None, "quantity": take}
            )
            need = _qty(need - take)
        out.append(
            {"line_id": line.id, "product_id": line.product_id, "product_name": line.name,
             "quantity": _qty(line.quantity), "steps": steps, "not_in_bins": need}
        )
    return {"order_id": order.id, "order_number": order.order_number, "lines": out}


async def report(db, *, tenant_id: str) -> dict:
    warehouses = (
        await db.execute(select(m.Warehouse).where(m.Warehouse.tenant_id == tenant_id, m.Warehouse.is_active.is_(True)))
    ).scalars().all()
    used_by_bin = dict(
        (
            await db.execute(
                select(m.FmcgBinStock.bin_id, func.coalesce(func.sum(m.FmcgBinStock.quantity), 0))
                .where(m.FmcgBinStock.tenant_id == tenant_id)
                .group_by(m.FmcgBinStock.bin_id)
            )
        ).all()
    )
    out = []
    for wh in warehouses:
        bins = (
            await db.execute(
                select(m.FmcgLocation).where(
                    m.FmcgLocation.tenant_id == tenant_id, m.FmcgLocation.warehouse_id == wh.id,
                    m.FmcgLocation.kind == "bin", m.FmcgLocation.is_active.is_(True),
                )
            )
        ).scalars().all()
        if not bins:
            continue
        capacity = sum(float(b.capacity) for b in bins if b.capacity is not None)
        used = sum(_qty(used_by_bin.get(b.id, 0)) for b in bins)
        capped_used = sum(_qty(used_by_bin.get(b.id, 0)) for b in bins if b.capacity is not None)
        out.append(
            {
                "warehouse_id": wh.id, "warehouse": wh.name, "bins": len(bins),
                "empty_bins": sum(1 for b in bins if _qty(used_by_bin.get(b.id, 0)) <= 0),
                "units_binned": _qty(used), "capacity": _qty(capacity),
                "utilisation_pct": round(100 * capped_used / capacity, 1) if capacity else None,
            }
        )
    rows = (
        await db.execute(
            select(m.Product.id, m.Product.name, m.Product.stock_qty, func.coalesce(func.sum(m.FmcgBinStock.quantity), 0))
            .join(m.FmcgBinStock, m.FmcgBinStock.product_id == m.Product.id)
            .where(m.Product.tenant_id == tenant_id, m.FmcgBinStock.tenant_id == tenant_id)
            .group_by(m.Product.id, m.Product.name, m.Product.stock_qty)
        )
    ).all()
    over = [
        {"product_id": pid, "product": name, "stock": _qty(stock), "in_bins": _qty(binned), "over_by": _qty(float(binned) - float(stock or 0))}
        for pid, name, stock, binned in rows
        if float(binned) > float(stock or 0) + 0.0005
    ]
    unplaced = [
        {"product_id": pid, "product": name, "unplaced": _qty(float(stock or 0) - float(binned))}
        for pid, name, stock, binned in rows
        if float(stock or 0) - float(binned) > 0.0005
    ]
    return {"warehouses": out, "over_binned": over, "waiting_for_put_away": unplaced}
