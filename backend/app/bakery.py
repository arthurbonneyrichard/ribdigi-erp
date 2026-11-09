"""Bakery desk: recipes, production, its own till, pre-orders and waste, on its own tables.

Ingredients and finished goods are ordinary products, so the back office (stock, purchasing,
accounting, tax) stays the shared engine. Everything a bakery does at the counter lives here
and never touches retail ``transactions`` or ``pos_sessions``.

Every movement of money goes through ``bakery_payments``, so the drawer count is one sum.
A deposit is money held for the customer: it credits receivables, and becomes revenue when the
order is collected or the deposit is kept.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import inventory
from app import models as m
from app import tax as tax_svc
from app import desk_dashboard as dash
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

TILL_METHODS = frozenset({"cash", "card", "mobile_money", "wallet"})
WASTE_REASONS = frozenset({"unsold", "burnt", "damaged", "expired", "other"})
ORDER_OPEN = ("booked", "ready")
REF_BATCH = "bakery_batch"
REF_SALE = "bakery_sale"
REF_WASTE = "bakery_waste"
REF_ORDER = "bakery_order"


def _now() -> datetime:
    return datetime.utcnow()


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


def _qty(value) -> float:
    return money_json(round(float(value or 0), 3))


async def _next_number(db: AsyncSession, tenant_id: str, model, prefix: str) -> str:
    # key_share: see hotel._lock_numbers.
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    count = (await db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))).scalar_one()
    return f"{prefix}-{int(count or 0) + 1:04d}"


async def _product(db: AsyncSession, tenant_id: str, product_id: str) -> m.Product:
    row = await db.get(m.Product, product_id)
    if row is None or row.tenant_id != tenant_id or not row.is_active:
        raise HTTPException(status_code=404, detail="Item not found")
    return row


async def _post(db, tenant_id: str, *, user_id, description: str, lines: list[dict], reference: str, source: str, source_id: str):
    await accounting.ensure_default_accounts(db, tenant_id)
    if not lines:
        return None
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=reference,
        source_type=source,
        source_id=source_id,
    )
    return entry.id


def _money_account(method: str) -> str:
    return accounting.pos_debit_account_for_payment_method(method)[0]


async def _audit(db, tenant_id: str, user_id, action: str, entity: str, entity_id: str, details: dict) -> None:
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="bakery",
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
    )


# --- Items -------------------------------------------------------------------------------


async def list_items(db: AsyncSession, tenant_id: str) -> list[dict]:
    """What the counter sells: active products with a selling price."""
    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True), m.Product.selling_price > 0)
            .order_by(m.Product.name.asc())
        )
    ).scalars().all()
    out = []
    for row in rows:
        # What the customer actually pays for one, tax included, so the counter shows the
        # same total the sale will charge.
        spec = await tax_svc.resolve_product_tax(db, tenant_id, row)
        _net, _tax, gross = tax_svc.compute_line_total(1, _money(row.selling_price), spec.rate_pct, spec.pricing_mode)
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "price": _money(row.selling_price),
                "price_to_pay": _money(gross),
                "category": (row.category or "Bakery").strip() or "Bakery",
                "stock_qty": _qty(row.stock_qty),
            }
        )
    return out


async def list_ingredients(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True))
            .order_by(m.Product.name.asc())
        )
    ).scalars()
    return [
        {"id": row.id, "name": row.name, "stock_qty": _qty(row.stock_qty), "cost_price": _money(row.cost_price)}
        for row in rows
    ]


# --- Recipes -----------------------------------------------------------------------------


async def _recipe_lines(db: AsyncSession, recipe_id: str) -> list[m.BakeryRecipeLine]:
    return list(
        (await db.execute(select(m.BakeryRecipeLine).where(m.BakeryRecipeLine.recipe_id == recipe_id))).scalars()
    )


async def present_recipe(db: AsyncSession, recipe: m.BakeryRecipe) -> dict:
    product = await db.get(m.Product, recipe.product_id)
    lines = []
    batch_cost = 0.0
    for line in await _recipe_lines(db, recipe.id):
        item = await db.get(m.Product, line.ingredient_id)
        cost = _money(float(line.quantity) * float(item.cost_price or 0)) if item else 0.0
        batch_cost += cost
        lines.append(
            {
                "ingredient_id": line.ingredient_id,
                "name": item.name if item else "Unknown",
                "quantity": _qty(line.quantity),
                "cost": cost,
                "in_stock": _qty(item.stock_qty) if item else 0,
            }
        )
    yield_qty = float(recipe.yield_qty or 1)
    unit_cost = _money(batch_cost / yield_qty) if yield_qty else 0.0
    price = _money(product.selling_price) if product else 0.0
    return {
        "id": recipe.id,
        "product_id": recipe.product_id,
        "name": recipe.name,
        "product_name": product.name if product else None,
        "yield_qty": _qty(recipe.yield_qty),
        "batch_cost": _money(batch_cost),
        "unit_cost": unit_cost,
        "selling_price": price,
        "margin_percent": money_json(round((price - unit_cost) / price * 100, 1)) if price > 0 else None,
        "is_active": bool(recipe.is_active),
        "notes": recipe.notes,
        "lines": lines,
    }


async def list_recipes(db: AsyncSession, tenant_id: str) -> list[m.BakeryRecipe]:
    return list(
        (
            await db.execute(
                select(m.BakeryRecipe).where(m.BakeryRecipe.tenant_id == tenant_id).order_by(m.BakeryRecipe.name.asc())
            )
        ).scalars()
    )


async def _recipe(db: AsyncSession, tenant_id: str, recipe_id: str) -> m.BakeryRecipe:
    row = await db.get(m.BakeryRecipe, recipe_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return row


async def save_recipe(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str,
    name: str,
    yield_qty: float,
    lines: list[dict],
    notes: str | None,
    recipe_id: str | None = None,
) -> m.BakeryRecipe:
    await _product(db, tenant_id, product_id)
    clean_name = require_honest_narrative(name, label="recipe name", max_length=150)
    if float(yield_qty) <= 0:
        raise HTTPException(status_code=422, detail="A recipe must make at least some")
    if not lines:
        raise HTTPException(status_code=422, detail="Add at least one ingredient")
    seen: set[str] = set()
    for line in lines:
        ingredient = str(line["ingredient_id"])
        if ingredient == product_id:
            raise HTTPException(status_code=422, detail="An item cannot be an ingredient of itself")
        if ingredient in seen:
            raise HTTPException(status_code=422, detail="An ingredient is listed twice")
        seen.add(ingredient)
        await _product(db, tenant_id, ingredient)
        if float(line["quantity"]) <= 0:
            raise HTTPException(status_code=422, detail="Ingredient amounts must be above zero")
    taken = (
        await db.execute(
            select(m.BakeryRecipe).where(
                m.BakeryRecipe.tenant_id == tenant_id,
                m.BakeryRecipe.product_id == product_id,
                m.BakeryRecipe.id != (recipe_id or ""),
            )
        )
    ).scalars().first()
    if taken:
        raise HTTPException(status_code=409, detail="This item already has a recipe")
    if recipe_id:
        row = await _recipe(db, tenant_id, recipe_id)
        for old in await _recipe_lines(db, row.id):
            await db.delete(old)
        await db.flush()
    else:
        row = m.BakeryRecipe(tenant_id=tenant_id, product_id=product_id, name=clean_name, yield_qty=yield_qty)
        db.add(row)
        await db.flush()
    row.product_id = product_id
    row.name = clean_name
    row.yield_qty = _qty(yield_qty)
    row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    row.updated_at = _now()
    for line in lines:
        db.add(
            m.BakeryRecipeLine(
                tenant_id=tenant_id,
                recipe_id=row.id,
                ingredient_id=str(line["ingredient_id"]),
                quantity=_qty(line["quantity"]),
            )
        )
    await db.flush()
    return row


# --- Production --------------------------------------------------------------------------


async def bake(
    db: AsyncSession,
    tenant_id: str,
    *,
    recipe_id: str,
    batches: float,
    user_id: str | None,
    notes: str | None = None,
) -> m.BakeryBatch:
    """Bake: ingredients leave stock, finished goods arrive, and the item's cost follows the flour."""
    if float(batches) <= 0:
        raise HTTPException(status_code=422, detail="Bake at least part of a batch")
    recipe = await _recipe(db, tenant_id, recipe_id)
    if not recipe.is_active:
        raise HTTPException(status_code=409, detail="This recipe is switched off")
    lines = await _recipe_lines(db, recipe.id)
    needs: list[tuple[m.Product, float]] = []
    short: list[dict] = []
    total_cost = 0.0
    for line in lines:
        item = await _product(db, tenant_id, line.ingredient_id)
        need = _qty(float(line.quantity) * float(batches))
        have = _qty(item.stock_qty)
        if need > have + 0.0005:
            short.append({"name": item.name, "need": need, "have": have})
        needs.append((item, need))
        total_cost += need * float(item.cost_price or 0)
    if short:
        names = ", ".join(f"{row['name']} (need {row['need']:g}, have {row['have']:g})" for row in short)
        raise HTTPException(
            status_code=409,
            detail={"code": "INGREDIENT_SHORT", "message": f"Not enough to bake this: {names}", "short": short},
        )
    made = _qty(float(recipe.yield_qty) * float(batches))
    row = m.BakeryBatch(
        tenant_id=tenant_id,
        batch_number=await _next_number(db, tenant_id, m.BakeryBatch, "BK"),
        recipe_id=recipe.id,
        product_id=recipe.product_id,
        batches=_qty(batches),
        made_qty=made,
        total_cost=_money(total_cost),
        unit_cost=_money(total_cost / made) if made else 0,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for item, need in needs:
        await inventory.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item.id,
            quantity_delta=-need,
            movement_type="stock_out",
            user_id=user_id,
            reference_type=REF_BATCH,
            reference_id=row.id,
            notes=f"Baked {row.batch_number}",
        )
    product = await _product(db, tenant_id, recipe.product_id)
    # Average cost, so a loaf sold later carries what the flour really cost. The value only moves
    # from ingredients to finished goods inside inventory, so no journal is needed.
    on_hand = max(0.0, float(product.stock_qty or 0))
    held_value = on_hand * float(product.cost_price or 0)
    product.cost_price = _money((held_value + total_cost) / (on_hand + made)) if (on_hand + made) else 0
    await inventory.apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=made,
        movement_type="stock_in",
        user_id=user_id,
        reference_type=REF_BATCH,
        reference_id=row.id,
        notes=f"Baked {row.batch_number}",
    )
    await _audit(
        db, tenant_id, user_id, "bakery_batch_baked", "bakery_batch", row.id,
        {"batch_number": row.batch_number, "made": made, "cost": row.total_cost},
    )
    await db.flush()
    return row


def serialize_batch(row: m.BakeryBatch, product_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "batch_number": row.batch_number,
        "recipe_id": row.recipe_id,
        "product_id": row.product_id,
        "product_name": product_name,
        "batches": _qty(row.batches),
        "made_qty": _qty(row.made_qty),
        "unit_cost": _money(row.unit_cost),
        "total_cost": _money(row.total_cost),
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_batches(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BakeryBatch, m.Product.name)
            .outerjoin(m.Product, m.Product.id == m.BakeryBatch.product_id)
            .where(m.BakeryBatch.tenant_id == tenant_id)
            .order_by(m.BakeryBatch.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [serialize_batch(row, name) for row, name in rows]


# --- Waste -------------------------------------------------------------------------------


async def record_waste(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str,
    quantity: float,
    reason: str,
    user_id: str | None,
    notes: str | None = None,
) -> m.BakeryWaste:
    key = (reason or "").strip().lower()
    if key not in WASTE_REASONS:
        raise HTTPException(status_code=422, detail="Choose why it was thrown away")
    qty = _qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Enter how much was thrown away")
    product = await _product(db, tenant_id, product_id)
    if qty > _qty(product.stock_qty) + 0.0005:
        raise HTTPException(status_code=409, detail=f"Only {_qty(product.stock_qty):g} {product.name} in stock")
    cost = _money(qty * float(product.cost_price or 0))
    row = m.BakeryWaste(
        tenant_id=tenant_id,
        product_id=product.id,
        quantity=qty,
        reason=key,
        unit_cost=_money(product.cost_price),
        total_cost=cost,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await inventory.apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=-qty,
        movement_type="stock_out",
        user_id=user_id,
        reference_type=REF_WASTE,
        reference_id=row.id,
        notes=f"Waste: {key}",
    )
    lines: list[dict] = []
    accounting.append_cogs_lines(lines, cost)
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=f"Bakery waste: {product.name}"[:255], lines=lines,
        reference=product.name[:100], source=REF_WASTE, source_id=row.id,
    )
    await _audit(
        db, tenant_id, user_id, "bakery_waste_recorded", "bakery_waste", row.id,
        {"product": product.name, "quantity": qty, "reason": key, "cost": cost},
    )
    await db.flush()
    return row


async def list_waste(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BakeryWaste, m.Product.name)
            .outerjoin(m.Product, m.Product.id == m.BakeryWaste.product_id)
            .where(m.BakeryWaste.tenant_id == tenant_id)
            .order_by(m.BakeryWaste.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": row.id,
            "product_name": name,
            "quantity": _qty(row.quantity),
            "reason": row.reason,
            "total_cost": _money(row.total_cost),
            "notes": row.notes,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row, name in rows
    ]


# --- Till shift --------------------------------------------------------------------------


async def current_shift(db: AsyncSession, tenant_id: str) -> m.BakeryTillShift | None:
    """The counter till. A driver's cash bag is never the till."""
    return (
        await db.execute(
            select(m.BakeryTillShift)
            .where(
                m.BakeryTillShift.tenant_id == tenant_id,
                m.BakeryTillShift.status == "open",
                m.BakeryTillShift.kind == "till",
            )
            .order_by(m.BakeryTillShift.opened_at.desc())
        )
    ).scalars().first()


async def driver_bag(db: AsyncSession, tenant_id: str, driver_id: str | None) -> m.BakeryTillShift | None:
    """The cash a driver carries while out."""
    if not driver_id:
        return None
    return (
        await db.execute(
            select(m.BakeryTillShift).where(
                m.BakeryTillShift.tenant_id == tenant_id,
                m.BakeryTillShift.status == "open",
                m.BakeryTillShift.kind == "driver",
                m.BakeryTillShift.opened_by == driver_id,
            )
        )
    ).scalars().first()


async def _need_shift(db: AsyncSession, tenant_id: str, driver_id: str | None = None) -> m.BakeryTillShift:
    if driver_id:
        bag = await driver_bag(db, tenant_id, driver_id)
        if bag is None:
            raise HTTPException(status_code=409, detail="Start your cash bag before taking money")
        return bag
    shift = await current_shift(db, tenant_id)
    if shift is None:
        raise HTTPException(status_code=409, detail="Open the till before taking money")
    return shift


async def drawer_cash(db: AsyncSession, tenant_id: str, shift: m.BakeryTillShift) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryPayment.amount), 0)).where(
                m.BakeryPayment.tenant_id == tenant_id,
                m.BakeryPayment.shift_id == shift.id,
                m.BakeryPayment.method == "cash",
            )
        )
    ).scalar_one()
    return _money(total)


async def present_shift(db: AsyncSession, tenant_id: str, shift: m.BakeryTillShift) -> dict:
    cash = await drawer_cash(db, tenant_id, shift)
    expected = _money(float(shift.opening_cash or 0) + cash)
    methods = (
        await db.execute(
            select(m.BakeryPayment.method, func.coalesce(func.sum(m.BakeryPayment.amount), 0))
            .where(m.BakeryPayment.tenant_id == tenant_id, m.BakeryPayment.shift_id == shift.id)
            .group_by(m.BakeryPayment.method)
        )
    ).all()
    counted = _money(shift.counted_cash) if shift.counted_cash is not None else None
    return {
        "id": shift.id,
        "status": shift.status,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "opening_cash": _money(shift.opening_cash),
        "cash_taken": cash,
        "expected_cash": expected,
        "counted_cash": counted,
        "over_short": _money(counted - expected) if counted is not None else None,
        "by_method": {method: _money(amount) for method, amount in methods},
        "notes": shift.notes,
    }


async def open_shift(db: AsyncSession, tenant_id: str, *, opening_cash: float, user_id: str | None) -> m.BakeryTillShift:
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    if await current_shift(db, tenant_id):
        raise HTTPException(status_code=409, detail="The till is already open")
    row = m.BakeryTillShift(tenant_id=tenant_id, opened_by=user_id, opening_cash=_money(opening_cash), status="open")
    db.add(row)
    await db.flush()
    return row


async def close_shift(
    db: AsyncSession, tenant_id: str, *, counted_cash: float, notes: str | None, user_id: str | None
) -> m.BakeryTillShift:
    row = await current_shift(db, tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="The till is not open")
    row.counted_cash = _money(counted_cash)
    row.closed_by = user_id
    row.closed_at = _now()
    row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    row.status = "closed"
    await db.flush()
    return row


async def list_closed_shifts(db: AsyncSession, tenant_id: str, *, limit: int = 10) -> list[m.BakeryTillShift]:
    return list(
        (
            await db.execute(
                select(m.BakeryTillShift)
                .where(m.BakeryTillShift.tenant_id == tenant_id, m.BakeryTillShift.status == "closed")
                .order_by(m.BakeryTillShift.closed_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def _pay(
    db, tenant_id: str, *, shift, kind: str, method: str, amount: float, user_id, sale_id=None, order_id=None
) -> None:
    db.add(
        m.BakeryPayment(
            tenant_id=tenant_id,
            shift_id=shift.id,
            kind=kind,
            method=method,
            amount=_money(amount),
            sale_id=sale_id,
            order_id=order_id,
            created_by=user_id,
        )
    )
    await db.flush()


def _method(value: str | None) -> str:
    key = (value or "cash").strip().lower()
    if key not in TILL_METHODS:
        raise HTTPException(status_code=422, detail="Choose cash, card, Mobile Money or wallet")
    return key


# --- Pricing -----------------------------------------------------------------------------


async def _priced_lines(db: AsyncSession, tenant_id: str, lines) -> tuple[list[dict], float, float, float]:
    """Price from the catalogue, never from the request. Returns lines, net, tax and gross."""
    if not lines:
        raise HTTPException(status_code=422, detail="Add at least one item")
    out: list[dict] = []
    net_total = tax_total = gross_total = 0.0
    for line in lines:
        product = await _product(db, tenant_id, line.product_id)
        qty = _qty(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Quantity must be above zero")
        price = _money(product.selling_price)
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        net, tax, gross = tax_svc.compute_line_total(qty, price, spec.rate_pct, spec.pricing_mode)
        out.append(
            {
                "product": product,
                "quantity": qty,
                "unit_price": price,
                "tax": _money(tax),
                "line_total": _money(gross),
                "note": optional_honest_narrative(getattr(line, "note", None), label="note", max_length=255),
            }
        )
        net_total += float(net)
        tax_total += float(tax)
        gross_total += float(gross)
    return out, _money(net_total), _money(tax_total), _money(gross_total)


async def _take_stock(db, tenant_id: str, lines: list[dict], *, user_id, reference: str, number: str) -> float:
    """Take sold items out of stock and return what they cost."""
    for line in lines:
        product = line["product"]
        if line["quantity"] > _qty(product.stock_qty) + 0.0005:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Only {_qty(product.stock_qty):g} {product.name} left",
                },
            )
    cost = 0.0
    for line in lines:
        product = line["product"]
        cost += float(line["quantity"]) * float(product.cost_price or 0)
        await inventory.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=product.id,
            quantity_delta=-line["quantity"],
            movement_type="stock_out",
            user_id=user_id,
            reference_type=REF_SALE,
            reference_id=reference,
            notes=f"Bakery sale {number}",
        )
    return _money(cost)


async def _write_sale(
    db, tenant_id: str, *, lines, net, tax, gross, method, shift, user_id, customer_name=None, order_id=None
) -> m.BakerySale:
    sale = m.BakerySale(
        tenant_id=tenant_id,
        sale_number=await _next_number(db, tenant_id, m.BakerySale, "BS"),
        shift_id=shift.id if shift else None,
        order_id=order_id,
        customer_name=optional_honest_narrative(customer_name, label="customer name", max_length=180),
        payment_method=method,
        status="completed",
        subtotal=net,
        tax=tax,
        total=gross,
        created_by=user_id,
    )
    db.add(sale)
    await db.flush()
    for line in lines:
        db.add(
            m.BakerySaleLine(
                tenant_id=tenant_id,
                sale_id=sale.id,
                product_id=line["product"].id,
                name=line["product"].name,
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                tax=line["tax"],
                line_total=line["line_total"],
                unit_cost=_money(line["product"].cost_price),
            )
        )
    await db.flush()
    return sale


# --- Counter sales -----------------------------------------------------------------------


async def create_sale(
    db: AsyncSession, tenant_id: str, payload, *, user_id: str | None, driver_id: str | None = None
) -> m.BakerySale:
    """A sale at the counter, or by a driver on the road into their cash bag."""
    method = _method(payload.payment_method)
    shift = await _need_shift(db, tenant_id, driver_id)
    lines, net, tax, gross = await _priced_lines(db, tenant_id, payload.lines)
    sale = await _write_sale(
        db, tenant_id, lines=lines, net=net, tax=tax, gross=gross, method=method, shift=shift, user_id=user_id,
        customer_name=payload.customer_name,
    )
    cost = await _take_stock(db, tenant_id, lines, user_id=user_id, reference=sale.id, number=sale.sale_number)
    sale.cost_of_goods = cost
    description = f"Bakery sale {sale.sale_number}"
    journal = [
        {"account_code": _money_account(method), "debit": gross, "credit": 0, "description": description},
        {"account_code": "4000", "debit": 0, "credit": _money(gross - tax), "description": description},
    ]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    accounting.append_cogs_lines(journal, cost)
    sale.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=sale.sale_number, source=REF_SALE, source_id=sale.id,
    )
    await _pay(db, tenant_id, shift=shift, kind="sale", method=method, amount=gross, user_id=user_id, sale_id=sale.id)
    await _audit(
        db, tenant_id, user_id, "bakery_sale", "bakery_sale", sale.id,
        {"sale_number": sale.sale_number, "total": gross, "payment_method": method},
    )
    await db.flush()
    return sale


async def refund_sale(
    db: AsyncSession, tenant_id: str, sale_id: str, *, reason: str, restock: bool, user_id: str | None
) -> m.BakerySale:
    """Give the money back. Food that left the counter is not resold unless staff say it can be."""
    row = (
        await db.execute(select(m.BakerySale).where(m.BakerySale.id == sale_id).with_for_update())
    ).scalar_one_or_none()
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Sale not found")
    if row.status == "refunded":
        raise HTTPException(status_code=409, detail="This sale has already been refunded")
    if row.order_id:
        raise HTTPException(status_code=409, detail="This was a collected order. Refund it from the order.")
    why = require_honest_narrative(reason, label="refund reason", max_length=255)
    shift = await _need_shift(db, tenant_id)
    gross, tax = _money(row.total), _money(row.tax)
    description = f"Bakery refund {row.sale_number}"
    journal = [
        {"account_code": "4000", "debit": _money(gross - tax), "credit": 0, "description": description},
        {"account_code": _money_account(row.payment_method), "debit": 0, "credit": gross, "description": description},
    ]
    if tax > 0:
        journal.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
    if restock:
        accounting.append_cogs_lines(journal, _money(row.cost_of_goods), reverse=True)
        lines = (await db.execute(select(m.BakerySaleLine).where(m.BakerySaleLine.sale_id == row.id))).scalars().all()
        for line in lines:
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=line.product_id,
                quantity_delta=float(line.quantity),
                movement_type="stock_in",
                user_id=user_id,
                reference_type=REF_SALE,
                reference_id=row.id,
                notes=f"Bakery refund {row.sale_number}",
            )
    await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.sale_number, source="bakery_refund", source_id=row.id,
    )
    await _pay(
        db, tenant_id, shift=shift, kind="refund", method=row.payment_method, amount=-gross, user_id=user_id,
        sale_id=row.id,
    )
    row.status = "refunded"
    row.refunded_at = _now()
    row.refund_reason = why
    await _audit(
        db, tenant_id, user_id, "bakery_refund", "bakery_sale", row.id,
        {"sale_number": row.sale_number, "total": gross, "reason": why, "restocked": bool(restock)},
    )
    await db.flush()
    return row


async def present_sale(db: AsyncSession, sale: m.BakerySale) -> dict:
    lines = (await db.execute(select(m.BakerySaleLine).where(m.BakerySaleLine.sale_id == sale.id))).scalars().all()
    return {
        "id": sale.id,
        "sale_number": sale.sale_number,
        "status": sale.status,
        "payment_method": sale.payment_method,
        "customer_name": sale.customer_name,
        "order_id": sale.order_id,
        "subtotal": _money(sale.subtotal),
        "tax": _money(sale.tax),
        "total": _money(sale.total),
        "refund_reason": sale.refund_reason,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
        "items": [
            {
                "name": line.name,
                "quantity": _qty(line.quantity),
                "unit_price": _money(line.unit_price),
                "line_total": _money(line.line_total),
            }
            for line in lines
        ],
    }


async def list_sales(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.BakerySale]:
    return list(
        (
            await db.execute(
                select(m.BakerySale)
                .where(m.BakerySale.tenant_id == tenant_id)
                .order_by(m.BakerySale.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


# --- Pre-orders --------------------------------------------------------------------------


async def _order(db: AsyncSession, tenant_id: str, order_id: str, *, lock: bool = False) -> m.BakeryOrder:
    stmt = select(m.BakeryOrder).where(m.BakeryOrder.id == order_id, m.BakeryOrder.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return row


async def create_order(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.BakeryOrder:
    if payload.due_date < date.today():
        raise HTTPException(status_code=422, detail="Collection cannot be in the past")
    lines, net, tax, gross = await _priced_lines(db, tenant_id, payload.lines)
    delivery = bool(getattr(payload, "delivery", False))
    address = optional_honest_narrative(getattr(payload, "address", None), label="address", max_length=500)
    if delivery and not address:
        raise HTTPException(status_code=422, detail="Add the delivery address")
    driver = await _driver(db, tenant_id, payload.driver_id) if getattr(payload, "driver_id", None) else None
    deposit = _money(payload.deposit or 0)
    if deposit > gross + 0.004:
        raise HTTPException(status_code=422, detail=f"The deposit is more than the {gross:.2f} order")
    method = _method(payload.deposit_method) if deposit > 0 else None
    shift = await _need_shift(db, tenant_id) if deposit > 0 else None
    row = m.BakeryOrder(
        tenant_id=tenant_id,
        order_number=await _next_number(db, tenant_id, m.BakeryOrder, "BO"),
        customer_name=require_honest_narrative(payload.customer_name, label="customer name", max_length=180),
        phone=payload.phone,
        due_date=payload.due_date,
        status="booked",
        subtotal=net,
        tax=tax,
        total=gross,
        deposit=deposit,
        deposit_method=method,
        notes=optional_honest_narrative(payload.notes, label="notes", max_length=500),
        created_by=user_id,
        delivery=delivery,
        address=address if delivery else None,
        driver_id=driver.id if (delivery and driver) else None,
        delivery_status="waiting" if delivery else None,
    )
    db.add(row)
    await db.flush()
    for line in lines:
        db.add(
            m.BakeryOrderLine(
                tenant_id=tenant_id,
                order_id=row.id,
                product_id=line["product"].id,
                name=line["product"].name,
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                tax=line["tax"],
                line_total=line["line_total"],
                note=line["note"],
            )
        )
    if deposit > 0:
        description = f"Bakery order {row.order_number} deposit"
        row.deposit_journal_id = await _post(
            db, tenant_id, user_id=user_id, description=description,
            lines=[
                {"account_code": _money_account(method), "debit": deposit, "credit": 0, "description": description},
                {"account_code": "1100", "debit": 0, "credit": deposit, "description": description},
            ],
            reference=row.order_number, source=REF_ORDER, source_id=row.id,
        )
        await _pay(db, tenant_id, shift=shift, kind="deposit", method=method, amount=deposit, user_id=user_id, order_id=row.id)
    await _audit(
        db, tenant_id, user_id, "bakery_order_created", "bakery_order", row.id,
        {"order_number": row.order_number, "total": gross, "deposit": deposit},
    )
    await db.flush()
    return row


async def mark_ready(db: AsyncSession, tenant_id: str, order_id: str) -> m.BakeryOrder:
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status != "booked":
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    row.status = "ready"
    row.updated_at = _now()
    await db.flush()
    return row


async def collect_order(
    db: AsyncSession,
    tenant_id: str,
    order_id: str,
    *,
    payment_method: str | None,
    user_id: str | None,
    driver_id: str | None = None,
) -> m.BakeryOrder:
    """Hand the order over, at the counter or at the door: the balance is paid, the deposit
    turns into revenue, stock leaves. A driver's money goes into their own cash bag."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN:
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    if driver_id:
        if not row.delivery or row.delivery_status != "out" or row.driver_id != driver_id:
            raise HTTPException(status_code=409, detail="Pick this order up before delivering it")
    gross, tax, deposit = _money(row.total), _money(row.tax), _money(row.deposit)
    balance = _money(gross - deposit)
    method = _method(payment_method) if balance > 0 else (row.deposit_method or "cash")
    if driver_id:
        shift = await _need_shift(db, tenant_id, driver_id) if balance > 0 else await driver_bag(db, tenant_id, driver_id)
    else:
        shift = await _need_shift(db, tenant_id) if balance > 0 else await current_shift(db, tenant_id)
    order_lines = (
        await db.execute(select(m.BakeryOrderLine).where(m.BakeryOrderLine.order_id == row.id))
    ).scalars().all()
    lines = [
        {
            "product": await _product(db, tenant_id, line.product_id),
            "quantity": _qty(line.quantity),
            "unit_price": _money(line.unit_price),
            "tax": _money(line.tax),
            "line_total": _money(line.line_total),
        }
        for line in order_lines
    ]
    sale = await _write_sale(
        db, tenant_id, lines=lines, net=_money(row.subtotal), tax=tax, gross=gross, method=method, shift=shift,
        user_id=user_id, customer_name=row.customer_name, order_id=row.id,
    )
    cost = await _take_stock(db, tenant_id, lines, user_id=user_id, reference=sale.id, number=sale.sale_number)
    sale.cost_of_goods = cost
    description = f"Bakery order {row.order_number} collected"
    journal: list[dict] = []
    if balance > 0:
        journal.append({"account_code": _money_account(method), "debit": balance, "credit": 0, "description": description})
    if deposit > 0:
        journal.append({"account_code": "1100", "debit": deposit, "credit": 0, "description": description})
    journal.append({"account_code": "4000", "debit": 0, "credit": _money(gross - tax), "description": description})
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    accounting.append_cogs_lines(journal, cost)
    sale.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.order_number, source=REF_SALE, source_id=sale.id,
    )
    if balance > 0:
        await _pay(
            db, tenant_id, shift=shift, kind="balance", method=method, amount=balance, user_id=user_id,
            sale_id=sale.id, order_id=row.id,
        )
    row.status = "collected"
    row.collected_at = _now()
    row.updated_at = _now()
    if row.delivery:
        row.delivery_status = "delivered"
    await _audit(
        db, tenant_id, user_id, "bakery_order_collected", "bakery_order", row.id,
        {"order_number": row.order_number, "balance": balance},
    )
    await db.flush()
    return row


async def cancel_order(
    db: AsyncSession, tenant_id: str, order_id: str, *, deposit_action: str | None, reason: str, user_id: str | None
) -> m.BakeryOrder:
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN:
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    deposit = _money(row.deposit)
    if deposit > 0:
        action = (deposit_action or "").strip().lower()
        if action not in {"refund", "keep"}:
            raise HTTPException(status_code=422, detail="Choose whether to refund the deposit or keep it")
        description = f"Bakery order {row.order_number} cancelled, deposit {action}"
        if action == "refund":
            shift = await _need_shift(db, tenant_id)
            method = row.deposit_method or "cash"
            await _post(
                db, tenant_id, user_id=user_id, description=description,
                lines=[
                    {"account_code": "1100", "debit": deposit, "credit": 0, "description": description},
                    {"account_code": _money_account(method), "debit": 0, "credit": deposit, "description": description},
                ],
                reference=row.order_number, source="bakery_order_cancelled", source_id=row.id,
            )
            await _pay(
                db, tenant_id, shift=shift, kind="deposit_refund", method=method, amount=-deposit, user_id=user_id,
                order_id=row.id,
            )
        else:
            await _post(
                db, tenant_id, user_id=user_id, description=description,
                lines=[
                    {"account_code": "1100", "debit": deposit, "credit": 0, "description": description},
                    {"account_code": "4000", "debit": 0, "credit": deposit, "description": description},
                ],
                reference=row.order_number, source="bakery_order_cancelled", source_id=row.id,
            )
        row.deposit_outcome = action
    row.status = "cancelled"
    row.cancel_reason = why
    row.updated_at = _now()
    await _audit(
        db, tenant_id, user_id, "bakery_order_cancelled", "bakery_order", row.id,
        {"order_number": row.order_number, "reason": why, "deposit": deposit, "outcome": row.deposit_outcome},
    )
    await db.flush()
    return row


async def present_order(db: AsyncSession, row: m.BakeryOrder) -> dict:
    lines = (await db.execute(select(m.BakeryOrderLine).where(m.BakeryOrderLine.order_id == row.id))).scalars().all()
    return {
        "id": row.id,
        "order_number": row.order_number,
        "customer_name": row.customer_name,
        "phone": row.phone,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "status": row.status,
        "subtotal": _money(row.subtotal),
        "tax": _money(row.tax),
        "total": _money(row.total),
        "deposit": _money(row.deposit),
        "balance": _money(float(row.total or 0) - float(row.deposit or 0)),
        "deposit_outcome": row.deposit_outcome,
        "notes": row.notes,
        "cancel_reason": row.cancel_reason,
        "delivery": bool(row.delivery),
        "address": row.address,
        "driver_id": row.driver_id,
        "driver_name": (await db.get(m.User, row.driver_id)).full_name if row.driver_id and await db.get(m.User, row.driver_id) else None,
        "delivery_status": row.delivery_status,
        "delivery_note": row.delivery_note,
        "items": [
            {
                "product_id": line.product_id,
                "name": line.name,
                "quantity": _qty(line.quantity),
                "line_total": _money(line.line_total),
                "note": line.note,
            }
            for line in lines
        ],
    }


async def list_orders(db: AsyncSession, tenant_id: str, *, show: str = "open") -> list[m.BakeryOrder]:
    stmt = select(m.BakeryOrder).where(m.BakeryOrder.tenant_id == tenant_id)
    if show == "open":
        stmt = stmt.where(m.BakeryOrder.status.in_(ORDER_OPEN)).order_by(m.BakeryOrder.due_date.asc())
    else:
        stmt = stmt.order_by(m.BakeryOrder.created_at.desc()).limit(200)
    return list((await db.execute(stmt)).scalars())


# --- Today and reports -------------------------------------------------------------------


async def to_bake(db: AsyncSession, tenant_id: str, *, until: date) -> list[dict]:
    """What open orders need by a date, against what is on the shelf."""
    rows = (
        await db.execute(
            select(m.BakeryOrderLine.product_id, m.BakeryOrderLine.name, func.sum(m.BakeryOrderLine.quantity))
            .join(m.BakeryOrder, m.BakeryOrder.id == m.BakeryOrderLine.order_id)
            .where(
                m.BakeryOrder.tenant_id == tenant_id,
                m.BakeryOrder.status.in_(ORDER_OPEN),
                m.BakeryOrder.due_date <= until,
            )
            .group_by(m.BakeryOrderLine.product_id, m.BakeryOrderLine.name)
        )
    ).all()
    out = []
    for product_id, name, ordered in rows:
        product = await db.get(m.Product, product_id)
        on_hand = _qty(product.stock_qty) if product else 0
        needed = _qty(float(ordered) - on_hand)
        out.append({"product_id": product_id, "name": name, "ordered": _qty(ordered), "on_hand": on_hand, "to_bake": max(0.0, needed)})
    return sorted(out, key=lambda row: row["to_bake"], reverse=True)


async def period_numbers(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    begin = datetime.combine(start, time.min)
    finish = datetime.combine(end, time.min) + timedelta(days=1)
    sales = (
        await db.execute(
            select(m.BakerySale).where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.status == "completed",
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
        )
    ).scalars().all()
    revenue = _money(sum(float(s.total or 0) - float(s.tax or 0) for s in sales))
    tax = _money(sum(float(s.tax or 0) for s in sales))
    cost_of_sales = _money(sum(float(s.cost_of_goods or 0) for s in sales))
    waste_rows = (
        await db.execute(
            select(m.BakeryWaste).where(
                m.BakeryWaste.tenant_id == tenant_id,
                m.BakeryWaste.created_at >= begin,
                m.BakeryWaste.created_at < finish,
            )
        )
    ).scalars().all()
    waste_cost = _money(sum(float(w.total_cost or 0) for w in waste_rows))
    by_reason: dict[str, float] = {}
    for w in waste_rows:
        by_reason[w.reason] = _money(by_reason.get(w.reason, 0) + float(w.total_cost or 0))
    batches = (
        await db.execute(
            select(m.BakeryBatch).where(
                m.BakeryBatch.tenant_id == tenant_id,
                m.BakeryBatch.created_at >= begin,
                m.BakeryBatch.created_at < finish,
            )
        )
    ).scalars().all()
    baked_cost = _money(sum(float(b.total_cost or 0) for b in batches))
    sold = (
        await db.execute(
            select(m.BakerySaleLine.name, func.sum(m.BakerySaleLine.quantity), func.sum(m.BakerySaleLine.line_total))
            .join(m.BakerySale, m.BakerySale.id == m.BakerySaleLine.sale_id)
            .where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.status == "completed",
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
            .group_by(m.BakerySaleLine.name)
        )
    ).all()
    paid = (
        await db.execute(
            select(m.BakeryPayment.method, func.coalesce(func.sum(m.BakeryPayment.amount), 0))
            .where(
                m.BakeryPayment.tenant_id == tenant_id,
                m.BakeryPayment.created_at >= begin,
                m.BakeryPayment.created_at < finish,
            )
            .group_by(m.BakeryPayment.method)
        )
    ).all()
    gross_profit = _money(revenue - cost_of_sales - waste_cost)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "revenue": revenue,
        "tax": tax,
        "sale_count": len(sales),
        "cost_of_sales": cost_of_sales,
        "waste_cost": waste_cost,
        "waste_by_reason": by_reason,
        "waste_percent_of_baked": money_json(round(waste_cost / baked_cost * 100, 1)) if baked_cost > 0 else 0,
        "gross_profit": gross_profit,
        "gross_margin_percent": money_json(round(gross_profit / revenue * 100, 1)) if revenue > 0 else 0,
        "baked_batches": len(batches),
        "baked_cost": baked_cost,
        "best_sellers": sorted(
            ({"name": name, "quantity": _qty(qty), "total": _money(total)} for name, qty, total in sold),
            key=lambda row: row["total"],
            reverse=True,
        )[:15],
        "payments_by_method": {method: _money(amount) for method, amount in paid},
    }


async def summary(db: AsyncSession, tenant_id: str, *, money: bool = True) -> dict:
    today = date.today()
    numbers = await period_numbers(db, tenant_id, start=today, end=today)
    open_orders = await list_orders(db, tenant_id, show="open")
    due_today = [o for o in open_orders if o.due_date <= today]
    shift = await current_shift(db, tenant_id)
    body = {
        "date": today.isoformat(),
        "till_open": shift is not None,
        "orders_due_today": len(due_today),
        "orders_overdue": sum(1 for o in open_orders if o.due_date < today),
        "orders_open": len(open_orders),
        "to_bake": await to_bake(db, tenant_id, until=today + timedelta(days=1)),
        "baked_batches_today": numbers["baked_batches"],
    }
    short = [r for r in body["to_bake"] if float(r.get("to_bake") or 0) > 0]
    attention = []
    if shift is None:
        attention.append(dash.item("warning", "The till is closed. Open it before the first sale.", "/bakery?tab=counter"))
    if body["orders_overdue"]:
        attention.append(dash.item("warning", f"{dash.plural(body['orders_overdue'], 'order')} past the collection day", "/bakery?tab=orders"))
    if short:
        attention.append(dash.item("warning", f"Bake {dash.plural(len(short), 'item')} to cover orders due by tomorrow", "/bakery?tab=baking"))
    if body["orders_due_today"]:
        attention.append(dash.item("info", f"{dash.plural(body['orders_due_today'], 'order')} to hand over today", "/bakery?tab=orders"))
    body["attention"] = attention
    if money:
        first, begin, finish = dash.window()
        rows = (
            await db.execute(
                select(m.BakerySale.created_at, m.BakerySale.total, m.BakerySale.tax).where(
                    m.BakerySale.tenant_id == tenant_id,
                    m.BakerySale.status == "completed",
                    m.BakerySale.created_at >= begin,
                    m.BakerySale.created_at <= finish,
                )
            )
        ).all()
        points: dict[date, float] = {}
        for when, total, tax in rows:
            points[when.date()] = points.get(when.date(), 0.0) + float(total or 0) - float(tax or 0)
        body["trend"] = dash.trend("Sales before tax, last 14 days", "money", dash.daily(points, first=first))
        body["sales_yesterday"] = _money(points.get(today - timedelta(days=1), 0.0))
        body.update(
            {
                "sales_today": numbers["revenue"],
                "waste_today": numbers["waste_cost"],
                "gross_profit_today": numbers["gross_profit"],
                "shift": await present_shift(db, tenant_id, shift) if shift else None,
            }
        )
    return body


# --- Stock: items and ingredients, bought in ---------------------------------------------

PAID_WITH = frozenset({"cash", "card", "mobile_money", "bank_transfer", "credit"})
EXPENSE_KINDS = {
    "rent": "Rent",
    "wages": "Wages",
    "utilities": "Light and water",
    "gas": "Gas and fuel",
    "transport": "Transport",
    "repairs": "Repairs",
    "packaging": "Packaging",
    "marketing": "Marketing",
    "other": "Other",
}


async def list_stock(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id).order_by(m.Product.name.asc()))
    ).scalars().all()
    baked = {
        pid
        for (pid,) in (
            await db.execute(select(m.BakeryRecipe.product_id).where(m.BakeryRecipe.tenant_id == tenant_id))
        ).all()
    }
    out = []
    for row in rows:
        stock, reorder = _qty(row.stock_qty), _qty(row.reorder_level)
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "kind": "item" if float(row.selling_price or 0) > 0 else "ingredient",
                "has_recipe": row.id in baked,
                "stock_qty": stock,
                "reorder_level": reorder,
                "low": reorder > 0 and stock <= reorder,
                "cost_price": _money(row.cost_price),
                "price": _money(row.selling_price),
                "value": _money(stock * float(row.cost_price or 0)),
                "is_active": bool(row.is_active),
            }
        )
    return out


async def save_stock_item(db: AsyncSession, tenant_id: str, payload, *, user_id, product_id: str | None = None) -> m.Product:
    """Add or change an item for sale (it has a price) or an ingredient (it has none)."""
    if product_id:
        row = await db.get(m.Product, product_id)
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Item not found")
    else:
        name = require_honest_narrative(payload.name, label="name", max_length=200)
        clash = (
            await db.execute(
                select(m.Product.id).where(m.Product.tenant_id == tenant_id, func.lower(m.Product.name) == name.lower())
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="Something with this name already exists")
        row = m.Product(
            tenant_id=tenant_id,
            name=name,
            sku=f"BK-{(await _next_number(db, tenant_id, m.Product, 'X')).split('-')[1]}",
            category="Bakery items" if payload.kind == "item" else "Ingredients",
            stock_qty=0,
            tracks_batches=False,
            is_active=True,
        )
        db.add(row)
    data = payload.model_dump(exclude_unset=True)
    if "price" in data and data["price"] is not None:
        row.selling_price = _money(data["price"])
    if getattr(payload, "kind", None) == "ingredient" and not product_id:
        row.selling_price = 0
    if "cost_price" in data and data["cost_price"] is not None:
        row.cost_price = _money(data["cost_price"])
    if "reorder_level" in data and data["reorder_level"] is not None:
        row.reorder_level = _qty(data["reorder_level"])
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    await db.flush()
    await _audit(db, tenant_id, user_id, "bakery_stock_saved", "product", row.id, {"name": row.name, "fields": sorted(data)})
    return row


async def receive_stock(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.BakeryStockReceipt:
    """Bought in: stock goes up, the average cost moves, and the books show how it was paid."""
    paid_with = str(payload.paid_with or "").strip().lower()
    if paid_with not in PAID_WITH:
        raise HTTPException(status_code=422, detail="Choose how it was paid")
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == payload.product_id, m.Product.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Item not found")
    qty, cost = _qty(payload.quantity), _money(payload.unit_cost)
    total = _money(qty * cost)
    on_hand = max(float(product.stock_qty or 0), 0.0)
    held = on_hand * float(product.cost_price or 0)
    product.cost_price = _money((held + total) / (on_hand + qty)) if (on_hand + qty) else cost
    await inventory.apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=qty,
        movement_type="stock_in",
        user_id=user_id,
        reference_type="bakery_receipt",
        notes=f"Bought in: {product.name}",
    )
    row = m.BakeryStockReceipt(
        tenant_id=tenant_id,
        receipt_number=await _next_number(db, tenant_id, m.BakeryStockReceipt, "BR"),
        product_id=product.id,
        quantity=qty,
        unit_cost=cost,
        total=total,
        paid_with=paid_with,
        supplier=optional_honest_narrative(payload.supplier, label="supplier", max_length=180),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"Bought {qty:g} {product.name}"
    credit = "2000" if paid_with == "credit" else _money_account(paid_with)
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "1200", "debit": total, "credit": 0, "description": description},
            {"account_code": credit, "debit": 0, "credit": total, "description": description},
        ],
        reference=row.receipt_number, source="bakery_receipt", source_id=row.id,
    )
    await _audit(db, tenant_id, user_id, "bakery_stock_received", "bakery_receipt", row.id, {"total": total, "paid_with": paid_with})
    await db.flush()
    return row


async def list_receipts(db: AsyncSession, tenant_id: str, *, limit: int = 50) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BakeryStockReceipt, m.Product.name)
            .join(m.Product, m.Product.id == m.BakeryStockReceipt.product_id)
            .where(m.BakeryStockReceipt.tenant_id == tenant_id)
            .order_by(m.BakeryStockReceipt.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": r.id,
            "receipt_number": r.receipt_number,
            "name": name,
            "quantity": _qty(r.quantity),
            "unit_cost": _money(r.unit_cost),
            "total": _money(r.total),
            "paid_with": r.paid_with,
            "supplier": r.supplier,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, name in rows
    ]


# --- Expenses ----------------------------------------------------------------------------


async def record_expense(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.BakeryExpense:
    if payload.category not in EXPENSE_KINDS:
        raise HTTPException(status_code=422, detail="Choose what it was for")
    paid_with = str(payload.paid_with or "").strip().lower()
    if paid_with not in PAID_WITH - {"credit"}:
        raise HTTPException(status_code=422, detail="Choose how it was paid")
    if payload.spent_on > date.today():
        raise HTTPException(status_code=422, detail="That day has not happened yet")
    shift = None
    if payload.from_till:
        if paid_with != "cash":
            raise HTTPException(status_code=422, detail="Only cash can come out of the till")
        shift = await _need_shift(db, tenant_id)
    amount = _money(payload.amount)
    row = m.BakeryExpense(
        tenant_id=tenant_id,
        expense_number=await _next_number(db, tenant_id, m.BakeryExpense, "BX"),
        category=payload.category,
        description=require_honest_narrative(payload.description, label="description", max_length=255),
        amount=amount,
        paid_with=paid_with,
        spent_on=payload.spent_on,
        shift_id=shift.id if shift else None,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"{EXPENSE_KINDS[row.category]}: {row.description}"
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "6000", "debit": amount, "credit": 0, "description": description},
            {"account_code": _money_account(paid_with), "debit": 0, "credit": amount, "description": description},
        ],
        reference=row.expense_number, source="bakery_expense", source_id=row.id,
    )
    if shift is not None:
        await _pay(db, tenant_id, shift=shift, kind="expense", method="cash", amount=-amount, user_id=user_id)
    await _audit(db, tenant_id, user_id, "bakery_expense", "bakery_expense", row.id, {"amount": amount, "category": row.category})
    await db.flush()
    return row


def serialize_expense(row: m.BakeryExpense) -> dict:
    return {
        "id": row.id,
        "expense_number": row.expense_number,
        "category": row.category,
        "category_label": EXPENSE_KINDS.get(row.category, row.category),
        "description": row.description,
        "amount": _money(row.amount),
        "paid_with": row.paid_with,
        "from_till": row.shift_id is not None,
        "spent_on": row.spent_on.isoformat(),
    }


async def list_expenses(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.BakeryExpense]:
    return list(
        (
            await db.execute(
                select(m.BakeryExpense)
                .where(m.BakeryExpense.tenant_id == tenant_id)
                .order_by(m.BakeryExpense.spent_on.desc(), m.BakeryExpense.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


# --- The full report ---------------------------------------------------------------------


async def full_report(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    """Everything an owner asks about a period, with the period before it to compare."""
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Choose a year or less")
    base = await period_numbers(db, tenant_id, start=start, end=end)
    span = (end - start).days + 1
    before = await period_numbers(db, tenant_id, start=start - timedelta(days=span), end=start - timedelta(days=1))
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.min) + timedelta(days=1)

    async def expenses_between(first: date, last: date) -> list[m.BakeryExpense]:
        return list(
            (
                await db.execute(
                    select(m.BakeryExpense).where(
                        m.BakeryExpense.tenant_id == tenant_id,
                        m.BakeryExpense.spent_on >= first,
                        m.BakeryExpense.spent_on <= last,
                    )
                )
            ).scalars().all()
        )

    spent = await expenses_between(start, end)
    spent_before = await expenses_between(start - timedelta(days=span), start - timedelta(days=1))
    expenses = _money(sum(float(e.amount or 0) for e in spent))
    by_kind: dict[str, float] = {}
    for e in spent:
        label = EXPENSE_KINDS.get(e.category, e.category)
        by_kind[label] = by_kind.get(label, 0) + float(e.amount or 0)

    sales = (
        await db.execute(
            select(m.BakerySale).where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
        )
    ).scalars().all()
    done = [s for s in sales if s.status == "completed"]
    refunded = [s for s in sales if s.status == "refunded"]
    daily: dict[date, float] = {}
    hours: dict[int, dict] = {}
    for s in done:
        net = float(s.total or 0) - float(s.tax or 0)
        daily[s.created_at.date()] = daily.get(s.created_at.date(), 0) + net
        slot = hours.setdefault(s.created_at.hour, {"hour": s.created_at.hour, "sales": 0, "total": 0.0})
        slot["sales"] += 1
        slot["total"] += net

    items: dict[str, dict] = {}
    if done:
        lines = (
            await db.execute(
                select(m.BakerySaleLine, m.Product.cost_price)
                .join(m.Product, m.Product.id == m.BakerySaleLine.product_id)
                .where(m.BakerySaleLine.sale_id.in_([s.id for s in done]))
            )
        ).all()
        for line, cost_now in lines:
            row = items.setdefault(line.name, {"name": line.name, "quantity": 0.0, "sales": 0.0, "cost": 0.0})
            qty = float(line.quantity or 0)
            unit_cost = float(line.unit_cost if line.unit_cost is not None else (cost_now or 0))
            row["quantity"] += qty
            row["sales"] += float(line.line_total or 0) - float(line.tax or 0)
            row["cost"] += qty * unit_cost
    by_item = []
    for row in items.values():
        profit = row["sales"] - row["cost"]
        by_item.append(
            {
                "name": row["name"],
                "quantity": _qty(row["quantity"]),
                "sales": _money(row["sales"]),
                "cost": _money(row["cost"]),
                "profit": _money(profit),
                "margin_percent": _money(profit / row["sales"] * 100) if row["sales"] > 0 else 0,
            }
        )
    by_item.sort(key=lambda r: -r["sales"])

    waste_rows = (
        await db.execute(
            select(m.BakeryWaste, m.Product.name)
            .join(m.Product, m.Product.id == m.BakeryWaste.product_id)
            .where(m.BakeryWaste.tenant_id == tenant_id, m.BakeryWaste.created_at >= begin, m.BakeryWaste.created_at < finish)
        )
    ).all()
    waste_items: dict[str, dict] = {}
    for w, name in waste_rows:
        row = waste_items.setdefault(name, {"name": name, "quantity": 0.0, "cost": 0.0})
        row["quantity"] += float(w.quantity or 0)
        row["cost"] += float(w.total_cost or 0)

    orders = (
        await db.execute(
            select(m.BakeryOrder).where(
                m.BakeryOrder.tenant_id == tenant_id, m.BakeryOrder.created_at >= begin, m.BakeryOrder.created_at < finish
            )
        )
    ).scalars().all()
    held = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryOrder.deposit), 0)).where(
                m.BakeryOrder.tenant_id == tenant_id, m.BakeryOrder.status.in_(ORDER_OPEN)
            )
        )
    ).scalar_one()
    shifts = (
        await db.execute(
            select(m.BakeryTillShift)
            .where(
                m.BakeryTillShift.tenant_id == tenant_id,
                m.BakeryTillShift.status == "closed",
                m.BakeryTillShift.closed_at >= begin,
                m.BakeryTillShift.closed_at < finish,
            )
            .order_by(m.BakeryTillShift.closed_at.desc())
        )
    ).scalars().all()
    shift_rows = [await present_shift(db, tenant_id, s) for s in shifts]
    bought = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryStockReceipt.total), 0)).where(
                m.BakeryStockReceipt.tenant_id == tenant_id,
                m.BakeryStockReceipt.created_at >= begin,
                m.BakeryStockReceipt.created_at < finish,
            )
        )
    ).scalar_one()

    net_profit = _money(base["gross_profit"] - expenses)
    first = start
    days = span if span <= 92 else 0
    return {
        **base,
        "expenses": expenses,
        "expenses_by_kind": sorted(({"name": k, "total": _money(v)} for k, v in by_kind.items()), key=lambda r: -r["total"]),
        "net_profit": net_profit,
        "net_margin_percent": _money(net_profit / base["revenue"] * 100) if base["revenue"] > 0 else 0,
        "average_sale": _money(base["revenue"] / base["sale_count"]) if base["sale_count"] else 0,
        "refunds": {"count": len(refunded), "total": _money(sum(float(s.total or 0) for s in refunded))},
        "previous": {
            "start_date": (start - timedelta(days=span)).isoformat(),
            "end_date": (start - timedelta(days=1)).isoformat(),
            "revenue": before["revenue"],
            "gross_profit": before["gross_profit"],
            "net_profit": _money(before["gross_profit"] - sum(float(e.amount or 0) for e in spent_before)),
            "sale_count": before["sale_count"],
            "waste_cost": before["waste_cost"],
        },
        "trend": dash.trend(
            "Sales before tax by day", "money", dash.daily(daily, first=first, days=days)
        ) if days else None,
        "by_item": by_item,
        "by_hour": [
            {**hours[h], "total": _money(hours[h]["total"])} for h in sorted(hours)
        ],
        "waste_by_item": sorted(
            ({"name": r["name"], "quantity": _qty(r["quantity"]), "cost": _money(r["cost"])} for r in waste_items.values()),
            key=lambda r: -r["cost"],
        ),
        "orders": {
            "taken": len(orders),
            "collected": sum(1 for o in orders if o.status == "collected"),
            "cancelled": sum(1 for o in orders if o.status == "cancelled"),
            "value": _money(sum(float(o.total or 0) for o in orders if o.status != "cancelled")),
            "deposits_held_now": _money(held),
        },
        "shifts": shift_rows,
        "stock_bought": _money(bought),
        "stock_value_now": _money(sum(r["value"] for r in await list_stock(db, tenant_id) if r["is_active"])),
    }


# --- Drivers: pick up, deliver, take the money, sell on the road ------------------------

DRIVER_ROLE = "bakery_driver"
# Managers and owners sometimes drive too. They use the same cash bag rules as a driver.
DRIVE_ROLES = frozenset({DRIVER_ROLE, "bakery_manager", "company_admin"})
SELF_COUNT_ROLES = frozenset({"bakery_manager", "company_admin"})


async def _driver(db: AsyncSession, tenant_id: str, driver_id: str) -> m.User:
    user = await db.get(m.User, driver_id)
    if user is None or user.tenant_id != tenant_id or user.role not in DRIVE_ROLES or not user.is_active:
        raise HTTPException(status_code=404, detail="Driver not found")
    return user


async def list_drivers(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.role.in_(DRIVE_ROLES), m.User.is_active.is_(True))
            .order_by(m.User.full_name.asc())
        )
    ).scalars().all()
    out = []
    for user in rows:
        bag = await driver_bag(db, tenant_id, user.id)
        out.append(
            {
                "id": user.id,
                "full_name": user.full_name,
                "is_driver": user.role == DRIVER_ROLE,
                "bag": await present_shift(db, tenant_id, bag) if bag else None,
            }
        )
    return out


async def assign_driver(db: AsyncSession, tenant_id: str, order_id: str, *, driver_id: str | None, user_id) -> m.BakeryOrder:
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN or not row.delivery:
        raise HTTPException(status_code=409, detail="Only an open delivery can be given to a driver")
    if row.delivery_status == "out":
        raise HTTPException(status_code=409, detail="The driver already has it on the road")
    row.driver_id = (await _driver(db, tenant_id, driver_id)).id if driver_id else None
    row.delivery_status = "waiting"
    row.updated_at = _now()
    await _audit(db, tenant_id, user_id, "bakery_driver_assigned", "bakery_order", row.id, {"driver_id": row.driver_id})
    await db.flush()
    return row


async def pick_up(
    db: AsyncSession, tenant_id: str, order_id: str, *, driver_id: str, takeover: bool = False
) -> m.BakeryOrder:
    """The driver takes it from the shop. Stock leaves when it is handed to the customer.
    A manager covering for a driver may take over a delivery that has not left yet."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN or not row.delivery:
        raise HTTPException(status_code=409, detail="This is not an open delivery")
    if row.driver_id and row.driver_id != driver_id and not takeover:
        raise HTTPException(status_code=409, detail="Another driver has this delivery")
    if row.delivery_status == "out":
        raise HTTPException(status_code=409, detail="It is already on the road")
    if await driver_bag(db, tenant_id, driver_id) is None:
        raise HTTPException(status_code=409, detail="Start your cash bag before picking up")
    row.driver_id = driver_id
    row.delivery_status = "out"
    row.delivery_note = None
    row.picked_up_at = _now()
    row.updated_at = _now()
    await _audit(db, tenant_id, driver_id, "bakery_picked_up", "bakery_order", row.id, {})
    await db.flush()
    return row


async def delivery_failed(db: AsyncSession, tenant_id: str, order_id: str, *, driver_id: str, reason: str) -> m.BakeryOrder:
    """Nobody home, or wrong address. The order comes back to the shop and stays open."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.delivery_status != "out" or row.driver_id != driver_id:
        raise HTTPException(status_code=409, detail="This delivery is not on the road with you")
    row.delivery_status = "failed"
    row.delivery_note = require_honest_narrative(reason, label="reason", max_length=255)
    row.updated_at = _now()
    await _audit(db, tenant_id, driver_id, "bakery_delivery_failed", "bakery_order", row.id, {"reason": row.delivery_note})
    await db.flush()
    return row


async def driving_this(db: AsyncSession, tenant_id: str, order_id: str, user_id: str | None) -> str | None:
    """The user's id when this order is on the road with them, so its money goes into their bag."""
    if not user_id:
        return None
    row = await db.get(m.BakeryOrder, order_id)
    if row is not None and row.tenant_id == tenant_id and row.delivery_status == "out" and row.driver_id == user_id:
        return user_id
    return None


async def list_deliveries(db: AsyncSession, tenant_id: str, *, driver_id: str | None = None) -> list[m.BakeryOrder]:
    """Open deliveries. A driver sees theirs and the ones nobody has taken yet."""
    stmt = select(m.BakeryOrder).where(
        m.BakeryOrder.tenant_id == tenant_id,
        m.BakeryOrder.delivery.is_(True),
        m.BakeryOrder.status.in_(ORDER_OPEN),
    )
    if driver_id:
        stmt = stmt.where((m.BakeryOrder.driver_id == driver_id) | (m.BakeryOrder.driver_id.is_(None)))
    return list((await db.execute(stmt.order_by(m.BakeryOrder.due_date.asc()))).scalars().all())


async def open_bag(db: AsyncSession, tenant_id: str, *, driver_id: str, opening_cash: float) -> m.BakeryTillShift:
    if await driver_bag(db, tenant_id, driver_id) is not None:
        raise HTTPException(status_code=409, detail="Your cash bag is already started")
    row = m.BakeryTillShift(
        tenant_id=tenant_id, status="open", kind="driver", opening_cash=_money(opening_cash), opened_by=driver_id
    )
    db.add(row)
    await db.flush()
    return row


async def hand_in(
    db: AsyncSession, tenant_id: str, bag_id: str, *, counted_cash: float, user_id, role: str = ""
) -> dict:
    """Back at the shop: the cash is counted by someone else, and any gap is kept on record.
    A manager or owner who drove may count their own bag; the record says so."""
    bag = (
        await db.execute(
            select(m.BakeryTillShift)
            .where(m.BakeryTillShift.id == bag_id, m.BakeryTillShift.tenant_id == tenant_id, m.BakeryTillShift.kind == "driver")
            .with_for_update()
        )
    ).scalar_one_or_none()
    if bag is None:
        raise HTTPException(status_code=404, detail="Cash bag not found")
    if bag.status != "open":
        raise HTTPException(status_code=409, detail="This cash bag is already handed in")
    self_count = bag.opened_by == user_id
    if self_count and role not in SELF_COUNT_ROLES:
        raise HTTPException(status_code=403, detail="Someone else must count your cash")
    out = (
        await db.execute(
            select(func.count()).select_from(m.BakeryOrder).where(
                m.BakeryOrder.tenant_id == tenant_id,
                m.BakeryOrder.driver_id == bag.opened_by,
                m.BakeryOrder.delivery_status == "out",
                m.BakeryOrder.status.in_(ORDER_OPEN),
            )
        )
    ).scalar_one()
    if out:
        raise HTTPException(status_code=409, detail=f"The driver still has {out} delivery on the road. Deliver it or mark it failed first.")
    bag.counted_cash = _money(counted_cash)
    bag.status = "closed"
    bag.closed_at = _now()
    bag.closed_by = user_id
    data = await present_shift(db, tenant_id, bag)
    await _audit(
        db, tenant_id, user_id, "bakery_cash_handed_in", "bakery_till_shift", bag.id,
        {
            "driver_id": bag.opened_by,
            "expected": data["expected_cash"],
            "counted": data["counted_cash"],
            "counted_own_bag": self_count,
        },
    )
    await db.flush()
    return data


async def driver_today(db: AsyncSession, tenant_id: str, *, driver_id: str) -> dict:
    bag = await driver_bag(db, tenant_id, driver_id)
    mine = await list_deliveries(db, tenant_id, driver_id=driver_id)
    today = date.today()
    begin = datetime.combine(today, time.min)
    delivered = (
        await db.execute(
            select(func.count()).select_from(m.BakeryOrder).where(
                m.BakeryOrder.tenant_id == tenant_id,
                m.BakeryOrder.driver_id == driver_id,
                m.BakeryOrder.delivery_status == "delivered",
                m.BakeryOrder.collected_at >= begin,
            )
        )
    ).scalar_one()
    sold = (
        await db.execute(
            select(func.count()).select_from(m.BakerySale).where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.created_by == driver_id,
                m.BakerySale.order_id.is_(None),
                m.BakerySale.status == "completed",
                m.BakerySale.created_at >= begin,
            )
        )
    ).scalar_one()
    return {
        "bag": await present_shift(db, tenant_id, bag) if bag else None,
        "to_pick_up": sum(1 for o in mine if o.delivery_status != "out"),
        "on_the_road": sum(1 for o in mine if o.delivery_status == "out" and o.driver_id == driver_id),
        "delivered_today": int(delivered or 0),
        "road_sales_today": int(sold or 0),
    }
