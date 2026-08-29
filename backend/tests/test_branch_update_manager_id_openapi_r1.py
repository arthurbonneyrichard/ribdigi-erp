"""BranchUpdate.manager_id ∈ UuidIdValue OpenAPI honesty (BR-2.2 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BranchUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_branch_update_manager_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = BranchUpdate.model_validate({})
    assert omit.manager_id is None
    ok = BranchUpdate.model_validate({"manager_id": f"  {_VALID}  "})
    assert ok.manager_id == _VALID.lower()
    nullish = BranchUpdate.model_validate({"manager_id": None})
    assert nullish.manager_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "user_001", "a b"):
        with pytest.raises(ValidationError):
            BranchUpdate.model_validate({"manager_id": bad})


def test_branch_update_manager_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Edit branch manager" in page
    assert "manager_id: brManagerId.trim() || null" in page
    assert "clear_manager: !brManagerId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Branch update manager_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit branch manager" in docs
    assert "PATCH /branches/{branch_id}" in docs


@pytest.mark.asyncio
async def test_branch_update_manager_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": f"B328{suffix[:4]}".upper(), "name": f"Tip328 Branch {suffix}"},
    )
    assert created.status_code == 200, created.text
    branch_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
        resp = await ac.patch(
            f"/api/v1/branches/{branch_id}",
            headers=headers,
            json={"manager_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"name": f"Tip328 omit manager {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"manager_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
