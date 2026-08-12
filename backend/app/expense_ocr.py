"""Receipt text extraction and field suggestions for expenses (suggest-only)."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app import storage as storage_svc

# Common total labels (case-insensitive)
_AMOUNT_PATTERNS = [
    re.compile(
        r"(?:grand\s*)?total(?:\s+due|\s+amount)?\s*[:\-]?\s*(?:GHS|GH₵|USD|\$|€|£)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})",
        re.I,
    ),
    re.compile(
        r"(?:amount\s*(?:due|paid)?|balance\s*due)\s*[:\-]?\s*(?:GHS|GH₵|USD|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})",
        re.I,
    ),
    re.compile(
        r"(?:GHS|GH₵|USD|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})",
        re.I,
    ),
]

_DATE_PATTERNS = [
    re.compile(
        r"(?:date|dated|invoice\s*date|receipt\s*date)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        re.I,
    ),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(\d{1,2}-\d{1,2}-\d{4})\b"),
]

_REF_PATTERNS = [
    re.compile(r"(?:invoice|receipt|ref(?:erence)?|bill)\s*(?:no\.?|#|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{2,})", re.I),
]

_PAYEE_PATTERNS = [
    re.compile(r"(?:merchant|vendor|payee|sold\s+by|from)\s*[:\-]\s*(.+)", re.I),
]


def tesseract_available() -> bool:
    return bool(shutil.which("tesseract"))


def extract_text_from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="PDF OCR requires pypdf (install backend requirements)",
        ) from exc
    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — page extract can fail on odd PDFs
            continue
    return "\n".join(parts).strip()


def extract_text_from_image(data: bytes, content_type: str) -> str:
    if not tesseract_available():
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    from io import BytesIO

    img = Image.open(BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return (pytesseract.image_to_string(img) or "").strip()


def extract_text(media: storage_svc.MediaObject) -> tuple[str, str]:
    """Return (text, engine) where engine is pdf|tesseract|none."""
    ct = (media.content_type or "").lower()
    name = (media.filename or "").lower()
    if ct == "application/pdf" or name.endswith(".pdf"):
        text = extract_text_from_pdf(media.data)
        return text, "pdf"
    if ct.startswith("image/") or any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        if not tesseract_available():
            return "", "unavailable"
        text = extract_text_from_image(media.data, ct)
        return text, "tesseract"
    return "", "unsupported"


def _parse_amount(text: str) -> float | None:
    for pat in _AMOUNT_PATTERNS:
        matches = pat.findall(text)
        if not matches:
            continue
        # Prefer last match (often the grand total)
        raw = matches[-1] if isinstance(matches[-1], str) else matches[-1][0]
        try:
            return round(float(str(raw).replace(",", "")), 2)
        except ValueError:
            continue
    return None


def _parse_date(text: str) -> str | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        raw = m.group(1)
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%y", "%m/%d/%y"):
            try:
                return datetime.strptime(raw.replace(".", "/"), fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _parse_reference(text: str) -> str | None:
    for pat in _REF_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()[:80]
    return None


def _parse_payee(text: str) -> str | None:
    for pat in _PAYEE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip().split("\n")[0][:120]
    # Fallback: first substantial line that is not a date/amount header
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 3 or len(line) > 80:
            continue
        if re.search(r"total|amount|invoice|receipt|date|tax|vat|subtotal", line, re.I):
            continue
        if re.fullmatch(r"[\d\s.,/$€£GHS]+", line):
            continue
        return line[:120]
    return None


def parse_receipt_text(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    amount = _parse_amount(cleaned) if cleaned else None
    expense_date = _parse_date(cleaned) if cleaned else None
    payee = _parse_payee(cleaned) if cleaned else None
    reference = _parse_reference(cleaned) if cleaned else None
    description = None
    if payee and amount is not None:
        description = f"Receipt — {payee}"
    elif payee:
        description = f"Receipt — {payee}"
    elif amount is not None:
        description = "Receipt capture"

    fields = {
        "amount": amount,
        "expense_date": expense_date,
        "payee": payee,
        "description": description,
        "reference": reference,
    }
    filled = sum(1 for v in fields.values() if v is not None)
    confidence = 0.0
    if cleaned:
        confidence = min(0.95, 0.25 + 0.15 * filled)
        if amount is not None:
            confidence = min(0.95, confidence + 0.15)
    return {
        "fields": fields,
        "confidence": round(confidence, 2),
        "raw_text_preview": cleaned[:2000] if cleaned else "",
    }


def suggest_from_media(media: storage_svc.MediaObject) -> dict[str, Any]:
    text, engine = extract_text(media)
    parsed = parse_receipt_text(text)
    warnings: list[str] = []
    if engine == "unavailable":
        warnings.append(
            "Image OCR requires Tesseract on the server; PDF text extraction still works"
        )
    elif engine == "unsupported":
        warnings.append("Unsupported attachment type for OCR")
    elif engine == "pdf" and not text:
        warnings.append("No extractable text in PDF (scanned image PDFs need Tesseract/OCR)")
    elif engine == "tesseract" and not text:
        warnings.append("Tesseract returned no text")
    elif not any(v is not None for v in parsed["fields"].values()):
        warnings.append("Could not parse amount/date/payee from receipt text")

    return {
        "engine": engine,
        "tesseract_available": tesseract_available(),
        "content_type": media.content_type,
        "filename": media.filename,
        "suggestions": parsed["fields"],
        "confidence": parsed["confidence"],
        "raw_text_preview": parsed["raw_text_preview"],
        "warnings": warnings,
        "apply_hint": "Review suggestions then PATCH /expenses/{id} with confirmed fields",
    }


async def suggest_for_expense(db, *, tenant_id: str, expense_id: str) -> dict[str, Any]:
    from app import expenses as expenses_svc
    from app import ai_expenses as ai_expenses_svc
    from sqlalchemy import select
    from app import models as m

    expense = await expenses_svc.get_expense(db, tenant_id, expense_id)
    if not expense.attachment_url:
        raise HTTPException(status_code=400, detail="Upload a receipt attachment before OCR")
    if "://" in expense.attachment_url:
        raise HTTPException(status_code=400, detail="External attachment URLs cannot be OCR'd")
    media = storage_svc.read_object(expense.attachment_url, tenant_id=tenant_id)
    result = suggest_from_media(media)
    await expenses_svc.ensure_default_categories(db, tenant_id)
    categories = (
        await db.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.tenant_id == tenant_id,
                m.ExpenseCategory.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    blob = " ".join(
        str(x)
        for x in (
            result.get("raw_text_preview"),
            (result.get("suggestions") or {}).get("payee"),
            (result.get("suggestions") or {}).get("description"),
            expense.description,
            expense.payee,
        )
        if x
    )
    cat_suggest = ai_expenses_svc.suggest_category_from_text(blob, list(categories))
    if cat_suggest:
        result.setdefault("suggestions", {})
        result["suggestions"]["category_id"] = cat_suggest["category_id"]
        result["suggestions"]["category"] = cat_suggest["category"]
        result["category_suggestion"] = cat_suggest
    result["expense_id"] = expense.id
    result["expense_status"] = expense.status
    return result
