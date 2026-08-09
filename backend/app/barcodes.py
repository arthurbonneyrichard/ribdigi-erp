"""Barcode validation and generation (EAN/UPC check digits + Code 128 strings)."""

from __future__ import annotations

import re
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

# Internal-use EAN-13 prefixes (GS1 restricted distribution / in-store)
_EAN13_PREFIX = "200"
_CODE128_PREFIX = "RD"


def normalize_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ean_check_digit(body: str) -> str:
    """Compute GS1 check digit for EAN-8/13 / UPC-A (body without check digit)."""
    digits = [int(c) for c in body]
    # Weight from the right: odd positions *3, even *1 (1-based from right)
    total = 0
    for i, d in enumerate(reversed(digits), start=1):
        total += d * (3 if i % 2 == 1 else 1)
    return str((10 - (total % 10)) % 10)


def is_valid_ean13(code: str) -> bool:
    if not re.fullmatch(r"\d{13}", code):
        return False
    return _ean_check_digit(code[:12]) == code[12]


def is_valid_ean8(code: str) -> bool:
    if not re.fullmatch(r"\d{8}", code):
        return False
    return _ean_check_digit(code[:7]) == code[7]


def is_valid_upca(code: str) -> bool:
    if not re.fullmatch(r"\d{12}", code):
        return False
    return _ean_check_digit(code[:11]) == code[11]


def is_valid_code128_payload(code: str) -> bool:
    """Printable ASCII subset suitable as a Code 128 payload (not symbology encoding)."""
    if not (1 <= len(code) <= 48):
        return False
    return bool(re.fullmatch(r"[\x20-\x7E]+", code))


def detect_barcode_format(code: str) -> str:
    if is_valid_ean13(code):
        return "ean13"
    if is_valid_upca(code):
        return "upca"
    if is_valid_ean8(code):
        return "ean8"
    if is_valid_code128_payload(code):
        return "code128"
    raise HTTPException(status_code=400, detail="Invalid barcode format")


def validate_barcode(value: str | None) -> str | None:
    code = normalize_barcode(value)
    if code is None:
        return None
    detect_barcode_format(code)
    return code


def generate_ean13(*, body12: str | None = None) -> str:
    if body12 is None:
        # 200 + 9 random digits
        body12 = _EAN13_PREFIX + f"{secrets.randbelow(10**9):09d}"
    if not re.fullmatch(r"\d{12}", body12):
        raise HTTPException(status_code=400, detail="EAN-13 body must be 12 digits")
    return body12 + _ean_check_digit(body12)


def generate_code128(*, tenant_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]", "", tenant_id)[:6].upper() or "T"
    token = secrets.token_hex(4).upper()
    return f"{_CODE128_PREFIX}{slug}{token}"


async def barcode_in_use(
    db: AsyncSession,
    *,
    tenant_id: str,
    barcode: str,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> bool:
    pstmt = select(m.Product.id).where(
        m.Product.tenant_id == tenant_id,
        m.Product.barcode == barcode,
    )
    if exclude_product_id:
        pstmt = pstmt.where(m.Product.id != exclude_product_id)
    if (await db.execute(pstmt.limit(1))).scalar_one_or_none():
        return True

    vstmt = select(m.ProductVariant.id).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.barcode == barcode,
    )
    if exclude_variant_id:
        vstmt = vstmt.where(m.ProductVariant.id != exclude_variant_id)
    return (await db.execute(vstmt.limit(1))).scalar_one_or_none() is not None


async def assert_barcode_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    barcode: str | None,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> str | None:
    code = validate_barcode(barcode)
    if code is None:
        return None
    if await barcode_in_use(
        db,
        tenant_id=tenant_id,
        barcode=code,
        exclude_product_id=exclude_product_id,
        exclude_variant_id=exclude_variant_id,
    ):
        raise HTTPException(status_code=409, detail="Barcode already in use")
    return code


async def allocate_barcode(
    db: AsyncSession,
    *,
    tenant_id: str,
    format: str = "code128",
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> str:
    fmt = (format or "code128").strip().lower()
    if fmt not in {"code128", "ean13"}:
        raise HTTPException(status_code=400, detail="format must be code128 or ean13")
    for _ in range(20):
        code = generate_ean13() if fmt == "ean13" else generate_code128(tenant_id=tenant_id)
        if not await barcode_in_use(
            db,
            tenant_id=tenant_id,
            barcode=code,
            exclude_product_id=exclude_product_id,
            exclude_variant_id=exclude_variant_id,
        ):
            return code
    raise HTTPException(status_code=500, detail="Unable to allocate unique barcode")


async def assign_product_barcode(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    format: str = "code128",
    force: bool = False,
) -> m.Product:
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.barcode and not force:
        return product
    product.barcode = await allocate_barcode(
        db, tenant_id=tenant_id, format=format, exclude_product_id=product.id
    )
    await db.flush()
    return product


async def assign_variant_barcode(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    variant_id: str,
    format: str = "code128",
    force: bool = False,
) -> m.ProductVariant:
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = (
        await db.execute(
            select(m.ProductVariant).where(
                m.ProductVariant.id == variant_id,
                m.ProductVariant.tenant_id == tenant_id,
                m.ProductVariant.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")
    if variant.barcode and not force:
        return variant
    variant.barcode = await allocate_barcode(
        db, tenant_id=tenant_id, format=format, exclude_variant_id=variant.id
    )
    await db.flush()
    return variant


def looks_like_barcode_scan(q: str) -> bool:
    """Heuristic: scanner payloads are typically compact codes, not free-text names."""
    text = (q or "").strip()
    if not text or " " in text:
        return False
    if re.fullmatch(r"\d{8,14}", text):
        return True
    if re.fullmatch(r"[A-Za-z0-9\-_.]{6,48}", text) and any(c.isdigit() for c in text):
        return True
    return False
