"""StoreCreate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-2.3 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StoreCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_store_create_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = StoreCreate.model_validate({"code": "DT01", "name": "Downtown"})
    assert omit.branch_id is None
    ok = StoreCreate.model_validate(
        {"code": "DT01", "name": "Downtown", "branch_id": f"  {_VALID}  "}
    )
    assert ok.branch_id == _VALID.lower()
    nullish = StoreCreate.model_validate(
        {"code": "DT01", "name": "Downtown", "branch_id": None}
    )
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "br_001", "a b"):
        with pytest.raises(ValidationError):
            StoreCreate.model_validate(
                {"code": "DT01", "name": "Downtown", "branch_id": bad}
            )


def test_store_create_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Store branch"' in page
    assert "branch_id: branchId.trim() || null" in page
    assert 'aria-label="Create store"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store create branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Store branch" in docs
    assert "POST /stores" in docs


@pytest.mark.asyncio
async def test_store_create_branch_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "br_001"):
        resp = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={
                "code": f"S333{suffix[:4]}".upper(),
                "name": f"Tip333 Store {suffix}",
                "branch_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": f"S333O{suffix[:3]}".upper(),
            "name": f"Tip333 omit branch {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": f"S333M{suffix[:3]}".upper(),
            "name": f"Tip333 missing branch {suffix}",
            "branch_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
