"""StoreUpdate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-2.3 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StoreUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_store_update_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = StoreUpdate.model_validate({})
    assert omit.branch_id is None
    ok = StoreUpdate.model_validate({"branch_id": f"  {_VALID}  "})
    assert ok.branch_id == _VALID.lower()
    nullish = StoreUpdate.model_validate({"branch_id": None})
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "br_001", "a b"):
        with pytest.raises(ValidationError):
            StoreUpdate.model_validate({"branch_id": bad})


def test_store_update_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Edit store branch"' in page
    assert "branch_id: editBranchId.trim() || null" in page
    assert "clear_branch: !editBranchId.trim()" in page
    assert 'aria-label="Save store"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store update branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit store branch" in docs
    assert "PATCH /stores/{store_id}" in docs


@pytest.mark.asyncio
async def test_store_update_branch_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": f"S335{suffix[:4]}".upper(), "name": f"Tip335 Store {suffix}"},
    )
    assert created.status_code == 200, created.text
    store_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "br_001"):
        resp = await ac.patch(
            f"/api/v1/stores/{store_id}",
            headers=headers,
            json={"branch_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"name": f"Tip335 omit branch {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"branch_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
