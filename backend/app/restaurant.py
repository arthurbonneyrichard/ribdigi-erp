"""Restaurant floor, kitchen, and recipe stock. Catalog products are the menu."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import false as sql_false
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import inventory
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.store_access import assert_store_access, assigned_store_ids

SERVICE_MODES = {"dine_in", "takeaway", "delivery"}
OPEN_STATUSES = {"open", "sent", "preparing", "ready"}
PAYMENT_METHODS = {"cash", "card", "wallet", "mobile_money", "credit"}


def _now() -> datetime:
    return datetime.utcnow()


async def _product(db: AsyncSession, tenant_id: str, product_id: str) -> m.Product:
    row = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


async def _allowed_stores(db: AsyncSession, tenant_id: str, user_id: str | None) -> list[str] | None:
    if not user_id:
        return None
    return await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)


def _store_clause(column, allowed: list[str] | None):
    if allowed is None:
        return None
    if not allowed:
        return sql_false()
    return column.in_(list(allowed))


async def _require_store_for_scoped_user(db, tenant_id: str, user_id: str | None, store_id: str | None) -> None:
    if store_id:
        await assert_store_access(db, tenant_id=tenant_id, user_id=user_id or "", store_id=store_id)
    allowed = await _allowed_stores(db, tenant_id, user_id)
    if allowed is not None and store_id not in set(allowed):
        raise HTTPException(status_code=403, detail="Store is outside your access")


async def summary(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> dict:
    allowed = await _allowed_stores(db, tenant_id, user_id)
    order_scope = _store_clause(m.RestaurantOrder.store_id, allowed)
    table_scope = _store_clause(m.RestaurantTable.store_id, allowed)
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    sales_stmt = select(func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0)).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status == "completed",
        m.RestaurantOrder.completed_at >= start,
    )
    if order_scope is not None:
        sales_stmt = sales_stmt.where(order_scope)
    sales = (await db.execute(sales_stmt)).scalar_one()
    open_stmt = select(func.count()).select_from(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status.in_(tuple(OPEN_STATUSES)),
    )
    if order_scope is not None:
        open_stmt = open_stmt.where(order_scope)
    open_orders = (await db.execute(open_stmt)).scalar_one()
    table_stmt = (
        select(m.RestaurantTable.status, func.count())
        .where(m.RestaurantTable.tenant_id == tenant_id, m.RestaurantTable.is_active.is_(True))
        .group_by(m.RestaurantTable.status)
    )
    if table_scope is not None:
        table_stmt = table_stmt.where(table_scope)
    tables = (await db.execute(table_stmt)).all()
    kitchen_stmt = (
        select(func.count())
        .select_from(m.RestaurantKitchenTicket)
        .join(m.RestaurantOrder, m.RestaurantOrder.id == m.RestaurantKitchenTicket.order_id)
        .where(
            m.RestaurantKitchenTicket.tenant_id == tenant_id,
            m.RestaurantKitchenTicket.status.in_(("queued", "preparing")),
        )
    )
    if order_scope is not None:
        kitchen_stmt = kitchen_stmt.where(order_scope)
    kitchen = (await db.execute(kitchen_stmt)).scalar_one()
    low_stock = (
        await db.execute(
            select(func.count()).select_from(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active.is_(True),
                m.Product.reorder_level > 0,
                m.Product.stock_qty <= m.Product.reorder_level,
            )
        )
    ).scalar_one()
    return {
        "sales_today": money_json(sales),
        "open_orders": int(open_orders or 0),
        "tables": {status: int(count) for status, count in tables},
        "kitchen_backlog": int(kitchen or 0),
        "low_stock_ingredients": int(low_stock or 0),
    }


async def create_table(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.RestaurantTable:
    code = require_honest_narrative(payload.code, label="table code", min_length=1)[:40]
    name = require_honest_narrative(payload.name, label="table name", min_length=1)[:120]
    await _require_store_for_scoped_user(db, tenant_id, user_id, payload.store_id)
    row = m.RestaurantTable(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        code=code,
        name=name,
        seats=max(1, int(payload.seats or 2)),
        status="available",
    )
    db.add(row)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_table_created", entity="restaurant_table", entity_id=row.id,
        details={"code": code},
    )
    return row


async def list_tables(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantTable]:
    stmt = select(m.RestaurantTable).where(m.RestaurantTable.tenant_id == tenant_id).order_by(m.RestaurantTable.code)
    scope = _store_clause(m.RestaurantTable.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def serialize_table(row: m.RestaurantTable) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "seats": row.seats,
        "status": row.status,
        "store_id": row.store_id,
        "is_active": row.is_active,
    }


async def create_modifier_group(db: AsyncSession, tenant_id: str, name: str) -> m.RestaurantModifierGroup:
    row = m.RestaurantModifierGroup(
        tenant_id=tenant_id,
        name=require_honest_narrative(name, label="modifier group", min_length=1)[:120],
    )
    db.add(row)
    await db.flush()
    return row


async def add_modifier(db: AsyncSession, tenant_id: str, group_id: str, *, name: str, price) -> m.RestaurantModifier:
    group = await db.get(m.RestaurantModifierGroup, group_id)
    if group is None or group.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Modifier group not found")
    row = m.RestaurantModifier(
        tenant_id=tenant_id,
        group_id=group.id,
        name=require_honest_narrative(name, label="modifier name", min_length=1)[:120],
        price=money_json(price or 0),
    )
    db.add(row)
    await db.flush()
    return row


async def create_recipe(db: AsyncSession, tenant_id: str, payload) -> m.RestaurantRecipe:
    await _product(db, tenant_id, payload.product_id)
    existing = (
        await db.execute(
            select(m.RestaurantRecipe).where(
                m.RestaurantRecipe.tenant_id == tenant_id,
                m.RestaurantRecipe.product_id == payload.product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Recipe already exists for this menu item")
    recipe = m.RestaurantRecipe(
        tenant_id=tenant_id,
        product_id=payload.product_id,
        name=require_honest_narrative(payload.name, label="recipe name", min_length=1)[:160],
    )
    db.add(recipe)
    await db.flush()
    for line in payload.lines:
        await _product(db, tenant_id, line.ingredient_id)
        qty = money_json(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Ingredient quantity must be greater than zero")
        db.add(
            m.RestaurantRecipeLine(
                tenant_id=tenant_id,
                recipe_id=recipe.id,
                ingredient_id=line.ingredient_id,
                quantity=qty,
            )
        )
    await db.flush()
    return recipe


async def _next_number(db: AsyncSession, tenant_id: str) -> str:
    count = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantOrder).where(m.RestaurantOrder.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"R-{int(count or 0) + 1:04d}"


async def create_order(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.RestaurantOrder:
    mode = (payload.service_mode or "").strip().lower()
    if mode not in SERVICE_MODES:
        raise HTTPException(status_code=422, detail="service_mode must be dine_in, takeaway, or delivery")
    method = (payload.payment_method or "cash").strip().lower()
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="payment_method is not supported")
    await _require_store_for_scoped_user(db, tenant_id, user_id, payload.store_id)
    if mode == "dine_in" and payload.table_id:
        table = await db.get(m.RestaurantTable, payload.table_id)
        if table is None or table.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Table not found")
        table.status = "occupied"
    if not payload.lines:
        raise HTTPException(status_code=422, detail="Order needs at least one menu item")
    order = m.RestaurantOrder(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        order_number=await _next_number(db, tenant_id),
        service_mode=mode,
        table_id=payload.table_id,
        customer_name=optional_honest_narrative(payload.customer_name, label="customer name"),
        status="open",
        payment_method=method,
        notes=optional_honest_narrative(payload.notes, label="order notes"),
        created_by=user_id,
    )
    db.add(order)
    await db.flush()
    subtotal = 0.0
    for line in payload.lines:
        product = await _product(db, tenant_id, line.product_id)
        qty = money_json(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Line quantity must be greater than zero")
        price = money_json(line.unit_price if line.unit_price is not None else product.selling_price or 0)
        extra = 0.0
        row = m.RestaurantOrderLine(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=price,
            line_total=money_json(qty * price),
            station=(product.prep_station or "kitchen") if (product.prep_station or "") in {"kitchen", "bar"} else "kitchen",
        )
        db.add(row)
        await db.flush()
        for modifier_id in line.modifier_ids or []:
            modifier = await db.get(m.RestaurantModifier, modifier_id)
            if modifier is None or modifier.tenant_id != tenant_id:
                raise HTTPException(status_code=404, detail="Modifier not found")
            extra += float(modifier.price or 0)
            db.add(
                m.RestaurantOrderModifier(
                    tenant_id=tenant_id,
                    line_id=row.id,
                    modifier_id=modifier.id,
                    name=modifier.name,
                    price=modifier.price,
                )
            )
        row.line_total = money_json(float(row.line_total) + extra)
        subtotal += float(row.line_total)
    order.subtotal = money_json(subtotal)
    order.total_amount = money_json(subtotal)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_created", entity="restaurant_order", entity_id=order.id,
        details={"order_number": order.order_number, "total": money_json(order.total_amount)},
    )
    return order


async def _order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None = None) -> m.RestaurantOrder:
    row = await db.get(m.RestaurantOrder, order_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    allowed = await _allowed_stores(db, tenant_id, user_id)
    if allowed is not None and row.store_id not in set(allowed):
        raise HTTPException(status_code=404, detail="Order not found")
    return row


async def send_to_kitchen(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status in {"completed", "cancelled", "voided", "refunded"}:
        raise HTTPException(status_code=409, detail="Order cannot be sent to the kitchen")
    existing = (
        await db.execute(
            select(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.order_id == order.id)
        )
    ).scalars().first()
    if existing is None:
        lines = (
            await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
        ).scalars()
        stations = {line.station or "kitchen" for line in lines} or {"kitchen"}
        for station in stations:
            db.add(
                m.RestaurantKitchenTicket(
                    tenant_id=tenant_id, order_id=order.id, station=station, status="queued"
                )
            )
    if order.status == "open":
        order.status = "sent"
    await db.flush()
    return order


async def _recipe_lines(db: AsyncSession, tenant_id: str, product_id: str) -> list[m.RestaurantRecipeLine]:
    recipe = (
        await db.execute(
            select(m.RestaurantRecipe).where(
                m.RestaurantRecipe.tenant_id == tenant_id,
                m.RestaurantRecipe.product_id == product_id,
                m.RestaurantRecipe.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if recipe is None:
        return []
    return list(
        (
            await db.execute(
                select(m.RestaurantRecipeLine).where(m.RestaurantRecipeLine.recipe_id == recipe.id)
            )
        ).scalars()
    )


async def _deduct_or_restore(db, tenant_id, order, *, user_id, sign: float) -> None:
    lines = (
        await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
    ).scalars()
    for line in lines:
        for ingredient in await _recipe_lines(db, tenant_id, line.product_id):
            delta = money_json(float(ingredient.quantity) * float(line.quantity) * sign)
            if delta == 0:
                continue
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=ingredient.ingredient_id,
                quantity_delta=delta,
                movement_type="stock_out" if sign < 0 else "stock_in",
                user_id=user_id,
                reference_type="restaurant_order",
                reference_id=order.id,
                notes=f"Restaurant order {order.order_number}",
            )


async def _post_sale_journal(db, tenant_id, order, *, user_id, reverse: bool) -> str | None:
    amount = money_json(order.total_amount)
    if amount <= 0:
        return order.journal_entry_id
    await accounting.ensure_default_accounts(db, tenant_id)
    debit_code, _label = accounting.pos_debit_account_for_payment_method(order.payment_method)
    if reverse:
        lines = [
            {"account_code": "4000", "debit": amount, "credit": 0},
            {"account_code": debit_code, "debit": 0, "credit": amount},
        ]
        description = f"Restaurant refund {order.order_number}"
    else:
        lines = [
            {"account_code": debit_code, "debit": amount, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": amount},
        ]
        description = f"Restaurant sale {order.order_number}"
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=order.order_number,
        source_type="restaurant_order",
        source_id=order.id,
    )
    return entry.id


async def complete_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status == "completed":
        return order
    if order.status in {"cancelled", "voided", "refunded"}:
        raise HTTPException(status_code=409, detail="Order cannot be completed")
    await _deduct_or_restore(db, tenant_id, order, user_id=user_id, sign=-1)
    order.journal_entry_id = await _post_sale_journal(db, tenant_id, order, user_id=user_id, reverse=False)
    order.status = "completed"
    order.completed_at = _now()
    if order.table_id:
        table = await db.get(m.RestaurantTable, order.table_id)
        if table and table.tenant_id == tenant_id:
            table.status = "available"
    tickets = (
        await db.execute(
            select(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.order_id == order.id)
        )
    ).scalars()
    for ticket in tickets:
        ticket.status = "done"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_completed", entity="restaurant_order", entity_id=order.id,
        details={"total": money_json(order.total_amount), "payment_method": order.payment_method},
    )
    return order


async def cancel_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None, void: bool) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status in {"completed", "refunded"}:
        raise HTTPException(status_code=409, detail="Completed orders must be refunded")
    if order.status in {"cancelled", "voided"}:
        return order
    order.status = "voided" if void else "cancelled"
    if order.table_id:
        table = await db.get(m.RestaurantTable, order.table_id)
        if table and table.tenant_id == tenant_id:
            table.status = "available"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_voided" if void else "restaurant_order_cancelled",
        entity="restaurant_order", entity_id=order.id, details={"status": order.status},
    )
    return order


async def refund_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status == "refunded":
        return order
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="Only a completed order can be refunded")
    await _deduct_or_restore(db, tenant_id, order, user_id=user_id, sign=1)
    await _post_sale_journal(db, tenant_id, order, user_id=user_id, reverse=True)
    order.status = "refunded"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_refunded", entity="restaurant_order", entity_id=order.id,
        details={"total": money_json(order.total_amount)},
    )
    return order


async def list_orders(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantOrder]:
    stmt = (
        select(m.RestaurantOrder)
        .where(m.RestaurantOrder.tenant_id == tenant_id)
        .order_by(m.RestaurantOrder.created_at.desc())
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


async def list_kitchen(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantKitchenTicket]:
    stmt = (
        select(m.RestaurantKitchenTicket)
        .join(m.RestaurantOrder, m.RestaurantOrder.id == m.RestaurantKitchenTicket.order_id)
        .where(
            m.RestaurantKitchenTicket.tenant_id == tenant_id,
            m.RestaurantKitchenTicket.status.in_(("queued", "preparing", "ready")),
        )
        .order_by(m.RestaurantKitchenTicket.created_at)
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def serialize_order(row: m.RestaurantOrder) -> dict:
    return {
        "id": row.id,
        "order_number": row.order_number,
        "service_mode": row.service_mode,
        "table_id": row.table_id,
        "customer_name": row.customer_name,
        "status": row.status,
        "payment_method": row.payment_method,
        "subtotal": money_json(row.subtotal),
        "total_amount": money_json(row.total_amount),
        "store_id": row.store_id,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def serialize_ticket(row: m.RestaurantKitchenTicket) -> dict:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "station": row.station,
        "status": row.status,
    }


async def reports(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> dict:
    body = await summary(db, tenant_id, user_id=user_id)
    mode_stmt = (
        select(m.RestaurantOrder.service_mode, func.count(), func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0))
        .where(m.RestaurantOrder.tenant_id == tenant_id, m.RestaurantOrder.status == "completed")
        .group_by(m.RestaurantOrder.service_mode)
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        mode_stmt = mode_stmt.where(scope)
    by_mode = (await db.execute(mode_stmt)).all()
    body["by_service_mode"] = [
        {"service_mode": mode, "orders": int(count), "sales": money_json(total)}
        for mode, count, total in by_mode
    ]
    return body
