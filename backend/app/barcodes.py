"""Product barcode generation and label rendering (Code 128)."""

from __future__ import annotations

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


def normalize_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    if not BARCODE_PATTERN.match(code):
        raise HTTPException(
            status_code=400,
            detail="Barcode must be 4–48 characters (letters, numbers, - . _)",
        )
    return code


def looks_like_barcode(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if " " in text:
        return False
    return bool(BARCODE_PATTERN.match(text))


def render_code128_png(code: str, *, module_height: float = 14.0) -> bytes:
    buf = io.BytesIO()
    writer = ImageWriter()
    barcode.get("code128", code, writer=writer).write(
        buf,
        options={
            "write_text": True,
            "module_height": module_height,
            "module_width": 0.35,
            "quiet_zone": 2.5,
            "font_size": 10,
            "text_distance": 4.0,
            "dpi": 200,
        },
    )
    return buf.getvalue()


def suggest_barcode_from_sku(sku: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9\-._]", "", (sku or "").strip().upper())
    if len(raw) < 4:
        raw = f"SKU-{raw or 'ITEM'}"
    return raw[:48]


async def assert_barcode_unique(
    db: AsyncSession,
    *,
    tenant_id: str,
    barcode_value: str,
    exclude_product_id: str | None = None,
) -> None:
    stmt = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.barcode == barcode_value,
    )
    if exclude_product_id:
        stmt = stmt.where(m.Product.id != exclude_product_id)
    clash = (await db.execute(stmt)).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="Barcode already assigned to another product")


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
) -> str:
    copies = max(1, min(int(copies or 1), 40))
    price_txt = f"{currency} {price:,.2f}"
    cards = []
    for _ in range(copies):
        cards.append(
            f"""
            <div class="label">
              <div class="co">{html.escape(company_name)}</div>
              <div class="name">{html.escape(product_name)}</div>
              <div class="price">{html.escape(price_txt)}</div>
              <img src="{png_data_uri}" alt="barcode"/>
              <div class="meta">SKU {html.escape(sku)} · {html.escape(barcode_value)}</div>
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
