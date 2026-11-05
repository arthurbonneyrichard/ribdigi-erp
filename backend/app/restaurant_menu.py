"""Restaurant digital menu: what guests see on the TV board and through the QR code.

The menu sits on the restaurant's existing dishes. Name, price, description and photo
stay on the dish, so the till and the menu always agree. These tables only add the
menu's shape: categories, display order, what is published and what is featured.

Guests reach a menu through a random ``public_token``, never a tenant id. The public
payload is built field by field, so cost prices and other business data cannot reach it.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import logo_media as logo_media_svc
from app import models as m
from app import restaurant as rs
from app.catalog import allocate_sku
from app.config import settings
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

MAX_CATEGORIES = 40
MAX_ITEMS = 400
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _now() -> datetime:
    return datetime.utcnow()


def _new_token() -> str:
    return secrets.token_urlsafe(16)


def menu_url(token: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/menu/{token}"


async def _settings_row(db: AsyncSession, tenant_id: str) -> m.RestaurantMenuSettings | None:
    return (
        await db.execute(select(m.RestaurantMenuSettings).where(m.RestaurantMenuSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def _categories(db: AsyncSession, tenant_id: str) -> list[m.RestaurantMenuCategory]:
    return list(
        (
            await db.execute(
                select(m.RestaurantMenuCategory)
                .where(m.RestaurantMenuCategory.tenant_id == tenant_id)
                .order_by(m.RestaurantMenuCategory.sort_order, m.RestaurantMenuCategory.name)
            )
        ).scalars()
    )


async def _items_with_dishes(db: AsyncSession, tenant_id: str) -> list[tuple[m.RestaurantMenuItem, m.Product]]:
    rows = await db.execute(
        select(m.RestaurantMenuItem, m.Product)
        .join(m.Product, m.Product.id == m.RestaurantMenuItem.product_id)
        .where(m.RestaurantMenuItem.tenant_id == tenant_id, m.Product.tenant_id == tenant_id)
        .order_by(m.RestaurantMenuItem.sort_order, m.Product.name)
    )
    return [(item, product) for item, product in rows.all()]


async def _sellable_dishes(db: AsyncSession, tenant: m.Tenant) -> list[m.Product]:
    products = (
        await db.execute(
            select(m.Product).where(m.Product.tenant_id == tenant.id, m.Product.is_active.is_(True))
        )
    ).scalars()
    return [p for p in products if await rs._is_public_menu_item(db, tenant.id, p)]


def _section_for(product: m.Product) -> str:
    station = (getattr(product, "prep_station", None) or "").strip().lower()
    label = (getattr(product, "category", None) or "").strip()
    if label and label.casefold() != "general":
        return label[:120]
    return "Drinks" if station == "bar" else "Food"


async def ensure_menu(db: AsyncSession, tenant: m.Tenant) -> m.RestaurantMenuSettings:
    """First visit: make the private link and lay out the restaurant's current dishes."""
    row = await _settings_row(db, tenant.id)
    if row is not None:
        return row
    row = m.RestaurantMenuSettings(tenant_id=tenant.id, public_token=_new_token(), updated_at=_now())
    db.add(row)
    await db.flush()
    sections: dict[str, m.RestaurantMenuCategory] = {}
    dishes = sorted(await _sellable_dishes(db, tenant), key=lambda p: (_section_for(p).casefold(), p.name.casefold()))
    for position, product in enumerate(dishes[:MAX_ITEMS]):
        name = _section_for(product)
        key = name.casefold()
        if key not in sections:
            if len(sections) >= MAX_CATEGORIES:
                continue
            sections[key] = m.RestaurantMenuCategory(tenant_id=tenant.id, name=name, sort_order=len(sections))
            db.add(sections[key])
            await db.flush()
        db.add(
            m.RestaurantMenuItem(
                tenant_id=tenant.id, category_id=sections[key].id, product_id=product.id, sort_order=position
            )
        )
    await db.flush()
    return row


def _serialize_settings(row: m.RestaurantMenuSettings) -> dict:
    return {
        "public_token": row.public_token,
        "public_url": menu_url(row.public_token),
        "board_url": f"{menu_url(row.public_token)}/board",
        "is_published": bool(row.is_published),
        "tagline": row.tagline,
        "accent_color": row.accent_color,
        "board_style": row.board_style,
        "board_rotate_seconds": int(row.board_rotate_seconds or 12),
        "show_unavailable": bool(row.show_unavailable),
    }


def _serialize_item(item: m.RestaurantMenuItem, product: m.Product, sold_out: set[str]) -> dict:
    return {
        "id": item.id,
        "product_id": product.id,
        "category_id": item.category_id,
        "name": product.name,
        "description": (product.description or "").strip() or None,
        "price": money_json(product.selling_price or 0),
        "has_image": bool(product.image_url),
        "is_published": bool(item.is_published),
        "is_featured": bool(item.is_featured),
        "promo_label": item.promo_label,
        "available": product.id not in sold_out,
        "dish_active": bool(product.is_active),
        "sort_order": int(item.sort_order or 0),
    }


async def admin_menu(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    sold_out = set(rs._stored_sold_out(tenant))
    pairs = await _items_with_dishes(db, tenant.id)
    listed = {product.id for _item, product in pairs}
    by_category: dict[str, list[dict]] = {}
    for item, product in pairs:
        by_category.setdefault(item.category_id, []).append(_serialize_item(item, product, sold_out))
    categories = [
        {
            "id": cat.id,
            "name": cat.name,
            "sort_order": int(cat.sort_order or 0),
            "is_published": bool(cat.is_published),
            "items": by_category.get(cat.id, []),
        }
        for cat in await _categories(db, tenant.id)
    ]
    unlisted = [
        {"id": p.id, "name": p.name, "price": money_json(p.selling_price or 0)}
        for p in await _sellable_dishes(db, tenant)
        if p.id not in listed
    ]
    unlisted.sort(key=lambda r: str(r["name"]).casefold())
    return {
        "company_name": tenant.company_name,
        "currency": tenant.currency or "GHS",
        "has_logo": bool(getattr(tenant, "logo_url", None)),
        "settings": _serialize_settings(row),
        "categories": categories,
        "unlisted": unlisted,
    }


async def _touch(db: AsyncSession, tenant_id: str) -> None:
    row = await _settings_row(db, tenant_id)
    if row is not None:
        row.updated_at = _now()


async def _log(db: AsyncSession, tenant_id: str, user_id: str | None, action: str, entity_id: str | None, details: dict) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant", action=action,
        entity="restaurant_menu", entity_id=entity_id, details=details,
    )


async def save_settings(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    data = payload.model_dump(exclude_unset=True)
    if "tagline" in data:
        row.tagline = optional_honest_narrative(data["tagline"], label="tagline", max_length=160)
    if "accent_color" in data:
        color = str(data["accent_color"] or "").strip()
        if not HEX_COLOR.match(color):
            raise HTTPException(status_code=422, detail="Choose a colour like #4AB012.")
        row.accent_color = color.upper()
    for field in ("board_style", "board_rotate_seconds", "show_unavailable", "is_published"):
        if field in data:
            setattr(row, field, data[field])
    row.updated_at = _now()
    await _log(db, tenant.id, user_id, "restaurant_menu_settings_saved", row.id, {"fields": sorted(data)})
    await db.flush()
    return _serialize_settings(row)


async def regenerate_link(db: AsyncSession, tenant_id: str, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    row.public_token = _new_token()
    row.updated_at = _now()
    await _log(db, tenant.id, user_id, "restaurant_menu_qr_regenerated", row.id, {})
    await db.flush()
    return _serialize_settings(row)


async def _category(db: AsyncSession, tenant_id: str, category_id: str) -> m.RestaurantMenuCategory:
    row = await db.get(m.RestaurantMenuCategory, category_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Menu category not found")
    return row


async def _item(db: AsyncSession, tenant_id: str, item_id: str) -> m.RestaurantMenuItem:
    row = await db.get(m.RestaurantMenuItem, item_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return row


async def _unique_name_guard(db: AsyncSession) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="There is already a category with that name.") from exc


async def create_category(db: AsyncSession, tenant_id: str, name: str, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    await ensure_menu(db, tenant)
    clean = require_honest_narrative(name, label="category name", max_length=120)
    rows = await _categories(db, tenant.id)
    if len(rows) >= MAX_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Keep {MAX_CATEGORIES} categories or fewer.")
    row = m.RestaurantMenuCategory(
        tenant_id=tenant.id, name=clean, sort_order=max((int(r.sort_order or 0) for r in rows), default=-1) + 1
    )
    db.add(row)
    await _unique_name_guard(db)
    await _touch(db, tenant.id)
    await _log(db, tenant.id, user_id, "restaurant_menu_category_created", row.id, {"name": clean})
    return {"id": row.id, "name": row.name, "sort_order": row.sort_order, "is_published": row.is_published, "items": []}


async def update_category(db: AsyncSession, tenant_id: str, category_id: str, payload, *, user_id: str | None) -> dict:
    row = await _category(db, tenant_id, category_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        row.name = require_honest_narrative(data["name"], label="category name", max_length=120)
    if "is_published" in data:
        row.is_published = bool(data["is_published"])
    await _unique_name_guard(db)
    await _touch(db, tenant_id)
    await _log(db, tenant_id, user_id, "restaurant_menu_category_updated", row.id, {"fields": sorted(data)})
    return {"id": row.id, "name": row.name, "sort_order": row.sort_order, "is_published": row.is_published}


async def delete_category(db: AsyncSession, tenant_id: str, category_id: str, *, user_id: str | None) -> None:
    row = await _category(db, tenant_id, category_id)
    used = (
        await db.execute(
            select(func.count())
            .select_from(m.RestaurantMenuItem)
            .where(m.RestaurantMenuItem.tenant_id == tenant_id, m.RestaurantMenuItem.category_id == row.id)
        )
    ).scalar_one()
    if used:
        raise HTTPException(status_code=409, detail="Move or remove the dishes in this category first.")
    await _log(db, tenant_id, user_id, "restaurant_menu_category_deleted", row.id, {"name": row.name})
    await db.delete(row)
    await _touch(db, tenant_id)
    await db.flush()


async def reorder_categories(db: AsyncSession, tenant_id: str, ids: list[str]) -> None:
    rows = {row.id: row for row in await _categories(db, tenant_id)}
    if set(ids) != set(rows) or len(ids) != len(rows):
        raise HTTPException(status_code=422, detail="Send every category once.")
    for position, category_id in enumerate(ids):
        rows[category_id].sort_order = position
    await _touch(db, tenant_id)
    await db.flush()


async def reorder_items(db: AsyncSession, tenant_id: str, category_id: str, ids: list[str]) -> None:
    await _category(db, tenant_id, category_id)
    rows = {
        row.id: row
        for row in (
            await db.execute(
                select(m.RestaurantMenuItem).where(
                    m.RestaurantMenuItem.tenant_id == tenant_id, m.RestaurantMenuItem.category_id == category_id
                )
            )
        ).scalars()
    }
    if set(ids) != set(rows) or len(ids) != len(rows):
        raise HTTPException(status_code=422, detail="Send every dish in this category once.")
    for position, item_id in enumerate(ids):
        rows[item_id].sort_order = position
    await _touch(db, tenant_id)
    await db.flush()


async def _next_item_position(db: AsyncSession, tenant_id: str, category_id: str) -> int:
    top = (
        await db.execute(
            select(func.max(m.RestaurantMenuItem.sort_order)).where(
                m.RestaurantMenuItem.tenant_id == tenant_id, m.RestaurantMenuItem.category_id == category_id
            )
        )
    ).scalar_one()
    return int(top if top is not None else -1) + 1


async def add_item(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> dict:
    """Put an existing dish on the menu, or create a new dish and list it."""
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    await ensure_menu(db, tenant)
    category = await _category(db, tenant.id, payload.category_id)
    total = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantMenuItem).where(m.RestaurantMenuItem.tenant_id == tenant.id)
        )
    ).scalar_one()
    if int(total or 0) >= MAX_ITEMS:
        raise HTTPException(status_code=422, detail=f"Keep {MAX_ITEMS} dishes or fewer on the menu.")
    if payload.product_id:
        product = await rs._product(db, tenant.id, payload.product_id)
        if not product.is_active or not await rs._is_public_menu_item(db, tenant.id, product):
            raise HTTPException(status_code=422, detail="Choose a dish or drink from your menu items.")
    else:
        name = require_honest_narrative(payload.name, label="dish name", max_length=200)
        if payload.price is None:
            raise HTTPException(status_code=422, detail="Set a price for the new dish.")
        product = m.Product(
            tenant_id=tenant.id,
            name=name,
            sku=await allocate_sku(db, tenant.id, prefix="MENU"),
            description=optional_honest_narrative(payload.description, label="description", max_length=500),
            category=category.name[:100],
            selling_price=money_json(round(float(payload.price), 2)),
            cost_price=0,
            prep_station=payload.station,
            is_active=True,
            created_by=user_id,
        )
        db.add(product)
        await db.flush()
    item = m.RestaurantMenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        product_id=product.id,
        sort_order=await _next_item_position(db, tenant.id, category.id),
    )
    db.add(item)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That dish is already on the menu.") from exc
    await _touch(db, tenant.id)
    await _log(db, tenant.id, user_id, "restaurant_menu_item_added", item.id, {"name": product.name})
    return _serialize_item(item, product, set(rs._stored_sold_out(tenant)))


async def update_item(db: AsyncSession, tenant_id: str, item_id: str, payload, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    item = await _item(db, tenant.id, item_id)
    product = await rs._product(db, tenant.id, item.product_id)
    data = payload.model_dump(exclude_unset=True)
    details: dict = {"fields": sorted(data)}
    if "name" in data:
        product.name = require_honest_narrative(data["name"], label="dish name", max_length=200)
    if "description" in data:
        product.description = optional_honest_narrative(data["description"], label="description", max_length=500)
    if "price" in data and data["price"] is not None:
        before = money_json(product.selling_price or 0)
        after = money_json(round(float(data["price"]), 2))
        if before != after:
            details["price"] = {"before": before, "after": after}
        product.selling_price = after
    if "category_id" in data:
        category = await _category(db, tenant.id, data["category_id"])
        if category.id != item.category_id:
            item.category_id = category.id
            item.sort_order = await _next_item_position(db, tenant.id, category.id)
    for field in ("is_published", "is_featured"):
        if field in data:
            setattr(item, field, bool(data[field]))
    if "promo_label" in data:
        item.promo_label = optional_honest_narrative(data["promo_label"], label="promotion label", max_length=60)
    if "available" in data:
        sold_out = rs._stored_sold_out(tenant)
        if data["available"]:
            sold_out = [pid for pid in sold_out if pid != product.id]
        elif product.id not in sold_out:
            sold_out = [*sold_out, product.id]
        await rs.replace_sold_out(db, tenant.id, sold_out)
    await _touch(db, tenant.id)
    await _log(db, tenant.id, user_id, "restaurant_menu_item_updated", item.id, details)
    await db.flush()
    return _serialize_item(item, product, set(rs._stored_sold_out(tenant)))


async def remove_item(db: AsyncSession, tenant_id: str, item_id: str, *, user_id: str | None) -> None:
    """Take a dish off the menu. The dish stays on the till."""
    item = await _item(db, tenant_id, item_id)
    await _log(db, tenant_id, user_id, "restaurant_menu_item_removed", item.id, {"product_id": item.product_id})
    await db.delete(item)
    await _touch(db, tenant_id)
    await db.flush()


async def item_dish(db: AsyncSession, tenant_id: str, item_id: str) -> m.Product:
    item = await _item(db, tenant_id, item_id)
    return await rs._product(db, tenant_id, item.product_id)


# ---------- public ----------


async def _published_menu(db: AsyncSession, token: str) -> tuple[m.RestaurantMenuSettings, m.Tenant]:
    row = (
        await db.execute(select(m.RestaurantMenuSettings).where(m.RestaurantMenuSettings.public_token == token))
    ).scalar_one_or_none()
    tenant = await db.get(m.Tenant, row.tenant_id) if row is not None else None
    if row is None or tenant is None or not row.is_published or tenant.status == "suspended":
        raise HTTPException(status_code=404, detail="This menu is not available")
    return row, tenant


def _guest_payload(
    row: m.RestaurantMenuSettings,
    tenant: m.Tenant,
    categories: list[m.RestaurantMenuCategory],
    pairs: list[tuple[m.RestaurantMenuItem, m.Product]],
) -> dict:
    """Every field a guest can see is named here. Nothing else leaves the ERP."""
    sold_out = set(rs._stored_sold_out(tenant))
    by_category: dict[str, list[dict]] = {}
    for item, product in pairs:
        if not product.is_active or not item.is_published:
            continue
        available = product.id not in sold_out
        if not available and not row.show_unavailable:
            continue
        by_category.setdefault(item.category_id, []).append(
            {
                "id": item.id,
                "name": product.name,
                "description": (product.description or "").strip() or None,
                "price": money_json(product.selling_price or 0),
                "image_version": logo_media_svc.logo_version(tenant.id, product.image_url),
                "available": available,
                "featured": bool(item.is_featured),
                "promo": item.promo_label,
            }
        )
    sections = [
        {"id": cat.id, "name": cat.name, "items": by_category[cat.id]}
        for cat in categories
        if cat.is_published and by_category.get(cat.id)
    ]
    body = {
        "restaurant": {
            "name": tenant.company_name,
            "logo_version": logo_media_svc.logo_version(tenant.id, getattr(tenant, "logo_url", None)),
            "phone": tenant.phone,
            "address": tenant.address,
            "tagline": row.tagline,
        },
        "currency": tenant.currency or "GHS",
        "theme": {
            "accent": row.accent_color,
            "style": row.board_style,
            "rotate_seconds": int(row.board_rotate_seconds or 12),
        },
        "categories": sections,
    }
    body["version"] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return body


async def public_menu(db: AsyncSession, token: str) -> dict:
    row, tenant = await _published_menu(db, token)
    return _guest_payload(row, tenant, await _categories(db, tenant.id), await _items_with_dishes(db, tenant.id))


async def preview_menu(db: AsyncSession, tenant_id: str) -> dict:
    """What guests would see, for staff, even before the menu is published."""
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    return _guest_payload(row, tenant, await _categories(db, tenant.id), await _items_with_dishes(db, tenant.id))


async def public_logo_tenant(db: AsyncSession, token: str) -> m.Tenant:
    _row, tenant = await _published_menu(db, token)
    if not getattr(tenant, "logo_url", None):
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return tenant


async def public_item_image(db: AsyncSession, token: str, item_id: str) -> tuple[m.Tenant, str]:
    _row, tenant = await _published_menu(db, token)
    item = await db.get(m.RestaurantMenuItem, item_id)
    product = await db.get(m.Product, item.product_id) if item is not None else None
    if (
        item is None
        or item.tenant_id != tenant.id
        or not item.is_published
        or product is None
        or product.tenant_id != tenant.id
        or not product.is_active
        or not product.image_url
    ):
        raise HTTPException(status_code=404, detail="Menu photo not found")
    return tenant, product.image_url


# ---------- QR ----------


async def qr_png(db: AsyncSession, tenant_id: str, *, large: bool) -> tuple[bytes, str]:
    from app.barcodes import render_qr_png

    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    data = render_qr_png(menu_url(row.public_token), box_size=24 if large else 12, border=4)
    return data, f"menu-qr-{tenant.slug}.png"


def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _fitted_font(draw, text: str, *, start: int, width: int):
    size = start
    while size > 22:
        font = _font(size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 4
    return _font(22)


def _logo_image(tenant: m.Tenant):
    """The company logo for the poster, or None. A bad logo must not stop the QR printing."""
    from PIL import Image

    key = getattr(tenant, "logo_url", None)
    if not key:
        return None
    try:
        from app import storage as storage_svc

        media = storage_svc.read_object(key, tenant_id=tenant.id)
        return Image.open(io.BytesIO(media.data)).convert("RGBA")
    except Exception:  # noqa: BLE001 - e.g. an SVG logo Pillow cannot read
        return None


async def qr_poster_pdf(db: AsyncSession, tenant_id: str) -> tuple[bytes, str]:
    """An A5 table card: company name, logo and QR, ready to print."""
    from PIL import Image, ImageDraw

    from app.barcodes import render_qr_png

    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    row = await ensure_menu(db, tenant)
    width, height = 1240, 1748  # A5 at 212 dpi
    forest, brand, ink = (0, 61, 31), (74, 176, 18), (16, 33, 27)
    page = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(page)
    band = 420
    draw.rectangle([0, 0, width, band], fill=forest)
    draw.rectangle([0, band, width, band + 14], fill=brand)
    logo = _logo_image(tenant)
    text_top = 140
    if logo is not None:
        logo.thumbnail((220, 170))
        chip = Image.new("RGB", (logo.width + 28, logo.height + 28), "white")
        chip.paste(logo, (14, 14), logo)
        page.paste(chip, ((width - chip.width) // 2, 36))
        text_top = 36 + chip.height + 26
    name = tenant.company_name or "Our menu"
    name_font = _fitted_font(draw, name, start=84, width=width - 120)
    draw.text((width / 2, text_top), name, font=name_font, fill="white", anchor="ma")
    title = _font(68)
    draw.text((width / 2, band + 70), "Scan to see our menu", font=title, fill=ink, anchor="ma")
    qr = Image.open(io.BytesIO(render_qr_png(menu_url(row.public_token), box_size=24, border=2))).convert("RGB")
    qr = qr.resize((860, 860), Image.NEAREST)
    page.paste(qr, ((width - 860) // 2, band + 180))
    foot = _font(36)
    draw.text(
        (width / 2, band + 1080), "Open your phone camera and point it at the code.", font=foot, fill=ink, anchor="ma"
    )
    draw.text((width / 2, band + 1136), "No app or sign-up needed.", font=foot, fill=ink, anchor="ma")
    buf = io.BytesIO()
    page.save(buf, format="PDF", resolution=212)
    return buf.getvalue(), f"menu-qr-card-{tenant.slug}.pdf"
