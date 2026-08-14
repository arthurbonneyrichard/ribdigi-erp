"""Sample print-template preview for Company Document Templates (Stage 119 T1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app import models as m
from app import receipts as receipts_svc
from app import sales as sales_svc
from app.print_branding import tenant_document_brand


SAMPLE_INVOICE: dict[str, Any] = {
    "invoice_number": "INV-SAMPLE-0001",
    "status": "draft",
    "due_date": "2026-08-31",
    "notes": "Sample preview — not a live invoice",
    "currency": None,
    "items": [
        {
            "product_id": "sample-1",
            "quantity": 2,
            "unit_price": 25.0,
            "line_total": 50.0,
        },
        {
            "product_id": "sample-2",
            "quantity": 1,
            "unit_price": 15.5,
            "line_total": 15.5,
        },
    ],
    "subtotal": 65.5,
    "tax_amount": 0,
    "total_amount": 65.5,
}

SAMPLE_RECEIPT: dict[str, Any] = {
    "reference": "POS-SAMPLE-0001",
    "created_at": datetime(2026, 8, 12, 10, 30, 0),
    "cashier_name": "Sample Cashier",
    "customer_name": "Walk-in",
    "subtotal": 40.0,
    "tax": 0.0,
    "discount_amount": 0.0,
    "total": 40.0,
    "payment_method": "cash",
    "payments": [{"payment_method": "cash", "amount": 40.0}],
    "items": [
        {"name": "Sample Item A", "quantity": 1, "unit_price": 25.0, "line_total": 25.0},
        {"name": "Sample Item B", "quantity": 1, "unit_price": 15.0, "line_total": 15.0},
    ],
}


def render_sample_invoice_preview(
    tenant: m.Tenant,
    *,
    company: m.Company | None = None,
    template: str | None = None,
    fmt: str = "html",
) -> tuple[str, str]:
    """Return (media_type, body) for a sample invoice using company/tenant print defaults."""
    doc_brand = tenant_document_brand(tenant, company)
    tpl = (template or doc_brand.get("invoice_print_template") or "a4").strip().lower()
    if tpl not in sales_svc.INVOICE_PRINT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"template must be one of: {sorted(sales_svc.INVOICE_PRINT_TEMPLATES)}",
        )
    fmt_n = (fmt or "html").strip().lower()
    if fmt_n not in {"html", "text"}:
        raise HTTPException(status_code=400, detail="format must be html or text")
    data = dict(SAMPLE_INVOICE)
    data["currency"] = (company.currency if company and company.currency else None) or tenant.currency or "GHS"
    brand = dict(
        company_name=doc_brand["company_name"],
        customer_name="Sample Customer",
        template=tpl,
        currency=data["currency"],
        company_address=doc_brand["company_address"],
        company_phone=doc_brand["company_phone"],
        company_email=doc_brand["company_email"],
        tax_registration_number=doc_brand["tax_registration_number"],
        customer_address="123 Sample Street",
        item_labels={"sample-1": "Sample Widget", "sample-2": "Sample Service"},
        logo_data_url=doc_brand["logo_data_url"],
        trading_name=doc_brand["trading_name"],
        legal_name=doc_brand["legal_name"],
        has_logo=doc_brand["has_logo"],
        document_header=doc_brand["document_header"],
        document_footer=doc_brand["document_footer"],
    )
    if fmt_n == "html":
        return "text/html", sales_svc.render_invoice_html(data, **brand)
    return "text/plain", sales_svc.render_invoice_text(data, **brand)


def render_sample_receipt_preview(
    tenant: m.Tenant,
    *,
    company: m.Company | None = None,
    template: str | None = None,
    fmt: str = "text",
) -> tuple[str, str]:
    """Return (media_type, body) for a sample POS receipt using company/tenant print defaults."""
    doc_brand = tenant_document_brand(tenant, company)
    tpl = (template or doc_brand.get("receipt_print_template") or "thermal_80").strip().lower()
    if tpl not in receipts_svc.RECEIPT_PRINT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"template must be one of: {sorted(receipts_svc.RECEIPT_PRINT_TEMPLATES)}",
        )
    fmt_n = (fmt or "text").strip().lower()
    if fmt_n not in {"html", "text"}:
        raise HTTPException(status_code=400, detail="format must be html or text")
    paper = receipts_svc.RECEIPT_TEMPLATE_TO_PAPER[tpl]
    receipt = dict(SAMPLE_RECEIPT)
    receipt.update(
        {
            "company_name": doc_brand["company_name"],
            "trading_name": doc_brand["trading_name"],
            "company_address": doc_brand["company_address"],
            "company_phone": doc_brand["company_phone"],
            "currency": (company.currency if company and company.currency else None)
            or tenant.currency
            or "GHS",
            "document_header": doc_brand["document_header"],
            "document_footer": doc_brand["document_footer"],
            "has_logo": doc_brand["has_logo"],
            "logo_data_url": doc_brand["logo_data_url"],
            "receipt_print_template": tpl,
            "default_paper": paper,
        }
    )
    text = receipts_svc.render_thermal_text(receipt, paper=paper)
    if fmt_n == "text":
        return "text/plain", text
    from html import escape

    body = escape(text).replace("\n", "<br>")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Receipt sample</title>"
        "<style>body{font:12px/1.35 monospace;white-space:pre-wrap;max-width:80mm;margin:16px}</style>"
        f"</head><body>{body}</body></html>"
    )
    return "text/html", html
