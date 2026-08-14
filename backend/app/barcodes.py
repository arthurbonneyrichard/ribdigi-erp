"""Product barcode generation and label rendering (Code 128, EAN-13, UPC-A)."""

from __future__ import annotations

import hashlib
import html
import io
import re
from datetime import datetime

import barcode
from barcode.writer import ImageWriter
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

# Scanners / labels: Code128 accepts alphanumeric SKUs and retail codes.
BARCODE_PATTERN = re.compile(r"^[A-Za-z0-9\-._]{4,48}$")
SYMBOLOGIES = frozenset({"code128", "ean13", "upca"})
# In-store / internal GTIN prefixes (not a GS1 company prefix).
EAN13_INTERNAL_PREFIX = "200"
UPCA_INTERNAL_PREFIX = "2"


def normalize_symbology(value: str | None) -> str:
    key = (value or "code128").strip().lower()
    if key not in SYMBOLOGIES:
        raise HTTPException(
            status_code=400,
            detail=f"symbology must be one of {sorted(SYMBOLOGIES)}",
        )
    return key


def ean13_check_digit(body12: str) -> str:
    if not body12.isdigit() or len(body12) != 12:
        raise ValueError("EAN-13 body must be 12 digits")
    total = 0
    for i, ch in enumerate(body12):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return str((10 - (total % 10)) % 10)


def upca_check_digit(body11: str) -> str:
    if not body11.isdigit() or len(body11) != 11:
        raise ValueError("UPC-A body must be 11 digits")
    total = 0
    for i, ch in enumerate(body11):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - (total % 10)) % 10)


def validate_ean13(code: str) -> str:
    digits = str(code).strip()
    if not digits.isdigit() or len(digits) != 13:
        raise HTTPException(status_code=400, detail="EAN-13 must be exactly 13 digits")
    expected = ean13_check_digit(digits[:12])
    if digits[12] != expected:
        raise HTTPException(status_code=400, detail="EAN-13 check digit is invalid")
    return digits


def validate_upca(code: str) -> str:
    digits = str(code).strip()
    if not digits.isdigit() or len(digits) != 12:
        raise HTTPException(status_code=400, detail="UPC-A must be exactly 12 digits")
    expected = upca_check_digit(digits[:11])
    if digits[11] != expected:
        raise HTTPException(status_code=400, detail="UPC-A check digit is invalid")
    return digits


def normalize_barcode(value: str | None, *, symbology: str | None = None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    sym = normalize_symbology(symbology) if symbology else None
    if sym == "ean13":
        return validate_ean13(raw)
    if sym == "upca":
        return validate_upca(raw)

    code = raw.upper()
    if not BARCODE_PATTERN.match(code):
        raise HTTPException(
            status_code=400,
            detail="Barcode must be 4–48 characters (letters, numbers, - . _)",
        )
    # Auto-validate retail GTINs when pasted as digits.
    if code.isdigit() and len(code) == 13:
        return validate_ean13(code)
    if code.isdigit() and len(code) == 12:
        return validate_upca(code)
    return code


def detect_symbology(code: str | None) -> str:
    if not code:
        return "code128"
    text = str(code).strip()
    if text.isdigit() and len(text) == 13:
        try:
            validate_ean13(text)
            return "ean13"
        except HTTPException:
            return "code128"
    if text.isdigit() and len(text) == 12:
        try:
            validate_upca(text)
            return "upca"
        except HTTPException:
            return "code128"
    return "code128"


def looks_like_barcode(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if " " in text:
        return False
    return bool(BARCODE_PATTERN.match(text))


def render_barcode_png(code: str, *, symbology: str | None = None, module_height: float = 14.0) -> bytes:
    sym = normalize_symbology(symbology) if symbology else detect_symbology(code)
    if sym == "ean13":
        code = validate_ean13(code)
        # python-barcode EAN13 expects 12 digits (adds check) or valid 13.
        payload = code[:12]
        barcode_name = "ean13"
    elif sym == "upca":
        code = validate_upca(code)
        payload = code[:11]
        barcode_name = "upca"
    else:
        payload = str(code)
        barcode_name = "code128"

    buf = io.BytesIO()
    writer = ImageWriter()
    try:
        barcode.get(barcode_name, payload, writer=writer).write(
            buf,
            options={
                "write_text": True,
                "module_height": module_height,
                "module_width": 0.35 if sym == "code128" else 0.4,
                "quiet_zone": 2.5,
                "font_size": 10,
                "text_distance": 4.0,
                "dpi": 200,
            },
        )
    except Exception as exc:  # noqa: BLE001 — surface as 400 for bad GTIN/render
        raise HTTPException(status_code=400, detail=f"Could not render {sym} barcode: {exc}") from exc
    return buf.getvalue()


def render_code128_png(code: str, *, module_height: float = 14.0) -> bytes:
    """Back-compat wrapper."""
    return render_barcode_png(code, symbology="code128", module_height=module_height)


def suggest_barcode_from_sku(sku: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9\-._]", "", (sku or "").strip().upper())
    if len(raw) < 4:
        raw = f"SKU-{raw or 'ITEM'}"
    return raw[:48]


def _digit_run(seed: str, *, length: int, attempt: int) -> str:
    digest = hashlib.sha256(f"{seed}:{attempt}".encode()).hexdigest()
    digits = "".join(ch for ch in digest if ch.isdigit())
    # Mix hex letters as 0-9 via ord for enough digits.
    if len(digits) < length:
        extra = "".join(str(ord(ch) % 10) for ch in digest)
        digits += extra
    return (digits + "0" * length)[:length]


def suggest_ean13(*, seed: str, attempt: int = 0) -> str:
    body = f"{EAN13_INTERNAL_PREFIX}{_digit_run(seed, length=9, attempt=attempt)}"
    return body + ean13_check_digit(body)


def suggest_upca(*, seed: str, attempt: int = 0) -> str:
    body = f"{UPCA_INTERNAL_PREFIX}{_digit_run(seed, length=10, attempt=attempt)}"
    return body + upca_check_digit(body)


def suggest_barcode(
    sku: str,
    *,
    symbology: str = "code128",
    seed: str | None = None,
    attempt: int = 0,
) -> str:
    sym = normalize_symbology(symbology)
    if sym == "ean13":
        return suggest_ean13(seed=seed or sku, attempt=attempt)
    if sym == "upca":
        return suggest_upca(seed=seed or sku, attempt=attempt)
    base = suggest_barcode_from_sku(sku)
    if attempt == 0:
        return base
    return f"{base[:40]}-{attempt}"


async def assert_barcode_unique(
    db: AsyncSession,
    *,
    tenant_id: str,
    barcode_value: str,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> None:
    """Ensure barcode is unique across products and variants in the tenant."""
    pstmt = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.barcode == barcode_value,
    )
    if exclude_product_id:
        pstmt = pstmt.where(m.Product.id != exclude_product_id)
    if (await db.execute(pstmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Barcode already assigned to another product"
        )

    vstmt = select(m.ProductVariant).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.barcode == barcode_value,
    )
    if exclude_variant_id:
        vstmt = vstmt.where(m.ProductVariant.id != exclude_variant_id)
    if (await db.execute(vstmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Barcode already assigned to another variant"
        )


async def allocate_unique_barcode(
    db: AsyncSession,
    *,
    tenant_id: str,
    sku: str,
    symbology: str,
    seed: str,
    exclude_product_id: str | None = None,
    exclude_variant_id: str | None = None,
) -> str:
    sym = normalize_symbology(symbology)
    for i in range(0, 50):
        try_code = suggest_barcode(sku, symbology=sym, seed=seed, attempt=i)
        try_code = normalize_barcode(try_code, symbology=sym)
        assert try_code
        try:
            await assert_barcode_unique(
                db,
                tenant_id=tenant_id,
                barcode_value=try_code,
                exclude_product_id=exclude_product_id,
                exclude_variant_id=exclude_variant_id,
            )
            return try_code
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
    raise HTTPException(status_code=409, detail="Could not allocate a unique barcode")


def label_html(
    *,
    company_name: str,
    product_name: str,
    sku: str,
    barcode_value: str,
    price: float,
    currency: str,
    png_data_uri: str,
    copies: int = 1,
    symbology: str | None = None,
) -> str:
    copies = max(1, min(int(copies or 1), 40))
    price_txt = f"{currency} {price:,.2f}"
    sym = normalize_symbology(symbology) if symbology else detect_symbology(barcode_value)
    cards = []
    for _ in range(copies):
        cards.append(
            f"""
            <div class="label">
              <div class="co">{html.escape(company_name)}</div>
              <div class="name">{html.escape(product_name)}</div>
              <div class="price">{html.escape(price_txt)}</div>
              <img src="{png_data_uri}" alt="barcode"/>
              <div class="meta">{html.escape(sym.upper())} · SKU {html.escape(sku)} · {html.escape(barcode_value)}</div>
            </div>
            """
        )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Barcode labels — {html.escape(product_name)}</title>
  <style>
    @page {{ margin: 8mm; }}
    body {{ font-family: Arial, sans-serif; margin: 0; color: #0f172a; }}
    .sheet {{ display: flex; flex-wrap: wrap; gap: 8mm; padding: 4mm; }}
    .label {{
      width: 60mm; min-height: 40mm; border: 1px solid #cbd5e1; border-radius: 4mm;
      padding: 3mm; box-sizing: border-box; page-break-inside: avoid;
      display: flex; flex-direction: column; align-items: center; gap: 1.5mm;
    }}
    .co {{ font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }}
    .name {{ font-size: 12px; font-weight: 800; text-align: center; line-height: 1.2; }}
    .price {{ font-size: 14px; font-weight: 800; }}
    img {{ width: 100%; max-width: 54mm; height: auto; }}
    .meta {{ font-size: 9px; color: #475569; text-align: center; word-break: break-all; }}
    .toolbar {{
      position: sticky; top: 0; background: #0f172a; color: #fff; padding: 10px 14px;
      display: flex; justify-content: space-between; align-items: center; gap: 12px;
    }}
    .toolbar button {{
      background: #0f766e; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px;
      font-weight: 700; cursor: pointer;
    }}
    @media print {{ .toolbar {{ display: none; }} body {{ background: #fff; }} }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div>
      <strong>Barcode labels</strong>
      <span style="opacity:.8;font-size:12px;margin-left:8px">Printed {html.escape(datetime.utcnow().strftime("%Y-%m-%d %H:%M"))}</span>
    </div>
    <button onclick="window.print()">Print labels</button>
  </div>
  <div class="sheet">
    {"".join(cards)}
  </div>
  <script>window.addEventListener('load', () => {{ /* ready for print */ }});</script>
</body>
</html>"""
