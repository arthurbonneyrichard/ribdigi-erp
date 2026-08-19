"""Printable product barcode labels (PNG / HTML / PDF)."""

from __future__ import annotations

import base64
import io
import zlib
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import barcodes as barcode_svc
from app import models as m

# Code 128B patterns: each value maps to 6 module widths (bar/space alternating), stop is 7.
_CODE128_PATTERNS: dict[int, str] = {
    0: "212222",
    1: "222122",
    2: "222221",
    3: "121223",
    4: "121322",
    5: "131222",
    6: "122213",
    7: "122312",
    8: "132212",
    9: "221213",
    10: "221312",
    11: "231212",
    12: "112232",
    13: "122132",
    14: "122231",
    15: "113222",
    16: "123122",
    17: "123221",
    18: "223211",
    19: "221132",
    20: "221231",
    21: "213212",
    22: "223112",
    23: "312131",
    24: "311222",
    25: "321122",
    26: "321221",
    27: "312212",
    28: "322112",
    29: "322211",
    30: "212123",
    31: "212321",
    32: "232121",
    33: "111323",
    34: "131123",
    35: "131321",
    36: "112313",
    37: "132113",
    38: "132311",
    39: "211313",
    40: "231113",
    41: "231311",
    42: "112133",
    43: "112331",
    44: "132131",
    45: "113123",
    46: "113321",
    47: "133121",
    48: "313121",
    49: "211331",
    50: "231131",
    51: "213113",
    52: "213311",
    53: "213131",
    54: "311123",
    55: "311321",
    56: "331121",
    57: "312113",
    58: "312311",
    59: "332111",
    60: "314111",
    61: "221411",
    62: "431111",
    63: "111224",
    64: "111422",
    65: "121124",
    66: "121421",
    67: "141122",
    68: "141221",
    69: "112214",
    70: "112412",
    71: "122114",
    72: "122411",
    73: "142112",
    74: "142211",
    75: "241211",
    76: "221114",
    77: "413111",
    78: "241112",
    79: "134111",
    80: "111242",
    81: "121142",
    82: "121241",
    83: "114212",
    84: "124112",
    85: "124211",
    86: "411212",
    87: "421112",
    88: "421211",
    89: "212141",
    90: "214121",
    91: "412121",
    92: "111143",
    93: "111341",
    94: "131141",
    95: "114113",
    96: "114311",
    97: "411113",
    98: "411311",
    99: "113141",
    100: "114131",
    101: "311141",
    102: "411131",
    103: "211412",  # Start A
    104: "211214",  # Start B
    105: "211232",  # Start C
    106: "2331112",  # Stop
}

_EAN_L = {
    "0": "0001101",
    "1": "0011001",
    "2": "0010011",
    "3": "0111101",
    "4": "0100011",
    "5": "0110001",
    "6": "0101111",
    "7": "0111011",
    "8": "0110111",
    "9": "0001011",
}
_EAN_G = {
    "0": "0100111",
    "1": "0110011",
    "2": "0011011",
    "3": "0100001",
    "4": "0011101",
    "5": "0111001",
    "6": "0000101",
    "7": "0010001",
    "8": "0001001",
    "9": "0010111",
}
_EAN_R = {
    "0": "1110010",
    "1": "1100110",
    "2": "1101100",
    "3": "1000010",
    "4": "1011100",
    "5": "1001110",
    "6": "1010000",
    "7": "1000100",
    "8": "1001000",
    "9": "1110100",
}
# First-digit parity for EAN-13 left half (L=A, G=B)
_EAN13_PARITY = {
    "0": "LLLLLL",
    "1": "LLGLGG",
    "2": "LLGGLG",
    "3": "LLGGGL",
    "4": "LGLLGG",
    "5": "LGGLLG",
    "6": "LGGGLL",
    "7": "LGLGLG",
    "8": "LGLGGL",
    "9": "LGGLGL",
}


def _code128b_values(text: str) -> list[int]:
    values = [104]  # Start B
    for ch in text:
        code = ord(ch) - 32
        if not 0 <= code <= 95:
            raise HTTPException(status_code=400, detail=f"Unsupported barcode character: {ch!r}")
        values.append(code)
    checksum = values[0]
    for i, v in enumerate(values[1:], start=1):
        checksum += i * v
    values.append(checksum % 103)
    values.append(106)  # Stop
    return values


def _draw_modules(modules: str, *, module_width: int = 2, height: int = 80, quiet: int = 10) -> Image.Image:
    """Draw a binary module string ('0' space / '1' bar) or width-run string of digits."""
    # Detect width-run (Code128) vs binary (EAN)
    if set(modules) <= {"0", "1"}:
        widths = [module_width for _ in modules]
        bits = modules
        total = len(bits) * module_width + quiet * 2 * module_width
        img = Image.new("RGB", (total, height + 4), "white")
        draw = ImageDraw.Draw(img)
        x = quiet * module_width
        for bit in bits:
            w = module_width
            if bit == "1":
                draw.rectangle((x, 2, x + w - 1, height + 1), fill="black")
            x += w
        return img

    # Width-run pattern list joined; interpret as alternating bar/space starting with bar
    runs = [int(c) * module_width for c in modules]
    total = sum(runs) + quiet * 2 * module_width
    img = Image.new("RGB", (total, height + 4), "white")
    draw = ImageDraw.Draw(img)
    x = quiet * module_width
    bar = True
    for w in runs:
        if bar:
            draw.rectangle((x, 2, x + w - 1, height + 1), fill="black")
        x += w
        bar = not bar
    return img


def render_barcode_image(code: str, *, module_width: int = 2, height: int = 70) -> Image.Image:
    fmt = barcode_svc.detect_barcode_format(code)
    if fmt in {"ean13", "upca", "ean8"}:
        return _render_ean_image(code, fmt=fmt, module_width=module_width, height=height)
    # Code 128
    values = _code128b_values(code)
    pattern = "".join(_CODE128_PATTERNS[v] for v in values)
    return _draw_modules(pattern, module_width=module_width, height=height)


def _render_ean_image(code: str, *, fmt: str, module_width: int, height: int) -> Image.Image:
    if fmt == "upca":
        # Encode UPC-A as EAN-13 with leading 0
        body = "0" + code
        return _render_ean_image(body, fmt="ean13", module_width=module_width, height=height)
    if fmt == "ean8":
        bits = "101"
        for d in code[:4]:
            bits += _EAN_L[d]
        bits += "01010"
        for d in code[4:]:
            bits += _EAN_R[d]
        bits += "101"
        return _draw_modules(bits, module_width=module_width, height=height)

    # ean13
    parity = _EAN13_PARITY[code[0]]
    bits = "101"
    for d, p in zip(code[1:7], parity):
        bits += _EAN_G[d] if p == "G" else _EAN_L[d]
    bits += "01010"
    for d in code[7:]:
        bits += _EAN_R[d]
    bits += "101"
    return _draw_modules(bits, module_width=module_width, height=height)


def _font(size: int = 14) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def render_qr_image(code: str, *, box_size: int = 5, border: int = 2) -> Image.Image:
    """Stage 97 I1 — QR encoding of the product barcode/SKU payload."""
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(code)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def render_label_image(
    *,
    name: str,
    sku: str,
    barcode: str,
    price: float | None = None,
    currency: str = "GHS",
    width: int = 400,
    height: int = 220,
    code_type: str = "barcode",
) -> Image.Image:
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = _font(16)
    small_font = _font(12)
    draw.rectangle((1, 1, width - 2, height - 2), outline="black", width=1)

    name_text = (name or "Product")[:42]
    draw.text((12, 10), name_text, fill="black", font=title_font)
    draw.text((12, 34), f"SKU: {sku}", fill="black", font=small_font)
    if price is not None:
        draw.text((12, 52), f"{currency} {float(price):.2f}", fill="black", font=small_font)

    ctype = (code_type or "barcode").strip().lower()
    if ctype == "qr":
        bars = render_qr_image(barcode, box_size=4, border=1)
        max_side = min(width - 24, height - 100)
        if bars.width > max_side or bars.height > max_side:
            bars = bars.resize((max_side, max_side), Image.Resampling.NEAREST)
    else:
        bars = render_barcode_image(barcode, module_width=2, height=70)
        # Fit barcode into label width with margins
        max_bar_w = width - 24
        if bars.width > max_bar_w:
            ratio = max_bar_w / bars.width
            bars = bars.resize((max_bar_w, max(40, int(bars.height * ratio))), Image.Resampling.NEAREST)
    bx = (width - bars.width) // 2
    by = 78
    img.paste(bars, (bx, by))
    # Human-readable code
    code_font = _font(14)
    bbox = draw.textbbox((0, 0), barcode, font=code_font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, by + bars.height + 8), barcode, fill="black", font=code_font)
    return img


def label_png_bytes(**kwargs: Any) -> bytes:
    img = render_label_image(**kwargs)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_labels_html(
    labels: list[dict[str, Any]], *, currency: str = "GHS", code_type: str = "barcode"
) -> str:
    cards: list[str] = []
    for label in labels:
        png = label_png_bytes(
            name=label["name"],
            sku=label["sku"],
            barcode=label["barcode"],
            price=label.get("price"),
            currency=currency,
            code_type=code_type,
        )
        b64 = base64.b64encode(png).decode("ascii")
        copies = max(1, int(label.get("copies") or 1))
        for _ in range(copies):
            cards.append(
                f'<div class="label"><img src="data:image/png;base64,{b64}" alt="{label["barcode"]}"/></div>'
            )
    title = "QR labels" if (code_type or "barcode").strip().lower() == "qr" else "Barcode labels"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>{title}</title>
<style>
  @page {{ margin: 8mm; }}
  body {{ font-family: sans-serif; margin: 0; }}
  .sheet {{ display: flex; flex-wrap: wrap; gap: 4mm; }}
  .label {{ width: 60mm; break-inside: avoid; page-break-inside: avoid; }}
  .label img {{ width: 100%; height: auto; display: block; }}
  .toolbar {{ padding: 12px; }}
  @media print {{ .toolbar {{ display: none; }} }}
</style></head>
<body>
  <div class="toolbar"><button onclick="window.print()">Print labels</button></div>
  <div class="sheet">{"".join(cards)}</div>
</body></html>"""


def build_labels_sheet_png(
    labels: list[dict[str, Any]],
    *,
    currency: str = "GHS",
    cols: int = 3,
    code_type: str = "barcode",
) -> bytes:
    expanded: list[Image.Image] = []
    for label in labels:
        copies = max(1, int(label.get("copies") or 1))
        img = render_label_image(
            name=label["name"],
            sku=label["sku"],
            barcode=label["barcode"],
            price=label.get("price"),
            currency=currency,
            code_type=code_type,
        )
        for _ in range(copies):
            expanded.append(img)
    if not expanded:
        raise HTTPException(status_code=400, detail="No labels to render")
    cols = max(1, min(cols, 4))
    rows = (len(expanded) + cols - 1) // cols
    lw, lh = expanded[0].size
    pad = 12
    sheet = Image.new("RGB", (cols * lw + (cols + 1) * pad, rows * lh + (rows + 1) * pad), "white")
    for i, img in enumerate(expanded):
        r, c = divmod(i, cols)
        sheet.paste(img, (pad + c * (lw + pad), pad + r * (lh + pad)))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def _png_to_pdf(png_bytes: bytes) -> bytes:
    """Wrap a PNG as a single-page PDF (FlateDecode RGB)."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    raw = img.tobytes()
    compressed = zlib.compress(raw, 9)
    # PDF points ≈ pixels for screen-ish print
    page_w, page_h = w, h

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        (
            f"3 0 obj<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /XObject << /Im0 4 0 R >> >> "
            f"/Contents 5 0 R >>endobj\n"
        ).encode("ascii")
    )
    objects.append(
        (
            f"4 0 obj<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(compressed)} >>stream\n"
        ).encode("ascii")
        + compressed
        + b"\nendstream\nendobj\n"
    )
    content = f"q {page_w} 0 0 {page_h} 0 0 cm /Im0 Do Q".encode("ascii")
    objects.append(
        f"5 0 obj<< /Length {len(content)} >>stream\n".encode("ascii") + content + b"\nendstream\nendobj\n"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def build_labels_pdf(
    labels: list[dict[str, Any]], *, currency: str = "GHS", code_type: str = "barcode"
) -> bytes:
    return _png_to_pdf(build_labels_sheet_png(labels, currency=currency, code_type=code_type))


async def resolve_label_targets(
    db: AsyncSession,
    *,
    tenant_id: str,
    items: list[dict[str, Any]],
    company_id: str | None = None,
) -> list[dict[str, Any]]:
    if not items:
        raise HTTPException(status_code=400, detail="At least one label item is required")
    if len(items) > 100:
        raise HTTPException(status_code=400, detail="At most 100 label items per request")

    out: list[dict[str, Any]] = []
    for item in items:
        product_id = item.get("product_id")
        if not product_id:
            raise HTTPException(status_code=400, detail="product_id is required")
        pstmt = select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        if company_id:
            pstmt = pstmt.where(m.Product.company_id == company_id)
        product = (await db.execute(pstmt)).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

        variant_id = item.get("variant_id")
        name = product.name
        sku = product.sku
        barcode = product.barcode
        if variant_id:
            vstmt = select(m.ProductVariant).where(
                m.ProductVariant.id == variant_id,
                m.ProductVariant.tenant_id == tenant_id,
                m.ProductVariant.product_id == product_id,
            )
            if company_id:
                vstmt = vstmt.where(m.ProductVariant.company_id == company_id)
            variant = (await db.execute(vstmt)).scalar_one_or_none()
            if variant is None:
                raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
            name = f"{product.name} — {variant.name}"
            sku = variant.sku or product.sku
            barcode = variant.barcode or product.barcode

        if not barcode:
            raise HTTPException(
                status_code=400,
                detail=f"Product {product.sku} has no barcode; generate one before printing labels",
            )
        barcode_svc.validate_barcode(barcode)
        copies = int(item.get("copies") or 1)
        if copies < 1 or copies > 50:
            raise HTTPException(status_code=400, detail="copies must be between 1 and 50")
        out.append(
            {
                "product_id": product.id,
                "variant_id": variant_id,
                "name": name,
                "sku": sku,
                "barcode": barcode,
                "price": float(product.selling_price or 0),
                "copies": copies,
            }
        )
    return out
