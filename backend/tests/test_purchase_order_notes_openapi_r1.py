"""PurchaseOrderCreate/Amend.notes OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PurchaseOrderAmend, PurchaseOrderCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE_CREATE = {
    "supplier_id": "sup-1",
    "items": [{"product_id": "p1", "quantity": 1, "unit_price": 2}],
}


def test_purchase_order_notes_schema():
    omit = PurchaseOrderCreate.model_validate(_BASE_CREATE)
    assert omit.notes is None
    ok = PurchaseOrderCreate.model_validate({**_BASE_CREATE, "notes": "  Monthly restock  "})
    assert ok.notes == "Monthly restock"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseOrderCreate.model_validate({**_BASE_CREATE, "notes": bad})

    amend_ok = PurchaseOrderAmend.model_validate(
        {"reason": "price change", "notes": "  Revised qty  "}
    )
    assert amend_ok.notes == "Revised qty"
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "x", "notes": "!!!"})


def test_purchase_order_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO notes"' in page
    assert "poNotes.trim() || null" in page
    assert 'aria-label="Create draft PO"' in page
    assert 'aria-label="PO amend notes"' in page
    assert "amendNotes.trim() || null" in page
    assert 'aria-label="PO supplier"' in page
    assert 'aria-label="PO product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO notes OpenAPI" in agents
    assert "PurchaseOrderNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseOrderNotesValue" in docs
    assert "PO notes" in docs


@pytest.mark.asyncio
async def test_purchase_order_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    tag = f"Tip172 notes {suffix}"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Tip172 Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    item = {"product_id": seed["p1"].id, "quantity": 2, "unit_price": 3.5}

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/orders",
            headers=admin,
            json={
                "supplier_id": supplier_id,
                "notes": bad,
                "items": [item],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={"supplier_id": supplier_id, "items": [item]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "notes": f"  {tag}  ",
            "items": [item],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
    po_id = ok.json()["data"]["id"]

    bad_amend = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={"reason": "fix notes", "notes": "!!!"},
    )
    assert bad_amend.status_code == 422, bad_amend.text

    keep_amend = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={
            "reason": "update notes",
            "notes": f"  Amended {suffix}  ",
        },
    )
    assert keep_amend.status_code == 200, keep_amend.text
    assert keep_amend.json()["data"].get("notes") == f"Amended {suffix}"
