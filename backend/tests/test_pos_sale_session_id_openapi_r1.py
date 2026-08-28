"""PosSaleCreate.session_id ∈ UuidIdValue OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PosSaleCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1}]


def test_pos_sale_session_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PosSaleCreate.model_validate({"items": _ITEMS})
    assert omit.session_id is None
    ok = PosSaleCreate.model_validate(
        {"session_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.session_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "sess_001"):
        with pytest.raises(ValidationError):
            PosSaleCreate.model_validate({"session_id": bad, "items": _ITEMS})


def test_pos_sale_session_id_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "session_id: String(session.session_id).trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS sale session_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "session_id" in docs
    assert "/pos/sales" in docs


@pytest.mark.asyncio
async def test_pos_sale_session_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sess_001"):
        resp = await ac.post(
            "/api/v1/pos/sales",
            headers=headers,
            json={
                "session_id": bad,
                "items": [item],
                "total": 1,
                "status": "completed",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
            "total": 1,
            "status": "completed",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
