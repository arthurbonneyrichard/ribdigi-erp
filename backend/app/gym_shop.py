"""Gym shop: its own products and stock, sold and restocked through the gym till.

It never touches retail sales, products or stock. Money rules match the rest of the gym desk:

- A sale needs an open till. It books Dr money account (gross), Cr 4000 revenue (net), Cr 2100 tax,
  and Dr 5000 cost of sales / Cr 1200 inventory at the product's average cost. Every sale is a row
  in `gym_payments` (`shop_sale`).
- A restock is paid from the till (cash, Mobile Money, card or bank transfer): Dr 1200 inventory,
  Cr the money account, and a negative `gym_payments` row (`stock_purchase`) so the shift's cash
  count falls. The average cost is updated. Buying on supplier credit is not supported here.
- Stock never goes below zero: products are locked in a fixed order while selling.
- A restock on supplier credit (`method=credit`, with the supplier's name) books Dr 1200 / Cr 2000 and
  creates a bill. No cash moves until the bill is paid from the till (Dr 2000 / Cr money).
- A refund puts the stock back at the cost it was sold at, reverses revenue, tax and cost of sales in
  proportion, and pays the customer from the till (negative `gym_payments`, `shop_refund`). A line can
  never be refunded for more than was sold.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _method, _money, _money_account, _need_shift, _next_number, _post, _split_tax
from app.honesty import optional_honest_narrative, require_honest_narrative


def present_product(row: m.GymProduct) -> dict:
    return {
        "id": row.id, "name": row.name, "sku": row.sku, "price": _money(row.price), "cost": round(float(row.cost or 0), 4),
        "stock_qty": int(row.stock_qty), "reorder_level": int(row.reorder_level), "is_active": bool(row.is_active),
        "low": int(row.stock_qty) <= int(row.reorder_level),
    }


async def create_product(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    name = require_honest_narrative(payload.name, label="product name", max_length=150)
    if (await db.execute(select(m.GymProduct.id).where(m.GymProduct.tenant_id == tenant_id, func.lower(m.GymProduct.name) == name.lower()))).first():
        raise HTTPException(status_code=409, detail="A product with this name already exists")
    row = m.GymProduct(
        tenant_id=tenant_id, name=name, price=_money(payload.price), reorder_level=int(payload.reorder_level),
        sku=optional_honest_narrative(payload.sku, label="sku", max_length=60),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_product_created", "gym_product", row.id, {"name": name})
    return present_product(row)


async def list_products(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[dict]:
    stmt = select(m.GymProduct).where(m.GymProduct.tenant_id == tenant_id).order_by(m.GymProduct.name)
    if active_only:
        stmt = stmt.where(m.GymProduct.is_active.is_(True))
    return [present_product(r) for r in (await db.execute(stmt)).scalars().all()]


async def update_product(db: AsyncSession, tenant_id: str, product_id: str, payload, *, user_id) -> dict:
    row = await db.get(m.GymProduct, product_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Product not found")
    if payload.price is not None:
        row.price = _money(payload.price)
    if payload.reorder_level is not None:
        row.reorder_level = int(payload.reorder_level)
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_product_updated", "gym_product", row.id, {"price": _money(row.price), "is_active": row.is_active})
    return present_product(row)


async def restock(
    db: AsyncSession, tenant_id: str, product_id: str, *, quantity: int, unit_cost: float, method: str, user_id,
    supplier_name: str | None = None, due_on: date | None = None,
) -> dict:
    on_credit = method == "credit"
    if on_credit:
        supplier = require_honest_narrative(supplier_name or "", label="supplier", max_length=150)
        how, shift = None, None  # nothing is paid today, so no till is needed
    else:
        how = _method(method)
        shift = await _need_shift(db, tenant_id)
    row = (await db.execute(select(m.GymProduct).where(m.GymProduct.id == product_id, m.GymProduct.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    total = _money(quantity * unit_cost)
    if total <= 0:
        raise HTTPException(status_code=422, detail="The cost must be above zero")
    old_value = float(row.stock_qty) * float(row.cost or 0)
    row.stock_qty = int(row.stock_qty) + int(quantity)
    row.cost = round((old_value + quantity * unit_cost) / row.stock_qty, 4)
    desc = f"Gym shop stock bought: {row.name}"
    credit_side = "2000" if on_credit else _money_account(how)
    await _post(
        db, tenant_id, user_id=user_id, description=desc, reference=f"STOCK-{row.id[:8]}", source="gym_stock_purchase", source_id=row.id,
        lines=[{"account_code": "1200", "debit": total, "credit": 0, "description": desc}, {"account_code": credit_side, "debit": 0, "credit": total, "description": desc}],
    )
    out = present_product(row)
    if on_credit:
        if due_on and due_on < date.today():
            raise HTTPException(status_code=422, detail="The due date has already passed")
        bill = m.GymSupplierBill(
            tenant_id=tenant_id, bill_number=await _next_number(db, tenant_id, m.GymSupplierBill, "SB"), supplier_name=supplier,
            product_id=row.id, quantity=int(quantity), amount=total, due_on=due_on, created_by=user_id,
        )
        db.add(bill)
        await db.flush()
        out["bill_id"] = bill.id
    else:
        db.add(m.GymPayment(tenant_id=tenant_id, shift_id=shift.id, kind="stock_purchase", method=how, amount=-total, created_by=user_id))
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_stock_bought", "gym_product", row.id, {"quantity": quantity, "total": total, "method": method})
    return out


async def sell(db: AsyncSession, tenant_id: str, *, items: list, method: str, member_id: str | None, user_id) -> dict:
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    wanted: dict[str, int] = {}
    for it in items:
        wanted[it.product_id] = wanted.get(it.product_id, 0) + int(it.quantity)
    if member_id:
        from app.gym import _member

        await _member(db, tenant_id, member_id)
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(m.GymProduct).where(m.GymProduct.tenant_id == tenant_id, m.GymProduct.id.in_(list(wanted))).order_by(m.GymProduct.id).with_for_update()
            )
        ).scalars().all()
    }
    if len(products) != len(wanted):
        raise HTTPException(status_code=404, detail="A product was not found")
    net = tax = gross = cost = 0.0
    lines = []
    for pid, qty in wanted.items():
        p = products[pid]
        if not p.is_active:
            raise HTTPException(status_code=409, detail=f"{p.name} is not on sale")
        if int(p.stock_qty) < qty:
            raise HTTPException(status_code=409, detail=f"Only {int(p.stock_qty)} of {p.name} left")
        n, t, g = await _split_tax(db, tenant_id, float(p.price) * qty)
        net, tax, gross, cost = net + n, tax + t, gross + g, cost + float(p.cost or 0) * qty
        lines.append((p, qty, g))
    net, tax, gross, cost = _money(net), _money(tax), _money(gross), _money(cost)
    sale = m.GymShopSale(
        tenant_id=tenant_id, sale_number=await _next_number(db, tenant_id, m.GymShopSale, "SH"), member_id=member_id, method=how,
        subtotal=net, tax=tax, total=gross, cost_total=cost, created_by=user_id,
    )
    db.add(sale)
    await db.flush()
    for p, qty, g in lines:
        db.add(m.GymShopSaleLine(tenant_id=tenant_id, sale_id=sale.id, product_id=p.id, name=p.name, quantity=qty, unit_price=p.price, unit_cost=p.cost, line_total=g))
        p.stock_qty = int(p.stock_qty) - qty
    desc = f"Gym shop sale {sale.sale_number}"
    journal = [
        {"account_code": _money_account(how), "debit": gross, "credit": 0, "description": desc},
        {"account_code": "4000", "debit": 0, "credit": net, "description": desc},
    ]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": desc})
    if cost > 0:
        journal += [
            {"account_code": "5000", "debit": cost, "credit": 0, "description": desc},
            {"account_code": "1200", "debit": 0, "credit": cost, "description": desc},
        ]
    sale.journal_entry_id = await _post(db, tenant_id, user_id=user_id, description=desc, lines=journal, reference=sale.sale_number, source="gym_shop_sale", source_id=sale.id)
    db.add(m.GymPayment(tenant_id=tenant_id, shift_id=shift.id, kind="shop_sale", method=how, amount=gross, member_id=member_id, created_by=user_id))
    await _audit(db, tenant_id, user_id, "gym_shop_sold", "gym_shop_sale", sale.id, {"total": gross, "method": how})
    await db.flush()
    return {
        "id": sale.id, "sale_number": sale.sale_number, "method": how, "subtotal": net, "tax": tax, "total": gross,
        "lines": [{"name": p.name, "quantity": q, "line_total": _money(g)} for p, q, g in lines], "date": date.today().isoformat(),
    }


async def list_sales(db: AsyncSession, tenant_id: str, *, limit: int = 50) -> list[dict]:
    rows = (await db.execute(select(m.GymShopSale).where(m.GymShopSale.tenant_id == tenant_id).order_by(m.GymShopSale.created_at.desc()).limit(limit))).scalars().all()
    lines: dict[str, list] = {}
    if rows:
        for ln in (await db.execute(select(m.GymShopSaleLine).where(m.GymShopSaleLine.sale_id.in_([r.id for r in rows])))).scalars().all():
            lines.setdefault(ln.sale_id, []).append(
                {"product_id": ln.product_id, "name": ln.name, "quantity": int(ln.quantity), "refundable": int(ln.quantity) - int(ln.refunded_qty or 0)}
            )
    return [
        {"id": r.id, "sale_number": r.sale_number, "method": r.method, "total": _money(r.total), "date": r.created_at.isoformat(), "lines": lines.get(r.id, [])}
        for r in rows
    ]


# --- Supplier bills and refunds --------------------------------------------------------------


def present_bill(b: m.GymSupplierBill, product: m.GymProduct | None) -> dict:
    return {
        "id": b.id, "bill_number": b.bill_number, "supplier": b.supplier_name, "product": product.name if product else None, "quantity": int(b.quantity),
        "amount": _money(b.amount), "due_on": b.due_on.isoformat() if b.due_on else None, "status": b.status,
        "overdue": bool(b.status == "open" and b.due_on and b.due_on < date.today()),
    }


async def list_bills(db: AsyncSession, tenant_id: str, *, status: str | None = None) -> list[dict]:
    stmt = select(m.GymSupplierBill, m.GymProduct).join(m.GymProduct, m.GymProduct.id == m.GymSupplierBill.product_id).where(m.GymSupplierBill.tenant_id == tenant_id).order_by(m.GymSupplierBill.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(m.GymSupplierBill.status == status)
    return [present_bill(b, p) for b, p in (await db.execute(stmt)).all()]


async def pay_bill(db: AsyncSession, tenant_id: str, bill_id: str, *, method: str, user_id) -> dict:
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    bill = (await db.execute(select(m.GymSupplierBill).where(m.GymSupplierBill.id == bill_id, m.GymSupplierBill.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.status == "paid":
        raise HTTPException(status_code=409, detail="This bill is already paid")
    amount = _money(bill.amount)
    desc = f"Gym supplier bill {bill.bill_number} paid"
    await _post(
        db, tenant_id, user_id=user_id, description=desc, reference=bill.bill_number, source="gym_supplier_payment", source_id=bill.id,
        lines=[{"account_code": "2000", "debit": amount, "credit": 0, "description": desc}, {"account_code": _money_account(how), "debit": 0, "credit": amount, "description": desc}],
    )
    db.add(m.GymPayment(tenant_id=tenant_id, shift_id=shift.id, kind="supplier_payment", method=how, amount=-amount, created_by=user_id))
    bill.status, bill.paid_on, bill.pay_method = "paid", date.today(), how
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_supplier_bill_paid", "gym_supplier_bill", bill.id, {"amount": amount, "method": how})
    return present_bill(bill, await db.get(m.GymProduct, bill.product_id))


async def refund(db: AsyncSession, tenant_id: str, sale_id: str, *, items: list, method: str, user_id) -> dict:
    """Refund some or all of a sale. Stock returns at the cost it was sold at."""
    how = _method(method)
    shift = await _need_shift(db, tenant_id)
    sale = (await db.execute(select(m.GymShopSale).where(m.GymShopSale.id == sale_id, m.GymShopSale.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    lines = {
        ln.product_id: ln
        for ln in (await db.execute(select(m.GymShopSaleLine).where(m.GymShopSaleLine.sale_id == sale.id).with_for_update())).scalars().all()
    }
    wanted: dict[str, int] = {}
    for it in items:
        wanted[it.product_id] = wanted.get(it.product_id, 0) + int(it.quantity)
    gross = cost = 0.0
    for pid, qty in wanted.items():
        ln = lines.get(pid)
        if ln is None:
            raise HTTPException(status_code=404, detail="That product was not on this sale")
        left = int(ln.quantity) - int(ln.refunded_qty or 0)
        if qty > left:
            raise HTTPException(status_code=409, detail=f"Only {left} of {ln.name} can still be refunded")
        gross += float(ln.line_total) * qty / int(ln.quantity)
        cost += float(ln.unit_cost or 0) * qty
    gross, cost = _money(gross), _money(cost)
    tax = _money(float(sale.tax) * gross / float(sale.total)) if float(sale.total) else 0.0
    net = _money(gross - tax)
    products = {
        p.id: p for p in (await db.execute(select(m.GymProduct).where(m.GymProduct.id.in_(list(wanted))).order_by(m.GymProduct.id).with_for_update())).scalars().all()
    }
    for pid, qty in wanted.items():
        lines[pid].refunded_qty = int(lines[pid].refunded_qty or 0) + qty
        products[pid].stock_qty = int(products[pid].stock_qty) + qty
    desc = f"Gym shop refund {sale.sale_number}"
    journal = [{"account_code": "4000", "debit": net, "credit": 0, "description": desc}, {"account_code": _money_account(how), "debit": 0, "credit": gross, "description": desc}]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": tax, "credit": 0, "description": desc})
    if cost > 0:
        journal += [{"account_code": "1200", "debit": cost, "credit": 0, "description": desc}, {"account_code": "5000", "debit": 0, "credit": cost, "description": desc}]
    await _post(db, tenant_id, user_id=user_id, description=desc, lines=journal, reference=sale.sale_number, source="gym_shop_refund", source_id=sale.id)
    db.add(m.GymPayment(tenant_id=tenant_id, shift_id=shift.id, kind="shop_refund", method=how, amount=-gross, member_id=sale.member_id, created_by=user_id))
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_shop_refunded", "gym_shop_sale", sale.id, {"total": gross, "method": how})
    return {"sale_number": sale.sale_number, "refunded": gross, "method": how}
