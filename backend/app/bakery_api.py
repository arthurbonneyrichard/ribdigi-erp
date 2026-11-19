"""Bakery routes. The `bakery` permission and the industry gate come from require_permission.

Each bakery role does one job, checked here on top of the module grant:
bakers bake and record waste, cashiers run the counter, and money corrections need a manager.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import bakery as svc
from app.db import get_db
from app.schemas import E164PhoneValue, IsoDateQueryValue, NonNegativeMoneyValue, PartyNameValue, UuidIdValue
from app.security import require_permission



async def _till_context(
    x_bakery_till: Annotated[UuidIdValue | None, Header(alias="X-Bakery-Till")] = None,
    claims=Depends(require_permission("bakery", "read")),
):
    """Which till this request uses, and who is asking. Set fresh on every request."""
    svc.CHOSEN_TILL.set(str(x_bakery_till) if x_bakery_till else None)
    svc.TILL_USER.set(claims.get("sub"))


router = APIRouter(prefix="/bakery", tags=["bakery"], dependencies=[Depends(_till_context)])

_JOBS = {
    "bakery_baker": frozenset({"bake", "waste", "labels", "sheet"}),
    # Cashiers also make the day's trade deliveries and take trade payments.
    "bakery_cashier": frozenset({"till", "orders", "waste", "trade", "labels", "sheet"}),
    "bakery_driver": frozenset({"deliver", "sell"}),
}
_WORDS = {
    "bakery_baker": "Bakers look after recipes, baking and waste. Sales and money need a cashier or manager.",
    "bakery_cashier": "Cashiers run the counter and orders. Recipes, refunds and reports need a manager.",
    "bakery_driver": "Drivers pick up, deliver, sell on the road and take the money. Ask the shop for the rest.",
}


def _driver_id(claims: dict) -> str | None:
    """A driver's money always goes into their own cash bag, never the counter till."""
    return claims.get("sub") if str(claims.get("role") or "") == "bakery_driver" else None


def _can_drive(claims: dict) -> bool:
    """Drivers, and managers or owners who sometimes drive."""
    return str(claims.get("role") or "") in svc.DRIVE_ROLES


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _job(claims: dict, area: str) -> None:
    role = str(claims.get("role") or "")
    if role in _JOBS and area not in _JOBS[role]:
        raise HTTPException(status_code=403, detail={"code": "BAKERY_ROLE_JOB", "message": _WORDS[role]})


def _sees_money(claims: dict) -> bool:
    return str(claims.get("role") or "") not in ("bakery_baker", "bakery_driver")


Qty = Annotated[float, Field(gt=0, le=100000, allow_inf_nan=False)]


class RecipeLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: UuidIdValue
    quantity: Qty
    # The unit the amount is written in (250 g of a kilo ingredient). Leave out for the stock unit.
    unit: Literal["kg", "g", "l", "ml", "each"] | None = None


class RecipeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    name: Annotated[str, Field(min_length=1, max_length=150)]
    yield_qty: Qty
    lines: list[RecipeLine] = Field(min_length=1, max_length=60)
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class BakeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: UuidIdValue
    batches: Qty = 1
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class WasteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    reason: Literal["unsold", "burnt", "damaged", "expired", "other"]
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class ShiftOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_cash: NonNegativeMoneyValue = 0
    # Which counter: "Front counter", "Second counter", "Market stall". Leave out for "Counter".
    till_name: Annotated[str, Field(min_length=1, max_length=60)] | None = None


class ShiftClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
TillMethod = Literal["cash", "card", "mobile_money", "wallet"]


class SaleLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    # Taken off this line's price before tax. Cashiers up to 10%, managers any amount.
    discount_percent: Percent | None = None
    # Sold at the item's day-old price, for bread baked before today.
    day_old: bool = False


class SalePart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: TillMethod
    # Leave out on one part to put the rest of the bill there.
    amount: Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)] | None = None


class SaleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: TillMethod = "cash"
    customer_name: PartyNameValue | None = None
    lines: list[SaleLine] = Field(min_length=1, max_length=60)
    # Paid more than one way (cash and Mobile Money...). The parts must add up to the bill.
    payments: list[SalePart] | None = Field(default=None, min_length=2, max_length=4)
    discount_reason: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    # A manager who is out driving sells from the van into their own cash bag.
    from_bag: bool = False


class RefundLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_line_id: UuidIdValue
    quantity: Qty


class RefundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    restock: bool = False
    # Leave out to refund everything not yet refunded.
    lines: list[RefundLine] | None = Field(default=None, min_length=1, max_length=60)
    # How the money goes back. Needed when the sale was paid more than one way.
    method: TillMethod | None = None


class OrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: PartyNameValue
    phone: E164PhoneValue | None = None
    due_date: date
    lines: list[OrderLine] = Field(min_length=1, max_length=60)
    deposit: NonNegativeMoneyValue = 0
    deposit_method: Literal["cash", "card", "mobile_money", "wallet"] | None = None
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    delivery: bool = False
    address: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    driver_id: UuidIdValue | None = None


class DriverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver_id: UuidIdValue | None = None


class FailedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]


class BagOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_cash: NonNegativeMoneyValue = 0


class HandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue


class CollectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: Literal["cash", "card", "mobile_money", "wallet"] | None = None


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    deposit_action: Literal["refund", "keep"] | None = None


@router.get("/summary")
async def bakery_summary(
    claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)
):
    return _env(await svc.summary(db, claims["tenant_id"], money=_sees_money(claims)))


@router.get("/items")
async def bakery_items(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.list_items(db, claims["tenant_id"]))


@router.get("/ingredients")
async def bakery_ingredients(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.list_ingredients(db, claims["tenant_id"]))


@router.get("/recipes")
async def bakery_recipes(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "bake")
    rows = await svc.list_recipes(db, claims["tenant_id"])
    return _env([await svc.present_recipe(db, row) for row in rows])


@router.post("/recipes")
async def bakery_recipe_create(
    payload: RecipeBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "bake")
    row = await svc.save_recipe(
        db,
        claims["tenant_id"],
        product_id=payload.product_id,
        name=payload.name,
        yield_qty=payload.yield_qty,
        lines=[line.model_dump() for line in payload.lines],
        notes=payload.notes,
    )
    await db.commit()
    return _env(await svc.present_recipe(db, row), "Recipe saved")


@router.put("/recipes/{recipe_id}")
async def bakery_recipe_update(
    recipe_id: UuidIdValue,
    payload: RecipeBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "bake")
    row = await svc.save_recipe(
        db,
        claims["tenant_id"],
        product_id=payload.product_id,
        name=payload.name,
        yield_qty=payload.yield_qty,
        lines=[line.model_dump() for line in payload.lines],
        notes=payload.notes,
        recipe_id=recipe_id,
    )
    await db.commit()
    return _env(await svc.present_recipe(db, row), "Recipe saved")


@router.get("/batches")
async def bakery_batches(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "bake")
    return _env(await svc.list_batches(db, claims["tenant_id"]))


@router.post("/batches")
async def bakery_bake(
    payload: BakeBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "bake")
    row = await svc.bake(
        db,
        claims["tenant_id"],
        recipe_id=payload.recipe_id,
        batches=payload.batches,
        user_id=claims.get("sub"),
        notes=payload.notes,
    )
    await db.commit()
    return _env(svc.serialize_batch(row), "Baked")


@router.get("/waste")
async def bakery_waste_list(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "waste")
    return _env(await svc.list_waste(db, claims["tenant_id"]))


@router.post("/waste")
async def bakery_waste(
    payload: WasteBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "waste")
    row = await svc.record_waste(
        db,
        claims["tenant_id"],
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        user_id=claims.get("sub"),
        notes=payload.notes,
    )
    await db.commit()
    return _env({"id": row.id, "total_cost": float(row.total_cost or 0)}, "Waste recorded")


@router.get("/till/shift")
async def bakery_shift(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "till")
    row = await svc.current_shift(db, claims["tenant_id"])
    return _env(await svc.present_shift(db, claims["tenant_id"], row) if row else None)


@router.get("/tills")
async def bakery_open_tills(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    """Every till open now, so a cashier can choose theirs."""
    _job(claims, "till")
    return _env([await svc.present_shift(db, claims["tenant_id"], row) for row in await svc.open_tills(db, claims["tenant_id"])])


@router.get("/till/shifts")
async def bakery_shifts(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "till")
    rows = await svc.list_closed_shifts(db, claims["tenant_id"])
    return _env([await svc.present_shift(db, claims["tenant_id"], row) for row in rows])


@router.post("/till/shift/open")
async def bakery_shift_open(
    payload: ShiftOpen, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "till")
    row = await svc.open_shift(
        db, claims["tenant_id"], opening_cash=payload.opening_cash, user_id=claims.get("sub"), till_name=payload.till_name
    )
    await db.commit()
    return _env(await svc.present_shift(db, claims["tenant_id"], row), "Till open")


@router.post("/till/shift/close")
async def bakery_shift_close(
    payload: ShiftClose, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "till")
    row = await svc.close_shift(
        db, claims["tenant_id"], counted_cash=payload.counted_cash, notes=payload.notes, user_id=claims.get("sub")
    )
    body = await svc.present_shift(db, claims["tenant_id"], row)
    await db.commit()
    return _env(body, "Till closed")


class OfflineSaleBody(BaseModel):
    """A paid counter sale the till kept while the internet was down."""

    model_config = ConfigDict(extra="forbid")

    offline_ref: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
    created_at: datetime
    payment_method: Literal["cash", "card", "mobile_money", "wallet"] = "cash"
    customer_name: PartyNameValue | None = None
    charged_total: Annotated[float, Field(ge=0, le=1e12)] | None = None
    lines: list[SaleLine] = Field(min_length=1, max_length=60)
    discount_reason: Annotated[str, Field(min_length=3, max_length=255)] | None = None


class OfflineSyncBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{4,64}$")] | None = None
    sales: list[OfflineSaleBody] = Field(min_length=1, max_length=100)


@router.get("/till/offline/prices")
async def bakery_offline_prices(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    """Prices and tax rules the till keeps so an offline bill totals like the server's."""
    _job(claims, "till")
    from app import bakery_offline as offline_svc

    return _env(await offline_svc.price_sheet(db, claims["tenant_id"]))


@router.post("/till/offline/sync")
async def bakery_offline_sync(
    payload: OfflineSyncBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Book counter sales rung offline. Each offline_ref books once."""
    _job(claims, "till")
    from app import bakery_offline as offline_svc

    body = await offline_svc.sync_sales(
        db, claims["tenant_id"], payload.sales, user_id=claims.get("sub"), device_id=payload.device_id,
        role=str(claims.get("role") or ""),
    )
    await db.commit()
    return _env(body, f"{body['counts'].get('booked', 0)} offline sale(s) booked")


@router.get("/sales")
async def bakery_sales(
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "till")
    rows = await svc.list_sales(db, claims["tenant_id"], limit=limit)
    return _env([await svc.present_sale(db, row) for row in rows])


@router.post("/sales")
async def bakery_sell(
    payload: SaleBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    if payload.from_bag and not _can_drive(claims):
        raise HTTPException(status_code=403, detail="Only someone who drives sells from a cash bag")
    bag_owner = _driver_id(claims) or (claims.get("sub") if payload.from_bag else None)
    _job(claims, "sell" if bag_owner else "till")
    row = await svc.create_sale(
        db, claims["tenant_id"], payload, user_id=claims.get("sub"), driver_id=bag_owner,
        role=str(claims.get("role") or ""),
    )
    await db.commit()
    return _env(await svc.present_sale(db, row), "Sale complete")


@router.post("/sales/{sale_id}/refund")
async def bakery_refund(
    sale_id: UuidIdValue,
    payload: RefundBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "correct")
    row = await svc.refund_sale(
        db, claims["tenant_id"], sale_id, reason=payload.reason, restock=payload.restock, user_id=claims.get("sub"),
        lines=payload.lines, method=payload.method,
    )
    await db.commit()
    return _env(await svc.present_sale(db, row), "Sale refunded")


@router.get("/orders")
async def bakery_orders(
    show: Annotated[Literal["open", "all"], Query()] = "open",
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    if str(claims.get("role") or "") != "bakery_baker":
        _job(claims, "orders")
    rows = await svc.list_orders(db, claims["tenant_id"], show=show)
    body = [await svc.present_order(db, row) for row in rows]
    if not _sees_money(claims):
        # A baker needs what to make and when, not the customer's money or phone.
        keep = ("id", "order_number", "customer_name", "due_date", "status", "notes")
        body = [
            {**{k: row[k] for k in keep}, "items": [{k: i[k] for k in ("name", "quantity", "note")} for i in row["items"]]}
            for row in body
        ]
    return _env(body)


@router.post("/orders")
async def bakery_order_create(
    payload: OrderBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "orders")
    row = await svc.create_order(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_order(db, row), "Order taken")


@router.post("/orders/{order_id}/ready")
async def bakery_order_ready(
    order_id: UuidIdValue, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    if str(claims.get("role") or "") != "bakery_baker":
        _job(claims, "orders")
    row = await svc.mark_ready(db, claims["tenant_id"], order_id)
    await db.commit()
    data = await svc.present_order(db, row)
    # Tell the customer, best effort: a failed text never undoes the bake.
    data["customer_texted"] = await _text_customer_ready(db, claims["tenant_id"], row)
    return _env(data, "Order ready")


async def _text_customer_ready(db, tenant_id: str, row) -> dict:
    from app import models as m
    from app import sms

    if not row.phone:
        return {"sent": False, "reason": "No phone number on this order"}
    try:
        company = await db.get(m.Tenant, tenant_id)
        balance = max(0.0, float(row.total or 0) - float(row.deposit or 0))
        owe = f" Balance to pay: {balance:.2f}." if balance > 0 else " It is fully paid."
        how = "It will be with you soon." if row.delivery else "Please come and collect it."
        body = (
            f"Hi {row.customer_name}, your order {row.order_number} at "
            f"{getattr(company, 'company_name', '') or 'our bakery'} is ready. {how}{owe}"
        )
        res = await sms.send_sms(to=row.phone, body=body, tenant=company)
        reason = res.error or ("SMS is not set up" if res.mode == "disabled" else None)
        return {"sent": bool(res.sent), "reason": reason}
    except Exception:
        return {"sent": False, "reason": "Could not send the text"}


_PRINT_CSS = (
    "body{font-family:Arial,sans-serif;max-width:720px;margin:24px auto;color:#10211B}"
    "table{width:100%;border-collapse:collapse}th,td{padding:6px;border-bottom:1px solid #D4E5C4;text-align:left}"
    "th{background:#F2F7EC}.r{text-align:right}"
)


@router.get("/orders/{order_id}/print", response_class=HTMLResponse)
async def bakery_order_print(order_id: UuidIdValue, claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    """The slip the customer takes away: what was ordered, when to collect, deposit and balance."""
    import html as h

    from app import models as m

    _job(claims, "orders")
    row = await db.get(m.BakeryOrder, order_id)
    if row is None or row.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="Order not found")
    company = await db.get(m.Tenant, claims["tenant_id"])
    o = await svc.present_order(db, row)
    lines = "".join(
        f"<tr><td>{h.escape(i['name'])}{('<br/><i>' + h.escape(i['note']) + '</i>') if i.get('note') else ''}</td>"
        f"<td class='r'>{i['quantity']:g}</td><td class='r'>{i['line_total']:.2f}</td></tr>"
        for i in o["items"]
    )
    where = f"Delivery to: {h.escape(o['address'] or '')}" if o["delivery"] else "Collect from the shop"
    cancelled = " (CANCELLED)" if o["status"] == "cancelled" else ""
    note = f"<p>Note: {h.escape(o['notes'])}</p>" if o.get("notes") else ""
    page = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Order {h.escape(o['order_number'])}</title><style>{_PRINT_CSS}</style></head><body>"
        f"<h2>{h.escape(getattr(company, 'company_name', '') or '')}</h2>"
        f"<p>{h.escape(getattr(company, 'address', '') or '')}<br/>Tel {h.escape(getattr(company, 'phone', '') or '-')}</p>"
        f"<h3>Order {h.escape(o['order_number'])}{cancelled}</h3>"
        f"<p>For: <b>{h.escape(o['customer_name'] or '')}</b> {h.escape(o['phone'] or '')}<br/>Needed on <b>{o['due_date']}</b> · {where}</p>"
        "<table><thead><tr><th>Item</th><th class='r'>Qty</th><th class='r'>Amount</th></tr></thead>"
        f"<tbody>{lines}</tbody></table>"
        f"<p class='r'><b>Total {o['total']:.2f}</b><br/>Deposit paid {o['deposit']:.2f}<br/><b>To pay on collection {o['balance']:.2f}</b></p>"
        f"{note}<p><small>Please bring this slip when you collect.</small></p>"
        "<script>window.onload=()=>window.print()</script></body></html>"
    )
    return HTMLResponse(page)


@router.get("/production-sheet/print", response_class=HTMLResponse)
async def bakery_production_sheet(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    """The baker's list for today and tomorrow: what to bake, and the orders behind it. No money."""
    import html as h

    from sqlalchemy import select

    from app import models as m

    _job(claims, "sheet")
    tid = claims["tenant_id"]
    today = await svc.bakery_today(db, tid)
    company = await db.get(m.Tenant, tid)
    todo = [r for r in await svc.to_bake(db, tid, until=today + timedelta(days=1)) if float(r["to_bake"]) > 0]
    orders = (
        await db.execute(
            select(m.BakeryOrder)
            .where(
                m.BakeryOrder.tenant_id == tid,
                m.BakeryOrder.status.in_(svc.ORDER_OPEN),
                m.BakeryOrder.due_date <= today + timedelta(days=1),
            )
            .order_by(m.BakeryOrder.due_date, m.BakeryOrder.order_number)
        )
    ).scalars().all()
    bake_rows = "".join(
        f"<tr><td>{h.escape(r['name'])}</td><td class='r'>{r['ordered']:g}</td><td class='r'>{r['trade']:g}</td>"
        f"<td class='r'>{r['shelf_level']:g}</td><td class='r'>{r['on_hand']:g}</td><td class='r'><b>{r['to_bake']:g}</b></td></tr>"
        for r in todo
    ) or "<tr><td colspan='6'>Nothing to bake.</td></tr>"
    order_rows = ""
    for o in orders:
        for i in (await svc.present_order(db, o))["items"]:
            order_rows += (
                f"<tr><td>{o.due_date}</td><td>{h.escape(o.order_number)} {h.escape(o.customer_name)}</td>"
                f"<td>{h.escape(i['name'])}</td><td class='r'>{i['quantity']:g}</td><td>{h.escape(i.get('note') or '')}</td></tr>"
            )
    order_rows = order_rows or "<tr><td colspan='5'>No orders due.</td></tr>"
    page = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Production sheet</title><style>{_PRINT_CSS}</style></head><body>"
        f"<h2>{h.escape(getattr(company, 'company_name', '') or '')} · Production sheet {today}</h2>"
        "<h3>To bake</h3><table><thead><tr><th>Item</th><th class='r'>Orders</th><th class='r'>Trade</th><th class='r'>Shelf level</th>"
        f"<th class='r'>On hand</th><th class='r'>Bake</th></tr></thead><tbody>{bake_rows}</tbody></table>"
        "<h3>Orders due today and tomorrow</h3><table><thead><tr><th>Due</th><th>Order</th><th>Item</th><th class='r'>Qty</th><th>Writing / note</th></tr></thead>"
        f"<tbody>{order_rows}</tbody></table>"
        "<script>window.onload=()=>window.print()</script></body></html>"
    )
    return HTMLResponse(page)


@router.post("/orders/{order_id}/collect")
async def bakery_order_collect(
    order_id: UuidIdValue,
    payload: CollectBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    bag_owner = _driver_id(claims) or await svc.driving_this(db, claims["tenant_id"], order_id, claims.get("sub"))
    _job(claims, "deliver" if bag_owner else "orders")
    row = await svc.collect_order(
        db, claims["tenant_id"], order_id, payment_method=payload.payment_method, user_id=claims.get("sub"),
        driver_id=bag_owner,
    )
    await db.commit()
    return _env(await svc.present_order(db, row), "Delivered" if row.delivery else "Order collected")


@router.get("/drivers")
async def bakery_drivers(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "orders")
    return _env(await svc.list_drivers(db, claims["tenant_id"]))


@router.get("/deliveries")
async def bakery_deliveries(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    if not _driver_id(claims):
        _job(claims, "orders")
    rows = await svc.list_deliveries(db, claims["tenant_id"], driver_id=_driver_id(claims))
    return _env([await svc.present_order(db, row) for row in rows])


@router.post("/orders/{order_id}/driver")
async def bakery_assign_driver(
    order_id: UuidIdValue,
    payload: DriverBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "orders")
    row = await svc.assign_driver(db, claims["tenant_id"], order_id, driver_id=payload.driver_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_order(db, row), "Driver set")


@router.post("/orders/{order_id}/pick-up")
async def bakery_pick_up(
    order_id: UuidIdValue, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "deliver")
    if not _can_drive(claims):
        raise HTTPException(status_code=403, detail="Only a driver or manager picks up deliveries")
    row = await svc.pick_up(
        db, claims["tenant_id"], order_id, driver_id=claims["sub"],
        takeover=str(claims.get("role") or "") in svc.SELF_COUNT_ROLES,
    )
    await db.commit()
    return _env(await svc.present_order(db, row), "Picked up")


@router.post("/orders/{order_id}/delivery-failed")
async def bakery_delivery_failed(
    order_id: UuidIdValue,
    payload: FailedBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "deliver")
    if not _can_drive(claims):
        raise HTTPException(status_code=403, detail="Only the person driving can mark a delivery failed")
    row = await svc.delivery_failed(db, claims["tenant_id"], order_id, driver_id=claims["sub"], reason=payload.reason)
    await db.commit()
    return _env(await svc.present_order(db, row), "Brought back to the shop")


@router.get("/driver/today")
async def bakery_driver_today(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    if not _can_drive(claims):
        raise HTTPException(status_code=403, detail="This page is for people who drive")
    return _env(await svc.driver_today(db, claims["tenant_id"], driver_id=claims["sub"]))


@router.post("/driver/bag")
async def bakery_bag_open(
    payload: BagOpen, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    if not _can_drive(claims):
        raise HTTPException(status_code=403, detail="Only a driver or manager starts a cash bag")
    row = await svc.open_bag(db, claims["tenant_id"], driver_id=claims["sub"], opening_cash=payload.opening_cash)
    await db.commit()
    return _env(await svc.present_shift(db, claims["tenant_id"], row), "Cash bag started")


@router.post("/driver/bags/{bag_id}/hand-in")
async def bakery_bag_hand_in(
    bag_id: UuidIdValue,
    payload: HandIn,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "till")
    data = await svc.hand_in(
        db, claims["tenant_id"], bag_id, counted_cash=payload.counted_cash, user_id=claims.get("sub"),
        role=str(claims.get("role") or ""),
    )
    await db.commit()
    return _env(data, "Cash handed in")


@router.post("/orders/{order_id}/cancel")
async def bakery_order_cancel(
    order_id: UuidIdValue,
    payload: CancelBody,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "correct")
    row = await svc.cancel_order(
        db,
        claims["tenant_id"],
        order_id,
        deposit_action=payload.deposit_action,
        reason=payload.reason,
        user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await svc.present_order(db, row), "Order cancelled")


class StockBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)]
    kind: Literal["item", "ingredient"]
    price: NonNegativeMoneyValue | None = None
    cost_price: NonNegativeMoneyValue | None = None
    reorder_level: Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)] | None = None


class StockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: NonNegativeMoneyValue | None = None
    cost_price: NonNegativeMoneyValue | None = None
    reorder_level: Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)] | None = None
    is_active: bool | None = None


class ReceiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    unit_cost: NonNegativeMoneyValue
    paid_with: Literal["cash", "card", "mobile_money", "bank_transfer", "credit"]
    supplier: Annotated[str, Field(min_length=1, max_length=180)] | None = None
    supplier_id: UuidIdValue | None = None
    bill_number: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    # Quantity and cost are per purchase unit (a 50 kg bag), turned into the stock unit.
    in_purchase_units: bool = False
    # VAT on the supplier's bill, on top of quantity x unit cost. Claimable input tax.
    tax: NonNegativeMoneyValue | None = None


class CountLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    counted_qty: Annotated[float, Field(ge=0, le=10000000, allow_inf_nan=False)]


class CountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[CountLine] = Field(min_length=1, max_length=500)
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class ExpenseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["rent", "wages", "utilities", "gas", "transport", "repairs", "packaging", "marketing", "other"]
    description: Annotated[str, Field(min_length=2, max_length=255)]
    amount: Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)]
    paid_with: Literal["cash", "card", "mobile_money", "bank_transfer"]
    spent_on: date
    from_till: bool = False
    # VAT inside the amount paid, when the bill shows it. Claimable input tax.
    tax: NonNegativeMoneyValue | None = None


@router.get("/stock")
async def bakery_stock(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    rows = await svc.list_stock(db, claims["tenant_id"])
    if not _sees_money(claims):
        for row in rows:
            for key in ("cost_price", "value"):
                row.pop(key, None)
    return _env({"items": rows, "receipts": await svc.list_receipts(db, claims["tenant_id"]) if _sees_money(claims) else []})


@router.post("/stock")
async def bakery_stock_create(
    payload: StockBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "correct")
    row = await svc.save_stock_item(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Saved")


@router.patch("/stock/{product_id}")
async def bakery_stock_update(
    product_id: UuidIdValue,
    payload: StockUpdate,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "correct")
    row = await svc.save_stock_item(db, claims["tenant_id"], payload, user_id=claims.get("sub"), product_id=product_id)
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Saved")


@router.post("/stock/receive")
async def bakery_stock_receive(
    payload: ReceiveBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "correct")
    row = await svc.receive_stock(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "receipt_number": row.receipt_number, "total": svc._money(row.total)}, "Stock received")


@router.get("/stock/counts")
async def bakery_stock_counts(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "correct")
    return _env(await svc.list_counts(db, claims["tenant_id"]))


@router.post("/stock/count")
async def bakery_stock_count(
    payload: CountBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "correct")
    row = await svc.count_stock(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(
        {"id": row.id, "count_number": row.count_number, "value_change": svc._money(row.value_change)},
        "Stock count saved",
    )


@router.get("/expenses")
async def bakery_expenses(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    _job(claims, "correct")
    return _env(
        {
            "kinds": [{"id": k, "label": v} for k, v in svc.EXPENSE_KINDS.items()],
            "rows": [svc.serialize_expense(r) for r in await svc.list_expenses(db, claims["tenant_id"])],
        }
    )


@router.post("/expenses")
async def bakery_expense_create(
    payload: ExpenseBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    _job(claims, "correct")
    row = await svc.record_expense(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_expense(row), "Expense recorded")


@router.get("/reports/full")
async def bakery_full_report(
    start_date: date | None = None,
    end_date: date | None = None,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "correct")
    end = end_date or await svc.bakery_today(db, claims["tenant_id"])
    start = start_date or end - timedelta(days=6)
    return _env(await svc.full_report(db, claims["tenant_id"], start=start, end=end))


@router.get("/reports")
async def bakery_reports(
    start_date: IsoDateQueryValue | None = None,
    end_date: IsoDateQueryValue | None = None,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    _job(claims, "correct")
    end = date.fromisoformat(str(end_date)[:10]) if end_date else await svc.bakery_today(db, claims["tenant_id"])
    start = date.fromisoformat(str(start_date)[:10]) if start_date else end - timedelta(days=6)
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    return _env(await svc.period_numbers(db, claims["tenant_id"], start=start, end=end))


# --- Item details: shelf life, day-old price, allergens, labels, units, shelf level ----------


class ItemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shelf_life_days: Annotated[int, Field(ge=1, le=365)] | None = None
    day_old_discount_pct: Annotated[float, Field(gt=0, le=90, allow_inf_nan=False)] | None = None
    allergens: list[Annotated[str, Field(min_length=2, max_length=20)]] | None = Field(default=None, max_length=14)
    ingredients_text: Annotated[str, Field(min_length=2, max_length=2000)] | None = None
    net_weight: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    storage_note: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    stock_unit: Literal["kg", "g", "l", "ml", "each"] | None = None
    purchase_unit: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    units_per_purchase: Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)] | None = None
    par_level: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)] | None = None


@router.get("/allergens")
async def bakery_allergens(claims=Depends(require_permission("bakery", "read"))):
    from app import bakery_items as items_svc

    return _env([{"id": k, "label": v} for k, v in items_svc.ALLERGENS.items()])


@router.get("/items/{product_id}/details")
async def bakery_item_details(product_id: UuidIdValue, claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    from app import bakery_items as items_svc

    product = await svc._product(db, claims["tenant_id"], product_id)
    body = items_svc.present(await items_svc.settings_for(db, claims["tenant_id"], product.id))
    body["label"] = await items_svc.label_facts(db, claims["tenant_id"], product)
    return _env(body)


@router.put("/items/{product_id}/details")
async def bakery_item_details_save(
    product_id: UuidIdValue,
    payload: ItemDetails,
    claims=Depends(require_permission("bakery", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app import bakery_items as items_svc

    _job(claims, "correct")
    row = await items_svc.save(db, claims["tenant_id"], product_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(items_svc.present(row), "Saved")


@router.get("/shelf")
async def bakery_shelf(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    """What is on the shelf by bake: fresh, day-old, last day or past its date."""
    from app import bakery_items as items_svc

    tenant = claims["tenant_id"]
    return _env(await items_svc.shelf(db, tenant, today=await svc.bakery_today(db, tenant), local=await svc._localiser(db, tenant)))


@router.get("/items/{product_id}/label", response_class=HTMLResponse)
async def bakery_label(
    product_id: UuidIdValue,
    batch_id: UuidIdValue | None = None,
    copies: Annotated[int, Query(ge=1, le=60)] = 1,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    """A printable label: ingredients largest first with allergen ingredients in bold, the
    allergen list, best before, batch, weight and price."""
    from app import bakery_items as items_svc

    _job(claims, "labels")
    tenant = claims["tenant_id"]
    page = await items_svc.label_html(
        db, tenant, product_id, batch_id=batch_id, copies=copies, today=await svc.bakery_today(db, tenant)
    )
    return HTMLResponse(page)


# --- Trade customers ---------------------------------------------------------------------


class CustomerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PartyNameValue | None = None
    phone: E164PhoneValue | None = None
    address: Annotated[str, Field(min_length=2, max_length=500)] | None = None
    credit_limit: NonNegativeMoneyValue | None = None
    trade_discount_pct: Annotated[float, Field(ge=0, le=60, allow_inf_nan=False)] | None = None
    terms_days: Annotated[int, Field(ge=0, le=120)] | None = None
    is_active: bool | None = None


class StandingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    days: Annotated[str, Field(pattern=r"^[01]{7}$")] = "1111111"


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty


class InvoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UuidIdValue
    lines: list[InvoiceLine] = Field(min_length=1, max_length=60)
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    # A manager may let one invoice go past the customer's credit limit.
    override_limit: bool = False


class VoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    restock: bool = False


class MoneyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)]
    method: Literal["cash", "card", "mobile_money", "bank_transfer"]
    reference: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    # Supplier payments only: cash taken out of the open till.
    from_till: bool = False


async def _today(db, claims) -> date:
    return await svc.bakery_today(db, claims["tenant_id"])


@router.get("/trade/customers")
async def trade_customers(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "trade")
    return _env(await trade.list_customers(db, claims["tenant_id"], today=await _today(db, claims)))


@router.post("/trade/customers")
async def trade_customer_create(payload: CustomerBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "correct")
    row = await trade.save_customer(db, claims["tenant_id"], payload)
    await db.commit()
    return _env(await trade.present_customer(db, claims["tenant_id"], row, today=await _today(db, claims)), "Customer added")


@router.patch("/trade/customers/{customer_id}")
async def trade_customer_update(
    customer_id: UuidIdValue, payload: CustomerBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "correct")
    row = await trade.save_customer(db, claims["tenant_id"], payload, customer_id=customer_id)
    await db.commit()
    return _env(await trade.present_customer(db, claims["tenant_id"], row, today=await _today(db, claims)), "Saved")


@router.put("/trade/customers/{customer_id}/standing")
async def trade_standing_save(
    customer_id: UuidIdValue, payload: StandingBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "correct")
    await trade.save_standing(db, claims["tenant_id"], customer_id, payload)
    await db.commit()
    row = await trade._customer(db, claims["tenant_id"], customer_id)
    return _env(await trade.present_customer(db, claims["tenant_id"], row, today=await _today(db, claims)), "Standing order saved")


@router.delete("/trade/standing/{standing_id}")
async def trade_standing_stop(standing_id: UuidIdValue, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "correct")
    await trade.stop_standing(db, claims["tenant_id"], standing_id)
    await db.commit()
    return _env(True, "Standing order stopped")


@router.post("/trade/run")
async def trade_run(claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)):
    """Make today's trade deliveries from standing orders."""
    from app import bakery_trade as trade

    _job(claims, "trade")
    body = await trade.run_standing(
        db, claims["tenant_id"], day=await _today(db, claims), user_id=claims.get("sub"), role=str(claims.get("role") or "")
    )
    await db.commit()
    return _env(body, f"{len(body['made'])} delivery invoice(s) made")


@router.get("/trade/invoices")
async def trade_invoices(
    customer_id: UuidIdValue | None = None,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bakery_trade as trade

    _job(claims, "trade")
    return _env(await trade.list_invoices(db, claims["tenant_id"], today=await _today(db, claims), customer_id=customer_id))


@router.post("/trade/invoices")
async def trade_invoice_create(payload: InvoiceBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "trade")
    row = await trade.create_invoice(
        db, claims["tenant_id"], payload.customer_id, payload.lines, user_id=claims.get("sub"),
        role=str(claims.get("role") or ""), notes=payload.notes, override_limit=payload.override_limit,
    )
    await db.commit()
    return _env(await trade.present_invoice(db, row, today=await _today(db, claims)), "Invoice made")


@router.post("/trade/invoices/{invoice_id}/void")
async def trade_invoice_void(
    invoice_id: UuidIdValue, payload: VoidBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "correct")
    row = await trade.void_invoice(db, claims["tenant_id"], invoice_id, reason=payload.reason, restock=payload.restock, user_id=claims.get("sub"))
    await db.commit()
    return _env(await trade.present_invoice(db, row, today=await _today(db, claims)), "Invoice voided")


@router.get("/trade/invoices/{invoice_id}/print", response_class=HTMLResponse)
async def trade_invoice_print(invoice_id: UuidIdValue, claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    import html as h

    from app import bakery_trade as trade
    from app import models as m

    _job(claims, "trade")
    row = await db.get(m.BakeryInvoice, invoice_id)
    if row is None or row.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="Invoice not found")
    customer = await db.get(m.BakeryCustomer, row.customer_id)
    company = await db.get(m.Tenant, claims["tenant_id"])
    inv = await trade.present_invoice(db, row, today=await _today(db, claims), customer_name=customer.name if customer else None)
    lines = "".join(
        f"<tr><td>{h.escape(i['name'])}</td><td style='text-align:right'>{i['quantity']:g}</td>"
        f"<td style='text-align:right'>{i['unit_price']:.2f}</td><td style='text-align:right'>{i['tax']:.2f}</td>"
        f"<td style='text-align:right'>{i['line_total']:.2f}</td></tr>"
        for i in inv["items"]
    )
    page = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Invoice</title><style>"
        "body{font-family:Arial,sans-serif;max-width:720px;margin:24px auto;color:#10211B}table{width:100%;border-collapse:collapse}"
        "th,td{padding:6px;border-bottom:1px solid #D4E5C4}th{text-align:left;background:#F2F7EC}.r{text-align:right}</style></head><body>"
        f"<h2>{h.escape(getattr(company, 'company_name', '') or '')}</h2>"
        f"<p>{h.escape(getattr(company, 'address', '') or '')}<br/>TIN {h.escape(getattr(company, 'tax_registration_number', '') or '-')}</p>"
        f"<h3>Invoice {h.escape(inv['invoice_number'])}{' (VOID)' if inv['status'] == 'void' else ''}</h3>"
        f"<p>To: <b>{h.escape(inv['customer_name'] or '')}</b><br/>{h.escape((customer.address if customer else '') or '')}</p>"
        f"<p>Date {inv['invoice_date']} · Pay by {inv['due_date']}</p>"
        "<table><thead><tr><th>Item</th><th class='r'>Qty</th><th class='r'>Price</th><th class='r'>VAT</th><th class='r'>Amount</th></tr></thead>"
        f"<tbody>{lines}</tbody></table>"
        f"<p class='r'>Before VAT {inv['subtotal']:.2f}<br/>VAT {inv['tax']:.2f}<br/><b>Total {inv['total']:.2f}</b><br/>"
        f"Paid {inv['paid']:.2f}<br/><b>To pay {inv['balance']:.2f}</b></p>"
        "<script>window.onload=()=>window.print()</script></body></html>"
    )
    return HTMLResponse(page)


@router.post("/trade/customers/{customer_id}/payments")
async def trade_payment(
    customer_id: UuidIdValue, payload: MoneyIn, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "trade")
    row = await trade.record_payment(db, claims["tenant_id"], customer_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "payment_number": row.payment_number, "amount": svc._money(row.amount)}, "Payment recorded")


@router.get("/trade/customers/{customer_id}/statement")
async def trade_statement(
    customer_id: UuidIdValue,
    start_date: date | None = None,
    end_date: date | None = None,
    claims=Depends(require_permission("bakery", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app import bakery_trade as trade

    _job(claims, "trade")
    today = await _today(db, claims)
    end = end_date or today
    start = start_date or end.replace(day=1)
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    return _env(await trade.statement(db, claims["tenant_id"], customer_id, start=start, end=end, today=today))


# --- Suppliers ---------------------------------------------------------------------------


class SupplierBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PartyNameValue | None = None
    phone: E164PhoneValue | None = None
    terms_days: Annotated[int, Field(ge=0, le=120)] | None = None
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    is_active: bool | None = None


@router.get("/suppliers")
async def bakery_suppliers(claims=Depends(require_permission("bakery", "read")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "correct")
    return _env(await trade.list_suppliers(db, claims["tenant_id"]))


@router.post("/suppliers")
async def bakery_supplier_create(payload: SupplierBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)):
    from app import bakery_trade as trade

    _job(claims, "correct")
    if not payload.name:
        raise HTTPException(status_code=422, detail="Enter the supplier's name")
    row = await trade.save_supplier(db, claims["tenant_id"], payload)
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Supplier saved")


@router.patch("/suppliers/{supplier_id}")
async def bakery_supplier_update(
    supplier_id: UuidIdValue, payload: SupplierBody, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "correct")
    row = await trade.save_supplier(db, claims["tenant_id"], payload, supplier_id=supplier_id)
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Saved")


@router.post("/suppliers/{supplier_id}/payments")
async def bakery_supplier_pay(
    supplier_id: UuidIdValue, payload: MoneyIn, claims=Depends(require_permission("bakery", "write")), db: AsyncSession = Depends(get_db)
):
    from app import bakery_trade as trade

    _job(claims, "correct")
    row = await trade.pay_supplier(db, claims["tenant_id"], supplier_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "payment_number": row.payment_number, "amount": svc._money(row.amount)}, "Supplier paid")
