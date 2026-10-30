"""Restaurant HTTP routes. Permission and industry gates stay in require_permission."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import restaurant as restaurant_svc
from app import restaurant_till as till_svc
from app.db import get_db
from app.honesty import money_json
from app.schemas import AddressValue, E164PhoneValue, NonNegativeMoneyValue, PositiveMoneyValue, PartyNameValue, PositiveQtyValue, StockOutNotesValue, UuidIdValue, WebsiteHostnameValue
from app.security import require_permission

router = APIRouter(prefix="/restaurant", tags=["restaurant"])


def _allergy_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not re.search(r"[A-Za-z0-9]", text)
    ):
        raise ValueError("Allergy must be a plain note.")
    return text


AllergyValue = Annotated[str, BeforeValidator(_allergy_value)]


def _spice_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"mild", "medium", "hot"}:
        raise ValueError("Spice must be mild, medium, or hot.")
    return text


SpiceValue = Annotated[str, BeforeValidator(_spice_value)]


def _doneness_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"rare", "medium", "well"}:
        raise ValueError("Doneness must be rare, medium, or well.")
    return text


DonenessValue = Annotated[str, BeforeValidator(_doneness_value)]


def _occasion_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not re.search(r"[A-Za-z0-9]", text)
    ):
        raise ValueError("Occasion must be a plain note.")
    return text


OccasionValue = Annotated[str, BeforeValidator(_occasion_value)]


def _item_note_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not re.search(r"[A-Za-z0-9]", text)
    ):
        raise ValueError("Item note must be a plain note.")
    return text


ItemNoteValue = Annotated[str, BeforeValidator(_item_note_value)]


def _ready_by_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        raise ValueError("Ready by must be a clock time.")
    return text


ReadyByValue = Annotated[str, BeforeValidator(_ready_by_value)]


def _fire_at_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        raise ValueError("Fire at must be a clock time.")
    return text


FireAtValue = Annotated[str, BeforeValidator(_fire_at_value)]


def _turn_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Turn must be 1 hour, 90 minutes, or 2 hours.")
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Turn must be 1 hour, 90 minutes, or 2 hours.") from None
    if number not in {60, 90, 120}:
        raise ValueError("Turn must be 1 hour, 90 minutes, or 2 hours.")
    return number


TurnValue = Annotated[int, BeforeValidator(_turn_value)]


def _packaging_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"bag", "box"}:
        raise ValueError("Packaging must be a bag or a box.")
    return text


PackagingValue = Annotated[str, BeforeValidator(_packaging_value)]


def _diet_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"vegetarian", "vegan", "halal"}:
        raise ValueError("Diet must be vegetarian, vegan, or halal.")
    return text


DietValue = Annotated[str, BeforeValidator(_diet_value)]


def _allergen_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"nuts", "gluten", "dairy", "shellfish"}:
        raise ValueError("Allergen must be nuts, gluten, dairy, or shellfish.")
    return text


AllergenValue = Annotated[str, BeforeValidator(_allergen_value)]


def _handoff_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"hand", "door"}:
        raise ValueError("Handoff must be hand to the guest or leave at the door.")
    return text


HandoffValue = Annotated[str, BeforeValidator(_handoff_value)]


def _receipt_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"print", "email", "declined"}:
        raise ValueError("Receipt must be print, email, or declined.")
    return text


ReceiptValue = Annotated[str, BeforeValidator(_receipt_value)]


def _guest_source_value(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text not in {"walk_in", "phone", "booking"}:
        raise ValueError("Source must be walk-in, phone, or booking.")
    return text


GuestSourceValue = Annotated[str, BeforeValidator(_guest_source_value)]


def _vehicle_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not re.search(r"[A-Za-z0-9]", text)
    ):
        raise ValueError("Vehicle must be a plain note.")
    return text


VehicleValue = Annotated[str, BeforeValidator(_vehicle_value)]


def _room_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Room must be dining, patio, or private.")
    text = str(value).strip().lower()
    if text not in {"dining", "patio", "private"}:
        raise ValueError("Room must be dining, patio, or private.")
    return text


RoomValue = Annotated[str, BeforeValidator(_room_value)]


def _cook_time_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Cook time must be from 1 to 180 minutes.")
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Cook time must be from 1 to 180 minutes.")
    if minutes < 1 or minutes > 180:
        raise ValueError("Cook time must be from 1 to 180 minutes.")
    return minutes


CookTimeValue = Annotated[int, BeforeValidator(_cook_time_value)]


def _servings_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Servings must be from 1 to 40.")
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Servings must be from 1 to 40.")
    if count < 1 or count > 40:
        raise ValueError("Servings must be from 1 to 40.")
    return count


ServingsValue = Annotated[int, BeforeValidator(_servings_value)]


class TableBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    seats: int = 2
    store_id: str | None = None
    room: RoomValue | None = None


class TableUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    seats: int | None = None
    store_id: UuidIdValue | None = None
    room: RoomValue | None = None


class ModifierGroupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class ModifierGroupUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)


class ModifierBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    price: Decimal = Decimal("0")


class ModifierUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    price: NonNegativeMoneyValue | None = None


class RecipeLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    quantity: Decimal


class RecipeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str = Field(min_length=1, max_length=160)
    lines: list[RecipeLineBody] = Field(default_factory=list)
    cook_time: CookTimeValue | None = None
    servings: ServingsValue | None = None


class RecipeUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    lines: list[RecipeLineBody] | None = None
    cook_time: CookTimeValue | None = None
    servings: ServingsValue | None = None


class OrderLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    quantity: Decimal
    unit_price: Decimal | None = None
    modifier_ids: list[str] = Field(default_factory=list)
    course: Literal["starter", "main", "dessert", "drink"] | None = None
    note: ItemNoteValue | None = None
    hold: bool | None = None
    seat: int | None = Field(default=None, ge=1, le=40)
    spice: SpiceValue | None = None
    doneness: DonenessValue | None = None


class OrderLineCourseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    course: Literal["starter", "main", "dessert", "drink"]


class OrderLineNoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    note: ItemNoteValue | None


class OrderLineHoldBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    hold: bool


class OrderLineSeatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    seat: int | None = Field(ge=1, le=40)


class OrderLineSpiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    spice: SpiceValue | None


class OrderLineDonenessBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    doneness: DonenessValue | None


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_mode: str
    payment_method: str = "cash"
    store_id: str | None = None
    table_id: str | None = None
    customer_name: str | None = None
    delivery_address: AddressValue | None = None
    delivery_zone: str | None = None
    notes: str | None = None
    covers: int | None = Field(default=None, ge=1, le=40)
    allergy: AllergyValue | None = None
    allergen: AllergenValue | None = None
    occasion: OccasionValue | None = None
    phone: E164PhoneValue | None = None
    pager: int | None = Field(default=None, ge=1, le=999)
    ready_by: ReadyByValue | None = None
    quoted_wait: int | None = Field(default=None, ge=5, le=180)
    fire_at: FireAtValue | None = None
    packaging: PackagingValue | None = None
    rush: bool | None = None
    bill_asked: bool | None = None
    guest_arrived: bool | None = None
    cutlery: bool | None = None
    high_chair: bool | None = None
    diet: DietValue | None = None
    guest_source: GuestSourceValue | None = None
    vehicle: VehicleValue | None = None
    bay: int | None = Field(default=None, ge=1, le=40)
    handoff: HandoffValue | None = None
    guest_email: EmailStr | None = None
    receipt: ReceiptValue | None = None
    lines: list[OrderLineBody]


class OrderLineModifiersBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    modifier_ids: list[UuidIdValue] = Field(default_factory=list)


class OrderLineQuantityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    quantity: PositiveQtyValue


class OrderLinePriceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    unit_price: NonNegativeMoneyValue


class OrderLineStationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    station: Literal["kitchen", "bar"]


class OrderUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str | None = None
    store_id: UuidIdValue | None = None
    notes: str | None = None
    delivery_address: AddressValue | None = None
    delivery_zone: str | None = None
    covers: int | None = Field(default=None, ge=1, le=40)
    allergy: AllergyValue | None = None
    allergen: AllergenValue | None = None
    occasion: OccasionValue | None = None
    phone: E164PhoneValue | None = None
    pager: int | None = Field(default=None, ge=1, le=999)
    ready_by: ReadyByValue | None = None
    quoted_wait: int | None = Field(default=None, ge=5, le=180)
    fire_at: FireAtValue | None = None
    packaging: PackagingValue | None = None
    rush: bool | None = None
    bill_asked: bool | None = None
    guest_arrived: bool | None = None
    cutlery: bool | None = None
    high_chair: bool | None = None
    diet: DietValue | None = None
    guest_source: GuestSourceValue | None = None
    vehicle: VehicleValue | None = None
    bay: int | None = Field(default=None, ge=1, le=40)
    handoff: HandoffValue | None = None
    guest_email: EmailStr | None = None
    receipt: ReceiptValue | None = None
    payment_method: Literal["cash", "card", "wallet", "mobile_money"] | None = None
    service_mode: Literal["dine_in", "takeaway", "delivery"] | None = None
    table_id: UuidIdValue | None = None
    lines: list[OrderLineBody] = Field(default_factory=list)
    remove_line_ids: list[UuidIdValue] = Field(default_factory=list)
    line_quantities: list[OrderLineQuantityBody] = Field(default_factory=list)
    line_prices: list[OrderLinePriceBody] = Field(default_factory=list)
    line_stations: list[OrderLineStationBody] = Field(default_factory=list)
    line_courses: list[OrderLineCourseBody] = Field(default_factory=list)
    line_notes: list[OrderLineNoteBody] = Field(default_factory=list)
    line_holds: list[OrderLineHoldBody] = Field(default_factory=list)
    line_seats: list[OrderLineSeatBody] = Field(default_factory=list)
    line_spices: list[OrderLineSpiceBody] = Field(default_factory=list)
    line_doneness: list[OrderLineDonenessBody] = Field(default_factory=list)
    line_modifiers: list[OrderLineModifiersBody] = Field(default_factory=list)


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


@router.get("/summary")
async def restaurant_summary(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.summary(db, claims["tenant_id"], user_id=claims.get("sub")))


@router.get("/tables")
async def restaurant_tables(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_tables(db, claims["tenant_id"], user_id=claims.get("sub"))
    rooms = await restaurant_svc.table_rooms(db, claims["tenant_id"])
    return _env([restaurant_svc.serialize_table(row, room=rooms.get(row.id)) for row in rows])


@router.post("/tables")
async def restaurant_create_table(
    payload: TableBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_table(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    rooms = await restaurant_svc.table_rooms(db, claims["tenant_id"])
    return _env(restaurant_svc.serialize_table(row, room=rooms.get(row.id)), "Table saved")


class TableHoldBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/tables/{table_id}/hold")
async def restaurant_hold_table(
    table_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.hold_table(
        db, claims["tenant_id"], table_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(restaurant_svc.serialize_table(row), "Table held")


@router.post("/tables/{table_id}/release")
async def restaurant_release_table(
    table_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.release_table(
        db, claims["tenant_id"], table_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(restaurant_svc.serialize_table(row), "Table released")


@router.patch("/tables/{table_id}")
async def restaurant_update_table(
    table_id: UuidIdValue,
    payload: TableUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_table(
        db, claims["tenant_id"], table_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    rooms = await restaurant_svc.table_rooms(db, claims["tenant_id"])
    return _env(restaurant_svc.serialize_table(row, room=rooms.get(row.id)), "Table saved")


@router.post("/tables/{table_id}/retire")
async def restaurant_retire_table(
    table_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.retire_table(
        db, claims["tenant_id"], table_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(restaurant_svc.serialize_table(row), "Table retired")


@router.get("/modifiers")
async def restaurant_modifiers(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_modifier_groups(db, claims["tenant_id"]))


@router.post("/modifier-groups")
async def restaurant_modifier_group(
    payload: ModifierGroupBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_modifier_group(db, claims["tenant_id"], payload.name)
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Modifier group saved")


@router.patch("/modifier-groups/{group_id}")
async def restaurant_update_modifier_group(
    group_id: UuidIdValue,
    payload: ModifierGroupUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_modifier_group(
        db, claims["tenant_id"], group_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Extra group saved")


@router.post("/modifier-groups/{group_id}/retire")
async def restaurant_retire_modifier_group(
    group_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.retire_modifier_group(
        db, claims["tenant_id"], group_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "is_active": row.is_active}, "Extra group retired")


@router.post("/modifier-groups/{group_id}/modifiers")
async def restaurant_modifier(
    group_id: str,
    payload: ModifierBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.add_modifier(
        db, claims["tenant_id"], group_id, name=payload.name, price=payload.price
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "price": float(row.price or 0)}, "Modifier saved")


@router.patch("/modifiers/{modifier_id}")
async def restaurant_update_modifier(
    modifier_id: UuidIdValue,
    payload: ModifierUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_modifier(
        db, claims["tenant_id"], modifier_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "price": money_json(row.price or 0)}, "Extra saved")


@router.post("/modifiers/{modifier_id}/retire")
async def restaurant_retire_modifier(
    modifier_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.retire_modifier(
        db, claims["tenant_id"], modifier_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "is_active": row.is_active}, "Extra retired")


@router.get("/recipes")
async def restaurant_recipes(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_recipes(db, claims["tenant_id"]))


@router.post("/recipes")
async def restaurant_recipe(
    payload: RecipeBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_recipe(db, claims["tenant_id"], payload)
    await db.commit()
    listed = await restaurant_svc.list_recipes(db, claims["tenant_id"])
    saved = next((item for item in listed if item["id"] == row.id), None)
    return _env(
        {
            "id": row.id,
            "product_id": row.product_id,
            "name": row.name,
            "cook_time": None if saved is None else saved.get("cook_time"),
            "servings": None if saved is None else saved.get("servings"),
        },
        "Recipe saved",
    )


@router.patch("/recipes/{recipe_id}")
async def restaurant_update_recipe(
    recipe_id: UuidIdValue,
    payload: RecipeUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_recipe(
        db, claims["tenant_id"], recipe_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    listed = await restaurant_svc.list_recipes(db, claims["tenant_id"])
    saved = next((item for item in listed if item["id"] == row.id), None)
    return _env(
        {
            "id": row.id,
            "product_id": row.product_id,
            "name": row.name,
            "cook_time": None if saved is None else saved.get("cook_time"),
            "servings": None if saved is None else saved.get("servings"),
        },
        "Recipe saved",
    )


@router.post("/recipes/{recipe_id}/retire")
async def restaurant_retire_recipe(
    recipe_id: UuidIdValue,
    payload: TableHoldBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.retire_recipe(
        db, claims["tenant_id"], recipe_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "is_active": row.is_active}, "Recipe retired")


class DeliveryZonesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(default_factory=list, max_length=20)


@router.get("/delivery-zones")
async def restaurant_delivery_zones(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_delivery_zones(db, claims["tenant_id"]))


@router.put("/delivery-zones")
async def restaurant_save_delivery_zones(
    payload: DeliveryZonesBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    names = await restaurant_svc.replace_delivery_zones(db, claims["tenant_id"], payload.names)
    await db.commit()
    return _env(names, "Delivery zones saved")


@router.get("/orders")
async def restaurant_orders(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_orders(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env(await restaurant_svc.present_orders(db, claims["tenant_id"], rows))


@router.post("/orders")
async def restaurant_create_order(
    payload: OrderBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_order(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order saved")


@router.patch("/orders/{order_id}")
async def restaurant_update_order(
    order_id: UuidIdValue,
    payload: OrderUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_order(
        db, claims["tenant_id"], order_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order saved")


@router.post("/orders/{order_id}/send")
async def restaurant_send(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.send_to_kitchen(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Sent to kitchen")


@router.post("/orders/{order_id}/complete")
async def restaurant_complete(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.complete_order(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order completed")


@router.post("/orders/{order_id}/cancel")
async def restaurant_cancel(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.cancel_order(
        db, claims["tenant_id"], order_id, user_id=claims.get("sub"), void=False
    )
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order cancelled")


@router.post("/orders/{order_id}/void")
async def restaurant_void(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.cancel_order(
        db, claims["tenant_id"], order_id, user_id=claims.get("sub"), void=True
    )
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order voided")


@router.post("/orders/{order_id}/refund")
async def restaurant_refund(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.refund_order(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order refunded")


class TillShiftOpenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_cash: NonNegativeMoneyValue = 0
    store_id: UuidIdValue | None = None


class TillCashMoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movement_type: Literal["cash_in", "cash_out"]
    amount: PositiveMoneyValue
    reason: Annotated[str, Field(min_length=3, max_length=200)]


class TillShiftCloseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue
    notes: Annotated[str, Field(max_length=500)] | None = None


@router.get("/till/shift")
async def restaurant_till_current_shift(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await till_svc.open_shift_for_user(db, claims["tenant_id"], claims.get("sub"))
    return _env(await till_svc.present_shift(db, row, with_moves=True) if row else None)


@router.post("/till/shift/open")
async def restaurant_till_open_shift(
    payload: TillShiftOpenBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await till_svc.open_shift(
        db, claims["tenant_id"], user_id=claims["sub"],
        opening_cash=payload.opening_cash, store_id=payload.store_id,
    )
    await db.commit()
    return _env(await till_svc.present_shift(db, row, with_moves=True), "Shift opened")


@router.post("/till/shift/{shift_id}/cash")
async def restaurant_till_cash_move(
    shift_id: UuidIdValue,
    payload: TillCashMoveBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    await till_svc.move_cash(
        db, claims["tenant_id"], shift_id, user_id=claims["sub"],
        movement_type=payload.movement_type, amount=payload.amount, reason=payload.reason,
    )
    await db.commit()
    row = await till_svc._shift(db, claims["tenant_id"], shift_id)
    return _env(await till_svc.present_shift(db, row, with_moves=True), "Cash recorded")


@router.post("/till/shift/{shift_id}/close")
async def restaurant_till_close_shift(
    shift_id: UuidIdValue,
    payload: TillShiftCloseBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await till_svc.close_shift(
        db, claims["tenant_id"], shift_id, user_id=claims["sub"],
        counted_cash=payload.counted_cash, notes=payload.notes,
    )
    await db.commit()
    return _env(await till_svc.present_shift(db, row, with_moves=True), "Shift closed")


@router.get("/till/shifts")
async def restaurant_till_shifts(
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await till_svc.list_shifts(db, claims["tenant_id"], limit=limit)
    return _env([await till_svc.present_shift(db, row) for row in rows])


@router.get("/guests")
async def restaurant_guests(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_guests(db, claims["tenant_id"], user_id=claims.get("sub")))


@router.get("/kitchen")
async def restaurant_kitchen(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_kitchen(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env(await restaurant_svc.present_kitchen(db, claims["tenant_id"], rows))


class KitchenLineReadyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/kitchen/lines/{line_id}/start")
async def restaurant_line_start(
    line_id: UuidIdValue,
    payload: KitchenLineReadyBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    await restaurant_svc.start_line(
        db, claims["tenant_id"], line_id, user_id=claims.get("sub")
    )
    await db.commit()
    rows = await restaurant_svc.list_kitchen(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env(await restaurant_svc.present_kitchen(db, claims["tenant_id"], rows), "Item started")


@router.post("/kitchen/lines/{line_id}/ready")
async def restaurant_line_ready(
    line_id: UuidIdValue,
    payload: KitchenLineReadyBody | None = None,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    await restaurant_svc.mark_line_ready(
        db, claims["tenant_id"], line_id, user_id=claims.get("sub")
    )
    await db.commit()
    rows = await restaurant_svc.list_kitchen(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env(await restaurant_svc.present_kitchen(db, claims["tenant_id"], rows), "Item ready")


class WasteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: PositiveQtyValue
    reason: Literal["spoilage", "damage", "waste"]
    notes: StockOutNotesValue | None = None
    warehouse_id: UuidIdValue | None = None


@router.get("/waste")
async def restaurant_waste_list(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_waste(db, claims["tenant_id"], user_id=claims.get("sub")))


@router.post("/waste")
async def restaurant_waste(
    payload: WasteBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.record_waste(
        db,
        claims["tenant_id"],
        user_id=claims.get("sub"),
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        notes=payload.notes,
        warehouse_id=payload.warehouse_id,
    )
    await db.commit()
    return _env(row, "Waste recorded")


@router.get("/reports")
async def restaurant_reports(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.reports(db, claims["tenant_id"], user_id=claims.get("sub")))


class BookingLinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: WebsiteHostnameValue
    link_kind: Literal["existing", "new"]


class PublicBookingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_name: str = Field(min_length=1, max_length=180)
    phone: E164PhoneValue
    party_size: int = Field(ge=1, le=40)
    booked_for: str = Field(min_length=10, max_length=40)
    notes: str | None = None


class StaffBookingBody(PublicBookingBody):
    turn: TurnValue | None = None


class BookingUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_name: str | None = Field(default=None, min_length=1, max_length=180)
    phone: E164PhoneValue | None = None
    party_size: int | None = Field(default=None, ge=1, le=40)
    booked_for: str | None = Field(default=None, min_length=10, max_length=40)
    notes: str | None = None
    turn: TurnValue | None = None


class ServiceChargeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: float | None = Field(default=None, ge=0, le=30)


@router.get("/service-charge")
async def restaurant_service_charge(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.get_service_charge(db, claims["tenant_id"]))


@router.put("/service-charge")
async def restaurant_save_service_charge(
    payload: ServiceChargeBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.save_service_charge(db, claims["tenant_id"], payload.percent)
    await db.commit()
    return _env(body, "Service charge saved")


@router.get("/booking-link")
async def restaurant_booking_link(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.get_booking_link(db, claims["tenant_id"]))


@router.put("/booking-link")
async def restaurant_save_booking_link(
    payload: BookingLinkBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.save_booking_link(
        db,
        claims["tenant_id"],
        hostname=payload.hostname,
        link_kind=payload.link_kind,
    )
    await db.commit()
    return _env(body, "Booking link saved")


@router.get("/bookings")
async def restaurant_bookings(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_bookings(db, claims["tenant_id"])
    return _env([restaurant_svc.serialize_booking(row) for row in rows])


@router.post("/bookings")
async def restaurant_create_booking(
    payload: StaffBookingBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_staff_booking(
        db,
        claims["tenant_id"],
        guest_name=payload.guest_name,
        phone=payload.phone,
        party_size=payload.party_size,
        booked_for=payload.booked_for,
        notes=payload.notes,
        turn=payload.turn,
    )
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Booking requested")


@router.patch("/bookings/{booking_id}")
async def restaurant_update_booking(
    booking_id: UuidIdValue,
    payload: BookingUpdateBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.update_booking(
        db, claims["tenant_id"], booking_id, payload, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Booking saved")


class SeatBookingBody(BaseModel):
    """Name the table when the party is seated. This does not open an order."""

    model_config = ConfigDict(extra="forbid")

    table_id: UuidIdValue | None = None


@router.post("/bookings/{booking_id}/seat")
async def restaurant_seat_booking(
    booking_id: str,
    payload: SeatBookingBody | None = Body(default=None),
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.set_booking_status(
        db,
        claims["tenant_id"],
        booking_id,
        "seated",
        table_id=payload.table_id if payload else None,
    )
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Guest seated")


class FinishBookingBody(BaseModel):
    """End a seated visit. This does not take a payment."""

    model_config = ConfigDict(extra="forbid")


@router.post("/bookings/{booking_id}/finish")
async def restaurant_finish_booking(
    booking_id: str,
    payload: FinishBookingBody | None = Body(default=None),
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    row = await restaurant_svc.finish_booking(db, claims["tenant_id"], booking_id)
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Visit finished")


@router.post("/bookings/{booking_id}/cancel")
async def restaurant_cancel_booking(
    booking_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.set_booking_status(db, claims["tenant_id"], booking_id, "cancelled")
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Booking cancelled")


class OnlineOrdersBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: bool


@router.get("/online-orders")
async def restaurant_online_orders(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.online_order_desk(db, claims["tenant_id"]))


@router.put("/online-orders")
async def restaurant_save_online_orders(
    payload: OnlineOrdersBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.set_online_orders(db, claims["tenant_id"], open_orders=payload.open)
    await db.commit()
    return _env(body, "Online food orders saved")


class FloorPlaceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: UuidIdValue
    x: int = Field(ge=0, le=100)
    y: int = Field(ge=0, le=100)


class FloorPlacesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    places: list[FloorPlaceBody] = Field(default_factory=list, max_length=40)


@router.get("/floor-places")
async def restaurant_floor_places(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_floor_places(db, claims["tenant_id"]))


@router.put("/floor-places")
async def restaurant_save_floor_places(
    payload: FloorPlacesBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.replace_floor_places(db, claims["tenant_id"], payload.places)
    await db.commit()
    return _env(body, "Floor saved")


class KitchenSoundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on: bool


@router.get("/kitchen-sound")
async def restaurant_kitchen_sound(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.kitchen_sound(db, claims["tenant_id"]))


@router.put("/kitchen-sound")
async def restaurant_save_kitchen_sound(
    payload: KitchenSoundBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.set_kitchen_sound(db, claims["tenant_id"], on=payload.on)
    await db.commit()
    return _env(body, "Kitchen sound saved")


class ClockBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.get("/clock")
async def restaurant_clock(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_clock(db, claims["tenant_id"], claims.get("sub") or ""))


@router.post("/clock/in")
async def restaurant_clock_in(
    payload: ClockBody | None = Body(default=None),
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    body = await restaurant_svc.clock_in(db, claims["tenant_id"], claims.get("sub") or "")
    await db.commit()
    return _env(body, "Clocked in")


@router.post("/clock/out")
async def restaurant_clock_out(
    payload: ClockBody | None = Body(default=None),
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    del payload
    body = await restaurant_svc.clock_out(db, claims["tenant_id"], claims.get("sub") or "")
    await db.commit()
    return _env(body, "Clocked out")


class SoldOutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_ids: list[UuidIdValue] = Field(default_factory=list)


@router.get("/sold-out")
async def restaurant_sold_out(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.list_sold_out(db, claims["tenant_id"]))


@router.put("/sold-out")
async def restaurant_save_sold_out(
    payload: SoldOutBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await restaurant_svc.replace_sold_out(db, claims["tenant_id"], payload.product_ids)
    await db.commit()
    return _env(body, "Sold out saved")


public_router = APIRouter(prefix="/public/restaurant-booking", tags=["restaurant-booking"])


@public_router.get("/by-host")
async def public_restaurant_booking_host(
    host: str = Query(min_length=1, max_length=253),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.booking_page_for_host(db, host))


@public_router.get("/{slug}")
async def public_restaurant_booking_page(slug: str, db: AsyncSession = Depends(get_db)):
    return _env(await restaurant_svc.booking_page(db, slug))


@public_router.post("/{slug}")
async def public_restaurant_booking_create(
    slug: str,
    payload: PublicBookingBody,
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_public_booking(
        db,
        slug,
        guest_name=payload.guest_name,
        phone=payload.phone,
        party_size=payload.party_size,
        booked_for=payload.booked_for,
        notes=payload.notes,
    )
    await db.commit()
    return _env(restaurant_svc.serialize_booking(row), "Booking requested")


class PublicOrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: float = Field(gt=0, le=40, allow_inf_nan=False)


class PublicOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: PartyNameValue
    notes: str | None = None
    lines: list[PublicOrderLine] = Field(min_length=1, max_length=8)


order_public_router = APIRouter(prefix="/public/restaurant-order", tags=["restaurant-order"])


@order_public_router.get("/{slug}")
async def public_restaurant_order_page(slug: str, db: AsyncSession = Depends(get_db)):
    return _env(await restaurant_svc.public_order_page(db, slug))


@order_public_router.post("/{slug}")
async def public_restaurant_order_create(
    slug: str,
    payload: PublicOrderBody,
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_public_order(
        db,
        slug,
        customer_name=payload.customer_name,
        notes=payload.notes,
        lines=payload.lines,
    )
    await db.commit()
    body = restaurant_svc.serialize_order(row)
    body["pay_at_counter"] = True
    return _env(body, "Order received. Pay at the counter.")
