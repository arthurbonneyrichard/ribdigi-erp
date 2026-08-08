"""Expense receipt OCR suggestion + apply (human confirm) tests."""

from datetime import datetime
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app import expense_ocr as ocr_svc
from app import expenses as expenses_svc
from app import models as m
from app import storage as storage_svc


def _text_pdf(text: str) -> bytes:
    """Build a minimal PDF. pypdf cannot embed arbitrary text easily — use a
    PDF with a content stream that PdfReader can still open; for parse tests we
    feed text directly. This helper is for attachment round-trips.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_parse_receipt_text_extracts_fields():
    text = """
    ACME Supplies Ltd
    Date: 2026-03-15
    Invoice No: INV-7788
    Subtotal 100.00
    Tax 15.00
    Total: GHS 250.50
    """
    parsed = ocr_svc.parse_receipt_text(text)
    assert parsed["fields"]["amount"] == 250.50
    assert parsed["fields"]["expense_date"] == "2026-03-15"
    assert parsed["fields"]["reference"] == "INV-7788"
    assert parsed["fields"]["payee"]
    assert parsed["confidence"] > 0


def test_parse_receipt_empty():
    parsed = ocr_svc.parse_receipt_text("")
    assert parsed["fields"]["amount"] is None
    assert parsed["confidence"] == 0


@pytest.mark.asyncio
async def test_ocr_suggest_from_attachment_text(db_session, seeded, tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    tenant_id = seeded["t1"].id
    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=10,
        category="Supplies",
        description="placeholder",
    )
    # Store a fake PDF key and monkeypatch read_object
    expense.attachment_url = f"{tenant_id}/expenses/fake.pdf"
    await db_session.commit()

    media = storage_svc.MediaObject(
        key=expense.attachment_url,
        data=_text_pdf("x"),
        content_type="application/pdf",
        filename="receipt.pdf",
        backend="local",
    )

    def fake_read(key, *, tenant_id=None):
        return media

    monkeypatch.setattr(storage_svc, "read_object", fake_read)
    monkeypatch.setattr(
        ocr_svc,
        "extract_text",
        lambda _m: (
            "Payee: Office Depot\nDate: 2026-04-01\nReceipt #: R-9\nAmount Due: 88.25",
            "pdf",
        ),
    )

    result = await ocr_svc.suggest_for_expense(db_session, tenant_id=tenant_id, expense_id=expense.id)
    assert result["suggestions"]["amount"] == 88.25
    assert result["suggestions"]["payee"]
    assert result["engine"] == "pdf"
    assert result["expense_id"] == expense.id


@pytest.mark.asyncio
async def test_update_expense_applies_ocr_fields(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 1000
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=50,
        category="Misc",
        description="old",
        payee="old",
    )
    # Under threshold → auto-approved; create one that stays pending
    tenant.expense_approval_threshold = 10
    await db_session.flush()
    pending = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=50,
        category="Misc",
        description="old",
        payee="old",
    )
    assert pending.status == "pending"

    updated = await expenses_svc.update_expense(
        db_session,
        tenant_id=tenant_id,
        expense_id=pending.id,
        user_id=seeded["admin1"].id,
        amount=75.5,
        payee="Office Depot",
        description="Receipt — Office Depot",
        reference="R-9",
        expense_date=datetime(2026, 4, 1),
    )
    await db_session.commit()
    assert float(updated.amount) == 75.5
    assert updated.payee == "Office Depot"
    assert updated.reference == "R-9"
    assert updated.status == "pending"


@pytest.mark.asyncio
async def test_cannot_edit_approved_expense(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 1000
    await db_session.flush()
    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=20,
        category="Misc",
        description="auto",
    )
    assert expense.status == "approved"
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await expenses_svc.update_expense(
            db_session,
            tenant_id=tenant_id,
            expense_id=expense.id,
            user_id=seeded["admin1"].id,
            description="nope",
        )
    assert exc.value.status_code == 409
