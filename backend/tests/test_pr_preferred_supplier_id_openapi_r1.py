"""PurchaseRequestCreate.preferred_supplier_id ∈ UuidIdValue OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseRequestCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ITEMS = [{"product_id": _PRODUCT, "quantity": 1}]


def test_pr_preferred_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseRequestCreate.model_validate(
        {"preferred_supplier_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.preferred_supplier_id == _VALID.lower()
    omit_ok = PurchaseRequestCreate.model_validate({"items": _ITEMS})
    assert omit_ok.preferred_supplier_id is None
    nullish = PurchaseRequestCreate.model_validate(
        {"preferred_supplier_id": None, "items": _ITEMS}
    )
    assert nullish.preferred_supplier_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "sup_002", "a b"):
        with pytest.raises(ValidationError):
            PurchaseRequestCreate.model_validate(
                {"preferred_supplier_id": bad, "items": _ITEMS}
            )


def test_pr_preferred_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request preferred supplier"' in page
    assert "preferred_supplier_id: prSupplierId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR preferred_supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Purchase request preferred supplier" in docs
    assert "POST /purchasing/requests" in docs


@pytest.mark.asyncio
async def test_pr_preferred_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    item = {"product_id": product_id, "quantity": 1}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_002"):
        resp = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={"preferred_supplier_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "preferred_supplier_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
