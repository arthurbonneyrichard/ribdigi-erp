"""FMCG import shipments and landed cost.

The goods themselves are bought and received through the normal purchase order and goods receipt
(which already books Dr Inventory / Cr Accounts Payable). A shipment adds what it cost to bring
them in: freight, insurance, customs duty, port, clearing and transport. Allocating a shipment
spreads those costs over its lines (by value or by quantity), adds the part that belongs to stock
still on hand to the product's cost (Dr Inventory) and charges the part that belongs to units
already sold to cost of goods (Dr COGS). The credit side is cash, bank or Accounts Payable for each
cost. A shipment can be allocated once; it cannot be changed afterwards.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import fmcg_orders as orders
from app import models as m
from app.honesty import money_json, optional_honest_narrative

COST_KINDS = ("freight", "insurance", "customs_duty", "port", "clearing", "transport", "other")
PAY_METHODS = tuple(sorted(orders.METHODS)) + ("payable",)
BASIS = ("value", "quantity")


def _c(value) -> int:
    return int(round(float(value or 0) * 100))


def _money(cents: int) -> float:
    return money_json(round(cents / 100, 2))


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_shipment", entity_id=entity_id, details=details,
    )


async def _shipment(db, tenant_id: str, shipment_id: str, *, lock: bool = False) -> m.FmcgShipment:
    stmt = select(m.FmcgShipment).where(m.FmcgShipment.id == shipment_id, m.FmcgShipment.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return row


def _open(row: m.FmcgShipment) -> None:
    if row.status != "open":
        raise HTTPException(status_code=409, detail=f"This shipment is {row.status} and can no longer be changed")


async def create(
    db, *, tenant_id: str, user_id, reference: str | None, container_no: str | None, supplier_id: str | None,
    grn_id: str | None, eta: date | None, basis: str, notes: str | None,
) -> dict:
    if basis not in BASIS:
        raise HTTPException(status_code=422, detail=f"basis must be one of: {', '.join(BASIS)}")
    grn = None
    if grn_id:
        grn = (await db.execute(select(m.GoodsReceipt).where(m.GoodsReceipt.id == grn_id, m.GoodsReceipt.tenant_id == tenant_id))).scalar_one_or_none()
        if grn is None:
            raise HTTPException(status_code=404, detail="Goods receipt not found")
        taken = (await db.execute(select(m.FmcgShipment.shipment_number).where(
            m.FmcgShipment.tenant_id == tenant_id, m.FmcgShipment.grn_id == grn_id, m.FmcgShipment.status != "cancelled"))).scalar_one_or_none()
        if taken:
            raise HTTPException(status_code=409, detail=f"That goods receipt is already on shipment {taken}")
        supplier_id = supplier_id or grn.supplier_id
    if supplier_id:
        sup = (await db.execute(select(m.Party).where(m.Party.id == supplier_id, m.Party.tenant_id == tenant_id, m.Party.kind == "supplier"))).scalar_one_or_none()
        if sup is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
    row = m.FmcgShipment(
        tenant_id=tenant_id, shipment_number=await orders._next_number(db, tenant_id, m.FmcgShipment, "SH"),
        reference=optional_honest_narrative(reference, label="reference", max_length=80),
        container_no=optional_honest_narrative(container_no, label="container number", max_length=40),
        supplier_id=supplier_id, grn_id=grn_id, eta=eta, basis=basis, notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if grn:
        items = (await db.execute(select(m.GoodsReceiptItem, m.PurchaseOrderItem).join(
            m.PurchaseOrderItem, m.PurchaseOrderItem.id == m.GoodsReceiptItem.po_item_id).where(
            m.GoodsReceiptItem.goods_receipt_id == grn.id, m.GoodsReceiptItem.accepted_qty > 0))).all()
        for gi, pi in items:
            db.add(m.FmcgShipmentLine(
                tenant_id=tenant_id, shipment_id=row.id, product_id=gi.product_id, quantity=gi.accepted_qty,
                goods_value=round(float(gi.accepted_qty) * float(pi.unit_price or 0), 2)))
    await _audit(db, tenant_id, user_id, "fmcg_shipment_opened", row.id, {"number": row.shipment_number, "grn_id": grn_id})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


async def add_line(db, *, tenant_id: str, shipment_id: str, product_id: str, quantity: float, goods_value: float, user_id) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    if quantity <= 0 or goods_value < 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero and the value cannot be negative")
    if (await db.execute(select(m.Product.id).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id))).first() is None:
        raise HTTPException(status_code=404, detail="Product not found")
    db.add(m.FmcgShipmentLine(tenant_id=tenant_id, shipment_id=row.id, product_id=product_id, quantity=quantity, goods_value=goods_value))
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


async def remove_line(db, *, tenant_id: str, shipment_id: str, line_id: str) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    line = (await db.execute(select(m.FmcgShipmentLine).where(
        m.FmcgShipmentLine.id == line_id, m.FmcgShipmentLine.shipment_id == row.id, m.FmcgShipmentLine.tenant_id == tenant_id))).scalar_one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Line not found")
    await db.delete(line)
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


async def add_cost(db, *, tenant_id: str, shipment_id: str, kind: str, amount: float, vendor: str | None, pay_method: str, note: str | None, user_id) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    if kind not in COST_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(COST_KINDS)}")
    if pay_method not in PAY_METHODS:
        raise HTTPException(status_code=422, detail=f"pay_method must be one of: {', '.join(PAY_METHODS)}")
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount")
    db.add(m.FmcgShipmentCost(
        tenant_id=tenant_id, shipment_id=row.id, kind=kind, amount=round(amount, 2), pay_method=pay_method,
        vendor=optional_honest_narrative(vendor, label="vendor", max_length=120), note=optional_honest_narrative(note, label="note", max_length=300)))
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


async def remove_cost(db, *, tenant_id: str, shipment_id: str, cost_id: str) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    cost = (await db.execute(select(m.FmcgShipmentCost).where(
        m.FmcgShipmentCost.id == cost_id, m.FmcgShipmentCost.shipment_id == row.id, m.FmcgShipmentCost.tenant_id == tenant_id))).scalar_one_or_none()
    if cost is None:
        raise HTTPException(status_code=404, detail="Cost not found")
    await db.delete(cost)
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


def spread(total_cents: int, weights: list[float]) -> list[int]:
    """Split money across weights to the cent; leftover cents go to the heaviest lines first."""
    w = sum(weights)
    if total_cents == 0 or not weights:
        return [0] * len(weights)
    if w <= 0:
        weights, w = [1.0] * len(weights), float(len(weights))
    parts = [int((total_cents * x) / w) for x in weights]
    left = total_cents - sum(parts)
    for i in sorted(range(len(weights)), key=lambda k: -weights[k])[: max(left, 0)]:
        parts[i] += 1
    return parts


async def _plan(db, tenant_id: str, row: m.FmcgShipment, lines: list[m.FmcgShipmentLine], costs: list[m.FmcgShipmentCost]) -> list[dict]:
    total = sum(_c(c.amount) for c in costs)
    if row.basis == "quantity" or sum(float(l.goods_value) for l in lines) <= 0:
        weights = [float(l.quantity) for l in lines]
    else:
        weights = [float(l.goods_value) for l in lines]
    alloc = spread(total, weights)
    products = {p.id: p for p in (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.id.in_({l.product_id for l in lines} or {""})))).scalars().all()}
    qty_by_product: dict[str, float] = {}
    for l in lines:
        qty_by_product[l.product_id] = qty_by_product.get(l.product_id, 0.0) + float(l.quantity)
    plan = []
    for l, a in zip(lines, alloc):
        p = products[l.product_id]
        stock, q = max(float(p.stock_qty or 0), 0.0), qty_by_product[l.product_id]
        cap = int(round(a * min(stock, q) / q)) if q > 0 else 0
        plan.append({"line": l, "product": p, "alloc": a, "cap": cap, "exp": a - cap, "stock": stock})
    return plan


async def _costs_lines(db, tenant_id: str, shipment_id: str):
    lines = (await db.execute(select(m.FmcgShipmentLine).where(m.FmcgShipmentLine.shipment_id == shipment_id, m.FmcgShipmentLine.tenant_id == tenant_id).order_by(m.FmcgShipmentLine.id))).scalars().all()
    costs = (await db.execute(select(m.FmcgShipmentCost).where(m.FmcgShipmentCost.shipment_id == shipment_id, m.FmcgShipmentCost.tenant_id == tenant_id).order_by(m.FmcgShipmentCost.created_at))).scalars().all()
    return list(lines), list(costs)


async def detail(db, *, tenant_id: str, shipment_id: str) -> dict:
    row = await _shipment(db, tenant_id, shipment_id)
    lines, costs = await _costs_lines(db, tenant_id, shipment_id)
    names = {p.id: p.name for p in (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.id.in_({l.product_id for l in lines} or {""})))).scalars().all()}
    supplier = await db.get(m.Party, row.supplier_id) if row.supplier_id else None
    goods = sum(_c(l.goods_value) for l in lines)
    total = sum(_c(c.amount) for c in costs)
    out_lines = []
    if row.status == "open" and lines and costs:
        for item in await _plan(db, tenant_id, row, lines, costs):
            l = item["line"]
            out_lines.append({"id": l.id, "product_id": l.product_id, "product": names.get(l.product_id), "quantity": money_json(l.quantity), "goods_value": money_json(l.goods_value),
                              "allocated": _money(item["alloc"]), "landed_unit_cost": round((_c(l.goods_value) + item["alloc"]) / 100 / float(l.quantity), 4),
                              "to_stock": _money(item["cap"]), "to_cost_of_goods": _money(item["exp"])})
    else:
        for l in lines:
            out_lines.append({"id": l.id, "product_id": l.product_id, "product": names.get(l.product_id), "quantity": money_json(l.quantity), "goods_value": money_json(l.goods_value),
                              "allocated": money_json(l.allocated) if l.allocated is not None else None,
                              "landed_unit_cost": round((float(l.goods_value) + float(l.allocated or 0)) / float(l.quantity), 4),
                              "to_stock": money_json(l.capitalised) if l.capitalised is not None else None,
                              "to_cost_of_goods": money_json(float(l.allocated) - float(l.capitalised)) if l.allocated is not None and l.capitalised is not None else None,
                              "cost_before": money_json(l.cost_before) if l.cost_before is not None else None, "cost_after": money_json(l.cost_after) if l.cost_after is not None else None})
    return {
        "id": row.id, "shipment_number": row.shipment_number, "reference": row.reference, "container_no": row.container_no,
        "supplier_id": row.supplier_id, "supplier": supplier.name if supplier else None, "grn_id": row.grn_id,
        "eta": row.eta.isoformat() if row.eta else None, "basis": row.basis, "status": row.status, "notes": row.notes,
        "goods_value": _money(goods), "total_costs": _money(total), "uplift_pct": round(100 * total / goods, 1) if goods else None,
        "lines": out_lines,
        "costs": [{"id": c.id, "kind": c.kind, "amount": money_json(c.amount), "vendor": c.vendor, "pay_method": c.pay_method, "note": c.note} for c in costs],
        "allocated_at": row.allocated_at.isoformat(timespec="seconds") if row.allocated_at else None,
    }


async def list_all(db, *, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.FmcgShipment).where(m.FmcgShipment.tenant_id == tenant_id).order_by(m.FmcgShipment.created_at.desc()).limit(200))).scalars().all()
    return [await detail(db, tenant_id=tenant_id, shipment_id=r.id) for r in rows]


async def allocate(db, *, tenant_id: str, shipment_id: str, user_id) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    lines, costs = await _costs_lines(db, tenant_id, shipment_id)
    if not lines:
        raise HTTPException(status_code=409, detail="Add the products on this shipment first")
    if not costs:
        raise HTTPException(status_code=409, detail="Add at least one cost first")
    plan = await _plan(db, tenant_id, row, lines, costs)
    total = sum(_c(c.amount) for c in costs)
    cap_total, exp_total = sum(i["cap"] for i in plan), sum(i["exp"] for i in plan)
    assert cap_total + exp_total == total  # the split is exact to the cent
    # New unit cost per product: its current cost plus the capitalised share spread over what is on hand.
    by_product: dict[str, int] = {}
    for i in plan:
        by_product[i["product"].id] = by_product.get(i["product"].id, 0) + i["cap"]
    new_cost: dict[str, tuple[float, float]] = {}
    for i in plan:
        p = i["product"]
        if p.id in new_cost:
            continue
        before = float(p.cost_price or 0)
        stock = max(float(p.stock_qty or 0), 0.0)
        after = round(before + (by_product[p.id] / 100) / stock, 4) if stock > 0 and by_product[p.id] else before
        new_cost[p.id] = (before, after)
    credits: dict[str, int] = {}
    for c in costs:
        code = "2000" if c.pay_method == "payable" else orders._money_account(c.pay_method)
        credits[code] = credits.get(code, 0) + _c(c.amount)
    journal = []
    if cap_total:
        journal.append({"account_code": "1200", "debit": _money(cap_total), "credit": 0, "description": f"Landed cost {row.shipment_number}"})
    if exp_total:
        journal.append({"account_code": "5000", "debit": _money(exp_total), "credit": 0, "description": f"Landed cost on goods already sold {row.shipment_number}"})
    for code, cents in credits.items():
        journal.append({"account_code": code, "debit": 0, "credit": _money(cents), "description": f"Shipment {row.shipment_number} costs"})
    row.journal_entry_id = await orders._post(
        db, tenant_id, user_id=user_id, description=f"Landed cost {row.shipment_number}", lines=journal,
        reference=row.shipment_number, source="fmcg_landed_cost", source_id=row.id,
    )
    for i in plan:
        l, p = i["line"], i["product"]
        before, after = new_cost[p.id]
        l.allocated, l.capitalised, l.cost_before, l.cost_after = _money(i["alloc"]), _money(i["cap"]), before, after
    for pid, (before, after) in new_cost.items():
        if after != before:
            (await db.get(m.Product, pid)).cost_price = after
    row.total_costs = _money(total)
    row.status = "allocated"
    row.allocated_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "fmcg_shipment_allocated", row.id, {"total": _money(total), "to_stock": _money(cap_total), "to_cogs": _money(exp_total)})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)


async def cancel(db, *, tenant_id: str, shipment_id: str, user_id) -> dict:
    row = await _shipment(db, tenant_id, shipment_id, lock=True)
    _open(row)
    row.status = "cancelled"
    await _audit(db, tenant_id, user_id, "fmcg_shipment_cancelled", row.id, {})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, shipment_id=row.id)
