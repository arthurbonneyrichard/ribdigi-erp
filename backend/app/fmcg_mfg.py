"""FMCG optional manufacturing: recipes (bills of materials), production orders, costing and traceability.

Switched on per company (``fmcg_manufacturing.enabled``); every route refuses with MODULE_OFF until a
manager turns it on, so a distributor never sees it.

Completing a production order, in one transaction:
1. each material is taken out of stock first-expiry-first-out (batches recorded for tracing);
2. the finished product is received into stock as a new batch (optionally held for quality control);
3. unit cost = (materials at current cost + overheads) / units made, and the product's cost becomes the
   weighted average of its stock before and the new batch;
4. overheads (labour, power, other) are booked Dr Inventory / Cr cash, bank or Accounts Payable.
Materials move inside Inventory, so they need no journal. Extra material used beyond the recipe is
wastage: it stays in the cost and is reported against the recipe.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import catalog as catalog_svc
from app import fmcg_orders as orders
from app import models as m
from app import pharmacy as pharmacy_svc
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

SETTINGS_KEY = "fmcg_manufacturing"
OVERHEAD_KINDS = ("labour", "power", "packaging", "transport", "other")
PAY_METHODS = tuple(sorted(orders.METHODS)) + ("payable",)


def _q(v) -> float:
    return money_json(round(float(v or 0), 3))


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_production", entity_id=entity_id, details=details,
    )


# ---------------------------------------------------------------- switch

async def is_enabled(db: AsyncSession, tenant_id: str) -> bool:
    t = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
    return bool(((t.document_numbering or {}).get(SETTINGS_KEY) or {}).get("enabled"))


async def require_enabled(db, tenant_id: str) -> None:
    if not await is_enabled(db, tenant_id):
        raise HTTPException(status_code=409, detail={"code": "MODULE_OFF", "message": "Manufacturing is not switched on for this company."})


async def set_enabled(db, tenant_id: str, enabled: bool, user_id) -> dict:
    t = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())).scalar_one()
    data = dict(t.document_numbering or {})
    data[SETTINGS_KEY] = {"enabled": bool(enabled)}
    t.document_numbering = data
    await _audit(db, tenant_id, user_id, "fmcg_manufacturing_switched", tenant_id, {"enabled": bool(enabled)})
    await db.flush()
    return {"enabled": bool(enabled)}


# ---------------------------------------------------------------- recipes

async def _product(db, tenant_id: str, product_id: str) -> m.Product:
    row = (await db.execute(select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


async def _bom(db, tenant_id: str, bom_id: str, *, lock: bool = False) -> m.FmcgBom:
    stmt = select(m.FmcgBom).where(m.FmcgBom.id == bom_id, m.FmcgBom.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return row


async def _bom_lines(db, tenant_id: str, bom_id: str) -> list[m.FmcgBomLine]:
    return list((await db.execute(select(m.FmcgBomLine).where(m.FmcgBomLine.bom_id == bom_id, m.FmcgBomLine.tenant_id == tenant_id).order_by(m.FmcgBomLine.id))).scalars().all())


async def _present_bom(db, bom: m.FmcgBom) -> dict:
    product = await db.get(m.Product, bom.product_id)
    lines = await _bom_lines(db, bom.tenant_id, bom.id)
    comps = {p.id: p for p in (await db.execute(select(m.Product).where(m.Product.id.in_({l.component_id for l in lines} or {""})))).scalars().all()}
    standard = sum(float(l.quantity) * (1 + float(l.wastage_pct or 0) / 100) * float(comps[l.component_id].cost_price or 0) for l in lines)
    used = (await db.execute(select(m.FmcgProductionOrder.id).where(
        m.FmcgProductionOrder.bom_id == bom.id, m.FmcgProductionOrder.status != "cancelled").limit(1))).first() is not None
    return {
        "id": bom.id, "name": bom.name, "product_id": bom.product_id, "product": product.name if product else None,
        "output_qty": _q(bom.output_qty), "shelf_life_days": bom.shelf_life_days, "is_active": bom.is_active, "in_use": used,
        "standard_material_cost": money_json(round(standard, 2)),
        "standard_unit_cost": round(standard / float(bom.output_qty), 4) if float(bom.output_qty) else None,
        "lines": [{"id": l.id, "component_id": l.component_id, "component": comps[l.component_id].name, "quantity": money_json(l.quantity),
                   "wastage_pct": money_json(l.wastage_pct), "unit_cost": money_json(comps[l.component_id].cost_price)} for l in lines],
    }


def _check_lines(product_id: str, lines: list[dict]) -> None:
    if not lines:
        raise HTTPException(status_code=422, detail="A recipe needs at least one material")
    seen = set()
    for l in lines:
        if l["component_id"] == product_id:
            raise HTTPException(status_code=422, detail="A product cannot be a material of itself")
        if l["component_id"] in seen:
            raise HTTPException(status_code=422, detail="Each material can be listed once")
        seen.add(l["component_id"])


async def create_bom(db, *, tenant_id: str, user_id, product_id: str, name: str, output_qty: float, shelf_life_days: int | None, lines: list[dict]) -> dict:
    await require_enabled(db, tenant_id)
    await _product(db, tenant_id, product_id)
    _check_lines(product_id, lines)
    for l in lines:
        await _product(db, tenant_id, l["component_id"])
    bom = m.FmcgBom(tenant_id=tenant_id, product_id=product_id, name=require_honest_narrative(name, label="name", max_length=150),
                    output_qty=output_qty, shelf_life_days=shelf_life_days, created_by=user_id)
    db.add(bom)
    await db.flush()
    for l in lines:
        db.add(m.FmcgBomLine(tenant_id=tenant_id, bom_id=bom.id, component_id=l["component_id"], quantity=l["quantity"], wastage_pct=l["wastage_pct"]))
    await _audit(db, tenant_id, user_id, "fmcg_bom_created", bom.id, {"product_id": product_id, "lines": len(lines)})
    await db.flush()
    return await _present_bom(db, bom)


async def update_bom(db, *, tenant_id: str, user_id, bom_id: str, name: str, output_qty: float, shelf_life_days: int | None, lines: list[dict]) -> dict:
    await require_enabled(db, tenant_id)
    bom = await _bom(db, tenant_id, bom_id, lock=True)
    if (await _present_bom(db, bom))["in_use"]:
        raise HTTPException(status_code=409, detail={"code": "RECIPE_IN_USE", "message": "Production orders use this recipe. Make a new recipe instead"})
    _check_lines(bom.product_id, lines)
    for l in lines:
        await _product(db, tenant_id, l["component_id"])
    bom.name, bom.output_qty, bom.shelf_life_days = require_honest_narrative(name, label="name", max_length=150), output_qty, shelf_life_days
    for old in await _bom_lines(db, tenant_id, bom.id):
        await db.delete(old)
    await db.flush()
    for l in lines:
        db.add(m.FmcgBomLine(tenant_id=tenant_id, bom_id=bom.id, component_id=l["component_id"], quantity=l["quantity"], wastage_pct=l["wastage_pct"]))
    await _audit(db, tenant_id, user_id, "fmcg_bom_updated", bom.id, {"lines": len(lines)})
    await db.flush()
    return await _present_bom(db, bom)


async def set_bom_active(db, *, tenant_id: str, user_id, bom_id: str, active: bool) -> dict:
    await require_enabled(db, tenant_id)
    bom = await _bom(db, tenant_id, bom_id, lock=True)
    bom.is_active = active
    await _audit(db, tenant_id, user_id, "fmcg_bom_active", bom.id, {"active": active})
    await db.flush()
    return await _present_bom(db, bom)


async def list_boms(db, *, tenant_id: str) -> list[dict]:
    await require_enabled(db, tenant_id)
    rows = (await db.execute(select(m.FmcgBom).where(m.FmcgBom.tenant_id == tenant_id).order_by(m.FmcgBom.created_at.desc()))).scalars().all()
    return [await _present_bom(db, b) for b in rows]


# ---------------------------------------------------------------- production orders

async def _order(db, tenant_id: str, order_id: str, *, lock: bool = False) -> m.FmcgProductionOrder:
    stmt = select(m.FmcgProductionOrder).where(m.FmcgProductionOrder.id == order_id, m.FmcgProductionOrder.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Production order not found")
    return row


def _standard(line: m.FmcgBomLine, bom: m.FmcgBom, qty: float) -> float:
    return round(float(line.quantity) * qty / float(bom.output_qty) * (1 + float(line.wastage_pct or 0) / 100), 3)


async def create_order(db, *, tenant_id: str, user_id, bom_id: str, planned_qty: float, planned_date: date | None, notes: str | None) -> dict:
    await require_enabled(db, tenant_id)
    bom = await _bom(db, tenant_id, bom_id)
    if not bom.is_active:
        raise HTTPException(status_code=409, detail="That recipe is switched off")
    row = m.FmcgProductionOrder(
        tenant_id=tenant_id, order_number=await orders._next_number(db, tenant_id, m.FmcgProductionOrder, "MO"), bom_id=bom.id,
        product_id=bom.product_id, planned_qty=planned_qty, planned_date=planned_date, status="planned",
        notes=optional_honest_narrative(notes, label="notes", max_length=500), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_production_planned", row.id, {"number": row.order_number, "planned_qty": planned_qty})
    return await detail(db, tenant_id=tenant_id, order_id=row.id)


async def check_materials(db, *, tenant_id: str, order_id: str) -> dict:
    await require_enabled(db, tenant_id)
    order = await _order(db, tenant_id, order_id)
    bom = await _bom(db, tenant_id, order.bom_id)
    rows, ok = [], True
    for l in await _bom_lines(db, tenant_id, bom.id):
        p = await db.get(m.Product, l.component_id)
        need, have = _standard(l, bom, float(order.planned_qty)), float(p.stock_qty or 0)
        short = max(need - have, 0.0)
        ok = ok and short <= 0.0005
        rows.append({"component_id": p.id, "component": p.name, "needed": _q(need), "in_stock": _q(have), "short_by": _q(short)})
    return {"order_id": order.id, "enough": ok, "materials": rows}


async def start(db, *, tenant_id: str, user_id, order_id: str) -> dict:
    await require_enabled(db, tenant_id)
    order = await _order(db, tenant_id, order_id, lock=True)
    if order.status != "planned":
        raise HTTPException(status_code=409, detail=f"This order is {order.status}")
    check = await check_materials(db, tenant_id=tenant_id, order_id=order_id)
    if not check["enough"]:
        short = ", ".join(f"{r['component']} (short {r['short_by']:g})" for r in check["materials"] if r["short_by"] > 0)
        raise HTTPException(status_code=409, detail={"code": "MATERIALS_SHORT", "message": f"Not enough material: {short}", "materials": check["materials"]})
    order.status, order.started_at = "in_progress", datetime.utcnow()
    await _audit(db, tenant_id, user_id, "fmcg_production_started", order.id, {})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, order_id=order.id)


async def cancel(db, *, tenant_id: str, user_id, order_id: str, reason: str) -> dict:
    await require_enabled(db, tenant_id)
    order = await _order(db, tenant_id, order_id, lock=True)
    if order.status not in ("planned", "in_progress"):
        raise HTTPException(status_code=409, detail=f"This order is {order.status}")
    order.status = "cancelled"
    order.cancel_reason = require_honest_narrative(reason, label="reason", max_length=255)
    await _audit(db, tenant_id, user_id, "fmcg_production_cancelled", order.id, {"reason": order.cancel_reason})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, order_id=order.id)


async def complete(
    db, *, tenant_id: str, user_id, order_id: str, produced_qty: float, batch_number: str | None, expiry_date: date | None,
    materials: list[dict], overheads: list[dict], hold_for_qc: bool,
) -> dict:
    await require_enabled(db, tenant_id)
    order = await _order(db, tenant_id, order_id, lock=True)
    if order.status != "in_progress":
        raise HTTPException(status_code=409, detail=f"This order is {order.status}. Start it first" if order.status == "planned" else f"This order is {order.status}")
    if produced_qty <= 0:
        raise HTTPException(status_code=422, detail="Enter how many were made")
    bom = await _bom(db, tenant_id, order.bom_id)
    lines = await _bom_lines(db, tenant_id, bom.id)
    override = {x["component_id"]: x["actual_qty"] for x in materials}
    unknown = set(override) - {l.component_id for l in lines}
    if unknown:
        raise HTTPException(status_code=422, detail="You gave a quantity for something that is not in the recipe")
    for o in overheads:
        if o["kind"] not in OVERHEAD_KINDS or o["pay_method"] not in PAY_METHODS or o["amount"] <= 0:
            raise HTTPException(status_code=422, detail=f"Each overhead needs a kind ({', '.join(OVERHEAD_KINDS)}), a payment method and an amount")
    product = await _product(db, tenant_id, order.product_id)
    stock_before, cost_before = max(float(product.stock_qty or 0), 0.0), float(product.cost_price or 0)

    material_cost = 0.0
    for l in lines:
        comp = await _product(db, tenant_id, l.component_id)
        standard = _standard(l, bom, produced_qty)
        actual = round(float(override.get(l.component_id, standard)), 3)
        if actual < 0:
            raise HTTPException(status_code=422, detail="Material used cannot be negative")
        unit = float(comp.cost_price or 0)
        material_cost += actual * unit
        db.add(m.FmcgProductionMaterial(tenant_id=tenant_id, order_id=order.id, component_id=comp.id, standard_qty=standard, actual_qty=actual, unit_cost=unit))
        if actual > 0:
            out = await catalog_svc.stock_out_with_batch(
                db, tenant_id=tenant_id, user_id=user_id, product_id=comp.id, quantity=actual, reference_type="fmcg_production",
                reference_id=order.id, notes=f"Production {order.order_number}",
            )
            for taken in out.get("batches_consumed") or []:
                db.add(m.FmcgProductionTrace(tenant_id=tenant_id, order_id=order.id, component_id=comp.id, batch_id=taken["batch_id"], quantity=taken["quantity"]))
    overhead_cost = round(sum(o["amount"] for o in overheads), 2)
    for o in overheads:
        db.add(m.FmcgProductionOverhead(tenant_id=tenant_id, order_id=order.id, kind=o["kind"], amount=o["amount"], pay_method=o["pay_method"],
                                        note=optional_honest_narrative(o.get("note"), label="note", max_length=300)))
    total = material_cost + overhead_cost
    unit_cost = round(total / produced_qty, 4)

    number = (batch_number or order.order_number).strip()
    expiry = expiry_date or (date.today() + timedelta(days=bom.shelf_life_days) if bom.shelf_life_days else None)
    await catalog_svc.stock_in_with_batch(
        db, tenant_id=tenant_id, user_id=user_id, product_id=product.id, quantity=produced_qty, batch_number=number,
        manufacturing_date=datetime.combine(date.today(), time.min), expiry_date=datetime.combine(expiry, time.min) if expiry else None,
        reference_type="fmcg_production", reference_id=order.id, notes=f"Production {order.order_number}",
    )
    product.cost_price = round((stock_before * cost_before + produced_qty * unit_cost) / (stock_before + produced_qty), 4)

    if overhead_cost > 0:
        credits: dict[str, float] = {}
        for o in overheads:
            code = "2000" if o["pay_method"] == "payable" else orders._money_account(o["pay_method"])
            credits[code] = credits.get(code, 0.0) + o["amount"]
        lines_j = [{"account_code": "1200", "debit": overhead_cost, "credit": 0, "description": f"Production overhead {order.order_number}"}]
        lines_j += [{"account_code": c, "debit": 0, "credit": round(a, 2), "description": f"Production {order.order_number}"} for c, a in credits.items()]
        order.journal_entry_id = await orders._post(
            db, tenant_id, user_id=user_id, description=f"Production overhead {order.order_number}", lines=lines_j,
            reference=order.order_number, source="fmcg_production", source_id=order.id,
        )
    held = False
    if hold_for_qc:
        batch = (await db.execute(select(m.ProductBatch).where(m.ProductBatch.tenant_id == tenant_id, m.ProductBatch.product_id == product.id, m.ProductBatch.batch_number == number))).scalars().first()
        if batch is not None:
            await pharmacy_svc.create_hold(db, tenant_id=tenant_id, created_by=user_id, batch_id=batch.id, hold_type="quarantine", reason=f"New production {order.order_number} waiting for quality check")
            held = True
    order.status, order.produced_qty, order.batch_number, order.expiry_date = "completed", produced_qty, number, expiry
    order.material_cost, order.overhead_cost, order.unit_cost, order.held_for_qc = round(material_cost, 2), overhead_cost, unit_cost, held
    order.completed_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "fmcg_production_completed", order.id, {"produced": produced_qty, "unit_cost": unit_cost, "batch": number})
    await db.flush()
    return await detail(db, tenant_id=tenant_id, order_id=order.id)


async def detail(db, *, tenant_id: str, order_id: str) -> dict:
    order = await _order(db, tenant_id, order_id)
    product = await db.get(m.Product, order.product_id)
    bom = await _bom(db, tenant_id, order.bom_id)
    mats = (await db.execute(select(m.FmcgProductionMaterial, m.Product).join(m.Product, m.Product.id == m.FmcgProductionMaterial.component_id).where(
        m.FmcgProductionMaterial.order_id == order.id, m.FmcgProductionMaterial.tenant_id == tenant_id))).all()
    ovh = (await db.execute(select(m.FmcgProductionOverhead).where(m.FmcgProductionOverhead.order_id == order.id, m.FmcgProductionOverhead.tenant_id == tenant_id))).scalars().all()
    trace = (await db.execute(select(m.FmcgProductionTrace, m.ProductBatch, m.Product).join(m.ProductBatch, m.ProductBatch.id == m.FmcgProductionTrace.batch_id).join(
        m.Product, m.Product.id == m.FmcgProductionTrace.component_id).where(m.FmcgProductionTrace.order_id == order.id, m.FmcgProductionTrace.tenant_id == tenant_id))).all()
    std_cost = sum(float(x.standard_qty) * float(x.unit_cost) for x, _ in mats)
    act_cost = sum(float(x.actual_qty) * float(x.unit_cost) for x, _ in mats)
    return {
        "id": order.id, "order_number": order.order_number, "status": order.status, "product_id": order.product_id,
        "product": product.name if product else None, "bom": bom.name, "bom_id": bom.id, "planned_qty": _q(order.planned_qty),
        "produced_qty": _q(order.produced_qty) if order.produced_qty is not None else None, "planned_date": order.planned_date.isoformat() if order.planned_date else None,
        "batch_number": order.batch_number, "expiry_date": order.expiry_date.isoformat() if order.expiry_date else None, "held_for_qc": order.held_for_qc,
        "material_cost": money_json(order.material_cost), "overhead_cost": money_json(order.overhead_cost),
        "unit_cost": money_json(order.unit_cost) if order.unit_cost is not None else None, "notes": order.notes, "cancel_reason": order.cancel_reason,
        "materials": [{"component_id": p.id, "component": p.name, "standard": _q(x.standard_qty), "actual": _q(x.actual_qty), "variance": _q(float(x.actual_qty) - float(x.standard_qty)), "unit_cost": money_json(x.unit_cost)} for x, p in mats],
        "overheads": [{"kind": o.kind, "amount": money_json(o.amount), "pay_method": o.pay_method, "note": o.note} for o in ovh],
        "wastage_cost": money_json(round(act_cost - std_cost, 2)) if mats else None,
        "wastage_pct": round(100 * (act_cost - std_cost) / std_cost, 1) if std_cost > 0 else None,
        "trace": [{"component": p.name, "batch_number": b.batch_number, "quantity": _q(t.quantity)} for t, b, p in trace],
        "created_at": order.created_at.isoformat(timespec="seconds"),
        "completed_at": order.completed_at.isoformat(timespec="seconds") if order.completed_at else None,
    }


async def list_orders(db, *, tenant_id: str, status: str | None) -> list[dict]:
    await require_enabled(db, tenant_id)
    stmt = select(m.FmcgProductionOrder.id).where(m.FmcgProductionOrder.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.FmcgProductionOrder.status == status)
    ids = (await db.execute(stmt.order_by(m.FmcgProductionOrder.created_at.desc()).limit(100))).scalars().all()
    return [await detail(db, tenant_id=tenant_id, order_id=i) for i in ids]


async def report(db, *, tenant_id: str, start: date, end: date) -> dict:
    await require_enabled(db, tenant_id)
    rows = (await db.execute(select(m.FmcgProductionOrder).where(
        m.FmcgProductionOrder.tenant_id == tenant_id, m.FmcgProductionOrder.status == "completed",
        m.FmcgProductionOrder.completed_at >= datetime.combine(start, time.min), m.FmcgProductionOrder.completed_at <= datetime.combine(end, time.max)).order_by(m.FmcgProductionOrder.completed_at))).scalars().all()
    out, by_product = [], {}
    for o in rows:
        d = await detail(db, tenant_id=tenant_id, order_id=o.id)
        out.append({"order_number": d["order_number"], "product": d["product"], "batch": d["batch_number"], "planned": d["planned_qty"], "produced": d["produced_qty"],
                    "yield_pct": round(100 * d["produced_qty"] / d["planned_qty"], 1) if d["planned_qty"] else None, "material_cost": d["material_cost"],
                    "overhead_cost": d["overhead_cost"], "unit_cost": d["unit_cost"], "wastage_cost": d["wastage_cost"], "wastage_pct": d["wastage_pct"]})
        g = by_product.setdefault(d["product"], {"product": d["product"], "orders": 0, "produced": 0.0, "cost": 0.0})
        g["orders"] += 1
        g["produced"] += d["produced_qty"]
        g["cost"] += d["material_cost"] + d["overhead_cost"]
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()}, "orders": out,
        "by_product": [{**g, "produced": round(g["produced"], 3), "cost": money_json(round(g["cost"], 2)), "average_unit_cost": round(g["cost"] / g["produced"], 4) if g["produced"] else None} for g in by_product.values()],
        "note": "Material cost uses each material's cost price at the time of production.",
    }
