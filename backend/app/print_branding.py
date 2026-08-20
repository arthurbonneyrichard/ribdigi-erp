"""Print branding helpers: logo embed, header/footer, default templates."""

from __future__ import annotations

import io
from typing import Any

from fastapi import HTTPException

from app import models as m

DEFAULT_INVOICE_TEMPLATE = "a4"
DEFAULT_RECEIPT_PAPER = "80mm"
DEFAULT_FOOTER_INVOICE = "Thank you for your business."
DEFAULT_FOOTER_RECEIPT = "Thank you"
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
        current["header_text"] = "" if val is None else str(val).strip()[:200]
    if "footer_text" in payload:
        val = payload["footer_text"]
        current["footer_text"] = "" if val is None else str(val).strip()[:300]
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

        media = storage_svc.read_object(tenant.logo_url, tenant_id=tenant.id)
        img = Image.open(io.BytesIO(media.data))
        img = img.convert("RGB")
        img.thumbnail((max_width_px, max_height_px))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), img.width, img.height
    except Exception:
        return None


def build_text_pdf(
    lines: list[tuple[str, int]],
    *,
    page_width: float,
    page_height: float,
    margin: float = 40,
    mono: bool = False,
    logo: tuple[bytes, int, int] | None = None,
    logo_max_pt: float = 80,
) -> bytes:
    """Minimal single-page PDF with optional JPEG logo and Helvetica/Courier text."""
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

    for text, size in lines:
        font = "F2" if (not mono and size >= 12) else "F1"
        content.append(
            f"BT /{font} {size} Tf {x_text:.2f} {y:.2f} Td ({_pdf_escape(text[:110])}) Tj ET"
        )
        y -= size + (3 if mono else 4)
        if y < margin:
            break

    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")

    if logo:
        jpeg, px_w, px_h = logo
        resources = (
            f"/Font << /F1 5 0 R /F2 6 0 R >> /XObject << /Im1 7 0 R >>"
            if not mono
            else f"/Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >>"
        )
        objects.append(
            (
                f"3 0 obj<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {page_width} {page_height}] "
                f"/Contents 4 0 R /Resources << {resources} >> >>endobj\n"
            ).encode("ascii")
        )
        objects.append(
            f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )
        if mono:
            objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
            objects.append(
                f"6 0 obj<< /Type /XObject /Subtype /Image /Width {px_w} /Height {px_h} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg)} >>stream\n".encode("ascii")
                + jpeg
                + b"\nendstream\nendobj\n"
            )
        else:
            objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
            objects.append(
                b"6 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>endobj\n"
            )
            objects.append(
                f"7 0 obj<< /Type /XObject /Subtype /Image /Width {px_w} /Height {px_h} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg)} >>stream\n".encode("ascii")
                + jpeg
                + b"\nendstream\nendobj\n"
            )
    else:
        if mono:
            objects.append(
                (
                    f"3 0 obj<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {page_width} {page_height}] "
                    f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
                ).encode("ascii")
            )
            objects.append(
                f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
                + stream
                + b"\nendstream\nendobj\n"
            )
            objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
        else:
            objects.append(
                (
                    f"3 0 obj<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {page_width} {page_height}] "
                    f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>endobj\n"
                ).encode("ascii")
            )
            objects.append(
                f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
                + stream
                + b"\nendstream\nendobj\n"
            )
            objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
            objects.append(
                b"6 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>endobj\n"
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
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)
