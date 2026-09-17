"""SalesReturnPost.liquid_account_id ∈ UuidIdValue OpenAPI honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SalesReturnPost, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_sr_post_liquid_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = SalesReturnPost.model_validate({})
    assert omit.liquid_account_id is None
    ok = SalesReturnPost.model_validate({"liquid_account_id": f"  {_VALID}  "})
    assert ok.liquid_account_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        with pytest.raises(ValidationError):
            SalesReturnPost.model_validate({"liquid_account_id": bad})


def test_sr_post_liquid_account_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales return post liquid_account_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "liquid_account_id" in docs
    assert "/sales/returns" in docs


@pytest.mark.asyncio
async def test_sr_post_liquid_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rid = str(uuid4())
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            f"/api/v1/sales/returns/{rid}/post",
            headers=headers,
            json={"settlement_method": "adjust", "liquid_account_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/sales/returns/{rid}/post",
        headers=headers,
        json={
            "settlement_method": "adjust",
            "liquid_account_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
