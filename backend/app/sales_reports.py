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
    apply_store_scope,
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
                "total": money_json(inv.total_amount or 0),
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
                "total": money_json(tx.total or 0),
                "store_id": store_id_row,
                "store_name": stores.get(store_id_row or ""),
                "_sort": when or datetime.min,
            }
        )
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    total = money_json(round(sum(row["total"] for row in rows), 2))
    for row in rows:
        row.pop("_sort", None)
    shown = rows[:LINE_CAP]
    return {
        "returns_note": RETURNS_NOTE,
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
    for tx, session in pos_rows:
        payload = tx.payload or {}
        if payload.get("cashier_user_id"):
            user_ids.add(str(payload["cashier_user_id"]))
        if session and session.user_id:
            user_ids.add(session.user_id)
    users = await _user_names(db, tenant_id, user_ids)
    store_ids_seen = {inv.store_id for inv in invoices if inv.store_id}
    store_ids_seen.update(session.store_id for _, session in pos_rows if session and session.store_id)
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
        line_total = money_json(item.line_total)
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
            "unit_price": money_json(item.unit_price),
            "discount": money_json(item.discount or 0),
            "tax": money_json(item.line_tax or 0),
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
            if include_cost:
                if product.cost_price is None:
                    row["cost"] = None
                    row["profit"] = None
                else:
                    cost = money_json(round(money_json(product.cost_price) * qty, 2))
                    row["cost"] = cost
                    row["profit"] = money_json(round(sales_total - cost, 2))
            _append(row, tx.created_at)

    lines.sort(key=lambda row: row["_sort"], reverse=True)
    for row in lines:
        row.pop("_sort", None)
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
                collected = money_json(round(collected + money_json(pay.amount), 2))
                _add(str(pay.payment_method or "other"), money_json(pay.amount))
            due = max(money_json(inv.total_amount) - money_json(inv.paid_amount), 0)
            if due > 0:
                _add("on_account", due)
            elif not by_invoice.get(inv.id) and money_json(inv.total_amount) > 0:
                _add("recorded_on_invoice", money_json(inv.total_amount))

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
                collected = money_json(round(collected + money_json(pay.amount), 2))
                _add(str(pay.payment_method or "other"), money_json(pay.amount))
            due = max(money_json(tx.total) - collected, 0)
            if due > 0:
                _add("on_account", due)
        else:
            method = str((tx.payload or {}).get("payment_method") or "on_account")
            _add(method, money_json(tx.total or 0))

    rows = sorted(buckets.values(), key=lambda row: row["amount"], reverse=True)
    return {
        "returns_note": RETURNS_NOTE,
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
            header = money_json(inv.discount_amount or 0)
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
                amount = money_json(item.discount or 0)
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
    rows.sort(key=lambda row: row["_sort"], reverse=True)
    for row in rows:
        row.pop("_sort", None)
    return {
        "returns_note": (
            "Discounts are listed here and are already taken out of sales revenue. "
            "They are not subtracted again."
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
                "total": money_json(tx.total or 0),
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
