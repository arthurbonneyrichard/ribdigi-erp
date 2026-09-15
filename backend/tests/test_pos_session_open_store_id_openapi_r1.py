"""PosSessionOpen.store_id ∈ UuidIdValue OpenAPI honesty (BR-8.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PosSessionOpen, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_pos_session_open_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PosSessionOpen.model_validate({})
    assert omit.store_id is None
    ok = PosSessionOpen.model_validate({"store_id": f"  {_VALID}  "})
    assert ok.store_id == _VALID.lower()
    nullish = PosSessionOpen.model_validate({"store_id": None})
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_001"):
        with pytest.raises(ValidationError):
            PosSessionOpen.model_validate({"store_id": bad})


def test_pos_session_open_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS store"' in page
    assert "store_id: storeId.trim() || null" in page
    assert 'aria-label="Open shift"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS session open store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "POS store" in docs
    assert "/pos/sessions/open" in docs


@pytest.mark.asyncio
async def test_pos_session_open_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    # Close any open shift so open can be exercised cleanly.
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and (cur.json().get("data") or {}).get("session_id"):
        sid = cur.json()["data"]["session_id"]
        await ac.post(
            f"/api/v1/pos/sessions/{sid}/close",
            headers=headers,
            json={"actual_cash": 0},
        )

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_001"):
        resp = await ac.post(
            "/api/v1/pos/sessions/open",
            headers=headers,
            json={"store_id": bad, "opening_cash": 0},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0},
    )
    assert omit.status_code == 200, omit.text
    opened_id = omit.json()["data"].get("session_id") or omit.json()["data"].get("id")
    await ac.post(
        f"/api/v1/pos/sessions/{opened_id}/close",
        headers=headers,
        json={"actual_cash": 0},
    )

    missing = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": f"  {str(uuid4()).upper()}  ", "opening_cash": 0},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
