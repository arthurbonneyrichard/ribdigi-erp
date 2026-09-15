"""PartyUpdate.customer_group_id ∈ UuidIdValue OpenAPI honesty (BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PartyUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID_GROUP = "11111111-2222-3333-4444-555555555555"


def test_party_update_customer_group_id_schema():
    assert _uuid.validate_python(f"  {_VALID_GROUP}  ") == _VALID_GROUP.lower()
    ok = PartyUpdate.model_validate({"customer_group_id": f"  {_VALID_GROUP}  "})
    assert ok.customer_group_id == _VALID_GROUP.lower()
    omit_ok = PartyUpdate.model_validate({"name": "Renamed"})
    assert omit_ok.customer_group_id is None
    nullish = PartyUpdate.model_validate({"customer_group_id": None})
    assert nullish.customer_group_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "cg_002", "a b"):
        with pytest.raises(ValidationError):
            PartyUpdate.model_validate({"customer_group_id": bad})


def test_party_update_customer_group_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer group"' in page
    assert "customer_group_id: customerGroupId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer update customer_group_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "customer_group_id" in docs
    assert "PATCH /customers/{customer_id}" in docs


@pytest.mark.asyncio
async def test_party_update_customer_group_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"TIP349 Customer {suffix}"},
    )
    assert created.status_code == 200, created.text
    customer_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cg_002"):
        resp = await ac.patch(
            f"/api/v1/customers/{customer_id}",
            headers=headers,
            json={"customer_group_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.patch(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
        json={"customer_group_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
