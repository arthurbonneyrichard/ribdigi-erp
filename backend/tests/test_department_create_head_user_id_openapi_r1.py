"""DepartmentCreate.head_user_id ∈ UuidIdValue OpenAPI honesty (BR-2.5 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import DepartmentCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_department_create_head_user_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = DepartmentCreate.model_validate({"code": "SALES", "name": "Sales"})
    assert omit.head_user_id is None
    ok = DepartmentCreate.model_validate(
        {"code": "SALES", "name": "Sales", "head_user_id": f"  {_VALID}  "}
    )
    assert ok.head_user_id == _VALID.lower()
    nullish = DepartmentCreate.model_validate(
        {"code": "SALES", "name": "Sales", "head_user_id": None}
    )
    assert nullish.head_user_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "user_001", "a b"):
        with pytest.raises(ValidationError):
            DepartmentCreate.model_validate(
                {"code": "SALES", "name": "Sales", "head_user_id": bad}
            )


def test_department_create_head_user_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Department head" in page
    assert "head_user_id: deptHeadId.trim() || null" in page
    assert 'aria-label="Create department"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Department create head_user_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Department head" in docs
    assert "POST /departments" in docs


@pytest.mark.asyncio
async def test_department_create_head_user_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
        resp = await ac.post(
            "/api/v1/departments",
            headers=headers,
            json={
                "code": f"D329{suffix[:4]}".upper(),
                "name": f"Tip329 Dept {suffix}",
                "head_user_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": f"D329O{suffix[:3]}".upper(),
            "name": f"Tip329 omit head {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": f"D329M{suffix[:3]}".upper(),
            "name": f"Tip329 missing head {suffix}",
            "head_user_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
