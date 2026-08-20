"""SalesReturnCreate.notes OpenAPI honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import SalesReturnCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE = {
    "sales_invoice_id": "inv-1",
    "reason": "damaged",
    "items": [{"product_id": "p1", "quantity": 1, "condition": "discard"}],
}


def test_sales_return_notes_schema():
    omit = SalesReturnCreate.model_validate(_BASE)
    assert omit.notes is None
    nullish = SalesReturnCreate.model_validate({**_BASE, "notes": None})
    assert nullish.notes is None
    ok = SalesReturnCreate.model_validate({**_BASE, "notes": "  Box crushed  "})
    assert ok.notes == "Box crushed"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            SalesReturnCreate.model_validate({**_BASE, "notes": bad})


def test_sales_return_notes_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales return notes"' in page
    assert "returnNotes.trim() || null" in page
    assert 'aria-label="Create sales return"' in page
    assert 'aria-label="Return from invoice"' in page
    assert 'aria-label="Sales product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales return notes OpenAPI" in agents
    assert "SalesReturnNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesReturnNotesValue" in docs
    assert "Sales return notes" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _posted_invoice(ac, admin, seed, *, unit_price=50.0):
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": unit_price}],
        },
    )
    assert created.status_code == 200, created.text
    iid = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    return posted.json()["data"]


@pytest.mark.asyncio
async def test_sales_return_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed)
    suffix = uuid4().hex[:8]
    tag = f"Tip171 notes {suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/sales/returns",
            headers=admin,
            json={
                "sales_invoice_id": inv["id"],
                "reason": "damaged",
                "restock": False,
                "notes": bad,
                "items": [
                    {
                        "product_id": seed["p1"].id,
                        "quantity": 1,
                        "condition": "discard",
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "wrong_item",
            "restock": False,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "condition": "discard",
                }
            ],
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    # Same invoice still has 1 unit remaining after omit return.
    ok = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "defective",
            "restock": False,
            "notes": f"  {tag}  ",
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "condition": "discard",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
