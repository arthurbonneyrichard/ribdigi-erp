"""Sales report queries that sit beside the shared aggregations in reports.py.

Every query filters by tenant_id. Register sales that already created a completed
invoice are omitted from revenue reports so they are not counted twice.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json
from app.rbac import apply_created_by_scope, is_platform_role, record_scope_for_claims
from app.reports import (
    COMPLETED_SALE_STATUSES,
    _amount_base,
    _tx_base,
    apply_store_scope,
    apply_store_scope_or_unassigned,
    linked_sales_invoice_id,
    pos_counts_with_invoice,
)

LINE_CAP = 500
RETURNS_NOTE = (
    "Completed sales only. Header discounts are already taken out of revenue. "
    "Posted returns are listed on Sales returns and are not subtracted here."
)
QUOTATION_NOTE = "Quotations are not sales. They are not included in sales totals."
CREDIT_NOTE = (
    "Outstanding balances on open invoices as of now. Paid invoices are omitted. "
    "This is not a list of sales in the selected date range."
)
POS_NOTE = (
    "Register receipts for this period. A receipt that also created an invoice is the same "
    "sale as on Detailed sales, and Sales summary counts it once."
)
VOID_TX_STATUSES = frozenset({"cancelled", "void", "voided", "draft"})
QUOTATION_INDUSTRIES = frozenset({"retail"})
COST_ROLES = frozenset(
    {
        "company_admin",
        "accountant",
        "super_admin",
        "platform_owner",
        "platform_admin",
        "platform_finance",
    }
)


def may_see_sales_cost(claims: dict) -> bool:
    role = str(claims.get("role") or "").strip().lower()
    return is_platform_role(role) or role in COST_ROLES


def assert_quotation_reports(claims: dict) -> None:
    """Quotations belong to the sales-document workflow, not hotel or restaurant tills."""
    from app.packages import canonicalize_industry

    if is_platform_role(claims.get("role")):
        return
    industry = canonicalize_industry(claims.get("industry"))
    if industry in QUOTATION_INDUSTRIES:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "INDUSTRY_MODULE_DISABLED",
            "message": "This feature is not available for this company.",
            "module": "sales",
            "industry": industry,
        },
    )


def _scope_user_ids(claims: dict) -> list[str] | None:
    scope_ids = claims.get("scope_user_ids")
    if scope_ids is None and record_scope_for_claims(claims) != "all":
        return [str(claims.get("sub") or "")]
    if scope_ids is None:
        return None
    return [str(item) for item in scope_ids]


def _tx_void(tx) -> bool:
    return str(tx.status or "").strip().lower() in VOID_TX_STATUSES


def _sale_when(inv) -> datetime | None:
    return inv.posted_at or inv.created_at


async def _completed_invoices(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    store_ids: list[str] | None,
) -> list:
    when = func.coalesce(m.SalesInvoice.posted_at, m.SalesInvoice.created_at)
    stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == claims["tenant_id"],
        m.SalesInvoice.status.in_(list(COMPLETED_SALE_STATUSES)),
    )
    if from_date:
        stmt = stmt.where(when >= from_date)
    if to_date:
        stmt = stmt.where(when <= to_date)
    stmt = apply_store_scope(stmt, m.SalesInvoice.store_id, store_id, store_ids)
    stmt = apply_created_by_scope(stmt, m.SalesInvoice, claims)
    return list((await db.execute(stmt)).scalars().all())


async def _pos_rows(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    store_ids: list[str] | None,
) -> list:
    stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
        )
    )
    if from_date:
        stmt = stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.Transaction.created_at <= to_date)
    stmt = apply_store_scope(stmt, m.PosSession.store_id, store_id, store_ids)
    rows = []
    for tx, session in (await db.execute(stmt)).all():
        if _tx_void(tx):
            continue
        rows.append((tx, session))
    return rows


async def _names(db: AsyncSession, tenant_id: str, party_ids: set[str]) -> dict[str, str]:
    if not party_ids:
        return {}
    parties = (
        await db.execute(
            select(m.Party).where(
                m.Party.tenant_id == tenant_id,
                m.Party.id.in_(list(party_ids)),
            )
        )
    ).scalars().all()
    return {party.id: party.name for party in parties}


async def _user_names(db: AsyncSession, tenant_id: str, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.id.in_(list(user_ids)),
            )
        )
    ).scalars().all()
    return {user.id: user.full_name for user in users}


async def _store_names(db: AsyncSession, tenant_id: str, store_ids: set[str]) -> dict[str, str]:
    if not store_ids:
        return {}
    stores = (
        await db.execute(
            select(m.Store).where(
                m.Store.tenant_id == tenant_id,
                m.Store.id.in_(list(store_ids)),
            )
        )
    ).scalars().all()
    return {store.id: store.name for store in stores}


def _method_label(methods: list[str]) -> str:
    unique: list[str] = []
    for method in methods:
        key = str(method or "").strip().lower()
        if not key or key in unique:
            continue
        unique.append(key)
    if not unique:
        return "on_account"
    if len(unique) > 1:
        return "split"
    return unique[0]


async def _restaurant_bills(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    store_ids: list[str] | None,
) -> list[m.RestaurantOrder]:
    """Completed table bills for a restaurant company. Other industries get none."""
    tenant = await db.get(m.Tenant, tenant_id)
    from app.packages import canonicalize_industry

    if tenant is None or canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return []
    when = func.coalesce(m.RestaurantOrder.completed_at, m.RestaurantOrder.created_at)
    stmt = select(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status == "completed",
    )
    if from_date is not None:
        stmt = stmt.where(when >= from_date)
    if to_date is not None:
        stmt = stmt.where(when <= to_date)
    stmt = apply_store_scope(stmt, m.RestaurantOrder.store_id, store_id, store_ids)
    return list((await db.execute(stmt)).scalars().all())


async def completed_sales(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    """Each completed invoice and unlinked register sale, newest first."""
    tenant_id = claims["tenant_id"]
    invoices = await _completed_invoices(
        db,
        claims,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    counted = {str(inv.id) for inv in invoices}
    pos_rows = await _pos_rows(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    scope_ids = _scope_user_ids(claims)
    party_ids = {inv.customer_id for inv in invoices if inv.customer_id}
    party_ids.update(tx.party_id for tx, _ in pos_rows if tx.party_id)
    names = await _names(db, tenant_id, party_ids)
    store_ids_seen = {inv.store_id for inv in invoices if inv.store_id}
    store_ids_seen.update(session.store_id for _, session in pos_rows if session and session.store_id)
    stores = await _store_names(db, tenant_id, store_ids_seen)

    rows: list[dict] = []
    for inv in invoices:
        when = _sale_when(inv)
        rows.append(
            {
                "id": inv.id,
                "source": "invoice",
                "number": inv.invoice_number,
                "customer": names.get(inv.customer_id) or "Customer",
                "when": when.isoformat() if when else None,
                "status": inv.status,
                "total": _amount_base(inv, inv.total_amount or 0),
                "store_id": inv.store_id,
                "store_name": stores.get(inv.store_id or ""),
                "_sort": when or datetime.min,
            }
        )
    for tx, session in pos_rows:
        if pos_counts_with_invoice(tx, counted):
            continue
        payload = tx.payload or {}
        if scope_ids is not None:
            cashier = str(payload.get("cashier_user_id") or (session.user_id if session else "") or "")
            if cashier not in scope_ids:
                continue
        when = tx.created_at
        customer = names.get(tx.party_id) if tx.party_id else None
        customer = customer or payload.get("customer_name") or "Walk-in"
        store_id_row = session.store_id if session else None
        rows.append(
            {
                "id": tx.id,
                "source": "register",
                "number": tx.reference,
                "customer": customer,
                "when": when.isoformat() if when else None,
                "status": tx.status or "completed",
                "total": _tx_base(tx),
                "store_id": store_id_row,
                "store_name": stores.get(store_id_row or ""),
                "_sort": when or datetime.min,
            }
        )
    bills = await _restaurant_bills(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    if bills:
        extra_stores = {row.store_id for row in bills if row.store_id and row.store_id not in stores}
        if extra_stores:
            stores.update(await _store_names(db, tenant_id, extra_stores))
        for order in bills:
            when = order.completed_at or order.created_at
            rows.append(
                {
                    "id": order.id,
                    "source": "table_bill",
                    "number": order.order_number,
                    "customer": (order.customer_name or "").strip() or "No customer",
                    "when": when.isoformat() if when else None,
                    "status": "completed",
                    "total": money_json(order.total_amount),
                    "store_id": order.store_id,
                    "store_name": stores.get(order.store_id or ""),
                    "_sort": when or datetime.min,
                }
            )
    from app.restaurant import _restaurant_company, posted_till_returns

    restaurant_company = await _restaurant_company(db, tenant_id)
    if restaurant_company:
        returned_by_sale: dict[str, float] = {}
        for ret in await posted_till_returns(
            db,
            tenant_id,
            start=from_date,
            end=to_date,
            inclusive_end=to_date is not None,
            store_id=store_id,
            store_ids=store_ids,
        ):
            if not ret.transaction_id:
                continue
            returned_by_sale[ret.transaction_id] = money_json(
                round(returned_by_sale.get(ret.transaction_id, 0) + money_json(ret.total_amount), 2)
            )
        kept: list[dict] = []
        for row in rows:
            taken = returned_by_sale.get(row["id"])
            if row["source"] == "register" and taken:
                row["total"] = money_json(round(row["total"] - taken, 2))
            if abs(money_json(row["total"])) > 0.004:
                kept.append(row)
        rows = kept
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    total = money_json(round(sum(row["total"] for row in rows), 2))
    for row in rows:
        row.pop("_sort", None)
    shown = rows[:LINE_CAP]
    return {
        "returns_note": (
            "A restaurant till return comes off this list. The original receipt stays on the till report."
            if restaurant_company
            else RETURNS_NOTE
        ),
        "count": len(rows),
        "truncated": len(rows) > LINE_CAP,
        "total": total,
        "rows": shown,
    }


async def product_lines(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
    category_id: str | None = None,
    include_cost: bool = False,
) -> dict:
    tenant_id = claims["tenant_id"]
    from app.packages import canonicalize_industry

    tenant = await db.get(m.Tenant, tenant_id)
    restaurant_company = tenant is not None and canonicalize_industry(getattr(tenant, "industry", None)) == "restaurant"
    invoices = await _completed_invoices(
        db,
        claims,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    by_invoice = {inv.id: inv for inv in invoices}
    counted = {str(inv.id) for inv in invoices}
    items = []
    if by_invoice:
        items = list(
            (
                await db.execute(
                    select(m.SalesInvoiceItem).where(
                        m.SalesInvoiceItem.tenant_id == tenant_id,
                        m.SalesInvoiceItem.sales_invoice_id.in_(list(by_invoice)),
                    )
                )
            ).scalars().all()
        )
    pos_rows = await _pos_rows(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    scope_ids = _scope_user_ids(claims)
    product_ids = {item.product_id for item in items}
    for tx, _session in pos_rows:
        if pos_counts_with_invoice(tx, counted):
            continue
        for line in (tx.payload or {}).get("items") or []:
            if line.get("product_id"):
                product_ids.add(str(line["product_id"]))
    bills = await _restaurant_bills(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    bill_lines: list[m.RestaurantOrderLine] = []
    if bills:
        bill_lines = list(
            (
                await db.execute(
                    select(m.RestaurantOrderLine).where(
                        m.RestaurantOrderLine.tenant_id == tenant_id,
                        m.RestaurantOrderLine.order_id.in_([row.id for row in bills]),
                    )
                )
            ).scalars().all()
        )
        for line in bill_lines:
            if line.product_id:
                product_ids.add(line.product_id)
    products = {}
    if product_ids:
        for product in (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_(list(product_ids)),
                )
            )
        ).scalars().all():
            products[product.id] = product
    cat_ids = {product.category_id for product in products.values() if product.category_id}
    brand_ids = {product.brand_id for product in products.values() if product.brand_id}
    cat_names = {}
    if cat_ids:
        for cat in (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.tenant_id == tenant_id,
                    m.ProductCategory.id.in_(list(cat_ids)),
                )
            )
        ).scalars().all():
            cat_names[cat.id] = cat.name
    brand_names = {}
    if brand_ids:
        for brand in (
            await db.execute(
                select(m.Brand).where(
                    m.Brand.tenant_id == tenant_id,
                    m.Brand.id.in_(list(brand_ids)),
                )
            )
        ).scalars().all():
            brand_names[brand.id] = brand.name

    pay_methods: dict[str, list[str]] = {}
    if by_invoice:
        for pay in (
            await db.execute(
                select(m.CustomerPayment).where(
                    m.CustomerPayment.tenant_id == tenant_id,
                    m.CustomerPayment.sales_invoice_id.in_(list(by_invoice)),
                )
            )
        ).scalars().all():
            pay_methods.setdefault(pay.sales_invoice_id, []).append(pay.payment_method)
    pos_ids = [tx.id for tx, _ in pos_rows if not pos_counts_with_invoice(tx, counted)]
    pos_methods: dict[str, list[str]] = {}
    if pos_ids:
        for pay in (
            await db.execute(
                select(m.PosPayment).where(
                    m.PosPayment.tenant_id == tenant_id,
                    m.PosPayment.sale_id.in_(pos_ids),
                )
            )
        ).scalars().all():
            pos_methods.setdefault(pay.sale_id, []).append(pay.payment_method)

    party_ids = {inv.customer_id for inv in invoices if inv.customer_id}
    party_ids.update(tx.party_id for tx, _ in pos_rows if tx.party_id)
    names = await _names(db, tenant_id, party_ids)
    user_ids = {inv.created_by for inv in invoices if inv.created_by}
    user_ids.update(order.created_by for order in bills if order.created_by)
    for tx, session in pos_rows:
        payload = tx.payload or {}
        if payload.get("cashier_user_id"):
            user_ids.add(str(payload["cashier_user_id"]))
        if session and session.user_id:
            user_ids.add(session.user_id)
    users = await _user_names(db, tenant_id, user_ids)
    store_ids_seen = {inv.store_id for inv in invoices if inv.store_id}
    store_ids_seen.update(session.store_id for _, session in pos_rows if session and session.store_id)
    store_ids_seen.update(order.store_id for order in bills if order.store_id)
    stores = await _store_names(db, tenant_id, store_ids_seen)

    lines: list[dict] = []

    def _append(row: dict, when: datetime | None) -> None:
        row["_sort"] = when or datetime.min
        lines.append(row)

    for item in items:
        inv = by_invoice.get(item.sales_invoice_id)
        product = products.get(item.product_id)
        if not inv or not product:
            continue
        if category_id and product.category_id != category_id:
            continue
        when = _sale_when(inv)
        qty = money_json(item.quantity)
        line_total = _amount_base(inv, item.line_total)
        row = {
            "id": item.id,
            "when": when.isoformat() if when else None,
            "number": inv.invoice_number,
            "product": product.name,
            "sku": product.sku,
            "barcode": product.barcode,
            "category": cat_names.get(product.category_id or "") or product.category,
            "brand": brand_names.get(product.brand_id or ""),
            "quantity": qty,
            "unit_price": _amount_base(inv, item.unit_price),
            "discount": _amount_base(inv, item.discount or 0),
            "tax": _amount_base(inv, item.line_tax or 0),
            "sales_total": line_total,
            "customer": names.get(inv.customer_id) or "Customer",
            "cashier": users.get(inv.created_by or ""),
            "payment_method": _method_label(pay_methods.get(inv.id) or []),
            "store_id": inv.store_id,
            "store_name": stores.get(inv.store_id or ""),
        }
        if include_cost:
            if product.cost_price is None:
                row["cost"] = None
                row["profit"] = None
            else:
                cost = money_json(round(money_json(product.cost_price) * qty, 2))
                row["cost"] = cost
                row["profit"] = money_json(round(line_total - cost, 2))
        _append(row, when)

    for tx, session in pos_rows:
        if pos_counts_with_invoice(tx, counted):
            continue
        payload = tx.payload or {}
        cashier_id = str(payload.get("cashier_user_id") or (session.user_id if session else "") or "")
        if scope_ids is not None and cashier_id not in scope_ids:
            continue
        methods = pos_methods.get(tx.id) or []
        if not methods and payload.get("payment_method"):
            methods = [str(payload.get("payment_method"))]
        customer = names.get(tx.party_id) if tx.party_id else None
        customer = customer or payload.get("customer_name") or "Walk-in"
        store_id_row = session.store_id if session else None
        for index, line in enumerate((payload.get("items") or [])):
            pid = str(line.get("product_id") or "")
            product = products.get(pid)
            if not product:
                continue
            if category_id and product.category_id != category_id:
                continue
            qty = money_json(line.get("quantity") or 0)
            unit_price = money_json(line.get("unit_price") or product.selling_price or 0)
            discount = money_json(line.get("discount") or 0)
            tax = money_json(line.get("line_tax") or line.get("tax") or 0)
            sales_total = money_json(line.get("line_total") or (unit_price * qty))
            if restaurant_company and line.get("line_subtotal") is not None:
                sales_total = money_json(line.get("line_subtotal"))
            row = {
                "id": f"{tx.id}:{index}",
                "when": tx.created_at.isoformat() if tx.created_at else None,
                "number": tx.reference,
                "product": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "category": cat_names.get(product.category_id or "") or product.category,
                "brand": brand_names.get(product.brand_id or ""),
                "quantity": qty,
                "unit_price": unit_price,
                "discount": discount,
                "tax": tax,
                "sales_total": sales_total,
                "customer": customer,
                "cashier": users.get(cashier_id),
                "payment_method": _method_label(methods),
                "store_id": store_id_row,
                "store_name": stores.get(store_id_row or ""),
            }
            if restaurant_company:
                row["_sale_id"] = tx.id
                row["_product_id"] = product.id
            if include_cost:
                if restaurant_company:
                    from app.restaurant import sale_line_cost

                    cost = await sale_line_cost(db, tenant_id, product.id, qty)
                    row["cost"] = cost
                    row["profit"] = money_json(round(sales_total - cost, 2))
                elif product.cost_price is None:
                    row["cost"] = None
                    row["profit"] = None
                else:
                    cost = money_json(round(money_json(product.cost_price) * qty, 2))
                    row["cost"] = cost
                    row["profit"] = money_json(round(sales_total - cost, 2))
            _append(row, tx.created_at)
        if restaurant_company:
            header = money_json(payload.get("discount_amount") or 0)
            if header > 0:
                sale_rows = [row for row in lines if row.get("_sale_id") == tx.id]
                base = money_json(round(sum(money_json(row["sales_total"]) for row in sale_rows), 2))
                if base > 0 and sale_rows:
                    allocated = 0.0
                    for index, row in enumerate(sale_rows):
                        if index == len(sale_rows) - 1:
                            share = money_json(round(header - allocated, 2))
                        else:
                            share = money_json(round(header * money_json(row["sales_total"]) / base, 2))
                            allocated = money_json(round(allocated + share, 2))
                        row["discount"] = money_json(round(money_json(row["discount"]) + share, 2))
                        row["sales_total"] = money_json(round(money_json(row["sales_total"]) - share, 2))
                        if row.get("cost") is not None:
                            row["profit"] = money_json(round(row["sales_total"] - row["cost"], 2))

    bill_by_id = {order.id: order for order in bills}
    for line in bill_lines:
        order = bill_by_id.get(line.order_id)
        product = products.get(line.product_id)
        if order is None or product is None:
            continue
        if category_id and product.category_id != category_id:
            continue
        when = order.completed_at or order.created_at
        qty = money_json(line.quantity)
        sales_total = money_json(line.line_total)
        row = {
            "id": line.id,
            "when": when.isoformat() if when else None,
            "number": order.order_number,
            "product": product.name,
            "sku": product.sku,
            "barcode": product.barcode,
            "category": cat_names.get(product.category_id or "") or product.category,
            "brand": brand_names.get(product.brand_id or ""),
            "quantity": qty,
            "unit_price": money_json(line.unit_price),
            "discount": 0,
            "tax": 0,
            "_order_id": order.id,
            "sales_total": sales_total,
            "customer": (order.customer_name or "").strip() or "No customer",
            "cashier": users.get(order.created_by or ""),
            "payment_method": order.payment_method or "cash",
            "store_id": order.store_id,
            "store_name": stores.get(order.store_id or ""),
        }
        if include_cost:
            from app.restaurant import sale_line_cost

            cost = await sale_line_cost(db, tenant_id, product.id, qty)
            row["cost"] = cost
            row["profit"] = money_json(round(sales_total - cost, 2))
        _append(row, when)

    if bills:
        from app.restaurant import bill_parts, service_percent

        percent = await service_percent(db, tenant_id)
        tax_by_order: dict[str, float] = {}
        subtotal_by_order: dict[str, float] = {}
        for order in bills:
            subtotal = money_json(order.subtotal or 0)
            _service, tax = bill_parts(subtotal, money_json(order.total_amount or 0), percent)
            tax_by_order[order.id] = tax
            subtotal_by_order[order.id] = subtotal
        rows_by_order: dict[str, list] = {}
        for row in lines:
            order_id = row.get("_order_id")
            if order_id:
                rows_by_order.setdefault(order_id, []).append(row)
        for order_id, rows in rows_by_order.items():
            tax = tax_by_order.get(order_id, 0.0)
            subtotal = subtotal_by_order.get(order_id, 0.0)
            included = money_json(round(sum(money_json(row["sales_total"]) for row in rows), 2))
            complete = abs(included - subtotal) <= 0.02
            allocated = 0.0
            for index, row in enumerate(rows):
                if subtotal <= 0:
                    share = 0.0
                elif complete and index == len(rows) - 1:
                    share = money_json(round(tax - allocated, 2))
                else:
                    share = money_json(round(tax * money_json(row["sales_total"]) / subtotal, 2))
                    allocated = money_json(round(allocated + share, 2))
                row["tax"] = share

    if restaurant_company:
        from app.restaurant import posted_till_return_moves

        for move in await posted_till_return_moves(
            db,
            tenant_id,
            start=from_date,
            end=to_date,
            inclusive_end=to_date is not None,
            store_id=store_id,
            store_ids=store_ids,
        ):
            qty = move["quantity"]
            for row in lines:
                if qty <= 1e-9:
                    break
                if row.get("_sale_id") != move["transaction_id"] or row.get("_product_id") != move["product_id"]:
                    continue
                row_qty = money_json(row["quantity"])
                if row_qty <= 0:
                    continue
                take = min(row_qty, qty)
                kept = money_json(round(1 - (take / row_qty), 6))
                row["quantity"] = money_json(round(row_qty - take, 3))
                row["sales_total"] = money_json(round(money_json(row["sales_total"]) * kept, 2))
                row["tax"] = money_json(round(money_json(row["tax"]) * kept, 2))
                row["discount"] = money_json(round(money_json(row["discount"]) * kept, 2))
                if row.get("cost") is not None:
                    row["cost"] = money_json(round(money_json(row["cost"]) * kept, 2))
                    row["profit"] = money_json(round(row["sales_total"] - row["cost"], 2))
                qty = money_json(round(qty - take, 3))
        lines[:] = [
            row
            for row in lines
            if abs(money_json(row["quantity"])) > 1e-9 or abs(money_json(row["sales_total"])) > 0.004
        ]

    lines.sort(key=lambda row: row["_sort"], reverse=True)
    for row in lines:
        row.pop("_sort", None)
        row.pop("_sale_id", None)
        row.pop("_product_id", None)
        row.pop("_order_id", None)
    total_sales = money_json(round(sum(row["sales_total"] for row in lines), 2))
    total_qty = money_json(round(sum(row["quantity"] for row in lines), 3))
    total_discount = money_json(round(sum(row["discount"] for row in lines), 2))
    total_tax = money_json(round(sum(row["tax"] for row in lines), 2))
    payload = {
        "returns_note": RETURNS_NOTE,
        "include_cost": include_cost,
        "count": len(lines),
        "truncated": len(lines) > LINE_CAP,
        "total_quantity": total_qty,
        "total_discount": total_discount,
        "total_tax": total_tax,
        "total_sales": total_sales,
        "lines": lines[:LINE_CAP],
    }
    if include_cost:
        known = [row for row in lines if row.get("cost") is not None]
        payload["total_cost"] = money_json(round(sum(row["cost"] for row in known), 2))
        payload["total_profit"] = money_json(round(sum(row["profit"] for row in known), 2))
    return payload


async def payment_methods(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    """Collected tenders plus the unpaid balance. A sale is not added twice."""
    tenant_id = claims["tenant_id"]
    invoices = await _completed_invoices(
        db,
        claims,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    counted = {str(inv.id) for inv in invoices}
    buckets: dict[str, dict] = {}

    def _add(method: str, amount: float, count: int = 1) -> None:
        key = method or "on_account"
        row = buckets.setdefault(key, {"payment_method": key, "amount": 0.0, "count": 0})
        row["amount"] = money_json(round(row["amount"] + money_json(amount), 2))
        row["count"] += count

    if invoices:
        payments = (
            await db.execute(
                select(m.CustomerPayment).where(
                    m.CustomerPayment.tenant_id == tenant_id,
                    m.CustomerPayment.sales_invoice_id.in_([inv.id for inv in invoices]),
                )
            )
        ).scalars().all()
        by_invoice: dict[str, list] = {}
        for pay in payments:
            by_invoice.setdefault(pay.sales_invoice_id, []).append(pay)
        for inv in invoices:
            collected = 0.0
            for pay in by_invoice.get(inv.id, []):
                paid = _amount_base(pay, pay.amount)
                collected = money_json(round(collected + paid, 2))
                _add(str(pay.payment_method or "other"), paid)
            due = max(
                _amount_base(inv, inv.total_amount) - _amount_base(inv, inv.paid_amount),
                0,
            )
            if due > 0:
                _add("on_account", due)
            elif not by_invoice.get(inv.id) and _amount_base(inv, inv.total_amount) > 0:
                _add("recorded_on_invoice", _amount_base(inv, inv.total_amount))

    pos_rows = await _pos_rows(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    open_pos = [(tx, session) for tx, session in pos_rows if not pos_counts_with_invoice(tx, counted)]
    scope_ids = _scope_user_ids(claims)
    if scope_ids is not None:
        kept = []
        for tx, session in open_pos:
            cashier = str((tx.payload or {}).get("cashier_user_id") or (session.user_id if session else "") or "")
            if cashier in scope_ids:
                kept.append((tx, session))
        open_pos = kept
    pos_ids = [tx.id for tx, _ in open_pos]
    pos_pays: dict[str, list] = {}
    if pos_ids:
        for pay in (
            await db.execute(
                select(m.PosPayment).where(
                    m.PosPayment.tenant_id == tenant_id,
                    m.PosPayment.sale_id.in_(pos_ids),
                )
            )
        ).scalars().all():
            pos_pays.setdefault(pay.sale_id, []).append(pay)
    for tx, _session in open_pos:
        pays = pos_pays.get(tx.id) or []
        if pays:
            collected = 0.0
            for pay in pays:
                collected = money_json(round(collected + _tx_base(tx, pay.amount), 2))
                _add(str(pay.payment_method or "other"), _tx_base(tx, pay.amount))
            due = max(_tx_base(tx) - collected, 0)
            if due > 0:
                _add("on_account", due)
        else:
            method = str((tx.payload or {}).get("payment_method") or "on_account")
            _add(method, _tx_base(tx))

    for order in await _restaurant_bills(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    ):
        _add(str(order.payment_method or "cash"), money_json(order.total_amount))

    from app.restaurant import _restaurant_company, posted_till_returns

    restaurant_company = await _restaurant_company(db, tenant_id)
    if restaurant_company:
        for ret in await posted_till_returns(
            db,
            tenant_id,
            start=from_date,
            end=to_date,
            inclusive_end=to_date is not None,
            store_id=store_id,
            store_ids=store_ids,
        ):
            amount = money_json(ret.refunded_amount or 0)
            if amount <= 0 and (ret.settlement_method or "") == "refund":
                amount = money_json(ret.total_amount or 0)
            if amount <= 0:
                continue
            _add(str(ret.refund_payment_method or "cash"), -amount, count=0)
    rows = sorted(
        (row for row in buckets.values() if abs(money_json(row["amount"])) > 0.004),
        key=lambda row: row["amount"],
        reverse=True,
    )
    return {
        "returns_note": (
            "A restaurant till return comes off this tender. The original receipt stays on the till report."
            if restaurant_company
            else RETURNS_NOTE
        ),
        "rows": rows,
        "total": money_json(round(sum(row["amount"] for row in rows), 2)),
    }


async def discount_lines(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    tenant_id = claims["tenant_id"]
    invoices = await _completed_invoices(
        db,
        claims,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    counted = {str(inv.id) for inv in invoices}
    rows: list[dict] = []
    header_total = 0.0
    line_total = 0.0
    if invoices:
        items = (
            await db.execute(
                select(m.SalesInvoiceItem).where(
                    m.SalesInvoiceItem.tenant_id == tenant_id,
                    m.SalesInvoiceItem.sales_invoice_id.in_([inv.id for inv in invoices]),
                )
            )
        ).scalars().all()
        by_invoice: dict[str, list] = {}
        for item in items:
            by_invoice.setdefault(item.sales_invoice_id, []).append(item)
        for inv in invoices:
            when = _sale_when(inv)
            header = _amount_base(inv, inv.discount_amount or 0)
            if header > 0:
                header_total = money_json(round(header_total + header, 2))
                rows.append(
                    {
                        "id": f"{inv.id}:header",
                        "when": when.isoformat() if when else None,
                        "number": inv.invoice_number,
                        "kind": "Invoice discount",
                        "amount": header,
                        "_sort": when or datetime.min,
                    }
                )
            for item in by_invoice.get(inv.id, []):
                amount = _amount_base(inv, item.discount or 0)
                if amount <= 0:
                    continue
                line_total = money_json(round(line_total + amount, 2))
                rows.append(
                    {
                        "id": item.id,
                        "when": when.isoformat() if when else None,
                        "number": inv.invoice_number,
                        "kind": "Line discount",
                        "amount": amount,
                        "_sort": when or datetime.min,
                    }
                )
    for tx, session in await _pos_rows(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    ):
        if pos_counts_with_invoice(tx, counted):
            continue
        payload = tx.payload or {}
        scope_ids = _scope_user_ids(claims)
        if scope_ids is not None:
            cashier = str(payload.get("cashier_user_id") or (session.user_id if session else "") or "")
            if cashier not in scope_ids:
                continue
        header = money_json(payload.get("discount_amount") or 0)
        if header > 0:
            header_total = money_json(round(header_total + header, 2))
            rows.append(
                {
                    "id": f"{tx.id}:header",
                    "when": tx.created_at.isoformat() if tx.created_at else None,
                    "number": tx.reference,
                    "kind": "Sale discount",
                    "amount": header,
                    "_sort": tx.created_at or datetime.min,
                }
            )
        for index, line in enumerate(payload.get("items") or []):
            amount = money_json(line.get("discount") or 0)
            if amount <= 0:
                continue
            line_total = money_json(round(line_total + amount, 2))
            rows.append(
                {
                    "id": f"{tx.id}:{index}",
                    "when": tx.created_at.isoformat() if tx.created_at else None,
                    "number": tx.reference,
                    "kind": "Line discount",
                    "amount": amount,
                    "_sort": tx.created_at or datetime.min,
                }
            )
    from app.restaurant import _restaurant_company, posted_till_returns

    restaurant_company = await _restaurant_company(db, tenant_id)
    if restaurant_company:
        discount_returns = await posted_till_returns(
            db,
            tenant_id,
            start=from_date,
            end=to_date,
            inclusive_end=to_date is not None,
        )
        if discount_returns:
            sale_ids = [ret.transaction_id for ret in discount_returns if ret.transaction_id]
            sales = (
                await db.execute(select(m.Transaction).where(m.Transaction.id.in_(sale_ids)))
            ).scalars().all() if sale_ids else []
            sale_by_id = {sale.id: sale for sale in sales}
            return_items = (
                await db.execute(
                    select(m.SalesReturnItem).where(
                        m.SalesReturnItem.sales_return_id.in_([ret.id for ret in discount_returns])
                    )
                )
            ).scalars().all()
            items_by_return: dict[str, list] = {}
            for item in return_items:
                items_by_return.setdefault(item.sales_return_id, []).append(item)
            left_qty: dict[tuple[str, int], float] = {}
            unit_discount: dict[tuple[str, int], float] = {}
            for sale in sales:
                for index, line in enumerate((sale.payload or {}).get("items") or []):
                    qty = money_json(line.get("quantity") or 0)
                    discount = money_json(line.get("discount") or 0)
                    if qty <= 0 or discount <= 0:
                        continue
                    key = (sale.id, index)
                    left_qty[key] = qty
                    unit_discount[key] = discount / qty
            take: dict[str, float] = {}
            for ret in discount_returns:
                sale = sale_by_id.get(ret.transaction_id)
                if sale is None:
                    continue
                pending: dict[str, float] = {}
                for item in items_by_return.get(ret.id, []):
                    pending[item.product_id] = money_json(
                        round(pending.get(item.product_id, 0.0) + money_json(item.quantity or 0), 3)
                    )
                for index, line in enumerate((sale.payload or {}).get("items") or []):
                    product_id = line.get("product_id")
                    waiting = pending.get(product_id, 0.0)
                    key = (sale.id, index)
                    open_qty = left_qty.get(key, 0.0)
                    if waiting <= 0 or open_qty <= 0:
                        continue
                    used = min(waiting, open_qty)
                    share = money_json(round(unit_discount[key] * used, 2))
                    if share > 0:
                        row_id = f"{sale.id}:{index}"
                        take[row_id] = money_json(round(take.get(row_id, 0.0) + share, 2))
                    left_qty[key] = money_json(round(open_qty - used, 3))
                    pending[product_id] = money_json(round(waiting - used, 3))
                header = money_json((sale.payload or {}).get("discount_amount") or 0)
                gross = money_json(sale.total or 0)
                refunded = money_json(ret.total_amount or 0)
                if header > 0 and gross > 0 and refunded > 0:
                    share = money_json(round(header * min(refunded, gross) / gross, 2))
                    if share > 0:
                        row_id = f"{sale.id}:header"
                        take[row_id] = money_json(round(take.get(row_id, 0.0) + share, 2))
            kept_rows = []
            for row in rows:
                cut = take.get(row["id"], 0.0)
                if cut:
                    cut = min(cut, row["amount"])
                    row["amount"] = money_json(round(row["amount"] - cut, 2))
                    if abs(row["amount"]) <= 0.004:
                        continue
                kept_rows.append(row)
            rows = kept_rows
            header_total = money_json(
                round(sum(row["amount"] for row in rows if row["kind"] in {"Invoice discount", "Sale discount"}), 2)
            )
            line_total = money_json(
                round(sum(row["amount"] for row in rows if row["kind"] == "Line discount"), 2)
            )
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    for row in rows:
        row.pop("_sort", None)
    return {
        "returns_note": (
            "A restaurant till return comes off this discount. The original receipt stays on the till report."
            if restaurant_company
            else (
                "Discounts are listed here and are already taken out of sales revenue. "
                "They are not subtracted again."
            )
        ),
        "count": len(rows),
        "truncated": len(rows) > LINE_CAP,
        "header_discounts": header_total,
        "line_discounts": line_total,
        "total": money_json(round(header_total + line_total, 2)),
        "rows": rows[:LINE_CAP],
    }


async def pos_sales(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    tenant_id = claims["tenant_id"]
    invoices = await _completed_invoices(
        db,
        claims,
        from_date=None,
        to_date=None,
        store_id=None,
        store_ids=None,
    )
    counted = {str(inv.id) for inv in invoices}
    pos_rows = await _pos_rows(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        store_ids=store_ids,
    )
    scope_ids = _scope_user_ids(claims)
    if scope_ids is not None:
        pos_rows = [
            (tx, session)
            for tx, session in pos_rows
            if str((tx.payload or {}).get("cashier_user_id") or (session.user_id if session else "") or "")
            in scope_ids
        ]
    party_ids = {tx.party_id for tx, _ in pos_rows if tx.party_id}
    names = await _names(db, tenant_id, party_ids)
    user_ids = set()
    for tx, session in pos_rows:
        if (tx.payload or {}).get("cashier_user_id"):
            user_ids.add(str(tx.payload["cashier_user_id"]))
        if session and session.user_id:
            user_ids.add(session.user_id)
    users = await _user_names(db, tenant_id, user_ids)
    store_ids_seen = {session.store_id for _, session in pos_rows if session and session.store_id}
    stores = await _store_names(db, tenant_id, store_ids_seen)
    pos_ids = [tx.id for tx, _ in pos_rows]
    methods: dict[str, list[str]] = {}
    if pos_ids:
        for pay in (
            await db.execute(
                select(m.PosPayment).where(
                    m.PosPayment.tenant_id == tenant_id,
                    m.PosPayment.sale_id.in_(pos_ids),
                )
            )
        ).scalars().all():
            methods.setdefault(pay.sale_id, []).append(pay.payment_method)
    rows = []
    for tx, session in pos_rows:
        payload = tx.payload or {}
        cashier_id = str(payload.get("cashier_user_id") or (session.user_id if session else "") or "")
        method_list = methods.get(tx.id) or ([str(payload["payment_method"])] if payload.get("payment_method") else [])
        store_id_row = session.store_id if session else None
        linked = linked_sales_invoice_id(tx)
        rows.append(
            {
                "id": tx.id,
                "when": tx.created_at.isoformat() if tx.created_at else None,
                "number": tx.reference,
                "customer": (names.get(tx.party_id) if tx.party_id else None)
                or payload.get("customer_name")
                or "Walk-in",
                "cashier": users.get(cashier_id),
                "payment_method": _method_label(method_list),
                "total": _tx_base(tx),
                "store_id": store_id_row,
                "store_name": stores.get(store_id_row or ""),
                "also_invoiced": bool(linked and linked in counted),
                "_sort": tx.created_at or datetime.min,
            }
        )
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    total = money_json(round(sum(row["total"] for row in rows), 2))
    for row in rows:
        row.pop("_sort", None)
    return {
        "returns_note": POS_NOTE,
        "count": len(rows),
        "truncated": len(rows) > LINE_CAP,
        "total": total,
        "rows": rows[:LINE_CAP],
    }


async def quotations_report(
    db: AsyncSession,
    claims: dict,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    stmt = select(m.SalesQuotation).where(m.SalesQuotation.tenant_id == claims["tenant_id"])
    if from_date:
        stmt = stmt.where(m.SalesQuotation.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.SalesQuotation.created_at <= to_date)
    stmt = apply_created_by_scope(stmt, m.SalesQuotation, claims)
    quotes = list((await db.execute(stmt)).scalars().all())
    names = await _names(db, claims["tenant_id"], {quote.customer_id for quote in quotes if quote.customer_id})
    rows = []
    for quote in quotes:
        when = quote.created_at
        rows.append(
            {
                "id": quote.id,
                "when": when.isoformat() if when else None,
                "number": quote.quotation_number,
                "customer": names.get(quote.customer_id) or "Customer",
                "status": quote.status,
                "total": money_json(quote.total_amount or 0),
                "_sort": when or datetime.min,
            }
        )
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    total = money_json(round(sum(row["total"] for row in rows), 2))
    for row in rows:
        row.pop("_sort", None)
    return {
        "returns_note": QUOTATION_NOTE,
        "count": len(rows),
        "truncated": len(rows) > LINE_CAP,
        "total": total,
        "rows": rows[:LINE_CAP],
    }


async def credit_outstanding(
    db: AsyncSession,
    claims: dict,
    *,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    from app.credit import ar_aging

    tenant_id = claims["tenant_id"]
    aging = await ar_aging(db, tenant_id)
    documents = list(aging.get("documents") or [])
    if store_id or store_ids is not None:
        ids = [doc["id"] for doc in documents]
        allowed: set[str] = set()
        if ids:
            stmt = select(m.SalesInvoice.id).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.id.in_(ids),
            )
            stmt = apply_store_scope(stmt, m.SalesInvoice.store_id, store_id, store_ids)
            allowed = {str(row) for row in (await db.execute(stmt)).scalars().all()}
        documents = [doc for doc in documents if str(doc["id"]) in allowed]
    parties: dict[str, dict] = {}
    for doc in documents:
        party_id = doc.get("party_id")
        row = parties.setdefault(
            str(party_id),
            {
                "party_id": party_id,
                "name": doc.get("party_name") or "Customer",
                "total_due": 0.0,
            },
        )
        row["total_due"] = money_json(
            round(
                row["total_due"]
                + money_json(doc.get("balance_due_base") if doc.get("balance_due_base") is not None else doc.get("balance_due")),
                2,
            )
        )
    party_rows = sorted(parties.values(), key=lambda row: row["total_due"], reverse=True)
    as_of = aging.get("as_of")
    return {
        "returns_note": CREDIT_NOTE,
        "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else as_of,
        "total_due": money_json(round(sum(row["total_due"] for row in party_rows), 2)),
        "parties": party_rows,
        "documents": documents,
    }
