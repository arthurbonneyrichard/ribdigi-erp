"""PurchaseRequestItemCreate.notes OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseRequestCreate, PurchaseRequestItemCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_request_item_notes_schema():
    omit = PurchaseRequestItemCreate.model_validate({"product_id": "p1", "quantity": 1})
    assert omit.notes is None
    ok = PurchaseRequestItemCreate.model_validate(
        {"product_id": "p1", "quantity": 1, "notes": "  Urgent SKU  "}
    )
    assert ok.notes == "Urgent SKU"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseRequestItemCreate.model_validate(
                {"product_id": "p1", "quantity": 1, "notes": bad}
            )

    create_ok = PurchaseRequestCreate.model_validate(
        {
            "items": [{"product_id": "p1", "quantity": 1, "notes": "  Bin A  "}],
        }
    )
    assert create_ok.items[0].notes == "Bin A"
    with pytest.raises(ValidationError):
        PurchaseRequestCreate.model_validate(
            {"items": [{"product_id": "p1", "quantity": 1, "notes": "!!!!"}]}
        )


def test_purchase_request_item_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request line notes"' in page
    assert "prItemNotes.trim() || null" in page
    assert 'aria-label="Create draft purchase request"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseRequestItemCreate.notes" in agents
    assert "PurchaseRequestNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestItemCreate.notes" in docs
    assert "Purchase request line notes" in docs


@pytest.mark.asyncio
async def test_purchase_request_item_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP183 line {suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={
                "items": [
                    {"product_id": seed["p1"].id, "quantity": 1, "notes": bad},
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "notes": f"  {tag}  "},
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json().get("data") or {}
    items = data.get("items") or []
    assert items, data
    assert items[0].get("notes") == tag, data
