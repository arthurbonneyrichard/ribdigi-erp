"""AI document assistant (Phase 4 / BR-21.8).

Wraps existing receipt/invoice OCR, auto-matches extracted fields to tenant
parties/products, and flags discrepancies — suggest-only, no silent writes.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import expense_ocr as expense_ocr_svc
from app import models as m
from app import storage as storage_svc
from app.ai_expenses import suggest_category_from_text
from app.reports import apply_company_filter


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


async def _match_party(
    db: AsyncSession,
    tenant_id: str,
    *,
    kind: str,
    payee: str | None,
    company_id: str | None = None,
) -> dict | None:
    if not payee:
        return None
    needle = _norm(payee)
    if len(needle) < 2:
        return None
    stmt = select(m.Party).where(
        m.Party.tenant_id == tenant_id,
        m.Party.kind == kind,
    )
    stmt = apply_company_filter(stmt, m.Party.company_id, company_id)
    parties = (await db.execute(stmt)).scalars().all()
    exact = [p for p in parties if _norm(p.name) == needle]
    if exact:
        p = exact[0]
        return {"id": p.id, "name": p.name, "kind": kind, "match": "exact", "confidence": 0.95}
    partial = [p for p in parties if needle in _norm(p.name) or _norm(p.name) in needle]
    if partial:
        p = partial[0]
        return {"id": p.id, "name": p.name, "kind": kind, "match": "partial", "confidence": 0.7}
    return None


async def _match_products(
    db: AsyncSession,
    tenant_id: str,
    text: str,
    company_id: str | None = None,
) -> list[dict]:
    stmt = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.is_active == True,  # noqa: E712
    )
    stmt = apply_company_filter(stmt, m.Product.company_id, company_id)
    products = (await db.execute(stmt)).scalars().all()
    hay = _norm(text)
    hits = []
    for p in products:
        for token in filter(None, [_norm(p.sku), _norm(p.name)]):
            if len(token) >= 3 and token in hay:
                hits.append(
                    {
                        "id": p.id,
                        "sku": p.sku,
                        "name": p.name,
                        "match": "sku" if token == _norm(p.sku) else "name",
                        "confidence": 0.8 if token == _norm(p.sku) else 0.6,
                    }
                )
                break
    return hits[:20]


async def analyze_document(
    db: AsyncSession,
    tenant_id: str,
    *,
    upload: UploadFile,
    document_type: str = "receipt",
    company_id: str | None = None,
) -> dict:
    doc_type = (document_type or "receipt").strip().lower()
    if doc_type not in {"receipt", "expense", "invoice", "purchase_order", "purchase", "po"}:
        raise HTTPException(
            status_code=400,
            detail="document_type must be receipt|expense|invoice|purchase_order",
        )

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 8MB)")

    media = storage_svc.MediaObject(
        key="inline",
        data=data,
        content_type=upload.content_type or "application/octet-stream",
        filename=upload.filename or "upload.bin",
        backend="memory",
    )
    ocr = expense_ocr_svc.suggest_from_media(media)
    fields = dict(ocr.get("suggestions") or {})
    warnings = list(ocr.get("warnings") or [])
    discrepancies: list[dict] = []

    # Category suggestion for receipts/expenses
    cat_stmt = select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
    cat_stmt = apply_company_filter(cat_stmt, m.ExpenseCategory.company_id, company_id)
    cats = (await db.execute(cat_stmt)).scalars().all()
    text_blob = " ".join(
        filter(
            None,
            [
                ocr.get("raw_text_preview"),
                fields.get("description"),
                fields.get("payee"),
                fields.get("reference"),
            ],
        )
    )
    cat_sug = suggest_category_from_text(text_blob, cats) if cats else None
    if cat_sug:
        fields["category"] = cat_sug["name"]
        fields["category_id"] = cat_sug["id"]

    matches: dict = {"party": None, "products": []}
    if doc_type in {"invoice", "purchase", "purchase_order", "po"}:
        matches["party"] = await _match_party(
            db, tenant_id, kind="supplier", payee=fields.get("payee"), company_id=company_id
        )
        if fields.get("payee") and not matches["party"]:
            discrepancies.append(
                {
                    "field": "payee",
                    "severity": "medium",
                    "detail": f"No supplier matched for payee '{fields.get('payee')}'.",
                }
            )
    else:
        matches["party"] = await _match_party(
            db, tenant_id, kind="supplier", payee=fields.get("payee"), company_id=company_id
        )
        # also try customer for credit notes / receipts from buyers — rare
        if not matches["party"]:
            matches["party"] = await _match_party(
                db, tenant_id, kind="customer", payee=fields.get("payee"), company_id=company_id
            )

    matches["products"] = await _match_products(
        db, tenant_id, text_blob, company_id=company_id
    )

    if fields.get("amount") is None:
        discrepancies.append(
            {
                "field": "amount",
                "severity": "high",
                "detail": "Could not extract a total amount from the document.",
            }
        )
    if fields.get("expense_date") is None and doc_type in {"receipt", "expense", "invoice"}:
        discrepancies.append(
            {
                "field": "date",
                "severity": "medium",
                "detail": "Could not extract a document date.",
            }
        )

    return {
        "generated_at": datetime.utcnow(),
        "method": "rules_v1",
        "document_type": doc_type,
        "filename": upload.filename,
        "content_type": upload.content_type,
        "ocr": {
            "engine": ocr.get("engine"),
            "confidence": ocr.get("confidence"),
            "raw_text_preview": ocr.get("raw_text_preview"),
            "tesseract_available": ocr.get("tesseract_available"),
        },
        "extracted_fields": fields,
        "matches": matches,
        "discrepancies": discrepancies,
        "warnings": warnings,
        "apply_hint": (
            "Review extracted fields and matches, then create/update the related "
            "expense or purchase invoice manually — analysis is suggest-only."
        ),
    }
