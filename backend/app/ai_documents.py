"""Rule-based AI Document Assistant (BR-21.8) — OCR extract, auto-match, discrepancies.

Reuses expense_ocr (pypdf / Tesseract). No LLM. Suggest-only — never creates records.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai as ai_svc
from app import ai_expenses as ai_expenses_svc
from app import expense_ocr as ocr_svc
from app import expenses as expenses_svc
from app import models as m
from app import storage as storage_svc

VALID_DOC_TYPES = frozenset({"receipt", "invoice", "purchase_order", "auto"})


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 2}


def name_similarity(a: str, b: str) -> float:
    """Heuristic 0..1 similarity for party / document name matching."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    j = inter / union if union else 0.0
    shorter = ta if len(ta) <= len(tb) else tb
    cover = inter / len(shorter) if shorter else 0.0
    return round(max(j, cover * 0.85), 3)


def infer_document_type(text: str, explicit: str | None) -> str:
    if explicit and explicit != "auto":
        return explicit if explicit in VALID_DOC_TYPES else "auto"
    t = (text or "").lower()
    if re.search(r"\bpurchase\s*order\b|\bpo[\s#:.-]*\d|\bpo\s*number\b", t):
        return "purchase_order"
    if re.search(r"\binvoice\b|\btax\s*invoice\b|\bsupplier\s*invoice\b", t):
        return "invoice"
    if re.search(r"\breceipt\b|\bmerchant\b|\bcashier\b", t):
        return "receipt"
    return "invoice"


def match_parties(
    payee: str | None,
    parties: list[m.Party],
    *,
    preferred_kinds: set[str] | None = None,
    min_score: float = 0.45,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not payee:
        return []
    hits: list[dict[str, Any]] = []
    for p in parties:
        score = name_similarity(payee, p.name)
        if preferred_kinds and p.kind not in preferred_kinds:
            score = score * 0.85
        if score < min_score:
            continue
        hits.append(
            {
                "party_id": p.id,
                "name": p.name,
                "kind": p.kind,
                "score": round(score, 3),
            }
        )
    hits.sort(key=lambda x: (-x["score"], x["name"]))
    return hits[:limit]


def match_purchase_orders(
    *,
    reference: str | None,
    raw_text: str,
    orders: list[m.PurchaseOrder],
    parties_by_id: dict[str, m.Party],
) -> list[dict[str, Any]]:
    blob = f"{reference or ''}\n{raw_text or ''}".upper()
    hits: list[dict[str, Any]] = []
    for po in orders:
        po_n = (po.po_number or "").strip()
        if not po_n:
            continue
        if po_n.upper() in blob or _norm(po_n) in _norm(blob):
            supplier = parties_by_id.get(po.supplier_id)
            hits.append(
                {
                    "purchase_order_id": po.id,
                    "po_number": po.po_number,
                    "status": po.status,
                    "total_amount": float(po.total_amount or 0),
                    "supplier_id": po.supplier_id,
                    "supplier_name": supplier.name if supplier else None,
                    "score": 1.0 if po_n.upper() in blob else 0.8,
                }
            )
    hits.sort(key=lambda x: -x["score"])
    return hits[:10]


def build_discrepancies(
    *,
    fields: dict[str, Any],
    confidence: float,
    expected_amount: float | None,
    party_matches: list[dict[str, Any]],
    po_matches: list[dict[str, Any]],
    duplicate_refs: list[dict[str, Any]],
    document_type: str,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if fields.get("amount") is None:
        flags.append(
            {
                "code": "missing_amount",
                "severity": "medium",
                "message": "Could not extract a total amount",
            }
        )
    if fields.get("expense_date") is None:
        flags.append(
            {
                "code": "missing_date",
                "severity": "low",
                "message": "Could not extract a document date",
            }
        )
    if fields.get("payee") is None:
        flags.append(
            {
                "code": "missing_payee",
                "severity": "medium",
                "message": "Could not extract vendor/payee",
            }
        )
    if confidence < 0.4:
        flags.append(
            {
                "code": "low_confidence",
                "severity": "high",
                "message": f"OCR confidence is low ({confidence})",
            }
        )
    if expected_amount is not None and fields.get("amount") is not None:
        amt = float(fields["amount"])
        if abs(amt - float(expected_amount)) > 0.05:
            flags.append(
                {
                    "code": "amount_mismatch",
                    "severity": "high",
                    "message": (
                        f"Extracted amount {amt} differs from expected {float(expected_amount):.2f}"
                    ),
                    "extracted": amt,
                    "expected": float(expected_amount),
                }
            )
    if fields.get("payee") and not party_matches:
        flags.append(
            {
                "code": "no_party_match",
                "severity": "medium",
                "message": f"No tenant party matched payee '{fields['payee']}'",
            }
        )
    if document_type == "purchase_order" and not po_matches:
        flags.append(
            {
                "code": "no_po_match",
                "severity": "medium",
                "message": "Document looks like a PO but no purchase_order.po_number matched",
            }
        )
    for dup in duplicate_refs:
        flags.append(
            {
                "code": "duplicate_reference",
                "severity": "high",
                "message": dup["message"],
                "record": dup,
            }
        )
    if po_matches and fields.get("amount") is not None:
        top = po_matches[0]
        if abs(float(fields["amount"]) - float(top["total_amount"])) > 0.05:
            flags.append(
                {
                    "code": "po_amount_mismatch",
                    "severity": "medium",
                    "message": (
                        f"Extracted amount {fields['amount']} differs from matched PO "
                        f"{top['po_number']} total {top['total_amount']}"
                    ),
                }
            )
    return flags


async def analyze_upload(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    upload: UploadFile,
    document_type: str = "auto",
    expected_amount: float | None = None,
) -> dict[str, Any]:
    doc_type = (document_type or "auto").strip().lower()
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"document_type must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
        )

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    max_bytes = int(
        getattr(storage_svc.settings, "MEDIA_MAX_ATTACHMENT_BYTES", 10_000_000) or 10_000_000
    )
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    filename = upload.filename or "document.bin"
    content_type = upload.content_type or "application/octet-stream"
    media = storage_svc.MediaObject(
        key=f"{tenant_id}/ai-documents/{filename}",
        data=data,
        content_type=content_type,
        filename=filename,
        backend="memory",
    )
    ocr = ocr_svc.suggest_from_media(media)
    fields = dict(ocr.get("suggestions") or {})
    raw = ocr.get("raw_text_preview") or ""
    confidence = float(ocr.get("confidence") or 0)
    resolved_type = infer_document_type(raw, doc_type)

    parties = (
        await db.execute(select(m.Party).where(m.Party.tenant_id == tenant_id))
    ).scalars().all()
    preferred = {"supplier"} if resolved_type in {"invoice", "purchase_order"} else None
    party_matches = match_parties(
        fields.get("payee"), list(parties), preferred_kinds=preferred
    )

    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(m.PurchaseOrder.tenant_id == tenant_id)
        )
    ).scalars().all()
    parties_by_id = {p.id: p for p in parties}
    po_matches = match_purchase_orders(
        reference=fields.get("reference"),
        raw_text=raw,
        orders=list(orders),
        parties_by_id=parties_by_id,
    )

    duplicate_refs: list[dict[str, Any]] = []
    ref = (fields.get("reference") or "").strip()
    if ref:
        inv_hits = (
            await db.execute(
                select(m.PurchaseInvoice).where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.supplier_invoice_number == ref,
                )
            )
        ).scalars().all()
        for inv in inv_hits:
            duplicate_refs.append(
                {
                    "kind": "purchase_invoice",
                    "id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "message": (
                        f"Reference {ref} already on purchase invoice {inv.invoice_number}"
                    ),
                }
            )
        exp_hits = (
            await db.execute(
                select(m.Expense).where(
                    m.Expense.tenant_id == tenant_id,
                    m.Expense.reference == ref,
                )
            )
        ).scalars().all()
        for exp in exp_hits:
            duplicate_refs.append(
                {
                    "kind": "expense",
                    "id": exp.id,
                    "message": f"Reference {ref} already on expense {exp.id}",
                }
            )

    category_suggestion = None
    if resolved_type == "receipt":
        await expenses_svc.ensure_default_categories(db, tenant_id)
        cats = (
            await db.execute(
                select(m.ExpenseCategory).where(
                    m.ExpenseCategory.tenant_id == tenant_id,
                    m.ExpenseCategory.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        blob = " ".join(
            str(x)
            for x in (raw, fields.get("payee"), fields.get("description"))
            if x
        )
        category_suggestion = ai_expenses_svc.suggest_category_from_text(blob, list(cats))
        if category_suggestion:
            fields["category_id"] = category_suggestion["category_id"]
            fields["category"] = category_suggestion["category"]

    mapped = {
        "supplier_invoice_number": fields.get("reference") or fields.get("payee"),
        "invoice_date": fields.get("expense_date"),
        "notes": fields.get("description"),
        "ocr_amount": fields.get("amount"),
        "ocr_payee": fields.get("payee"),
    }

    discrepancies = build_discrepancies(
        fields=fields,
        confidence=confidence,
        expected_amount=expected_amount,
        party_matches=party_matches,
        po_matches=po_matches,
        duplicate_refs=duplicate_refs,
        document_type=resolved_type,
    )

    warnings = list(ocr.get("warnings") or [])
    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="documents_analyze",
        status="ok",
        message=f"{resolved_type}:{filename}",
        details={
            "document_type": resolved_type,
            "engine": ocr.get("engine"),
            "confidence": confidence,
            "match_count": len(party_matches),
            "discrepancy_count": len(discrepancies),
            "method": "rule_based_ocr",
        },
    )
    await db.commit()

    return {
        "method": "rule_based_ocr",
        "document_type": resolved_type,
        "document_type_requested": doc_type,
        "engine": ocr.get("engine"),
        "tesseract_available": ocr.get("tesseract_available"),
        "filename": filename,
        "content_type": content_type,
        "confidence": confidence,
        "extracted": fields,
        "mapped": mapped,
        "matches": {
            "parties": party_matches,
            "purchase_orders": po_matches,
        },
        "category_suggestion": category_suggestion,
        "discrepancies": discrepancies,
        "warnings": warnings,
        "raw_text_preview": raw[:2000],
        "apply_hint": (
            "Suggest-only: review matches/discrepancies, then create or PATCH expense / "
            "purchase invoice / PO manually — nothing was written to business records"
        ),
    }
