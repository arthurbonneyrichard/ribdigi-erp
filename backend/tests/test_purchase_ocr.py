"""Purchase invoice OCR suggest + draft header apply tests."""

import pytest
from fastapi import HTTPException

from app import models as m
from app import purchase_ocr as purchase_ocr_svc
from app import purchasing as purchasing_svc
from app import storage as storage_svc


def test_map_purchase_suggestions():
    mapped = purchase_ocr_svc.map_purchase_suggestions(
        {
            "amount": 115.0,
            "expense_date": "2026-03-10",
            "payee": "Acme Vendor",
            "description": "Receipt — Acme Vendor",
            "reference": "SUP-99",
        }
    )
    assert mapped["supplier_invoice_number"] == "SUP-99"
    assert mapped["invoice_date"] == "2026-03-10"
    assert mapped["ocr_amount"] == 115.0


@pytest.mark.asyncio
async def test_ocr_suggest_purchase_invoice(db_session, seeded, monkeypatch):
    tenant_id = seeded["t1"].id
    supplier = m.Party(tenant_id=tenant_id, name="OCR Vendor", kind="supplier", credit_limit=0)
    product = seeded["p1"]
    db_session.add(supplier)
    await db_session.flush()

    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": product.id, "quantity": 1, "unit_price": 100, "tax_rate": 15}],
    )
    inv.attachment_url = f"{tenant_id}/purchasing/fake.pdf"
    await db_session.commit()

    media = storage_svc.MediaObject(
        key=inv.attachment_url,
        data=b"%PDF-1.4",
        content_type="application/pdf",
        filename="inv.pdf",
        backend="local",
    )
    monkeypatch.setattr(storage_svc, "read_object", lambda *a, **k: media)
    monkeypatch.setattr(
        "app.expense_ocr.extract_text",
        lambda _m: (
            "Vendor: OCR Vendor\nDate: 2026-03-10\nInvoice No: SUP-99\nTotal: GHS 115.00",
            "pdf",
        ),
    )

    result = await purchase_ocr_svc.suggest_for_purchase_invoice(
        db_session, tenant_id=tenant_id, invoice_id=inv.id
    )
    assert result["suggestions"]["supplier_invoice_number"] == "SUP-99"
    assert result["suggestions"]["invoice_date"] == "2026-03-10"
    assert result["invoice_status"] == "draft"


@pytest.mark.asyncio
async def test_update_draft_applies_header_fields(db_session, seeded):
    tenant_id = seeded["t1"].id
    supplier = m.Party(tenant_id=tenant_id, name="Patch Vendor", kind="supplier", credit_limit=0)
    db_session.add(supplier)
    await db_session.flush()
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seeded["p1"].id, "quantity": 1, "unit_price": 50, "tax_rate": 0}],
    )
    updated = await purchase_ocr_svc.update_purchase_invoice_draft(
        db_session,
        tenant_id=tenant_id,
        invoice_id=inv.id,
        supplier_invoice_number="SUP-42",
        notes="From OCR",
    )
    await db_session.commit()
    assert updated.supplier_invoice_number == "SUP-42"
    assert updated.notes == "From OCR"


@pytest.mark.asyncio
async def test_cannot_patch_approved_invoice(db_session, seeded):
    tenant_id = seeded["t1"].id
    supplier = m.Party(tenant_id=tenant_id, name="Locked Vendor", kind="supplier", credit_limit=0)
    db_session.add(supplier)
    await db_session.flush()
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seeded["p1"].id, "quantity": 1, "unit_price": 40, "tax_rate": 0}],
    )
    await purchasing_svc.approve_purchase_invoice(
        db_session, tenant_id=tenant_id, user_id=seeded["admin1"].id, invoice_id=inv.id
    )
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await purchase_ocr_svc.update_purchase_invoice_draft(
            db_session,
            tenant_id=tenant_id,
            invoice_id=inv.id,
            notes="nope",
        )
    assert exc.value.status_code == 409
