"""Bakery routes. The `bakery` permission and the industry gate come from require_permission.

Each bakery role does one job, checked here on top of the module grant:
bakers bake and record waste, cashiers run the counter, and money corrections need a manager.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import bakery as svc
from app.db import get_db
from app.schemas import E164PhoneValue, IsoDateQueryValue, NonNegativeMoneyValue, PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/bakery", tags=["bakery"])

_JOBS = {
    "bakery_baker": frozenset({"bake", "waste"}),
    "bakery_cashier": frozenset({"till", "orders", "waste"}),
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


class ShiftClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class SaleLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty


class SaleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: Literal["cash", "card", "mobile_money", "wallet"] = "cash"
    customer_name: PartyNameValue | None = None
    lines: list[SaleLine] = Field(min_length=1, max_length=60)
    # A manager who is out driving sells from the van into their own cash bag.
    from_bag: bool = False


class RefundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    restock: bool = False


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
    row = await svc.open_shift(db, claims["tenant_id"], opening_cash=payload.opening_cash, user_id=claims.get("sub"))
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
    row = await svc.create_sale(db, claims["tenant_id"], payload, user_id=claims.get("sub"), driver_id=bag_owner)
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
        db, claims["tenant_id"], sale_id, reason=payload.reason, restock=payload.restock, user_id=claims.get("sub")
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
    return _env(await svc.present_order(db, row), "Order ready")


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


class ExpenseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["rent", "wages", "utilities", "gas", "transport", "repairs", "packaging", "marketing", "other"]
    description: Annotated[str, Field(min_length=2, max_length=255)]
    amount: Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)]
    paid_with: Literal["cash", "card", "mobile_money", "bank_transfer"]
    spent_on: date
    from_till: bool = False


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
    end = end_date or date.today()
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
    end = date.fromisoformat(str(end_date)[:10]) if end_date else date.today()
    start = date.fromisoformat(str(start_date)[:10]) if start_date else end - timedelta(days=6)
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    return _env(await svc.period_numbers(db, claims["tenant_id"], start=start, end=end))
