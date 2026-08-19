"""PurchaseOrderAmend.due_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseOrderAmend
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_po_amend_due_date_schema():
    omit = PurchaseOrderAmend.model_validate({"reason": "notes only"})
    assert omit.due_date is None
    assert omit.clear_due_date is False
    ok = PurchaseOrderAmend.model_validate(
        {"reason": "extend", "due_date": " 2026-09-30 "}
    )
    assert ok.due_date == "2026-09-30"
    iso = PurchaseOrderAmend.model_validate(
        {"reason": "extend", "due_date": "2026-10-15T12:00:00"}
    )
    assert iso.due_date == "2026-10-15T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            PurchaseOrderAmend.model_validate({"reason": "x", "due_date": bad})


def test_po_amend_due_date_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO amend due date"' in page
    assert "amendDueDate.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO amend due_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PO amend due date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_po_amend_due_date_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"PO Due Vendor {uuid4().hex[:6]}",
            "kind": "supplier",
            "email": f"po-due-{uuid4().hex[:6]}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    item = {
        "product_id": seed["p1"].id,
        "quantity": 2,
        "unit_price": 5,
        "tax_rate": 0,
    }
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [item],
            "notes": "po amend due_date OpenAPI hello-world",
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["status"] == "draft"
    po_id = po["id"]

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            f"/api/v1/purchasing/orders/{po_id}/amend",
            headers=headers,
            json={"reason": f"bad due {bad!r}", "due_date": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={"reason": "set due date", "due_date": "2026-09-30"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    # Response may nest under po or top-level serialize
    due = data.get("due_date")
    if due is None and isinstance(data.get("po"), dict):
        due = data["po"].get("due_date")
    assert str(due).startswith("2026-09-30"), data

    omit = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={"reason": "notes only — due unchanged", "notes": "keep due"},
    )
    assert omit.status_code == 200, omit.text
    kept = omit.json()["data"]
    kept_due = kept.get("due_date")
    if kept_due is None and isinstance(kept.get("po"), dict):
        kept_due = kept["po"].get("due_date")
    assert str(kept_due).startswith("2026-09-30"), kept
