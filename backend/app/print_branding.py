"""Company branding for printable documents (BR-20.1 / ADR-490 phase 17)."""

from __future__ import annotations

import base64
import logging
from typing import Any

from app import models as m
from app import storage as storage_svc

logger = logging.getLogger(__name__)


def print_templates_for_serialize(
    tenant: m.Tenant | None, company: m.Company | None = None
) -> dict[str, Any]:
    """Prefer company print templates when a company workspace/row is active."""
    if company is not None:
        return {
            "invoice_print_template": (
                getattr(company, "invoice_print_template", None)
                or getattr(tenant, "invoice_print_template", None)
                or "a4"
            ),
            "receipt_print_template": (
                getattr(company, "receipt_print_template", None)
                or getattr(tenant, "receipt_print_template", None)
                or "thermal_80"
            ),
            "document_header": getattr(company, "document_header", None),
            "document_footer": getattr(company, "document_footer", None),
        }
    return {
        "invoice_print_template": getattr(tenant, "invoice_print_template", None) or "a4",
        "receipt_print_template": getattr(tenant, "receipt_print_template", None) or "thermal_80",
        "document_header": getattr(tenant, "document_header", None) if tenant else None,
        "document_footer": getattr(tenant, "document_footer", None) if tenant else None,
    }


def document_company_name(
    tenant: m.Tenant | None, company: m.Company | None = None
) -> str:
    """Prefer legal name on documents; fall back to trading/company name."""
    if company is not None:
        legal = (getattr(company, "legal_name", None) or "").strip()
        if legal:
            return legal
        name = (getattr(company, "name", None) or "").strip()
        if name:
            return name
    if tenant is None:
        return "RIBDIGI ERP"
    legal = (getattr(tenant, "legal_name", None) or "").strip()
    if legal:
        return legal
    return (tenant.company_name or "").strip() or "RIBDIGI ERP"


def trading_name_if_distinct(
    tenant: m.Tenant | None, company: m.Company | None = None
) -> str | None:
    """Trading/company name when different from the document headline (legal name)."""
    if company is not None:
        legal = (getattr(company, "legal_name", None) or "").strip()
        trading = (getattr(company, "name", None) or "").strip()
        if legal and trading and legal.casefold() != trading.casefold():
            return trading
        return None
    if tenant is None:
        return None
    legal = (getattr(tenant, "legal_name", None) or "").strip()
    trading = (tenant.company_name or "").strip()
    if legal and trading and legal.casefold() != trading.casefold():
        return trading
    return None


def load_logo_data_url(
    tenant: m.Tenant | None, company: m.Company | None = None
) -> str | None:
    """Load logo as a data URI for HTML embeds. Prefer company logo when set."""
    logo_key = None
    tenant_id = None
    if company is not None and getattr(company, "logo_url", None):
        logo_key = company.logo_url
        tenant_id = company.tenant_id
    elif tenant is not None and getattr(tenant, "logo_url", None):
        logo_key = tenant.logo_url
        tenant_id = tenant.id
    if not logo_key or not tenant_id:
        return None
    try:
        media = storage_svc.read_object(logo_key, tenant_id=tenant_id)
        if not media.data:
            return None
        b64 = base64.b64encode(media.data).decode("ascii")
        ctype = media.content_type or "image/png"
        return f"data:{ctype};base64,{b64}"
    except Exception:
        logger.warning(
            "Failed to load logo for tenant %s key %s",
            tenant_id,
            logo_key,
            exc_info=True,
        )
        return None


def tenant_document_brand(
    tenant: m.Tenant | None, company: m.Company | None = None
) -> dict[str, Any]:
    """Shared brand fields for invoice/receipt/quotation/credit-note prints.

    When ``company`` is provided (ADR-490 company workspace), prefer company
    profile + print header/footer; tenant remains legacy fallback.
    """
    logo_data_url = load_logo_data_url(tenant, company)
    templates = print_templates_for_serialize(tenant, company)
    header = (templates.get("document_header") or "").strip()
    footer = (templates.get("document_footer") or "").strip()
    if company is not None:
        address = getattr(company, "address", None) or (getattr(tenant, "address", None) if tenant else None)
        phone = getattr(company, "phone", None) or (getattr(tenant, "phone", None) if tenant else None)
        email = getattr(company, "email", None) or (getattr(tenant, "email", None) if tenant else None)
        tax = getattr(company, "tax_registration_number", None) or (
            getattr(tenant, "tax_registration_number", None) if tenant else None
        )
        legal = (getattr(company, "legal_name", None) or "").strip() or None
    else:
        address = getattr(tenant, "address", None) if tenant else None
        phone = getattr(tenant, "phone", None) if tenant else None
        email = (str(getattr(tenant, "email", None) or "") or None) if tenant else None
        tax = getattr(tenant, "tax_registration_number", None) if tenant else None
        legal = (getattr(tenant, "legal_name", None) or "").strip() or None if tenant else None
    return {
        "company_name": document_company_name(tenant, company),
        "legal_name": legal,
        "trading_name": trading_name_if_distinct(tenant, company),
        "company_address": address,
        "company_phone": phone,
        "company_email": (str(email) or None) if email else None,
        "tax_registration_number": tax,
        "has_logo": bool(logo_data_url),
        "logo_data_url": logo_data_url,
        "document_header": header or None,
        "document_footer": footer or None,
        "invoice_print_template": templates["invoice_print_template"],
        "receipt_print_template": templates["receipt_print_template"],
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


# Platform branding on printable documents (invoices, receipts, quotes, POs, etc.)
PLATFORM_PRINT_FOOTER_LINES: tuple[str, ...] = (
    "RIBDIGI ERP",
    "One System. Total Business Control.",
    "A Ribdigi House Product",
)


def platform_print_footer_text_lines(*, width: int = 42, center: bool = False) -> list[str]:
    """Monospace platform footer lines for text / thermal / PDF-from-text prints."""

    def _fit(line: str) -> str:
        text = line if len(line) <= width else line[:width]
        if not center:
            return text
        pad = max(0, width - len(text))
        left = pad // 2
        return (" " * left) + text

    return ["", *(_fit(line) for line in PLATFORM_PRINT_FOOTER_LINES)]


def platform_print_footer_html() -> str:
    """HTML platform footer block appended below tenant document_footer on print views."""
    from html import escape

    body = "<br>".join(escape(line) for line in PLATFORM_PRINT_FOOTER_LINES)
    return (
        '<footer class="platform-footer" style="margin-top:32px;padding-top:14px;'
        "border-top:1px solid #d6d3d1;text-align:center;color:#57534e;font-size:0.85rem;"
        f'line-height:1.45">{body}</footer>'
    )


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
