"""Bakery desk: recipes, production, its own till, pre-orders and waste, on its own tables.

Ingredients and finished goods are ordinary products, so the back office (stock, purchasing,
accounting, tax) stays the shared engine. Everything a bakery does at the counter lives here
and never touches retail ``transactions`` or ``pos_sessions``.

Every movement of money goes through ``bakery_payments``, so the drawer count is one sum.
A deposit is money held for the customer: it credits receivables, and becomes revenue when the
order is collected or the deposit is kept.
"""

from __future__ import annotations

import contextvars
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
# A bakery may run more than one till. Each request says which one (header X-Bakery-Till, the
# shift id), or uses the till the signed-in person opened, or the only one open. Set per request
# by bakery_api; reset at the start of every request so nothing leaks between requests.
CHOSEN_TILL: contextvars.ContextVar[str | None] = contextvars.ContextVar("bakery_till", default=None)
TILL_USER: contextvars.ContextVar[str | None] = contextvars.ContextVar("bakery_till_user", default=None)
DEFAULT_TILL = "Counter"
WASTE_REASONS = frozenset({"unsold", "burnt", "damaged", "expired", "other"})
ORDER_OPEN = ("booked", "ready")
REF_BATCH = "bakery_batch"
REF_SALE = "bakery_sale"
REF_WASTE = "bakery_waste"
REF_ORDER = "bakery_order"
REF_REFUND = "bakery_refund"
REF_COUNT = "bakery_stock_count"

# A deposit is money held for the customer until the order is handed over: a liability.
DEPOSIT_ACCOUNT = "2168"
OLD_DEPOSIT_ACCOUNT = "1100"  # where deposits went before 15 Nov 2026
CASH_OVER_SHORT = "6900"
COUNT_DIFFERENCES = "5100"
INPUT_TAX = "1300"
BAKERY_ACCOUNTS = [
    ("2168", "Customer Deposits (Bakery Orders)", "liability"),
    ("5100", "Stock Count Differences", "expense"),
    ("6010", "Rent", "expense"),
    ("6030", "Light and Water", "expense"),
    ("6040", "Gas and Fuel", "expense"),
    ("6050", "Transport", "expense"),
    ("6060", "Repairs and Maintenance", "expense"),
    ("6070", "Packaging", "expense"),
    ("6080", "Marketing", "expense"),
    ("6200", "Salaries and Wages", "expense"),
    ("6900", "Cash Over and Short", "expense"),
]
EXPENSE_ACCOUNTS = {
    "rent": "6010",
    "wages": "6200",
    "utilities": "6030",
    "gas": "6040",
    "transport": "6050",
    "repairs": "6060",
    "packaging": "6070",
    "marketing": "6080",
    "other": "6000",
}
# Sales that happened. A refund is its own row on the day of the refund, so a refunded sale
# still counts on the day it was made.
SOLD = ("completed", "part_refunded", "refunded")
# Cashiers and drivers may take this much off a line; managers and owners any amount.
STAFF_MAX_DISCOUNT = 10.0
DISCOUNT_ANY_ROLES = frozenset({"bakery_manager", "company_admin", "super_admin"})


def _now() -> datetime:
    return datetime.utcnow()


async def _zone(db: AsyncSession, tenant_id: str):
    from app import hotel as hotel_svc

    return await hotel_svc.hotel_zone(db, tenant_id)


async def bakery_today(db: AsyncSession, tenant_id: str) -> date:
    """Today in the company's timezone (Company → Timezone), not the server's."""
    return datetime.now(await _zone(db, tenant_id)).date()


async def _bounds(db: AsyncSession, tenant_id: str, start: date, end: date) -> tuple[datetime, datetime]:
    """Local midnight at the start and after the end, as the UTC times rows are stored in."""
    from datetime import timezone

    zone = await _zone(db, tenant_id)

    def utc(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)

    return utc(start), utc(end + timedelta(days=1))


async def _localiser(db: AsyncSession, tenant_id: str):
    from datetime import timezone

    zone = await _zone(db, tenant_id)
    return lambda when: when.replace(tzinfo=timezone.utc).astimezone(zone).replace(tzinfo=None)


async def _ensure_accounts(db: AsyncSession, tenant_id: str) -> None:
    from app import schema_compat

    await accounting.ensure_default_accounts(db, tenant_id)
    existing = await schema_compat.existing_codes(db, "accounts", tenant_id)
    for code, name, account_type in BAKERY_ACCOUNTS:
        if code in existing:
            continue
        await schema_compat.insert_matching_row(
            db,
            "accounts",
            {
                "tenant_id": tenant_id,
                "code": code,
                "name": name,
                "account_type": account_type,
                "balance": 0,
                "opening_balance": 0,
                "is_cash_account": False,
                "is_bank_account": False,
                "is_system": True,
                "is_active": True,
                "parent_id": None,
                "company_id": None,
            },
        )
    await db.flush()


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
    await _ensure_accounts(db, tenant_id)
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
    from app import bakery_items as items_svc

    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True), m.Product.selling_price > 0)
            .order_by(m.Product.name.asc())
        )
    ).scalars().all()
    today = await bakery_today(db, tenant_id)
    shelf = await items_svc.shelf(db, tenant_id, today=today, local=await _localiser(db, tenant_id))
    settings = await items_svc.settings_map(db, tenant_id, [r.id for r in rows])
    out = []
    for row in rows:
        # What the customer actually pays for one, tax included, so the counter shows the
        # same total the sale will charge.
        spec = await tax_svc.resolve_product_tax(db, tenant_id, row)
        _net, _tax, gross = tax_svc.compute_line_total(1, _money(row.selling_price), spec.rate_pct, spec.pricing_mode)
        conf = settings.get(row.id)
        mine = [s for s in shelf if s["product_id"] == row.id]
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "price": _money(row.selling_price),
                "price_to_pay": _money(gross),
                "category": (row.category or "Bakery").strip() or "Bakery",
                "stock_qty": _qty(row.stock_qty),
                "day_old_qty": _qty(sum(s["quantity"] for s in mine if s["state"] in ("day_old", "last_day"))),
                "expired_qty": _qty(sum(s["quantity"] for s in mine if s["state"] == "expired")),
                "day_old_discount_pct": money_json(conf.day_old_discount_pct) if conf and conf.day_old_discount_pct else None,
                "allergens": list(conf.allergens or []) if conf else [],
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
    from app import bakery_items as items_svc

    product = await db.get(m.Product, recipe.product_id)
    lines = []
    batch_cost = 0.0
    recipe_lines = await _recipe_lines(db, recipe.id)
    settings = await items_svc.settings_map(db, recipe.tenant_id, [x.ingredient_id for x in recipe_lines])
    for line in recipe_lines:
        item = await db.get(m.Product, line.ingredient_id)
        cost = _money(float(line.quantity) * float(item.cost_price or 0)) if item else 0.0
        batch_cost += cost
        lines.append(
            {
                "ingredient_id": line.ingredient_id,
                "name": item.name if item else "Unknown",
                "quantity": _qty(line.quantity),
                "unit": items_svc.stock_unit(settings.get(line.ingredient_id)),
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
    """A line may be written in any unit of the ingredient's kind (250 g of a kilo ingredient);
    it is stored in the ingredient's stock unit, so a bake takes the right amount out."""
    from app import bakery_items as items_svc

    await _product(db, tenant_id, product_id)
    clean_name = require_honest_narrative(name, label="recipe name", max_length=150)
    if float(yield_qty) <= 0:
        raise HTTPException(status_code=422, detail="A recipe must make at least some")
    if not lines:
        raise HTTPException(status_code=422, detail="Add at least one ingredient")
    seen: set[str] = set()
    settings = await items_svc.settings_map(db, tenant_id, [str(x["ingredient_id"]) for x in lines])
    stored: list[tuple[str, float]] = []
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
        unit = items_svc.stock_unit(settings.get(ingredient))
        quantity = items_svc.convert(float(line["quantity"]), line.get("unit") or unit, unit)
        if _qty(quantity) <= 0:
            raise HTTPException(status_code=422, detail="That amount is too small to keep. Use a smaller stock unit.")
        stored.append((ingredient, quantity))
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
    for ingredient, quantity in stored:
        db.add(
            m.BakeryRecipeLine(
                tenant_id=tenant_id,
                recipe_id=row.id,
                ingredient_id=ingredient,
                quantity=_qty(quantity),
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
    """Bake: ingredients leave stock, finished goods arrive, and the item's cost follows the flour.
    With a shelf life set, the bake gets its best-before date."""
    from app import bakery_items as items_svc

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
    conf = await items_svc.settings_for(db, tenant_id, recipe.product_id)
    today = await bakery_today(db, tenant_id)
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
        best_before=today + timedelta(days=int(conf.shelf_life_days)) if conf and conf.shelf_life_days else None,
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
        "best_before": row.best_before.isoformat() if row.best_before else None,
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


async def open_tills(db: AsyncSession, tenant_id: str) -> list[m.BakeryTillShift]:
    return list(
        (
            await db.execute(
                select(m.BakeryTillShift)
                .where(
                    m.BakeryTillShift.tenant_id == tenant_id,
                    m.BakeryTillShift.status == "open",
                    m.BakeryTillShift.kind == "till",
                )
                .order_by(m.BakeryTillShift.opened_at.asc())
            )
        ).scalars()
    )


async def current_shift(db: AsyncSession, tenant_id: str) -> m.BakeryTillShift | None:
    """The counter till this request is using. A driver's cash bag is never the till."""
    tills = await open_tills(db, tenant_id)
    if not tills:
        return None
    chosen = CHOSEN_TILL.get()
    if chosen:
        return next((t for t in tills if t.id == chosen), None)
    user = TILL_USER.get()
    mine = [t for t in tills if user and t.opened_by == user]
    if mine:
        return mine[-1]
    return tills[0] if len(tills) == 1 else None


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
        tills = await open_tills(db, tenant_id)
        if CHOSEN_TILL.get() and tills:
            raise HTTPException(status_code=409, detail={"code": "TILL_CLOSED", "message": "That till is closed. Choose an open till."})
        if len(tills) > 1:
            raise HTTPException(
                status_code=409,
                detail={"code": "TILL_CHOOSE", "message": "More than one till is open. Choose which till you are using."},
            )
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
    opener = await db.get(m.User, shift.opened_by) if shift.opened_by else None
    return {
        "id": shift.id,
        "status": shift.status,
        "till_name": shift.till_name or (DEFAULT_TILL if shift.kind == "till" else None),
        "opened_by_name": opener.full_name if opener else None,
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


async def open_shift(
    db: AsyncSession, tenant_id: str, *, opening_cash: float, user_id: str | None, till_name: str | None = None
) -> m.BakeryTillShift:
    """Open a till. Several can be open at once (front counter, second counter, another shop),
    each with its own name and drawer; one person runs one till at a time."""
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    name = optional_honest_narrative(till_name, label="till name", max_length=60) or DEFAULT_TILL
    for till in await open_tills(db, tenant_id):
        if (till.till_name or DEFAULT_TILL).lower() == name.lower():
            raise HTTPException(status_code=409, detail="The till is already open" if name == DEFAULT_TILL else f"{name} is already open")
        if user_id and till.opened_by == user_id:
            raise HTTPException(status_code=409, detail=f"You already have {till.till_name or DEFAULT_TILL} open. Close it first.")
    row = m.BakeryTillShift(
        tenant_id=tenant_id, opened_by=user_id, opening_cash=_money(opening_cash), status="open", till_name=name
    )
    db.add(row)
    await db.flush()
    return row


async def _book_over_short(db, tenant_id: str, shift: m.BakeryTillShift, *, expected: float, user_id, label: str) -> float:
    """Cash counted against cash expected: the gap goes to Cash Over and Short, so the cash
    account matches the money really in the drawer or bag."""
    gap = _money(float(shift.counted_cash or 0) - float(expected or 0))
    if abs(gap) < 0.005:
        return 0.0
    cash = _money_account("cash")
    description = f"{label}: cash {'over' if gap > 0 else 'short'} {abs(gap):.2f}"
    if gap > 0:
        lines = [
            {"account_code": cash, "debit": gap, "credit": 0, "description": description},
            {"account_code": CASH_OVER_SHORT, "debit": 0, "credit": gap, "description": description},
        ]
    else:
        lines = [
            {"account_code": CASH_OVER_SHORT, "debit": -gap, "credit": 0, "description": description},
            {"account_code": cash, "debit": 0, "credit": -gap, "description": description},
        ]
    shift.variance_journal_id = await _post(
        db, tenant_id, user_id=user_id, description=description[:255], lines=lines,
        reference=label[:100], source="bakery_cash_count", source_id=shift.id,
    )
    return gap


async def close_shift(
    db: AsyncSession, tenant_id: str, *, counted_cash: float, notes: str | None, user_id: str | None
) -> m.BakeryTillShift:
    row = await current_shift(db, tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="The till is not open")
    expected = _money(float(row.opening_cash or 0) + await drawer_cash(db, tenant_id, row))
    row.counted_cash = _money(counted_cash)
    row.closed_by = user_id
    row.closed_at = _now()
    row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    row.status = "closed"
    gap = await _book_over_short(db, tenant_id, row, expected=expected, user_id=user_id, label="Till count")
    await _audit(
        db, tenant_id, user_id, "bakery_till_closed", "bakery_till_shift", row.id,
        {"expected": expected, "counted": row.counted_cash, "over_short": gap},
    )
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


async def _priced_lines(
    db: AsyncSession, tenant_id: str, lines, *, max_discount: float | None = 100.0, enforce_options: bool = False
) -> tuple[list[dict], float, float, float]:
    """Price from the catalogue, never from the request. Returns lines, net, tax and gross.

    A line may carry a discount percent; it comes off the price before tax is worked out, so the
    tax charged is tax on what the customer really paid. A day-old line takes the item's day-old
    percent (set by a manager), for as much day-old stock as there is, whoever is selling."""
    from app import bakery_items as items_svc

    if not lines:
        raise HTTPException(status_code=422, detail="Add at least one item")
    out: list[dict] = []
    net_total = tax_total = gross_total = 0.0
    day_old_used: dict[str, float] = {}
    for line in lines:
        product = await _product(db, tenant_id, line.product_id)
        qty = _qty(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Quantity must be above zero")
        price = _money(product.selling_price)
        picked = getattr(line, "options", None)
        opt_note = None
        if picked or enforce_options:
            extra, opt_note = items_svc.apply_options(
                await items_svc.settings_for(db, tenant_id, product.id), picked, product_name=product.name, enforce=enforce_options
            )
            price = _money(price + extra)
        pct = float(getattr(line, "discount_percent", None) or 0)
        day_old = bool(getattr(line, "day_old", False))
        if day_old:
            conf = await items_svc.settings_for(db, tenant_id, product.id)
            if not conf or not conf.day_old_discount_pct:
                raise HTTPException(status_code=422, detail=f"{product.name} has no day-old price. A manager sets it under Stock.")
            have = await items_svc.day_old_on_hand(
                db, tenant_id, product.id, today=await bakery_today(db, tenant_id), local=await _localiser(db, tenant_id)
            )
            used = day_old_used.get(product.id, 0.0) + qty
            if used > have + 0.0005:
                raise HTTPException(status_code=409, detail=f"Only {have:g} day-old {product.name} on the shelf")
            day_old_used[product.id] = used
            pct = float(conf.day_old_discount_pct)
        if pct < 0 or pct > 100:
            raise HTTPException(status_code=422, detail="A discount is between 0 and 100 percent")
        if not day_old and max_discount is not None and pct > max_discount + 1e-9:
            raise HTTPException(
                status_code=403,
                detail={"code": "DISCOUNT_TOO_BIG", "message": f"You can take off up to {max_discount:g}%. Ask a manager for more."},
            )
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        _, _, full_gross = tax_svc.compute_line_total(qty, price, spec.rate_pct, spec.pricing_mode)
        charged = _money(price * (1 - pct / 100)) if pct else price
        net, tax, gross = tax_svc.compute_line_total(qty, charged, spec.rate_pct, spec.pricing_mode)
        out.append(
            {
                "product": product,
                "quantity": qty,
                "unit_price": price,
                "discount": _money(float(full_gross) - float(gross)) if pct else 0.0,
                "day_old": day_old,
                "tax": _money(tax),
                "line_total": _money(gross),
                "note": (
                    "; ".join(x for x in (opt_note, optional_honest_narrative(getattr(line, "note", None), label="note", max_length=255)) if x)[:255]
                    or None
                ),
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
    db, tenant_id: str, *, lines, net, tax, gross, method, shift, user_id, customer_name=None, order_id=None,
    discount_reason=None,
) -> m.BakerySale:
    discount = _money(sum(float(line.get("discount") or 0) for line in lines))
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
        discount=discount,
        discount_reason=discount_reason if discount > 0 else None,
        refunded_total=0,
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
                discount=_money(line.get("discount") or 0),
                refunded_qty=0,
            )
        )
    await db.flush()
    return sale


# --- Counter sales -----------------------------------------------------------------------


def _split(payments, gross: float) -> list[tuple[str, float]]:
    """A bill paid more than one way. One part may leave its amount out and takes the rest
    ("10 in cash, the rest on Mobile Money"); otherwise the parts must add up to the bill."""
    parts: dict[str, float] = {}
    rest_method: str | None = None
    for part in payments:
        method = _method(part.method)
        if part.amount is None:
            if rest_method is not None:
                raise HTTPException(status_code=422, detail="Only one part can take the rest of the bill")
            rest_method = method
            continue
        amount = _money(part.amount)
        if amount <= 0:
            raise HTTPException(status_code=422, detail="Each part of the payment must be above zero")
        parts[method] = _money(parts.get(method, 0) + amount)
    if rest_method is not None:
        rest = _money(gross - sum(parts.values()))
        if rest <= 0:
            raise HTTPException(
                status_code=422,
                detail={"code": "SPLIT_NOT_EQUAL", "message": f"The other parts already cover the {gross:.2f} bill"},
            )
        parts[rest_method] = _money(parts.get(rest_method, 0) + rest)
    if len(parts) < 2:
        raise HTTPException(status_code=422, detail="A split payment needs two or more ways to pay")
    paid = _money(sum(parts.values()))
    if abs(paid - gross) > 0.009:
        raise HTTPException(
            status_code=422,
            detail={"code": "SPLIT_NOT_EQUAL", "message": f"The parts add up to {paid:.2f}; the bill is {gross:.2f}"},
        )
    return list(parts.items())


async def create_sale(
    db: AsyncSession,
    tenant_id: str,
    payload,
    *,
    user_id: str | None,
    driver_id: str | None = None,
    role: str | None = None,
) -> m.BakerySale:
    """A sale at the counter, or by a driver on the road into their cash bag."""
    payments = getattr(payload, "payments", None) or None
    method = "split" if payments else _method(payload.payment_method)
    shift = await _need_shift(db, tenant_id, driver_id)
    max_discount = None if (role or "") in DISCOUNT_ANY_ROLES else STAFF_MAX_DISCOUNT
    lines, net, tax, gross = await _priced_lines(db, tenant_id, payload.lines, max_discount=max_discount)
    discounted = any(float(line["discount"] or 0) > 0 for line in lines)
    reason = None
    if discounted:
        typed = getattr(payload, "discount_reason", None)
        if not (typed or "").strip() and all(line["day_old"] for line in lines if float(line["discount"] or 0) > 0):
            typed = "Day-old"
        reason = require_honest_narrative(typed, label="discount reason", max_length=255)
    parts = _split(payments, gross) if payments else [(method, gross)]
    sale = await _write_sale(
        db, tenant_id, lines=lines, net=net, tax=tax, gross=gross, method=method, shift=shift, user_id=user_id,
        customer_name=payload.customer_name, discount_reason=reason,
    )
    cost = await _take_stock(db, tenant_id, lines, user_id=user_id, reference=sale.id, number=sale.sale_number)
    sale.cost_of_goods = cost
    description = f"Bakery sale {sale.sale_number}"
    journal = [
        {"account_code": _money_account(part_method), "debit": amount, "credit": 0, "description": description}
        for part_method, amount in parts
    ]
    journal.append({"account_code": "4000", "debit": 0, "credit": _money(gross - tax), "description": description})
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    accounting.append_cogs_lines(journal, cost)
    sale.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=sale.sale_number, source=REF_SALE, source_id=sale.id,
    )
    for part_method, amount in parts:
        await _pay(db, tenant_id, shift=shift, kind="sale", method=part_method, amount=amount, user_id=user_id, sale_id=sale.id)
    details = {"sale_number": sale.sale_number, "total": gross, "payment_method": method}
    if payments:
        details["payments"] = {k: v for k, v in parts}
    if discounted:
        details.update({"discount": _money(sale.discount), "discount_reason": reason})
    await _audit(db, tenant_id, user_id, "bakery_sale", "bakery_sale", sale.id, details)
    await db.flush()
    return sale


async def _refunded_by_line(db, sale_id: str) -> dict[str, tuple[float, float, float]]:
    """What has gone back already on each sale line: quantity, tax and money."""
    rows = (
        await db.execute(
            select(
                m.BakeryRefundLine.sale_line_id,
                func.coalesce(func.sum(m.BakeryRefundLine.quantity), 0),
                func.coalesce(func.sum(m.BakeryRefundLine.tax), 0),
                func.coalesce(func.sum(m.BakeryRefundLine.line_total), 0),
            )
            .join(m.BakeryRefund, m.BakeryRefund.id == m.BakeryRefundLine.refund_id)
            .where(m.BakeryRefund.sale_id == sale_id)
            .group_by(m.BakeryRefundLine.sale_line_id)
        )
    ).all()
    return {lid: (float(q or 0), float(t or 0), float(g or 0)) for lid, q, t, g in rows if lid}


async def refund_sale(
    db: AsyncSession,
    tenant_id: str,
    sale_id: str,
    *,
    reason: str,
    restock: bool,
    user_id: str | None,
    lines: list | None = None,
    method: str | None = None,
) -> m.BakerySale:
    """Give money back on the whole sale or some of it. Food that left the counter is not
    resold unless staff say it can be. A collected order is refunded the same way."""
    row = (
        await db.execute(select(m.BakerySale).where(m.BakerySale.id == sale_id).with_for_update())
    ).scalar_one_or_none()
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Sale not found")
    if row.status == "refunded":
        raise HTTPException(status_code=409, detail="This sale has already been refunded")
    why = require_honest_narrative(reason, label="refund reason", max_length=255)
    if row.payment_method == "split":
        if not method:
            raise HTTPException(status_code=422, detail="This sale was paid more than one way. Choose how to give the money back.")
        pay_back = _method(method)
    else:
        pay_back = _method(method) if method else row.payment_method
    sale_lines = (
        await db.execute(select(m.BakerySaleLine).where(m.BakerySaleLine.sale_id == row.id))
    ).scalars().all()
    by_id = {line.id: line for line in sale_lines}
    done = await _refunded_by_line(db, row.id)
    wanted: dict[str, float] = {}
    if lines:
        for part in lines:
            line_id = str(part.sale_line_id)
            if line_id not in by_id:
                raise HTTPException(status_code=404, detail="That item is not on this sale")
            wanted[line_id] = _qty(wanted.get(line_id, 0) + float(part.quantity))
    else:
        for line in sale_lines:
            left = _qty(float(line.quantity) - done.get(line.id, (0, 0, 0))[0])
            if left > 0:
                wanted[line.id] = left
    if not wanted:
        raise HTTPException(status_code=409, detail="Nothing is left to refund on this sale")
    out_lines: list[dict] = []
    for line_id, qty in wanted.items():
        line = by_id[line_id]
        back_qty, back_tax, back_total = done.get(line_id, (0.0, 0.0, 0.0))
        left = _qty(float(line.quantity) - back_qty)
        if qty <= 0 or qty > left + 0.0005:
            raise HTTPException(status_code=409, detail=f"Only {left:g} {line.name} can still be refunded")
        if abs(qty - left) < 0.0005:
            # The last of the line takes what is left, so rounding never leaves a cent behind.
            tax = _money(float(line.tax or 0) - back_tax)
            total = _money(float(line.line_total or 0) - back_total)
        else:
            share = qty / float(line.quantity)
            tax = _money(float(line.tax or 0) * share)
            total = _money(float(line.line_total or 0) * share)
        cost = _money(qty * float(line.unit_cost or 0)) if restock else 0.0
        out_lines.append({"line": line, "quantity": qty, "tax": tax, "total": total, "cost": cost})
    total = _money(sum(x["total"] for x in out_lines))
    tax = _money(sum(x["tax"] for x in out_lines))
    cost_back = _money(sum(x["cost"] for x in out_lines))
    shift = await _need_shift(db, tenant_id)
    if pay_back == "cash":
        in_drawer = _money(float(shift.opening_cash or 0) + await drawer_cash(db, tenant_id, shift))
        if total > in_drawer + 0.004:
            raise HTTPException(status_code=409, detail=f"The drawer should only hold {in_drawer:.2f}. Refund another way.")
    refund = m.BakeryRefund(
        tenant_id=tenant_id,
        refund_number=await _next_number(db, tenant_id, m.BakeryRefund, "RF"),
        sale_id=row.id,
        shift_id=shift.id,
        method=pay_back,
        subtotal=_money(total - tax),
        tax=tax,
        total=total,
        cost_back=cost_back,
        restock=bool(restock),
        reason=why,
        created_by=user_id,
    )
    db.add(refund)
    await db.flush()
    description = f"Bakery refund {refund.refund_number} on {row.sale_number}"
    journal = [{"account_code": "4000", "debit": _money(total - tax), "credit": 0, "description": description}]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": tax, "credit": 0, "description": description})
    journal.append({"account_code": _money_account(pay_back), "debit": 0, "credit": total, "description": description})
    accounting.append_cogs_lines(journal, cost_back, reverse=True)
    for x in out_lines:
        line = x["line"]
        db.add(
            m.BakeryRefundLine(
                tenant_id=tenant_id, refund_id=refund.id, sale_line_id=line.id, product_id=line.product_id,
                name=line.name, quantity=x["quantity"], tax=x["tax"], line_total=x["total"],
            )
        )
        line.refunded_qty = _qty(float(line.refunded_qty or 0) + x["quantity"])
        if restock:
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=line.product_id,
                quantity_delta=float(x["quantity"]),
                movement_type="stock_in",
                user_id=user_id,
                reference_type=REF_REFUND,
                reference_id=refund.id,
                notes=f"Bakery refund {refund.refund_number}",
            )
    refund.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description[:255], lines=journal,
        reference=refund.refund_number, source=REF_REFUND, source_id=refund.id,
    )
    await _pay(
        db, tenant_id, shift=shift, kind="refund", method=pay_back, amount=-total, user_id=user_id, sale_id=row.id,
    )
    row.refunded_total = _money(float(row.refunded_total or 0) + total)
    everything_back = all(
        float(line.refunded_qty or 0) >= float(line.quantity or 0) - 0.0005 for line in sale_lines
    )
    row.status = "refunded" if everything_back else "part_refunded"
    row.refunded_at = _now()
    row.refund_reason = why
    await _audit(
        db, tenant_id, user_id, "bakery_refund", "bakery_sale", row.id,
        {
            "sale_number": row.sale_number, "refund_number": refund.refund_number, "total": total,
            "reason": why, "restocked": bool(restock), "method": pay_back, "whole_sale": everything_back,
        },
    )
    await db.flush()
    return row


async def present_sale(db: AsyncSession, sale: m.BakerySale) -> dict:
    lines = (await db.execute(select(m.BakerySaleLine).where(m.BakerySaleLine.sale_id == sale.id))).scalars().all()
    paid = (
        await db.execute(
            select(m.BakeryPayment.method, func.coalesce(func.sum(m.BakeryPayment.amount), 0))
            .where(m.BakeryPayment.sale_id == sale.id, m.BakeryPayment.amount > 0)
            .group_by(m.BakeryPayment.method)
        )
    ).all() if sale.payment_method == "split" else []
    return {
        "id": sale.id,
        "sale_number": sale.sale_number,
        "status": sale.status,
        "payment_method": sale.payment_method,
        "payments": [{"method": k, "amount": _money(v)} for k, v in paid],
        "customer_name": sale.customer_name,
        "order_id": sale.order_id,
        "subtotal": _money(sale.subtotal),
        "tax": _money(sale.tax),
        "total": _money(sale.total),
        "discount": _money(sale.discount),
        "discount_reason": sale.discount_reason,
        "refunded_total": _money(sale.refunded_total),
        "refund_reason": sale.refund_reason,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
        "items": [
            {
                "id": line.id,
                "name": line.name,
                "quantity": _qty(line.quantity),
                "unit_price": _money(line.unit_price),
                "discount": _money(line.discount),
                "line_total": _money(line.line_total),
                "refunded_qty": _qty(line.refunded_qty),
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
    if payload.due_date < await bakery_today(db, tenant_id):
        raise HTTPException(status_code=422, detail="Collection cannot be in the past")
    lines, net, tax, gross = await _priced_lines(db, tenant_id, payload.lines, enforce_options=True)
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
        deposit_account=DEPOSIT_ACCOUNT if deposit > 0 else None,
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
                {"account_code": DEPOSIT_ACCOUNT, "debit": 0, "credit": deposit, "description": description},
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


def _deposit_account(row: m.BakeryOrder) -> str:
    """The account this order's deposit sits in: 2168, or 1100 for deposits taken before."""
    return row.deposit_account or OLD_DEPOSIT_ACCOUNT


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
        journal.append({"account_code": _deposit_account(row), "debit": deposit, "credit": 0, "description": description})
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


async def _deposit_parts(db: AsyncSession, tenant_id: str, row: m.BakeryOrder) -> list[tuple[str, float]]:
    """What was paid on this order's deposit, by method. Falls back to one part for old orders."""
    rows = (await db.execute(
        select(m.BakeryPayment.method, func.sum(m.BakeryPayment.amount)).where(
            m.BakeryPayment.tenant_id == tenant_id, m.BakeryPayment.order_id == row.id, m.BakeryPayment.kind == "deposit",
        ).group_by(m.BakeryPayment.method)
    )).all()
    parts = [(meth, _money(amt)) for meth, amt in rows if _money(amt) > 0]
    total = _money(row.deposit)
    if not parts or abs(sum(a for _, a in parts) - total) > 0.009:
        return [(row.deposit_method or "cash", total)]
    return parts


async def add_deposit(
    db: AsyncSession, tenant_id: str, order_id: str, *, amount: float, method: str | None, user_id: str | None
) -> m.BakeryOrder:
    """Take another part-payment on a big order (a wedding cake paid in instalments). It joins
    the same liability as the first deposit and turns into revenue on collection."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN:
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    pay = _money(amount)
    if pay <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount paid")
    owed = _money(float(row.total or 0) - float(row.deposit or 0))
    if pay > owed + 0.004:
        raise HTTPException(status_code=422, detail=f"Only {owed:.2f} is still owed on this order")
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    account = row.deposit_account if float(row.deposit or 0) > 0 else DEPOSIT_ACCOUNT
    description = f"Bakery order {row.order_number} part-payment"
    entry = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": _money_account(how), "debit": pay, "credit": 0, "description": description},
            {"account_code": account or OLD_DEPOSIT_ACCOUNT, "debit": 0, "credit": pay, "description": description},
        ],
        reference=row.order_number, source=REF_ORDER, source_id=row.id,
    )
    await _pay(db, tenant_id, shift=shift, kind="deposit", method=how, amount=pay, user_id=user_id, order_id=row.id)
    if float(row.deposit or 0) <= 0:
        row.deposit_method, row.deposit_account, row.deposit_journal_id = how, DEPOSIT_ACCOUNT, entry
    row.deposit = _money(float(row.deposit or 0) + pay)
    row.updated_at = _now()
    await _audit(
        db, tenant_id, user_id, "bakery_order_part_payment", "bakery_order", row.id,
        {"order_number": row.order_number, "amount": pay, "method": how, "paid_so_far": _money(row.deposit)},
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
    held_in = _deposit_account(row)
    if deposit > 0:
        action = (deposit_action or "").strip().lower()
        if action not in {"refund", "keep"}:
            raise HTTPException(status_code=422, detail="Choose whether to refund the deposit or keep it")
        description = f"Bakery order {row.order_number} cancelled, deposit {action}"
        if action == "refund":
            shift = await _need_shift(db, tenant_id)
            # Instalments may have come in by different methods: give each back the way it came.
            parts = await _deposit_parts(db, tenant_id, row)
            journal = [{"account_code": held_in, "debit": deposit, "credit": 0, "description": description}]
            for method, amount in parts:
                journal.append({"account_code": _money_account(method), "debit": 0, "credit": amount, "description": description})
            await _post(
                db, tenant_id, user_id=user_id, description=description, lines=journal,
                reference=row.order_number, source="bakery_order_cancelled", source_id=row.id,
            )
            for method, amount in parts:
                await _pay(
                    db, tenant_id, shift=shift, kind="deposit_refund", method=method, amount=-amount, user_id=user_id,
                    order_id=row.id,
                )
        else:
            # A kept deposit pays for no goods: it is compensation for the cancelled order, booked
            # as other income. Whether VAT is due on it is a question for the company's accountant.
            await _post(
                db, tenant_id, user_id=user_id, description=description,
                lines=[
                    {"account_code": held_in, "debit": deposit, "credit": 0, "description": description},
                    {"account_code": "4400", "debit": 0, "credit": deposit, "description": description},
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
    """What to bake: open orders due by a date, today's trade standing orders, and each item's
    shelf level (what should be on the shelf for walk-in customers), less what is on the shelf
    and still in date."""
    from app import bakery_items as items_svc
    from app import bakery_trade as trade_svc

    rows = (
        await db.execute(
            select(m.BakeryOrderLine.product_id, func.sum(m.BakeryOrderLine.quantity))
            .join(m.BakeryOrder, m.BakeryOrder.id == m.BakeryOrderLine.order_id)
            .where(
                m.BakeryOrder.tenant_id == tenant_id,
                m.BakeryOrder.status.in_(ORDER_OPEN),
                m.BakeryOrder.due_date <= until,
            )
            .group_by(m.BakeryOrderLine.product_id)
        )
    ).all()
    ordered = {pid: float(q or 0) for pid, q in rows}
    today = await bakery_today(db, tenant_id)
    standing = await trade_svc.due_today(db, tenant_id, day=today)
    settings = await items_svc.settings_map(db, tenant_id)
    par = {pid: float(s.par_level) for pid, s in settings.items() if s.par_level}
    shelf = await items_svc.shelf(db, tenant_id, today=today, local=await _localiser(db, tenant_id))
    expired: dict[str, float] = {}
    for s in shelf:
        if s["state"] == "expired":
            expired[s["product_id"]] = expired.get(s["product_id"], 0.0) + s["quantity"]
    out = []
    for pid in set(ordered) | set(standing) | set(par):
        product = await db.get(m.Product, pid)
        if product is None or not product.is_active:
            continue
        on_hand = _qty(float(product.stock_qty or 0) - expired.get(pid, 0.0))
        need = ordered.get(pid, 0.0) + standing.get(pid, 0.0) + par.get(pid, 0.0)
        out.append(
            {
                "product_id": pid,
                "name": product.name,
                "ordered": _qty(ordered.get(pid, 0.0)),
                "trade": _qty(standing.get(pid, 0.0)),
                "shelf_level": _qty(par.get(pid, 0.0)),
                "on_hand": on_hand,
                "to_bake": max(0.0, _qty(need - on_hand)),
            }
        )
    return sorted(out, key=lambda row: row["to_bake"], reverse=True)


async def _refunds_between(db, tenant_id: str, begin: datetime, finish: datetime) -> list[m.BakeryRefund]:
    return list(
        (
            await db.execute(
                select(m.BakeryRefund).where(
                    m.BakeryRefund.tenant_id == tenant_id,
                    m.BakeryRefund.created_at >= begin,
                    m.BakeryRefund.created_at < finish,
                )
            )
        ).scalars().all()
    )


async def period_numbers(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    begin, finish = await _bounds(db, tenant_id, start, end)
    sales = (
        await db.execute(
            select(m.BakerySale).where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.status.in_(SOLD),
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
        )
    ).scalars().all()
    refunds = await _refunds_between(db, tenant_id, begin, finish)
    refund_net = sum(float(r.total or 0) - float(r.tax or 0) for r in refunds)
    refund_tax = sum(float(r.tax or 0) for r in refunds)
    from app import bakery_trade as trade_svc

    trade = await trade_svc.trade_numbers(db, tenant_id, begin=begin, finish=finish, start=start, end=end)
    counter_revenue = _money(sum(float(s.total or 0) - float(s.tax or 0) for s in sales) - refund_net)
    revenue = _money(counter_revenue + trade["revenue"])
    tax = _money(sum(float(s.tax or 0) for s in sales) - refund_tax + trade["tax"])
    cost_of_sales = _money(
        sum(float(s.cost_of_goods or 0) for s in sales) - sum(float(r.cost_back or 0) for r in refunds) + trade["cost"]
    )
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
                m.BakerySale.status.in_(SOLD),
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
            .group_by(m.BakerySaleLine.name)
        )
    ).all()
    sellers: dict[str, list[float]] = {name: [float(qty or 0), float(total or 0)] for name, qty, total in sold}
    if refunds:
        back = (
            await db.execute(
                select(m.BakeryRefundLine.name, func.sum(m.BakeryRefundLine.quantity), func.sum(m.BakeryRefundLine.line_total))
                .where(m.BakeryRefundLine.refund_id.in_([r.id for r in refunds]))
                .group_by(m.BakeryRefundLine.name)
            )
        ).all()
        for name, qty, total in back:
            row = sellers.setdefault(name, [0.0, 0.0])
            row[0] -= float(qty or 0)
            row[1] -= float(total or 0)
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
        "counter_revenue": counter_revenue,
        "trade_revenue": trade["revenue"],
        "trade_invoices": trade["count"],
        "tax": tax,
        "sale_count": len(sales),
        "discounts": _money(sum(float(s.discount or 0) for s in sales)),
        "refund_count": len(refunds),
        "refund_total": _money(sum(float(r.total or 0) for r in refunds)),
        "cost_of_sales": cost_of_sales,
        "waste_cost": waste_cost,
        "waste_by_reason": by_reason,
        "waste_percent_of_baked": money_json(round(waste_cost / baked_cost * 100, 1)) if baked_cost > 0 else 0,
        "gross_profit": gross_profit,
        "gross_margin_percent": money_json(round(gross_profit / revenue * 100, 1)) if revenue > 0 else 0,
        "baked_batches": len(batches),
        "baked_cost": baked_cost,
        "best_sellers": sorted(
            ({"name": name, "quantity": _qty(v[0]), "total": _money(v[1])} for name, v in sellers.items() if v[0] > 0.0005),
            key=lambda row: row["total"],
            reverse=True,
        )[:15],
        "payments_by_method": {method: _money(amount) for method, amount in paid},
    }


async def summary(db: AsyncSession, tenant_id: str, *, money: bool = True) -> dict:
    today = await bakery_today(db, tenant_id)
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
    from app import bakery_items as items_svc
    from app import bakery_trade as trade_svc

    tills = await open_tills(db, tenant_id)
    body["tills_open"] = len(tills)
    body["till_open"] = bool(tills)
    shelf = await items_svc.shelf(db, tenant_id, today=today, local=await _localiser(db, tenant_id))
    expired = [s for s in shelf if s["state"] == "expired"]
    last_day = [s for s in shelf if s["state"] == "last_day"]
    body["shelf"] = {
        "expired": _qty(sum(s["quantity"] for s in expired)),
        "last_day": _qty(sum(s["quantity"] for s in last_day)),
        "day_old": _qty(sum(s["quantity"] for s in shelf if s["state"] == "day_old")),
    }
    attention = []
    from app import bakery_safety as safety_svc

    safe = await safety_svc.summary(db, tenant_id)
    if safe["bad_readings_today"]:
        attention.append(dash.item("warning", f"{dash.plural(safe['bad_readings_today'], 'temperature reading')} outside the safe range today", "/bakery?tab=safety"))
    if safe["points"] and safe["readings_still_due"]:
        attention.append(dash.item("info", f"{dash.plural(safe['readings_still_due'], 'temperature reading')} still to take", "/bakery?tab=safety"))
    if not tills:
        attention.append(dash.item("warning", "The till is closed. Open it before the first sale.", "/bakery?tab=counter"))
    if expired:
        names = ", ".join(sorted({s["name"] for s in expired}))[:120]
        attention.append(dash.item("warning", f"Past its date, take off the shelf: {names}", "/bakery?tab=waste"))
    if last_day:
        names = ", ".join(sorted({s["name"] for s in last_day}))[:120]
        attention.append(dash.item("info", f"Last day to sell: {names}", "/bakery?tab=counter"))
    if await trade_svc.due_today(db, tenant_id, day=today):
        attention.append(dash.item("info", "Trade deliveries for today are not made yet", "/bakery?tab=trade"))
    if body["orders_overdue"]:
        attention.append(dash.item("warning", f"{dash.plural(body['orders_overdue'], 'order')} past the collection day", "/bakery?tab=orders"))
    if short:
        attention.append(dash.item("warning", f"Bake {dash.plural(len(short), 'item')} to cover orders due by tomorrow", "/bakery?tab=baking"))
    if body["orders_due_today"]:
        attention.append(dash.item("info", f"{dash.plural(body['orders_due_today'], 'order')} to hand over today", "/bakery?tab=orders"))
    body["attention"] = attention
    if money:
        first, begin, finish = dash.window()
        local = await _localiser(db, tenant_id)
        rows = (
            await db.execute(
                select(m.BakerySale.created_at, m.BakerySale.total, m.BakerySale.tax).where(
                    m.BakerySale.tenant_id == tenant_id,
                    m.BakerySale.status.in_(SOLD),
                    m.BakerySale.created_at >= begin,
                    m.BakerySale.created_at <= finish,
                )
            )
        ).all()
        points: dict[date, float] = {}
        for when, total, tax in rows:
            day = local(when).date()
            points[day] = points.get(day, 0.0) + float(total or 0) - float(tax or 0)
        for refund in await _refunds_between(db, tenant_id, begin, finish + timedelta(seconds=1)):
            day = local(refund.created_at).date()
            points[day] = points.get(day, 0.0) - (float(refund.total or 0) - float(refund.tax or 0))
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
    """Bought in: stock goes up at the price before VAT, the VAT on the bill is claimable input
    tax, and the books show how it was paid. Bought on credit, it is owed to a supplier.

    With `in_purchase_units`, quantity and cost are per purchase unit (a 50 kg bag) and turn into
    the stock unit (kg) here."""
    from app import bakery_items as items_svc
    from app import bakery_trade as trade_svc

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
    supplier = None
    if getattr(payload, "supplier_id", None):
        supplier = await trade_svc._supplier(db, tenant_id, str(payload.supplier_id))
    elif (payload.supplier or "").strip():
        supplier = await trade_svc.supplier_by_name(db, tenant_id, payload.supplier)
    if paid_with == "credit" and supplier is None:
        raise HTTPException(status_code=422, detail="Say which supplier you owe")
    entered_qty, entered_cost = float(payload.quantity), float(payload.unit_cost)
    if getattr(payload, "in_purchase_units", False):
        conf = await items_svc.settings_for(db, tenant_id, product.id)
        if not conf or not conf.units_per_purchase:
            raise HTTPException(status_code=422, detail="Set how this item is bought (e.g. a 50 kg bag) under Stock first")
        per = float(conf.units_per_purchase)
        bill = entered_qty * entered_cost
        entered_qty = entered_qty * per
        entered_cost = bill / entered_qty if entered_qty else 0.0
        total = _money(bill)
    else:
        total = _money(entered_qty * entered_cost)
    qty, cost = _qty(entered_qty), _money(entered_cost)
    vat = _money(getattr(payload, "tax", None) or 0)
    if vat < 0 or vat > total + 0.004:
        raise HTTPException(status_code=422, detail="The VAT cannot be more than the goods cost")
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
        tax=vat,
        paid_with=paid_with,
        supplier=supplier.name if supplier else None,
        supplier_id=supplier.id if supplier else None,
        bill_number=optional_honest_narrative(getattr(payload, "bill_number", None), label="bill number", max_length=60),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"Bought {qty:g} {product.name}"
    credit = "2000" if paid_with == "credit" else _money_account(paid_with)
    lines = [{"account_code": "1200", "debit": total, "credit": 0, "description": description}]
    if vat > 0:
        lines.append({"account_code": INPUT_TAX, "debit": vat, "credit": 0, "description": f"{description} (VAT)"})
    lines.append({"account_code": credit, "debit": 0, "credit": _money(total + vat), "description": description})
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=lines,
        reference=row.receipt_number, source="bakery_receipt", source_id=row.id,
    )
    await _audit(
        db, tenant_id, user_id, "bakery_stock_received", "bakery_receipt", row.id,
        {"total": total, "tax": vat, "paid_with": paid_with, "supplier": row.supplier},
    )
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
            "tax": _money(r.tax),
            "paid": _money(float(r.total or 0) + float(r.tax or 0)),
            "paid_with": r.paid_with,
            "supplier": r.supplier,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, name in rows
    ]


# --- Expenses ----------------------------------------------------------------------------


async def count_stock(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.BakeryStockCount:
    """A stocktake. Each counted item is set to what is really there; the value gained or lost
    goes to Stock Count Differences, so the books follow the shelf."""
    if not payload.lines:
        raise HTTPException(status_code=422, detail="Count at least one item")
    seen: set[str] = set()
    row = m.BakeryStockCount(
        tenant_id=tenant_id,
        count_number=await _next_number(db, tenant_id, m.BakeryStockCount, "SC"),
        notes=optional_honest_narrative(getattr(payload, "notes", None), label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    change = 0.0
    changed = 0
    for line in payload.lines:
        pid = str(line.product_id)
        if pid in seen:
            raise HTTPException(status_code=422, detail="An item is counted twice")
        seen.add(pid)
        product = (
            await db.execute(
                select(m.Product).where(m.Product.id == pid, m.Product.tenant_id == tenant_id).with_for_update()
            )
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Item not found")
        expected = _qty(product.stock_qty)
        counted = _qty(line.counted_qty)
        if counted < 0:
            raise HTTPException(status_code=422, detail="A count cannot be below zero")
        diff = _qty(counted - expected)
        unit = _money(product.cost_price)
        value = _money(diff * unit)
        db.add(
            m.BakeryStockCountLine(
                tenant_id=tenant_id, count_id=row.id, product_id=product.id, name=product.name,
                expected_qty=expected, counted_qty=counted, unit_cost=unit, value_change=value,
            )
        )
        if abs(diff) >= 0.0005:
            changed += 1
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=product.id,
                quantity_delta=diff,
                movement_type="adjustment",
                user_id=user_id,
                reference_type=REF_COUNT,
                reference_id=row.id,
                notes=f"Stock count {row.count_number}",
                allow_negative=True,
            )
            change += value
    row.value_change = _money(change)
    if abs(row.value_change) >= 0.005:
        amount = abs(row.value_change)
        description = f"Stock count {row.count_number}"
        if row.value_change < 0:
            lines = [
                {"account_code": COUNT_DIFFERENCES, "debit": amount, "credit": 0, "description": description},
                {"account_code": "1200", "debit": 0, "credit": amount, "description": description},
            ]
        else:
            lines = [
                {"account_code": "1200", "debit": amount, "credit": 0, "description": description},
                {"account_code": COUNT_DIFFERENCES, "debit": 0, "credit": amount, "description": description},
            ]
        row.journal_entry_id = await _post(
            db, tenant_id, user_id=user_id, description=description, lines=lines,
            reference=row.count_number, source=REF_COUNT, source_id=row.id,
        )
    await _audit(
        db, tenant_id, user_id, "bakery_stock_counted", "bakery_stock_count", row.id,
        {"count_number": row.count_number, "items": len(seen), "changed": changed, "value_change": row.value_change},
    )
    await db.flush()
    return row


async def list_counts(db: AsyncSession, tenant_id: str, *, limit: int = 20) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BakeryStockCount)
            .where(m.BakeryStockCount.tenant_id == tenant_id)
            .order_by(m.BakeryStockCount.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    out = []
    for row in rows:
        lines = (
            await db.execute(select(m.BakeryStockCountLine).where(m.BakeryStockCountLine.count_id == row.id))
        ).scalars().all()
        out.append(
            {
                "id": row.id,
                "count_number": row.count_number,
                "notes": row.notes,
                "value_change": _money(row.value_change),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "lines": [
                    {
                        "name": line.name,
                        "expected_qty": _qty(line.expected_qty),
                        "counted_qty": _qty(line.counted_qty),
                        "difference": _qty(float(line.counted_qty) - float(line.expected_qty)),
                        "value_change": _money(line.value_change),
                    }
                    for line in lines
                ],
            }
        )
    return out


async def record_expense(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.BakeryExpense:
    """An expense goes to its own account (rent to Rent, wages to Salaries and Wages...). VAT on
    the bill, when there is any, is claimable input tax and stays out of the cost."""
    if payload.category not in EXPENSE_KINDS:
        raise HTTPException(status_code=422, detail="Choose what it was for")
    paid_with = str(payload.paid_with or "").strip().lower()
    if paid_with not in PAID_WITH - {"credit"}:
        raise HTTPException(status_code=422, detail="Choose how it was paid")
    if payload.spent_on > await bakery_today(db, tenant_id):
        raise HTTPException(status_code=422, detail="That day has not happened yet")
    shift = None
    if payload.from_till:
        if paid_with != "cash":
            raise HTTPException(status_code=422, detail="Only cash can come out of the till")
        shift = await _need_shift(db, tenant_id)
    amount = _money(payload.amount)
    vat = _money(getattr(payload, "tax", None) or 0)
    if vat < 0 or vat >= amount:
        raise HTTPException(status_code=422, detail="The VAT must be less than the amount paid")
    row = m.BakeryExpense(
        tenant_id=tenant_id,
        expense_number=await _next_number(db, tenant_id, m.BakeryExpense, "BX"),
        category=payload.category,
        description=require_honest_narrative(payload.description, label="description", max_length=255),
        amount=amount,
        tax=vat,
        paid_with=paid_with,
        spent_on=payload.spent_on,
        shift_id=shift.id if shift else None,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"{EXPENSE_KINDS[row.category]}: {row.description}"
    lines = [
        {
            "account_code": EXPENSE_ACCOUNTS.get(row.category, "6000"),
            "debit": _money(amount - vat),
            "credit": 0,
            "description": description,
        }
    ]
    if vat > 0:
        lines.append({"account_code": INPUT_TAX, "debit": vat, "credit": 0, "description": f"{description} (VAT)"})
    lines.append({"account_code": _money_account(paid_with), "debit": 0, "credit": amount, "description": description})
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=lines,
        reference=row.expense_number, source="bakery_expense", source_id=row.id,
    )
    if shift is not None:
        await _pay(db, tenant_id, shift=shift, kind="expense", method="cash", amount=-amount, user_id=user_id)
    await _audit(
        db, tenant_id, user_id, "bakery_expense", "bakery_expense", row.id,
        {"amount": amount, "tax": vat, "category": row.category},
    )
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
        "tax": _money(row.tax),
        "cost": _money(float(row.amount or 0) - float(row.tax or 0)),
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
    begin, finish = await _bounds(db, tenant_id, start, end)
    local = await _localiser(db, tenant_id)

    def cost_of(e: m.BakeryExpense) -> float:
        # What the bakery really spent: VAT on the bill is claimed back, so it is not a cost.
        return float(e.amount or 0) - float(e.tax or 0)

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
    expenses = _money(sum(cost_of(e) for e in spent))
    by_kind: dict[str, float] = {}
    for e in spent:
        label = EXPENSE_KINDS.get(e.category, e.category)
        by_kind[label] = by_kind.get(label, 0) + cost_of(e)

    sales = (
        await db.execute(
            select(m.BakerySale).where(
                m.BakerySale.tenant_id == tenant_id,
                m.BakerySale.created_at >= begin,
                m.BakerySale.created_at < finish,
            )
        )
    ).scalars().all()
    done = [s for s in sales if s.status in SOLD]
    refunds = await _refunds_between(db, tenant_id, begin, finish)
    daily: dict[date, float] = {}
    hours: dict[int, dict] = {}
    for s in done:
        net = float(s.total or 0) - float(s.tax or 0)
        when = local(s.created_at)
        daily[when.date()] = daily.get(when.date(), 0) + net
        slot = hours.setdefault(when.hour, {"hour": when.hour, "sales": 0, "total": 0.0})
        slot["sales"] += 1
        slot["total"] += net
    for r in refunds:
        when = local(r.created_at)
        daily[when.date()] = daily.get(when.date(), 0) - (float(r.total or 0) - float(r.tax or 0))

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
    if refunds:
        back = (
            await db.execute(
                select(m.BakeryRefundLine, m.BakeryRefund.restock, m.BakerySaleLine.unit_cost)
                .join(m.BakeryRefund, m.BakeryRefund.id == m.BakeryRefundLine.refund_id)
                .outerjoin(m.BakerySaleLine, m.BakerySaleLine.id == m.BakeryRefundLine.sale_line_id)
                .where(m.BakeryRefundLine.refund_id.in_([r.id for r in refunds]))
            )
        ).all()
        for line, restocked, unit_cost in back:
            row = items.setdefault(line.name, {"name": line.name, "quantity": 0.0, "sales": 0.0, "cost": 0.0})
            qty = float(line.quantity or 0)
            row["quantity"] -= qty
            row["sales"] -= float(line.line_total or 0) - float(line.tax or 0)
            if restocked:
                row["cost"] -= qty * float(unit_cost or 0)
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
            select(func.coalesce(func.sum(m.BakeryStockReceipt.total), 0)).where(  # before VAT
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
        "refunds": {"count": len(refunds), "total": _money(sum(float(r.total or 0) for r in refunds))},
        "previous": {
            "start_date": (start - timedelta(days=span)).isoformat(),
            "end_date": (start - timedelta(days=1)).isoformat(),
            "revenue": before["revenue"],
            "gross_profit": before["gross_profit"],
            "net_profit": _money(before["gross_profit"] - sum(cost_of(e) for e in spent_before)),
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
    """Back at the shop: the cash is counted by someone else, and any gap is booked.
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
    expected = _money(float(bag.opening_cash or 0) + await drawer_cash(db, tenant_id, bag))
    bag.counted_cash = _money(counted_cash)
    bag.status = "closed"
    bag.closed_at = _now()
    bag.closed_by = user_id
    await _book_over_short(db, tenant_id, bag, expected=expected, user_id=user_id, label="Driver cash bag")
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
    today = await bakery_today(db, tenant_id)
    begin, _ = await _bounds(db, tenant_id, today, today)
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
                m.BakerySale.status.in_(SOLD),
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
