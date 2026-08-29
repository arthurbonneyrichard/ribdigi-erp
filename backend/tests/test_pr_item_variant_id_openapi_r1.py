"""PurchaseRequestItemCreate.variant_id ∈ UuidIdValue OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseRequestCreate, PurchaseRequestItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_pr_item_variant_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseRequestItemCreate.model_validate(
        {
            "product_id": _PRODUCT,
            "quantity": 1,
            "variant_id": f"  {_VALID}  ",
        }
    )
    assert ok.variant_id == _VALID.lower()
    omit_ok = PurchaseRequestItemCreate.model_validate(
        {"product_id": _PRODUCT, "quantity": 1}
    )
    assert omit_ok.variant_id is None
    nullish = PurchaseRequestItemCreate.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "variant_id": None}
    )
    assert nullish.variant_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "var_001", "a b"):
        with pytest.raises(ValidationError):
            PurchaseRequestItemCreate.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "variant_id": bad}
            )


def test_pr_item_variant_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR item variant_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "variant_id" in docs
    assert "POST /purchasing/requests" in docs
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request product"' in page


@pytest.mark.asyncio
async def test_pr_item_variant_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "var_001"):
        resp = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={
                "items": [
                    {"product_id": product_id, "quantity": 1, "variant_id": bad},
                ]
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "variant_id": f"  {str(uuid4()).upper()}  ",
                },
            ]
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
