"""PurchaseRequestCreate.notes OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseRequestCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE = {"items": [{"product_id": "p1", "quantity": 1}]}


def test_purchase_request_notes_schema():
    omit = PurchaseRequestCreate.model_validate(_BASE)
    assert omit.notes is None
    nullish = PurchaseRequestCreate.model_validate({**_BASE, "notes": None})
    assert nullish.notes is None
    ok = PurchaseRequestCreate.model_validate({**_BASE, "notes": "  Monthly replenishment  "})
    assert ok.notes == "Monthly replenishment"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseRequestCreate.model_validate({**_BASE, "notes": bad})


def test_purchase_request_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request notes"' in page
    assert "prNotes.trim() || null" in page
    assert 'aria-label="Create draft purchase request"' in page
    assert 'aria-label="Purchase request required date"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR notes OpenAPI" in agents
    assert "PurchaseRequestNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestNotesValue" in docs
    assert "Purchase request notes" in docs


@pytest.mark.asyncio
async def test_purchase_request_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"Tip174 notes {suffix}"
    item = {"product_id": seed["p1"].id, "quantity": 2}

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={"notes": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={"items": [item]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={"notes": f"  {tag}  ", "items": [item]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
