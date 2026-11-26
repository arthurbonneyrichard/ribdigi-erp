"""One receipt printing service for every desk.

A receipt is built only from a payment record that is already saved, so a failed
or unconfirmed payment has nothing to print. Printing never writes to a sale or
payment: it only creates print jobs, which are idempotent per document, printer
and reprint number.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app import models as m
from app import printers as printers_svc
from app import receipts as receipts_svc
from app.honesty import money_json
from app.print_branding import branding_fields_for_payload

# An agent that has not polled for this long is treated as switched off.
AGENT_ONLINE_SECONDS = 20
TERMINALS_KEY = "pos_terminals"
MAX_TERMINALS = 200

# Which module permission lets a person print each kind of receipt (any one of them).
SOURCE_MODULES: dict[str, tuple[str, ...]] = {
    "pos_sale": ("pos",),
    "layaway_payment": ("pos",),
    "restaurant_order": ("restaurant",),
    "bakery_sale": ("bakery",),
    "bakery_order_payment": ("bakery",),
    "bakery_customer_payment": ("bakery",),
    "hotel_payment": ("hotel",),
    "hotel_shop_sale": ("hotel",),
    "gym_payment": ("gym",),
    "gym_sale": ("gym",),
    "fmcg_payment": ("fmcg",),
    "customer_payment": ("sales", "credit", "hotel"),
}


# ---------------------------------------------------------------- terminals


def _terminals(tenant: m.Tenant | None) -> dict[str, Any]:
    branding = getattr(tenant, "print_branding", None) if tenant else None
    if not isinstance(branding, dict):
        return {}
    rows = branding.get(TERMINALS_KEY)
    return rows if isinstance(rows, dict) else {}


def terminal_settings(tenant: m.Tenant | None, terminal_id: str | None) -> dict[str, Any]:
    row = _terminals(tenant).get(str(terminal_id or "")) or {}
    return {
        "terminal_id": terminal_id or None,
        "name": row.get("name"),
        "receipt_printer_id": row.get("receipt_printer_id"),
        "auto_print": bool(row.get("auto_print", True)),
        "saved": bool(row),
    }


def list_terminals(tenant: m.Tenant | None) -> list[dict[str, Any]]:
    return [terminal_settings(tenant, key) for key in sorted(_terminals(tenant))]


async def save_terminal(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    terminal_id: str,
    name: str | None,
    receipt_printer_id: str | None,
    auto_print: bool,
) -> dict[str, Any]:
    if receipt_printer_id:
        printer = await db.get(m.Printer, receipt_printer_id)
        if not printer or printer.tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Printer not found")
        if "customer_receipt" not in (printer.purposes or []):
            raise HTTPException(status_code=400, detail="That printer is not set up for customer receipts")
    rows = dict(_terminals(tenant))
    if terminal_id not in rows and len(rows) >= MAX_TERMINALS:
        raise HTTPException(status_code=409, detail="Too many tills saved. Remove an old one first.")
    rows[terminal_id] = {
        "name": (name or "").strip()[:80] or None,
        "receipt_printer_id": receipt_printer_id or None,
        "auto_print": bool(auto_print),
    }
    branding = dict(tenant.print_branding or {})
    branding[TERMINALS_KEY] = rows
    tenant.print_branding = branding
    flag_modified(tenant, "print_branding")
    await db.flush()
    return terminal_settings(tenant, terminal_id)


async def receipt_printers(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    store_id: str | None,
    terminal_id: str | None,
) -> list[m.Printer]:
    """This till's own receipt printer when one is assigned, else the store's receipt printers."""
    chosen = terminal_settings(tenant, terminal_id)["receipt_printer_id"]
    if chosen:
        row = await db.get(m.Printer, chosen)
        if (
            row
            and row.tenant_id == tenant.id
            and row.is_enabled
            and "customer_receipt" in (row.purposes or [])
        ):
            return [row]
    return await printers_svc.matching_printers(
        db, tenant_id=tenant.id, store_id=store_id, purpose="customer_receipt"
    )


# ---------------------------------------------------------------- receipts


def _base(
    tenant: m.Tenant,
    store: m.Store | None,
    *,
    reference: str,
    created_at: datetime | None,
    title: str | None = None,
) -> dict[str, Any]:
    branding = branding_fields_for_payload(tenant)
    return {
        "title": title,
        "reference": reference,
        "company_name": (tenant.company_name or "").strip() or "RIBDIGI ERP",
        "store_name": store.name if store else None,
        "store_id": store.id if store else None,
        "company_phone": (store.phone if store else None) or tenant.phone,
        "company_email": tenant.email,
        "company_website": tenant.website,
        "company_address": (store.address if store else None) or tenant.address,
        "print_header": branding["print_header"],
        "print_footer": branding["print_footer"],
        "default_receipt_paper": branding["default_receipt_paper"],
        "currency": tenant.currency or "GHS",
        "customer_name": None,
        "cashier_name": None,
        "items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "discount_amount": 0.0,
        "total": 0.0,
        "payment_method": "cash",
        "payments": [],
        "paid_amount": 0.0,
        "balance_due": 0.0,
        "payment_status": "",
        "created_at": created_at,
    }


def _item(name: str, quantity: Any, line_total: Any) -> dict[str, Any]:
    return {
        "name": name or "Item",
        "quantity": money_json(quantity or 0),
        "line_total": money_json(line_total or 0),
    }


def _payment_only(receipt: dict[str, Any], *, what: str, amount: Any, method: str) -> dict[str, Any]:
    value = money_json(amount or 0)
    receipt.update(
        items=[_item(what, 1, value)],
        subtotal=value,
        total=value,
        payment_method=method or "cash",
        payments=[{"payment_method": method or "cash", "amount": value}],
    )
    return receipt


async def _owned(db: AsyncSession, model: Any, tenant_id: str, row_id: str | None, label: str) -> Any:
    row = await db.get(model, row_id) if row_id else None
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


async def _name_of(db: AsyncSession, model: Any, tenant_id: str, row_id: str | None, field: str) -> str | None:
    row = await db.get(model, row_id) if row_id else None
    if row is None or row.tenant_id != tenant_id:
        return None
    return getattr(row, field, None)


async def _store(db: AsyncSession, tenant_id: str, store_id: str | None) -> m.Store | None:
    row = await db.get(m.Store, store_id) if store_id else None
    return row if row is not None and row.tenant_id == tenant_id else None


def _not_paid() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "PAYMENT_NOT_CONFIRMED", "message": "This payment is not complete, so there is no receipt to print."},
    )


async def _lines(db: AsyncSession, model: Any, tenant_id: str, column: Any, parent_id: str) -> list[Any]:
    rows = await db.execute(select(model).where(model.tenant_id == tenant_id, column == parent_id))
    return list(rows.scalars().all())


async def _b_pos_sale(db, tenant, source_id):
    tx = await _owned(db, m.Transaction, tenant.id, source_id, "POS sale")
    if tx.tx_type != "pos_sale":
        raise HTTPException(status_code=404, detail="POS sale not found")
    if tx.status != "completed":
        raise _not_paid()
    return await receipts_svc.build_sale_receipt(
        db, tenant_id=tenant.id, sale_id=tx.id, user_id=(tx.payload or {}).get("cashier_user_id")
    )


async def _b_restaurant_order(db, tenant, source_id):
    from app import restaurant as restaurant_svc

    order = await _owned(db, m.RestaurantOrder, tenant.id, source_id, "Order")
    if order.status != "completed":
        raise _not_paid()
    store = await _store(db, tenant.id, order.store_id)
    receipt = _base(tenant, store, reference=order.order_number, created_at=order.completed_at or order.created_at)
    lines = await _lines(db, m.RestaurantOrderLine, tenant.id, m.RestaurantOrderLine.order_id, order.id)
    names: dict[str, str] = {}
    if lines:
        rows = await db.execute(
            select(m.Product.id, m.Product.name).where(
                m.Product.tenant_id == tenant.id, m.Product.id.in_({x.product_id for x in lines})
            )
        )
        names = {r[0]: r[1] for r in rows.all()}
    tenders = await restaurant_svc.order_tenders(db, order)
    total = money_json(order.total_amount)
    subtotal = money_json(order.subtotal)
    discount = money_json(order.discount_amount or 0)
    receipt.update(
        customer_name=order.customer_name,
        cashier_name=await _name_of(db, m.User, tenant.id, order.completed_by, "full_name"),
        items=[_item(names.get(x.product_id, "Item"), x.quantity, x.line_total) for x in lines],
        subtotal=subtotal,
        # What sits between the dishes and the bill: tax and service, after any discount.
        tax=money_json(max(0.0, round(total - subtotal + discount, 2))),
        tax_label="Tax and service",
        discount_amount=discount,
        total=total,
        tip=money_json(order.tip_amount or 0),
        payment_method=order.payment_method or "cash",
        payments=[{"payment_method": method, "amount": amount} for method, amount in tenders],
    )
    return receipt


async def _b_bakery_sale(db, tenant, source_id):
    from app import bakery as bakery_svc

    sale = await _owned(db, m.BakerySale, tenant.id, source_id, "Sale")
    if sale.status not in bakery_svc.SOLD:
        raise _not_paid()
    receipt = _base(tenant, None, reference=sale.sale_number, created_at=sale.created_at)
    lines = await _lines(db, m.BakerySaleLine, tenant.id, m.BakerySaleLine.sale_id, sale.id)
    tenders = await _lines(db, m.BakeryPayment, tenant.id, m.BakeryPayment.sale_id, sale.id)
    paid = [
        {"payment_method": p.method, "amount": money_json(p.amount)}
        for p in tenders
        if money_json(p.amount) > 0
    ]
    receipt.update(
        customer_name=sale.customer_name,
        cashier_name=await _name_of(db, m.User, tenant.id, sale.created_by, "full_name"),
        items=[_item(x.name, x.quantity, x.line_total) for x in lines],
        subtotal=money_json(sale.subtotal),
        tax=money_json(sale.tax),
        discount_amount=money_json(sale.discount or 0),
        total=money_json(sale.total),
        payment_method=sale.payment_method,
        payments=paid,
    )
    return receipt


async def _b_bakery_order_payment(db, tenant, source_id):
    pay = await _owned(db, m.BakeryPayment, tenant.id, source_id, "Payment")
    if not pay.order_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = await _owned(db, m.BakeryOrder, tenant.id, pay.order_id, "Order")
    receipt = _base(tenant, None, reference=order.order_number, created_at=pay.created_at, title="PAYMENT RECEIPT")
    receipt["customer_name"] = getattr(order, "customer_name", None)
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    word = "Refund" if money_json(pay.amount) < 0 else "Payment"
    return _payment_only(receipt, what=f"{word} on {order.order_number}", amount=pay.amount, method=pay.method)


async def _b_bakery_customer_payment(db, tenant, source_id):
    pay = await _owned(db, m.BakeryCustomerPayment, tenant.id, source_id, "Payment")
    receipt = _base(tenant, None, reference=pay.payment_number, created_at=pay.created_at, title="PAYMENT RECEIPT")
    receipt["customer_name"] = await _name_of(db, m.BakeryCustomer, tenant.id, pay.customer_id, "name")
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    return _payment_only(receipt, what="Payment on account", amount=pay.amount, method=pay.method)


async def _b_hotel_payment(db, tenant, source_id):
    pay = await _owned(db, m.HotelFolioPayment, tenant.id, source_id, "Payment")
    folio = await _owned(db, m.HotelFolio, tenant.id, pay.folio_id, "Bill")
    refund = bool(pay.refund_of_id) or money_json(pay.amount) < 0
    receipt = _base(
        tenant,
        None,
        reference=folio.folio_number,
        created_at=pay.created_at,
        title="REFUND RECEIPT" if refund else "PAYMENT RECEIPT",
    )
    receipt["customer_name"] = await _name_of(db, m.HotelGuest, tenant.id, folio.guest_id, "full_name")
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.recorded_by, "full_name")
    what = f"{'Refund' if refund else 'Payment'} on bill {folio.folio_number}"
    return _payment_only(receipt, what=what, amount=pay.amount, method=pay.method)


async def _b_hotel_shop_sale(db, tenant, source_id):
    sale = await _owned(db, m.HotelShopSale, tenant.id, source_id, "Sale")
    if sale.status not in {"completed", "refunded"}:
        raise _not_paid()
    store = await _store(db, tenant.id, sale.store_id)
    receipt = _base(tenant, store, reference=sale.sale_number, created_at=sale.created_at)
    lines = await _lines(db, m.HotelShopSaleLine, tenant.id, m.HotelShopSaleLine.sale_id, sale.id)
    total = money_json(sale.total)
    receipt.update(
        customer_name=sale.customer_name,
        cashier_name=await _name_of(db, m.User, tenant.id, sale.created_by, "full_name"),
        items=[_item(x.name, x.quantity, x.line_total) for x in lines],
        subtotal=money_json(sale.subtotal),
        tax=money_json(sale.tax),
        total=total,
        payment_method=sale.payment_method,
        payments=[{"payment_method": sale.payment_method, "amount": total}],
    )
    return receipt


async def _b_gym_payment(db, tenant, source_id):
    pay = await _owned(db, m.GymPayment, tenant.id, source_id, "Payment")
    receipt = _base(
        tenant,
        None,
        reference=f"GYM-{pay.id[:8].upper()}",
        created_at=pay.created_at,
        title="REFUND RECEIPT" if money_json(pay.amount) < 0 else "PAYMENT RECEIPT",
    )
    receipt["customer_name"] = await _name_of(db, m.GymMember, tenant.id, pay.member_id, "full_name")
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    what = str(pay.kind or "payment").replace("_", " ").capitalize()
    return _payment_only(receipt, what=what, amount=pay.amount, method=pay.method)


async def _b_gym_sale(db, tenant, source_id):
    sale = await _owned(db, m.GymShopSale, tenant.id, source_id, "Sale")
    receipt = _base(tenant, None, reference=sale.sale_number, created_at=sale.created_at)
    lines = await _lines(db, m.GymShopSaleLine, tenant.id, m.GymShopSaleLine.sale_id, sale.id)
    total = money_json(sale.total)
    receipt.update(
        customer_name=await _name_of(db, m.GymMember, tenant.id, sale.member_id, "full_name"),
        cashier_name=await _name_of(db, m.User, tenant.id, sale.created_by, "full_name"),
        items=[_item(x.name, x.quantity, x.line_total) for x in lines],
        subtotal=money_json(sale.subtotal),
        tax=money_json(sale.tax),
        total=total,
        payment_method=sale.method,
        payments=[{"payment_method": sale.method, "amount": total}],
    )
    return receipt


async def _b_fmcg_payment(db, tenant, source_id):
    pay = await _owned(db, m.FmcgPayment, tenant.id, source_id, "Payment")
    receipt = _base(tenant, None, reference=pay.payment_number, created_at=pay.created_at, title="PAYMENT RECEIPT")
    receipt["customer_name"] = await _name_of(db, m.Party, tenant.id, pay.customer_id, "name")
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    what = "Payment on account"
    if pay.order_id:
        number = await _name_of(db, m.FmcgOrder, tenant.id, pay.order_id, "order_number")
        if number:
            what = f"Payment on {number}"
    return _payment_only(receipt, what=what, amount=pay.amount, method=pay.method)


async def _b_customer_payment(db, tenant, source_id):
    pay = await _owned(db, m.CustomerPayment, tenant.id, source_id, "Payment")
    receipt = _base(tenant, None, reference=pay.payment_number, created_at=pay.created_at, title="PAYMENT RECEIPT")
    receipt["currency"] = pay.currency or receipt["currency"]
    receipt["customer_name"] = await _name_of(db, m.Party, tenant.id, pay.customer_id, "name")
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    what = "Payment on account"
    if pay.sales_invoice_id:
        number = await _name_of(db, m.SalesInvoice, tenant.id, pay.sales_invoice_id, "invoice_number")
        if number:
            what = f"Payment on {number}"
    return _payment_only(receipt, what=what, amount=pay.amount, method=pay.payment_method)


async def _b_layaway_payment(db, tenant, source_id):
    pay = await _owned(db, m.PosLayawayPayment, tenant.id, source_id, "Payment")
    lay = await _owned(db, m.PosLayaway, tenant.id, pay.layaway_id, "Layaway")
    store = await _store(db, tenant.id, lay.store_id)
    receipt = _base(tenant, store, reference=lay.layaway_number, created_at=pay.created_at, title="LAYAWAY RECEIPT")
    receipt["customer_name"] = lay.customer_name
    receipt["cashier_name"] = await _name_of(db, m.User, tenant.id, pay.created_by, "full_name")
    _payment_only(receipt, what=f"Layaway {lay.layaway_number}", amount=pay.amount, method=pay.method)
    receipt["balance_due"] = money_json(max(0.0, round(money_json(lay.total) - money_json(lay.paid), 2)))
    return receipt


_BUILDERS = {
    "pos_sale": _b_pos_sale,
    "restaurant_order": _b_restaurant_order,
    "bakery_sale": _b_bakery_sale,
    "bakery_order_payment": _b_bakery_order_payment,
    "bakery_customer_payment": _b_bakery_customer_payment,
    "hotel_payment": _b_hotel_payment,
    "hotel_shop_sale": _b_hotel_shop_sale,
    "gym_payment": _b_gym_payment,
    "gym_sale": _b_gym_sale,
    "fmcg_payment": _b_fmcg_payment,
    "customer_payment": _b_customer_payment,
    "layaway_payment": _b_layaway_payment,
}


async def newest_id(db: AsyncSession, model: Any, tenant_id: str, column: Any, value: str) -> str | None:
    """The latest row saved for a document, so a screen can print that payment's receipt."""
    rows = await db.execute(
        select(model.id)
        .where(model.tenant_id == tenant_id, column == value)
        .order_by(model.created_at.desc())
        .limit(1)
    )
    return rows.scalar_one_or_none()


async def build_receipt(db: AsyncSession, *, tenant: m.Tenant, source_type: str, source_id: str) -> dict[str, Any]:
    builder = _BUILDERS.get(source_type)
    if builder is None:
        raise HTTPException(status_code=422, detail="Unknown receipt type")
    return await builder(db, tenant, source_id)


def _with_cash(receipt: dict[str, Any], cash_tendered: float | None) -> dict[str, Any]:
    """Add cash received and change when the cash handed over covers the cash part."""
    if cash_tendered is None or receipt.get("cash_tendered") is not None:
        return receipt
    cash_due = sum(
        money_json(p.get("amount") or 0)
        for p in receipt.get("payments") or []
        if p.get("payment_method") == "cash"
    )
    if not receipt.get("payments") and receipt.get("payment_method") == "cash":
        cash_due = money_json(receipt.get("total") or 0)
    cash_due = money_json(round(cash_due + money_json(receipt.get("tip") or 0), 2))
    if cash_due <= 0 or money_json(cash_tendered) + 0.009 < cash_due:
        return receipt
    receipt["cash_tendered"] = money_json(cash_tendered)
    receipt["change_due"] = money_json(round(money_json(cash_tendered) - cash_due, 2))
    return receipt


def _public(receipt: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "title", "reference", "company_name", "store_name", "created_at", "cashier_name", "customer_name",
        "currency", "items", "subtotal", "tax", "tax_label", "discount_amount", "total", "tip",
        "payment_method", "payments", "cash_tendered", "change_due", "balance_due", "print_footer",
    )
    return {k: receipt.get(k) for k in keys}


async def fallback_slip(
    db: AsyncSession, *, tenant: m.Tenant, source_type: str, source_id: str, cash_tendered: float | None
) -> dict[str, str]:
    """The same receipt for the computer's print window. The screen opens it only when asked."""
    receipt = _with_cash(
        await build_receipt(db, tenant=tenant, source_type=source_type, source_id=source_id), cash_tendered
    )
    paper = receipt.get("default_receipt_paper") or "80mm"
    return {
        "text": receipts_svc.render_thermal_text(receipt, paper=paper),
        "html": receipts_svc.render_thermal_html(receipt, paper=paper),
    }


# ---------------------------------------------------------------- jobs


async def _jobs_for(db: AsyncSession, tenant_id: str, source_type: str, source_id: str) -> list[m.PrintJob]:
    rows = await db.execute(
        select(m.PrintJob)
        .where(
            m.PrintJob.tenant_id == tenant_id,
            m.PrintJob.source_type == source_type,
            m.PrintJob.source_id == source_id,
            m.PrintJob.purpose == "customer_receipt",
        )
        .order_by(m.PrintJob.created_at.asc())
    )
    return list(rows.scalars().all())


def _latest_per_printer(jobs: list[m.PrintJob]) -> list[m.PrintJob]:
    latest: dict[str, m.PrintJob] = {}
    for job in sorted(jobs, key=lambda j: (_reprint_no(j), j.created_at or datetime.min)):
        latest[job.printer_id] = job
    return list(latest.values())


def _reprint_no(job: m.PrintJob) -> int:
    return int((job.payload or {}).get("reprint_no") or 0)


async def describe_jobs(db: AsyncSession, jobs: list[m.PrintJob]) -> list[dict[str, Any]]:
    """Job status with the printer's name and whether anything is there to print it."""
    now = datetime.utcnow()
    out: list[dict[str, Any]] = []
    for job in jobs:
        printer = await db.get(m.Printer, job.printer_id)
        online: bool | None = None
        if printer and printer.connection_type == "print_agent":
            agent = await db.get(m.PrintAgent, printer.agent_id) if printer.agent_id else None
            online = bool(
                agent
                and agent.is_active
                and agent.last_seen_at
                and now - agent.last_seen_at < timedelta(seconds=AGENT_ONLINE_SECONDS)
            )
        row = printers_svc.serialize_job(job)
        row["printer_name"] = printer.name if printer else None
        row["connection_type"] = printer.connection_type if printer else None
        row["agent_online"] = online
        if job.status == "browser_pending":
            row["html"] = (job.payload or {}).get("html")
            row["text"] = (job.payload or {}).get("text")
        out.append(row)
    return out


async def print_receipt(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    source_type: str,
    source_id: str,
    mode: str,
    terminal_id: str | None,
    cash_tendered: float | None,
    user_id: str | None,
) -> dict[str, Any]:
    """mode: auto (straight after payment), print (cashier asked), reprint (another copy)."""
    receipt = _with_cash(
        await build_receipt(db, tenant=tenant, source_type=source_type, source_id=source_id), cash_tendered
    )
    result: dict[str, Any] = {"receipt": _public(receipt), "jobs": [], "auto_print": True}
    existing = await _jobs_for(db, tenant.id, source_type, source_id)
    if mode == "retry":
        mode = "print"  # nothing was ever queued (no printer then): print it now
    if mode == "auto" and not terminal_settings(tenant, terminal_id)["auto_print"]:
        result["auto_print"] = False
        result["jobs"] = await describe_jobs(db, _latest_per_printer(existing))
        return result
    if mode != "reprint" and existing:
        # The same payment asked again (double tap, repeated callback): never a second copy.
        result["jobs"] = await describe_jobs(db, _latest_per_printer(existing))
        return result
    printers = await receipt_printers(
        db, tenant=tenant, store_id=receipt.get("store_id"), terminal_id=terminal_id
    )
    reprint_no = max(len(existing), 1 + max(_reprint_no(j) for j in existing)) if existing else 0
    if reprint_no:
        waiting = [j for j in _latest_per_printer(existing) if j.status in {"queued", "claimed", "printing"}]
        if waiting:
            # A copy is still on its way; sending another would print twice.
            result["jobs"] = await describe_jobs(db, waiting)
            return result
    jobs: list[m.PrintJob] = []
    for printer in printers:
        paper = printer.paper if printer.paper in {"58mm", "80mm"} else "80mm"
        slip = dict(receipt, copy_label="REPRINT" if reprint_no else None)
        original = next((j for j in existing if j.printer_id == printer.id), None)
        jobs.append(
            await printers_svc.enqueue_job(
                db,
                tenant_id=tenant.id,
                printer=printer,
                source_type=source_type,
                source_id=source_id,
                purpose="customer_receipt",
                payload={
                    "kind": "customer_receipt",
                    "reference": receipt.get("reference"),
                    "reprint_no": reprint_no,
                    "text": receipts_svc.render_thermal_text(slip, paper=paper),
                    "html": receipts_svc.render_thermal_html(slip, paper=paper),
                    "browser_fallback": printer.connection_type == "browser_dialog",
                },
                user_id=user_id,
                reprint_of_job_id=original.id if reprint_no and original else None,
                reprint_seq=reprint_no,
            )
        )
    result["jobs"] = await describe_jobs(db, jobs)
    return result


# A claimed job this old means the agent stopped part way; the cashier may send it again.
CLAIM_STALE_SECONDS = 45


async def retry_receipt(
    db: AsyncSession, *, tenant: m.Tenant, source_type: str, source_id: str, user_id: str | None
) -> list[dict[str, Any]]:
    """Send failed or stuck copies again. Same document and same job: nothing is sold twice."""
    jobs = _latest_per_printer(await _jobs_for(db, tenant.id, source_type, source_id))
    stale = datetime.utcnow() - timedelta(seconds=CLAIM_STALE_SECONDS)
    for job in jobs:
        stuck = job.status in {"claimed", "printing"} and (job.updated_at or datetime.min) < stale
        if job.status == "failed" or stuck:
            await printers_svc.retry_job(db, tenant_id=tenant.id, job_id=job.id, user_id=user_id)
            await printers_svc.deliver_now(db, job)
    return await describe_jobs(db, jobs)


async def receipt_status(db: AsyncSession, *, tenant_id: str, source_type: str, source_id: str) -> list[dict[str, Any]]:
    jobs = await _jobs_for(db, tenant_id, source_type, source_id)
    return await describe_jobs(db, _latest_per_printer(jobs))
