"""SalesQuotation/Order/InvoiceCreate.notes OpenAPI honesty (BR-7.2–7.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import SalesInvoiceCreate, SalesOrderCreate, SalesQuotationCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_ITEMS = [{"product_id": "p1", "quantity": 1, "unit_price": 10}]


def test_sales_document_notes_schema():
    for cls, key in (
        (SalesInvoiceCreate, "customer_id"),
        (SalesQuotationCreate, "customer_id"),
        (SalesOrderCreate, "customer_id"),
    ):
        base = {key: "c1", "items": _ITEMS}
        omit = cls.model_validate(base)
        assert omit.notes is None
        ok = cls.model_validate({**base, "notes": "  Bulk pricing  "})
        assert ok.notes == "Bulk pricing"
        for bad in ("", " ", "!!!", "http://evil", "@@"):
            with pytest.raises(ValidationError):
                cls.model_validate({**base, "notes": bad})


def test_sales_document_notes_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales document notes"' in page
    assert "docNotes.trim() || null" in page
    assert 'aria-label="Create invoice"' in page
    assert 'aria-label="Create quotation"' in page
    assert 'aria-label="Create order"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales document notes OpenAPI" in agents
    assert "SalesDocumentNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesDocumentNotesValue" in docs
    assert "Sales document notes" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_document_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    tag = f"Tip178 notes {suffix}"
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}
    cust = seed["party1"].id

    for path in ("/api/v1/sales/invoices", "/api/v1/sales/quotations", "/api/v1/sales/orders"):
        for bad in ("", "!!!", "http://evil"):
            resp = await ac.post(
                path,
                headers=admin,
                json={"customer_id": cust, "notes": bad, "items": [item]},
            )
            assert resp.status_code == 422, (path, bad, resp.text)

    omit = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={"customer_id": cust, "items": [item]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok_inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={"customer_id": cust, "notes": f"  {tag}  ", "items": [item]},
    )
    assert ok_inv.status_code == 200, ok_inv.text
    assert ok_inv.json()["data"].get("notes") == tag

    ok_qt = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={"customer_id": cust, "notes": f"{tag} QT", "items": [item]},
    )
    assert ok_qt.status_code == 200, ok_qt.text
    assert ok_qt.json()["data"].get("notes") == f"{tag} QT"

    ok_so = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={"customer_id": cust, "notes": f"{tag} SO", "items": [item]},
    )
    assert ok_so.status_code == 200, ok_so.text
    assert ok_so.json()["data"].get("notes") == f"{tag} SO"
