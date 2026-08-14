"""Tenant-scoped product / variant lookup for barcode scans and search."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import barcodes as barcode_svc
from app import models as m


async def lookup_products(
    db: AsyncSession,
    *,
    tenant_id: str,
    q: str = "",
    barcode: str | None = None,
    limit: int = 40,
    company_id: str | None = None,
) -> list[dict]:
    """Resolve products and variants by barcode scan or text search."""
    q = (q or "").strip()
    scan = barcode_svc.normalize_barcode(barcode) or (
        q if barcode_svc.looks_like_barcode_scan(q) else None
    )
    stmt = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.is_active == True,  # noqa: E712
    )
    if company_id:
        stmt = stmt.where(m.Product.company_id == company_id)
    if scan:
        product_match = (m.Product.barcode == scan) | (m.Product.sku == scan)
        if q:
            product_match = product_match | m.Product.name.ilike(f"%{q}%")
        stmt = stmt.where(product_match)
    elif q:
        stmt = stmt.where(
            m.Product.name.ilike(f"%{q}%")
            | m.Product.sku.ilike(f"%{q}%")
            | m.Product.barcode.ilike(f"%{q}%")
        )
    products = (await db.execute(stmt.limit(30))).scalars().all()
    out: list[dict] = [
        {
            "id": p.id,
            "product_id": p.id,
            "variant_id": None,
            "name": p.name,
            "sku": p.sku,
            "barcode": p.barcode,
            "selling_price": float(p.selling_price or 0),
            "stock_qty": float(p.stock_qty or 0),
            "kind": "product",
        }
        for p in products
    ]

    vstmt = select(m.ProductVariant).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.is_active == True,  # noqa: E712
    )
    if company_id:
        vstmt = vstmt.where(m.ProductVariant.company_id == company_id)
    if scan:
        variant_match = (m.ProductVariant.barcode == scan) | (m.ProductVariant.sku == scan)
        if q:
            variant_match = variant_match | m.ProductVariant.name.ilike(f"%{q}%")
        vstmt = vstmt.where(variant_match)
    elif q:
        vstmt = vstmt.where(
            m.ProductVariant.name.ilike(f"%{q}%")
            | m.ProductVariant.sku.ilike(f"%{q}%")
            | m.ProductVariant.barcode.ilike(f"%{q}%")
        )
    else:
        return out[:limit]

    variants = (await db.execute(vstmt.limit(20))).scalars().all()
    for v in variants:
        out.append(
            {
                "id": v.id,
                "product_id": v.product_id,
                "variant_id": v.id,
                "name": v.name,
                "sku": v.sku,
                "barcode": v.barcode,
                "selling_price": float(v.selling_price or 0),
                "stock_qty": float(v.stock_qty or 0),
                "kind": "variant",
            }
        )
    return out[:limit]


def pick_exact_scan_match(rows: list[dict], code: str) -> dict | None:
    """Prefer exact barcode/SKU match for auto-add after a scan."""
    code = (code or "").strip()
    if not code:
        return None
    exact = [r for r in rows if (r.get("barcode") or "") == code or (r.get("sku") or "") == code]
    if len(exact) == 1:
        return exact[0]
    if len(exact) == 0 and len(rows) == 1:
        return rows[0]
    return None
