"""DepartmentUpdate.head_user_id ∈ UuidIdValue OpenAPI honesty (BR-2.5 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import DepartmentUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_department_update_head_user_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = DepartmentUpdate.model_validate({})
    assert omit.head_user_id is None
    ok = DepartmentUpdate.model_validate({"head_user_id": f"  {_VALID}  "})
    assert ok.head_user_id == _VALID.lower()
    nullish = DepartmentUpdate.model_validate({"head_user_id": None})
    assert nullish.head_user_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "user_001", "a b"):
        with pytest.raises(ValidationError):
            DepartmentUpdate.model_validate({"head_user_id": bad})


def test_department_update_head_user_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Edit department head" in page
    assert "head_user_id: deptHeadId.trim() || null" in page
    assert "clear_head: !deptHeadId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Department update head_user_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit department head" in docs
    assert "PATCH /departments/{department_id}" in docs


@pytest.mark.asyncio
async def test_department_update_head_user_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": f"D330{suffix[:4]}".upper(), "name": f"Tip330 Dept {suffix}"},
    )
    assert created.status_code == 200, created.text
    dept_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
        resp = await ac.patch(
            f"/api/v1/departments/{dept_id}",
            headers=headers,
            json={"head_user_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/departments/{dept_id}",
        headers=headers,
        json={"name": f"Tip330 omit head {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/departments/{dept_id}",
        headers=headers,
        json={"head_user_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
