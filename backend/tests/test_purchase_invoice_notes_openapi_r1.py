"""PurchaseInvoiceCreate/Update.notes OpenAPI honesty (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseInvoiceCreate, PurchaseInvoiceUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_invoice_notes_schema():
    create_omit = PurchaseInvoiceCreate.model_validate(
        {"supplier_id": "s1", "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}]}
    )
    assert create_omit.notes is None
    create_ok = PurchaseInvoiceCreate.model_validate(
        {
            "supplier_id": "s1",
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
            "notes": "  Vendor bill memo  ",
        }
    )
    assert create_ok.notes == "Vendor bill memo"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceCreate.model_validate(
                {
                    "supplier_id": "s1",
                    "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
                    "notes": bad,
                }
            )

    patch_omit = PurchaseInvoiceUpdate.model_validate({})
    assert patch_omit.notes is None
    patch_ok = PurchaseInvoiceUpdate.model_validate({"notes": "  OCR notes  "})
    assert patch_ok.notes == "OCR notes"
    with pytest.raises(ValidationError):
        PurchaseInvoiceUpdate.model_validate({"notes": "!!!"})


def test_purchase_invoice_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice notes"' in page
    assert "invNotes.trim() || null" in page
    assert 'aria-label="Purchase invoice OCR notes"' in page
    assert "ocrNotes !== ''" in page or "ocrDraft.notes.trim()" in page
    assert 'aria-label="Draft manual purchase invoice"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice notes OpenAPI" in agents
    assert "PurchaseInvoiceNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseInvoiceNotesValue" in docs
    assert "Purchase invoice notes" in docs


@pytest.mark.asyncio
async def test_purchase_invoice_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"Tip176 notes {suffix}"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"PI Notes Vendor {suffix}",
            "kind": "supplier",
            "email": f"pi-notes-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    item = {
        "product_id": seed["p1"].id,
        "quantity": 1,
        "unit_price": 12,
        "tax_rate": 0,
    }

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={"supplier_id": supplier_id, "notes": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"supplier_id": supplier_id, "items": [item]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"supplier_id": supplier_id, "notes": f"  {tag}  ", "items": [item]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
    inv_id = ok.json()["data"]["id"]

    bad_patch = await ac.patch(
        f"/api/v1/purchasing/invoices/{inv_id}",
        headers=headers,
        json={"notes": "!!!"},
    )
    assert bad_patch.status_code == 422, bad_patch.text

    keep = await ac.patch(
        f"/api/v1/purchasing/invoices/{inv_id}",
        headers=headers,
        json={"notes": f"  {tag} patched  "},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"].get("notes") == f"{tag} patched"
