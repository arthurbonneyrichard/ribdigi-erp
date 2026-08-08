"""Purchase invoice attachment OCR (suggest-only; draft apply via PATCH)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import expense_ocr as ocr_svc
from app import models as m
from app import purchasing as purchasing_svc
from app import storage as storage_svc


def map_purchase_suggestions(fields: dict) -> dict:
    """Map generic receipt fields → purchase invoice header suggestions."""
    return {
        "supplier_invoice_number": fields.get("reference") or fields.get("payee"),
        "invoice_date": fields.get("expense_date"),
        "notes": fields.get("description"),
        "ocr_amount": fields.get("amount"),
        "ocr_payee": fields.get("payee"),
    }


async def suggest_for_purchase_invoice(
    db: AsyncSession, *, tenant_id: str, invoice_id: str
) -> dict:
    inv = await purchasing_svc.get_purchase_invoice(db, tenant_id, invoice_id)
    if not inv.attachment_url:
        raise HTTPException(status_code=400, detail="Upload a supplier invoice attachment before OCR")
    if "://" in inv.attachment_url:
        raise HTTPException(status_code=400, detail="External attachment URLs cannot be OCR'd")
    media = storage_svc.read_object(inv.attachment_url, tenant_id=tenant_id)
    result = ocr_svc.suggest_from_media(media)
    mapped = map_purchase_suggestions(result.get("suggestions") or {})
    warnings = list(result.get("warnings") or [])
    ocr_amount = mapped.get("ocr_amount")
    if ocr_amount is not None and abs(float(ocr_amount) - float(inv.total_amount or 0)) > 0.05:
        warnings.append(
            f"OCR amount {ocr_amount} differs from invoice total {float(inv.total_amount):.2f} "
            "(header fields only — line amounts are not auto-changed)"
        )
    return {
        **result,
        "suggestions": mapped,
        "warnings": warnings,
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "invoice_status": inv.status,
        "apply_hint": "Review suggestions then PATCH /purchasing/invoices/{id} while status=draft",
    }


async def update_purchase_invoice_draft(
    db: AsyncSession,
    *,
    tenant_id: str,
    invoice_id: str,
    supplier_invoice_number: str | None = None,
    notes: str | None = None,
    invoice_date: datetime | None = None,
    due_date: datetime | None = None,
) -> m.PurchaseInvoice:
    inv = await purchasing_svc.get_purchase_invoice(db, tenant_id, invoice_id)
    if inv.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Only draft purchase invoices can be edited (status={inv.status})",
        )
    provided = any(
        x is not None for x in (supplier_invoice_number, notes, invoice_date, due_date)
    )
    if not provided:
        raise HTTPException(status_code=400, detail="No invoice fields provided")

    if supplier_invoice_number is not None:
        inv.supplier_invoice_number = supplier_invoice_number.strip() or None
    if notes is not None:
        inv.notes = notes.strip() or None
    if invoice_date is not None:
        inv.invoice_date = invoice_date
    if due_date is not None:
        inv.due_date = due_date
    inv.updated_at = datetime.utcnow()
    await db.flush()
    return inv
