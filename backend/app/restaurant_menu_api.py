"""Routes for the restaurant digital menu: staff management and the public guest menu."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import logo_media as logo_media_svc
from app import product_images as product_images_svc
from app import restaurant_menu as menu_svc
from app import storage as storage_svc
from app.config import settings
from app.db import get_db
from app.restaurant_api import _restaurant_job_gate
from app.schemas import NonNegativeMoneyValue, UuidIdValue
from app.security import require_permission

# Waiters, cashiers and the kitchen are stopped by the job gate. Writes also need inventory
# write, which is the permission that already guards dishes and their prices.
router = APIRouter(prefix="/restaurant/menu", tags=["restaurant-menu"], dependencies=[Depends(_restaurant_job_gate)])
public_router = APIRouter(prefix="/public/menu", tags=["restaurant-menu-public"])

can_read = require_permission("restaurant", "read")
can_edit = require_permission("inventory", "write")


def _env(data, message: str = "OK") -> dict:
    return {"success": True, "data": data, "message": message}


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsBody(Body):
    is_published: bool | None = None
    tagline: Annotated[str, Field(max_length=160)] | None = None
    accent_color: Annotated[str, Field(min_length=7, max_length=7)] | None = None
    board_style: Literal["forest", "mist"] | None = None
    board_rotate_seconds: int | None = Field(default=None, ge=5, le=60)
    show_unavailable: bool | None = None


class CategoryCreateBody(Body):
    name: Annotated[str, Field(min_length=1, max_length=120)]


class CategoryUpdateBody(Body):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    is_published: bool | None = None


class OrderBody(Body):
    ids: list[UuidIdValue] = Field(min_length=1, max_length=400)


class ItemCreateBody(Body):
    category_id: UuidIdValue
    # An existing dish, or the details of a new one.
    product_id: UuidIdValue | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    price: NonNegativeMoneyValue | None = None
    station: Literal["kitchen", "bar"] = "kitchen"


class ItemUpdateBody(Body):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    price: NonNegativeMoneyValue | None = None
    category_id: UuidIdValue | None = None
    is_published: bool | None = None
    is_featured: bool | None = None
    promo_label: Annotated[str, Field(max_length=60)] | None = None
    available: bool | None = None


def _drop_nulls(payload: BaseModel, *keep: str) -> BaseModel:
    """A null on most fields means leave it alone; ``keep`` fields may be cleared with null."""
    for field in list(payload.model_fields_set):
        if getattr(payload, field) is None and field not in keep:
            payload.model_fields_set.discard(field)
    return payload


@router.get("")
async def menu_get(claims=Depends(can_read), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.admin_menu(db, claims["tenant_id"])
    await db.commit()
    return _env(data)


@router.get("/preview")
async def menu_preview(claims=Depends(can_read), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.preview_menu(db, claims["tenant_id"])
    await db.commit()
    return _env(data)


@router.patch("/settings")
async def menu_settings(payload: SettingsBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.save_settings(
        db, claims["tenant_id"], _drop_nulls(payload, "tagline"), user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Menu settings saved")


@router.post("/regenerate-link")
async def menu_regenerate(claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.regenerate_link(db, claims["tenant_id"], user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "New QR code ready. Old printed codes no longer work.")


@router.post("/categories")
async def menu_category_create(payload: CategoryCreateBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.create_category(db, claims["tenant_id"], payload.name, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Category added")


@router.put("/categories/order")
async def menu_category_order(payload: OrderBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    await menu_svc.reorder_categories(db, claims["tenant_id"], payload.ids)
    await db.commit()
    return _env({"ok": True}, "Order saved")


@router.patch("/categories/{category_id}")
async def menu_category_update(
    category_id: UuidIdValue, payload: CategoryUpdateBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)
):
    data = await menu_svc.update_category(
        db, claims["tenant_id"], category_id, _drop_nulls(payload), user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Category saved")


@router.delete("/categories/{category_id}")
async def menu_category_delete(category_id: UuidIdValue, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    await menu_svc.delete_category(db, claims["tenant_id"], category_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({"ok": True}, "Category removed")


@router.put("/categories/{category_id}/items/order")
async def menu_item_order(
    category_id: UuidIdValue, payload: OrderBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)
):
    await menu_svc.reorder_items(db, claims["tenant_id"], category_id, payload.ids)
    await db.commit()
    return _env({"ok": True}, "Order saved")


@router.post("/items")
async def menu_item_create(payload: ItemCreateBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    data = await menu_svc.add_item(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Added to the menu")


@router.patch("/items/{item_id}")
async def menu_item_update(
    item_id: UuidIdValue, payload: ItemUpdateBody, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)
):
    data = await menu_svc.update_item(
        db, claims["tenant_id"], item_id, _drop_nulls(payload, "description", "promo_label"), user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Dish saved")


@router.delete("/items/{item_id}")
async def menu_item_delete(item_id: UuidIdValue, claims=Depends(can_edit), db: AsyncSession = Depends(get_db)):
    await menu_svc.remove_item(db, claims["tenant_id"], item_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({"ok": True}, "Taken off the menu")


@router.post("/items/{item_id}/photo")
async def menu_item_photo(
    item_id: UuidIdValue,
    file: UploadFile = File(...),
    claims=Depends(can_edit),
    db: AsyncSession = Depends(get_db),
):
    product = await menu_svc.item_dish(db, claims["tenant_id"], item_id)
    stored = await storage_svc.save_upload(
        tenant_id=claims["tenant_id"],
        category="product_images",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    await product_images_svc.add_product_image(
        db,
        tenant_id=claims["tenant_id"],
        product_id=product.id,
        storage_key=stored.key,
        content_type=stored.content_type,
        original_filename=stored.original_filename,
        is_primary=True,
    )
    await db.commit()
    return _env({"has_image": True}, "Photo saved")


@router.get("/items/{item_id}/photo")
async def menu_item_photo_get(
    item_id: UuidIdValue, request: Request, claims=Depends(can_read), db: AsyncSession = Depends(get_db)
):
    product = await menu_svc.item_dish(db, claims["tenant_id"], item_id)
    if not product.image_url:
        return Response(status_code=404)
    return logo_media_svc.keyed_media_response(
        product.image_url,
        tenant_id=claims["tenant_id"],
        request=request,
        cache_control="private, no-cache",
        vary="Authorization",
    )


def _download(data: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get("/qr.png")
async def menu_qr_png(
    size: Annotated[Literal["standard", "large"], Query()] = "standard",
    claims=Depends(can_read),
    db: AsyncSession = Depends(get_db),
):
    data, name = await menu_svc.qr_png(db, claims["tenant_id"], large=size == "large")
    await db.commit()
    return _download(data, name, "image/png")


@router.get("/qr.pdf")
async def menu_qr_pdf(claims=Depends(can_read), db: AsyncSession = Depends(get_db)):
    data, name = await menu_svc.qr_poster_pdf(db, claims["tenant_id"])
    await db.commit()
    return _download(data, name, "application/pdf")


@public_router.get("/{token}")
async def public_menu(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await menu_svc.public_menu(db, token)
    etag = f'"{body["version"]}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if (request.headers.get("if-none-match") or "").strip() == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(_env(body), headers=headers)


@public_router.get("/{token}/logo")
async def public_menu_logo(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    tenant = await menu_svc.public_logo_tenant(db, token)
    return logo_media_svc.tenant_logo_response(tenant, request=request, requested_version=None)


@public_router.get("/{token}/items/{item_id}/image")
async def public_menu_image(token: str, item_id: UuidIdValue, request: Request, db: AsyncSession = Depends(get_db)):
    tenant, key = await menu_svc.public_item_image(db, token, item_id)
    # Revalidate so a dish taken off the menu stops showing at once; 304 still skips the bytes.
    return logo_media_svc.keyed_media_response(
        key, tenant_id=tenant.id, request=request, cache_control="public, no-cache", vary="Accept"
    )
