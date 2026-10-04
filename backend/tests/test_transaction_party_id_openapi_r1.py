"""TransactionCreate.party_id ∈ UuidIdValue OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TransactionCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_transaction_party_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = TransactionCreate.model_validate({})
    assert omit.party_id is None
    ok = TransactionCreate.model_validate({"party_id": f"  {_VALID}  "})
    assert ok.party_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        with pytest.raises(ValidationError):
            TransactionCreate.model_validate({"party_id": bad})


def test_transaction_party_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Transaction create party_id OpenAPI" in agents
    assert "UuidIdValue" in agents


@pytest.mark.asyncio
async def test_transaction_party_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}
    # Legacy sale create uses TransactionCreate on POST /sales
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        resp = await ac.post(
            "/api/v1/sales",
            headers=headers,
            json={"party_id": bad, "items": [item], "total": 1, "status": "completed"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/sales",
        headers=headers,
        json={
            "party_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
            "total": 1,
            "status": "completed",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
