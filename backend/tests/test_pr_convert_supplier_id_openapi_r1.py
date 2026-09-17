"""PurchaseRequestConvert.supplier_id ∈ UuidIdValue OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseRequestConvert, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_pr_convert_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PurchaseRequestConvert.model_validate({})
    assert omit.supplier_id is None
    ok = PurchaseRequestConvert.model_validate({"supplier_id": f"  {_VALID}  "})
    assert ok.supplier_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "s1"):
        with pytest.raises(ValidationError):
            PurchaseRequestConvert.model_validate({"supplier_id": bad})


def test_pr_convert_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "aria-label={`Convert purchase request ${r.id}`}" in page
    assert "prAction(r.id, 'convert')" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase request convert supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestConvert" in docs
    assert "/convert" in docs


@pytest.mark.asyncio
async def test_pr_convert_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # Body UuidIdValue 422 fires before convert status / existence checks.
    rid = str(uuid4())

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "s1"):
        resp = await ac.post(
            f"/api/v1/purchasing/requests/{rid}/convert",
            headers=headers,
            json={"supplier_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/convert",
        headers=headers,
        json={"supplier_id": f"  {str(uuid4()).upper()}  "},
    )
    # Missing request → 404; valid UUID supplier on missing PR still not 422.
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
