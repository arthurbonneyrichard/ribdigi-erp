"""Print branding helpers: logo embed, header/footer, default templates."""

from __future__ import annotations

import io
from typing import Any

from fastapi import HTTPException

from app import models as m
from app.honesty import optional_honest_narrative

DEFAULT_INVOICE_TEMPLATE = "a4"
DEFAULT_RECEIPT_PAPER = "80mm"
DEFAULT_FOOTER_INVOICE = "Thank you for your business."
DEFAULT_FOOTER_RECEIPT = "Thank you"
# Logo leaf / CSS --brand (#4AB012) as PDF device RGB (0–1).
BRAND_GREEN_RGB: tuple[float, float, float] = (0.290, 0.690, 0.071)
# CSS --forest (#003D1F) as PDF device RGB (0–1).
FOREST_RGB: tuple[float, float, float] = (0.000, 0.239, 0.122)
# CSS --ink (#10211B) as PDF device RGB (0–1).
INK_RGB: tuple[float, float, float] = (0.063, 0.129, 0.106)
POWERED_BY_RIBDIGI = "Powered by RIBDIGI ERP"

# Shared HTML chrome for email / browser document tables (inline styles for clients).
DOC_TABLE_STYLE = (
    "border-collapse:collapse;width:100%;margin:16px 0;"
    "font-family:Arial,Helvetica,sans-serif;font-size:13px;"
)
DOC_TH_STYLE = (
    "background:#003d1f;color:#ffffff;text-align:left;padding:10px 12px;"
    "font-weight:700;border:0;"
)
DOC_TD_STYLE = "padding:9px 12px;border-bottom:1px solid #d4e5c4;color:#10211b;vertical-align:top;"
DOC_TD_RIGHT = DOC_TD_STYLE + "text-align:right;white-space:nowrap;"
DOC_TOTALS_STYLE = (
    "margin:8px 0 0;padding:14px 16px;background:#f2f7ec;border:1px solid #d4e5c4;"
    "border-radius:8px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.55;"
)
DOC_META_STYLE = (
    "margin:0 0 12px;padding:12px 14px;background:#f5f7ec;border-left:3px solid #4ab012;"
    "font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:#10211b;"
)


def document_table_html(*, headers: list[str], rows_html: str) -> str:
    """Brand-styled line-item table for email / printable HTML bodies."""
    import html as html_mod

    ths = "".join(
        f'<th style="{DOC_TH_STYLE}">{html_mod.escape(h)}</th>' for h in headers
    )
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" style="{DOC_TABLE_STYLE}">'
        f"<thead><tr>{ths}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )


def document_print_shell(
    *,
    title: str,
    company_name: str,
    body_html: str,
    subtitle: str | None = None,
) -> str:
    """Browser-printable HTML document with forest header + brand accent."""
    import html as html_mod

    company_esc = html_mod.escape(company_name or "RIBDIGI ERP")
    title_esc = html_mod.escape(title)
    sub_html = (
        f'<p class="doc-sub">{html_mod.escape(subtitle)}</p>' if subtitle else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title_esc}</title>
<style>
  :root {{
    --brand: #4ab012; --forest: #003d1f; --ink: #10211b; --muted: #4d5d56;
    --line: #d4e5c4; --mist: #f2f7ec; --sand: #f5f7ec;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; color: var(--ink);
    font-family: "Segoe UI", Arial, Helvetica, sans-serif;
    background: linear-gradient(180deg, #e8f2df 0%, #f5f7ec 40%, #fff 100%);
  }}
  .toolbar {{
    position: sticky; top: 0; z-index: 2;
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 12px 18px; background: var(--forest); color: #fff;
    border-bottom: 3px solid var(--brand);
  }}
  .toolbar button {{
    background: var(--brand); color: #fff; border: 0; border-radius: 8px;
    padding: 10px 16px; font-weight: 700; cursor: pointer;
  }}
  .sheet {{
    max-width: 820px; margin: 24px auto; padding: 0 16px 40px;
  }}
  .card {{
    background: #fff; border: 1px solid var(--line); border-radius: 12px;
    overflow: hidden; box-shadow: 0 8px 24px rgba(0, 61, 31, 0.06);
  }}
  .doc-head {{
    padding: 22px 28px; background: var(--forest); color: #fff;
    border-bottom: 3px solid var(--brand);
  }}
  .doc-head h1 {{
    margin: 0; font-size: 22px; letter-spacing: .02em; font-weight: 800;
  }}
  .doc-sub {{ margin: 6px 0 0; color: #c8e86a; font-size: 13px; }}
  .doc-body {{ padding: 24px 28px; }}
  .doc-body h2 {{
    margin: 0 0 12px; font-size: 15px; text-transform: uppercase;
    letter-spacing: .08em; color: var(--forest);
  }}
  table.doc {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 13px; }}
  table.doc th {{
    background: var(--forest); color: #fff; text-align: left;
    padding: 10px 12px; font-weight: 700;
  }}
  table.doc td {{
    padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top;
  }}
  table.doc td.r {{ text-align: right; white-space: nowrap; }}
  .meta {{
    margin: 0 0 16px; padding: 12px 14px; background: var(--sand);
    border-left: 3px solid var(--brand); font-size: 13px; line-height: 1.5;
  }}
  .totals {{
    margin: 8px 0 0; padding: 14px 16px; background: var(--mist);
    border: 1px solid var(--line); border-radius: 8px; font-size: 13px; line-height: 1.55;
  }}
  .totals strong {{ color: var(--forest); font-size: 15px; }}
  .foot {{
    margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--line);
    color: var(--muted); font-size: 12px; text-align: center;
  }}
  .powered {{ color: var(--brand); font-weight: 700; font-size: 11px; margin-top: 6px; }}
  @media print {{
    body {{ background: #fff; }}
    .toolbar {{ display: none; }}
    .sheet {{ margin: 0; max-width: none; padding: 0; }}
    .card {{ box-shadow: none; border: 0; border-radius: 0; }}
  }}
</style>
</head>
<body>
  <div class="toolbar">
    <div>{company_esc}</div>
    <button type="button" onclick="window.print()">Print</button>
  </div>
  <div class="sheet"><div class="card">
    <div class="doc-head"><h1>{title_esc}</h1>{sub_html}</div>
    <div class="doc-body">{body_html}</div>
  </div></div>
</body></html>"""


def style_powered_by_line(
    text: str,
    size: int = 8,
) -> tuple[str, int] | tuple[str, int, tuple[float, float, float]]:
    """Paint the shared 'Powered by RIBDIGI ERP' footer in brand green when matched."""
    raw = (text or "").strip()
    if raw == POWERED_BY_RIBDIGI:
        return (POWERED_BY_RIBDIGI, size, BRAND_GREEN_RGB)
    return (text, size)


INVOICE_TEMPLATES = frozenset({"a4", "thermal"})
RECEIPT_PAPERS = frozenset({"58mm", "80mm"})


def coerce_invoice_template_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def coerce_receipt_paper_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/lowercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def print_branding_settings(tenant: m.Tenant | None) -> dict[str, Any]:
    raw = (getattr(tenant, "print_branding", None) or {}) if tenant else {}
    if not isinstance(raw, dict):
        raw = {}
    header = str(raw.get("header_text") or "").strip()
    footer = str(raw.get("footer_text") or "").strip()
    inv = str(raw.get("default_invoice_template") or DEFAULT_INVOICE_TEMPLATE).lower()
    if inv not in INVOICE_TEMPLATES:
        inv = DEFAULT_INVOICE_TEMPLATE
    paper = str(raw.get("default_receipt_paper") or DEFAULT_RECEIPT_PAPER).lower()
    if paper not in RECEIPT_PAPERS:
        paper = DEFAULT_RECEIPT_PAPER
    return {
        "header_text": header,
        "footer_text": footer,
        "default_invoice_template": inv,
        "default_receipt_paper": paper,
        "has_logo": bool(getattr(tenant, "logo_url", None) if tenant else None),
    }


def apply_print_branding_update(tenant: m.Tenant, payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(getattr(tenant, "print_branding", None) or {})
    # Key present + null → clear; key present + value → set (schema already validated).
    if "header_text" in payload:
        val = payload["header_text"]
        if val is None:
            current["header_text"] = ""
        else:
            cleaned = optional_honest_narrative(
                val, label="print header text", max_length=200
            )
            current["header_text"] = cleaned or ""
    if "footer_text" in payload:
        val = payload["footer_text"]
        if val is None:
            current["footer_text"] = ""
        else:
            cleaned = optional_honest_narrative(
                val, label="print footer text", max_length=300
            )
            current["footer_text"] = cleaned or ""
    if payload.get("default_invoice_template") is not None:
        # Defense in depth: PrintBrandingUpdate Literal rejects blank/unknown with 422.
        # Read path still coerces garbage to a4 silently.
        inv = str(payload["default_invoice_template"]).lower().strip()
        if inv not in INVOICE_TEMPLATES:
            raise HTTPException(status_code=400, detail="default_invoice_template must be a4 or thermal")
        current["default_invoice_template"] = inv
    if payload.get("default_receipt_paper") is not None:
        paper = str(payload["default_receipt_paper"]).lower().strip()
        if paper not in RECEIPT_PAPERS:
            raise HTTPException(status_code=400, detail="default_receipt_paper must be 58mm or 80mm")
        current["default_receipt_paper"] = paper
    tenant.print_branding = current
    return print_branding_settings(tenant)


def branding_fields_for_payload(tenant: m.Tenant | None) -> dict[str, Any]:
    cfg = print_branding_settings(tenant)
    return {
        "print_header": cfg["header_text"] or None,
        "print_footer": cfg["footer_text"] or None,
        "has_logo": cfg["has_logo"],
        "default_invoice_template": cfg["default_invoice_template"],
        "default_receipt_paper": cfg["default_receipt_paper"],
    }


def load_logo_jpeg(
    tenant: m.Tenant | None,
    *,
    max_width_px: int = 360,
    max_height_px: int = 120,
) -> tuple[bytes, int, int] | None:
    """Return (jpeg_bytes, width_px, height_px) or None if unavailable."""
    if not tenant or not getattr(tenant, "logo_url", None):
        return None
    try:
        from PIL import Image

        from app import storage as storage_svc
        from app.logo_media import _open_image, flatten_on_white

        media = storage_svc.read_object(tenant.logo_url, tenant_id=tenant.id)
        img = flatten_on_white(_open_image(media.data))
        img.thumbnail((max_width_px, max_height_px), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), img.width, img.height
    except Exception:
        return None


def _pdf_font_objects(*, mono: bool, bold: bool) -> tuple[bytes, bytes]:
    if mono:
        regular = b"/Courier-Bold" if bold else b"/Courier"
        heavy = b"/Courier-Bold"
    else:
        regular = b"/Helvetica-Bold" if bold else b"/Helvetica"
        heavy = b"/Helvetica-Bold"
    f1 = b"<< /Type /Font /Subtype /Type1 /BaseFont " + regular + b" >>"
    f2 = b"<< /Type /Font /Subtype /Type1 /BaseFont " + heavy + b" >>"
    return f1, f2


def build_text_pdf(
    lines: list[tuple[str, int] | tuple[str, int, tuple[float, float, float]]],
    *,
    page_width: float,
    page_height: float,
    margin: float = 40,
    mono: bool = False,
    bold: bool = False,
    logo: tuple[bytes, int, int] | None = None,
    logo_max_pt: float = 80,
) -> bytes:
    """Minimal single-page PDF with optional JPEG logo and Helvetica/Courier text.

    Each line is ``(text, font_size)`` or ``(text, font_size, rgb)`` where ``rgb`` is
    0–1 floats (e.g. brand green for the Powered-by footer).
    """
    from app.report_export import _pdf_escape

    content: list[str] = []
    y = page_height - margin
    x_text = margin

    if logo:
        jpeg, px_w, px_h = logo
        scale = min(logo_max_pt / max(px_w, 1), logo_max_pt / max(px_h, 1), 1.0)
        draw_w = px_w * scale
        draw_h = px_h * scale
        y_img = y - draw_h
        content.append(
            f"q {draw_w:.2f} 0 0 {draw_h:.2f} {margin:.2f} {y_img:.2f} cm /Im1 Do Q"
        )
        y = y_img - 10

    for entry in lines:
        text_line = entry[0]
        size = int(entry[1])
        rgb = entry[2] if len(entry) >= 3 else None
        if y < margin + size:
            break
        if text_line:
            font = "/F1" if mono else ("/F2" if size >= 14 else "/F1")
            escaped = _pdf_escape(text_line)
            if rgb is not None:
                r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
                content.append(
                    f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg "
                    f"{x_text:.1f} {y - size:.1f} Td ({escaped}) Tj 0 0 0 rg ET"
                )
            else:
                content.append(
                    f"BT {font} {size} Tf {x_text:.1f} {y - size:.1f} Td ({escaped}) Tj ET"
                )
        y -= size + 4

    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects: list[bytes] = []

    def obj(n: int, body: bytes) -> None:
        objects.append(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")

    if logo:
        jpeg, _, _ = logo
        obj(
            1,
            b"<< /Type /Catalog /Pages 2 0 R >>",
        )
        obj(
            2,
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        )
        obj(
            3,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> "
                f"/XObject << /Im1 7 0 R >> >> >>"
            ).encode(),
        )
        obj(4, f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        f1, f2 = _pdf_font_objects(mono=mono, bold=bold)
        obj(5, f1)
        obj(6, f2)
        obj(
            7,
            (
                f"<< /Type /XObject /Subtype /Image /Width {logo[1]} /Height {logo[2]} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg)} >>\nstream\n"
            ).encode()
            + jpeg
            + b"\nendstream",
        )
        n_objs = 7
    else:
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        obj(
            3,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>"
            ).encode(),
        )
        obj(4, f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        f1, f2 = _pdf_font_objects(mono=mono, bold=bold)
        obj(5, f1)
        obj(6, f2)
        n_objs = 6

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, o in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(o)
    xref_pos = len(out)
    out.extend(f"xref\n0 {n_objs + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {n_objs + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)
