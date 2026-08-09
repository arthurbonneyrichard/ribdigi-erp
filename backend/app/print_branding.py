"""Company branding for printable documents (BR-20.1)."""

from __future__ import annotations

import base64
import logging
from typing import Any

from app import models as m
from app import storage as storage_svc

logger = logging.getLogger(__name__)


def document_company_name(tenant: m.Tenant | None) -> str:
    """Prefer legal name on documents; fall back to trading/company name."""
    if tenant is None:
        return "RIBDIGI ERP"
    legal = (getattr(tenant, "legal_name", None) or "").strip()
    if legal:
        return legal
    return (tenant.company_name or "").strip() or "RIBDIGI ERP"


def trading_name_if_distinct(tenant: m.Tenant | None) -> str | None:
    """Trading/company name when different from the document headline (legal name)."""
    if tenant is None:
        return None
    legal = (getattr(tenant, "legal_name", None) or "").strip()
    trading = (tenant.company_name or "").strip()
    if legal and trading and legal.casefold() != trading.casefold():
        return trading
    return None


def load_logo_data_url(tenant: m.Tenant | None) -> str | None:
    """Load tenant logo as a data URI for HTML embeds. Soft-fails if missing/unreadable."""
    if tenant is None or not getattr(tenant, "logo_url", None):
        return None
    try:
        media = storage_svc.read_object(tenant.logo_url, tenant_id=tenant.id)
        if not media.data:
            return None
        b64 = base64.b64encode(media.data).decode("ascii")
        ctype = media.content_type or "image/png"
        return f"data:{ctype};base64,{b64}"
    except Exception:
        logger.warning(
            "Failed to load logo for tenant %s key %s",
            getattr(tenant, "id", None),
            getattr(tenant, "logo_url", None),
            exc_info=True,
        )
        return None


def tenant_document_brand(tenant: m.Tenant | None) -> dict[str, Any]:
    """Shared brand fields for invoice/receipt/quotation/credit-note prints."""
    logo_data_url = load_logo_data_url(tenant)
    header = (getattr(tenant, "document_header", None) or "").strip() if tenant else ""
    footer = (getattr(tenant, "document_footer", None) or "").strip() if tenant else ""
    return {
        "company_name": document_company_name(tenant),
        "legal_name": (getattr(tenant, "legal_name", None) or "").strip() or None if tenant else None,
        "trading_name": trading_name_if_distinct(tenant),
        "company_address": getattr(tenant, "address", None) if tenant else None,
        "company_phone": getattr(tenant, "phone", None) if tenant else None,
        "company_email": (str(getattr(tenant, "email", None) or "") or None) if tenant else None,
        "tax_registration_number": getattr(tenant, "tax_registration_number", None) if tenant else None,
        "has_logo": bool(logo_data_url),
        "logo_data_url": logo_data_url,
        "document_header": header or None,
        "document_footer": footer or None,
    }


def header_footer_text_lines(text: str | None, width: int) -> list[str]:
    """Wrap optional header/footer for monospace thermal/A4 text layouts."""
    raw = (text or "").strip()
    if not raw:
        return []
    lines: list[str] = []
    for paragraph in raw.splitlines() or [raw]:
        para = paragraph.strip()
        if not para:
            continue
        while len(para) > width:
            cut = para.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = width
            lines.append(para[:cut].rstrip())
            para = para[cut:].lstrip()
        if para:
            lines.append(para)
    return lines


def header_footer_html(text: str | None, *, css_class: str) -> str:
    """Escaped HTML block for document header/footer customization."""
    from html import escape

    raw = (text or "").strip()
    if not raw:
        return ""
    body = "<br>".join(escape(line) for line in raw.splitlines() if line.strip())
    if not body:
        return ""
    return f'<p class="{css_class} muted">{body}</p>'


def brand_html_block(
    *,
    company_name: str,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    meta_html: str = "",
) -> str:
    """HTML fragment for the document brand header (logo + name + meta)."""
    from html import escape

    logo_html = ""
    if logo_data_url and logo_data_url.startswith("data:image/"):
        logo_html = (
            f'<img class="logo" src="{escape(logo_data_url, quote=True)}" '
            f'alt="{escape(company_name)} logo" />'
        )
    trading_html = (
        f'<div class="muted trading">Trading as {escape(trading_name)}</div>'
        if trading_name
        else ""
    )
    meta = f'<div class="muted">{meta_html}</div>' if meta_html else ""
    return (
        f'<div class="brand">{logo_html}'
        f"<h1>{escape(company_name)}</h1>"
        f"{trading_html}{meta}</div>"
    )
