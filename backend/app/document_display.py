"""Human labels for document lines and tenant calendar dates.

Emails, print HTML, and staff serializers share these helpers so a product UUID
is never shown as the item name.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _plain(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_id(value: str) -> bool:
    if not value:
        return False
    if _UUID_RE.match(value):
        return True
    # Short leftover hashes / truncated ids used as a label.
    return len(value) >= 8 and all(ch in "0123456789abcdefABCDEF-" for ch in value) and "-" in value


def document_item_label(item: dict[str, Any] | None) -> str:
    """Catalog name (SKU secondary). Never a raw product/variant UUID."""
    raw = item or {}
    name = _plain(raw.get("product_name") or raw.get("name"))
    sku = _plain(raw.get("sku") or raw.get("product_sku"))
    variant = _plain(raw.get("variant_name"))
    if _looks_like_id(name):
        name = ""
    if _looks_like_id(variant):
        variant = ""
    if _looks_like_id(sku):
        sku = ""
    if not name:
        return sku or "Item"
    if variant:
        name = f"{name} ({variant})"
    if sku:
        return f"{name} · {sku}"
    return name


def _calendar_ymd(value: Any) -> tuple[int, int, int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.year, value.month, value.day
    if isinstance(value, date):
        return value.year, value.month, value.day
    text = str(value).strip()
    if not text:
        return None
    # Prefer the calendar date prefix so ISO timestamps do not shift a day.
    head = text[:10]
    if len(head) == 10 and head[4] == "-" and head[7] == "-":
        try:
            y, m, d = int(head[0:4]), int(head[5:7]), int(head[8:10])
            if 1 <= m <= 12 and 1 <= d <= 31:
                return y, m, d
        except ValueError:
            return None
    return None


def format_tenant_date(value: Any, tenant: Any | None = None) -> str:
    """Format a date with the company date_format (default DD/MM/YYYY)."""
    ymd = _calendar_ymd(value)
    if ymd is None:
        return ""
    year, month, day = ymd
    fmt = _plain(getattr(tenant, "date_format", None)) or "DD/MM/YYYY"
    if fmt == "MM/DD/YYYY":
        return f"{month:02d}/{day:02d}/{year:04d}"
    if fmt == "YYYY-MM-DD":
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{day:02d}/{month:02d}/{year:04d}"


def first_document_date(doc: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if doc.get(key):
            return doc.get(key)
    return None


async def enrich_document_items(
    db: AsyncSession,
    tenant_id: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fill product_name / sku / variant_name on serialized document lines."""
    product_ids = {str(i.get("product_id")) for i in items if i.get("product_id")}
    variant_ids = {str(i.get("variant_id")) for i in items if i.get("variant_id")}
    products: dict[str, m.Product] = {}
    variants: dict[str, m.ProductVariant] = {}
    if product_ids:
        rows = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_(list(product_ids)),
                )
            )
        ).scalars().all()
        products = {p.id: p for p in rows}
    if variant_ids:
        rows = (
            await db.execute(
                select(m.ProductVariant).where(
                    m.ProductVariant.tenant_id == tenant_id,
                    m.ProductVariant.id.in_(list(variant_ids)),
                )
            )
        ).scalars().all()
        variants = {v.id: v for v in rows}
    for item in items:
        prod = products.get(str(item.get("product_id") or ""))
        if prod:
            item["product_name"] = prod.name
            item["sku"] = prod.sku
        var = variants.get(str(item.get("variant_id") or ""))
        if var:
            item["variant_name"] = var.name
            if var.sku:
                item["sku"] = var.sku
    return items
