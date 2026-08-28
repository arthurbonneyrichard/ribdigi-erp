"""DepartmentCreate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-2.4 / BR-13)."""

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


def test_department_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = DepartmentCreate.model_validate({"code": "SALES", "name": "Sales"})
    assert omit.branch_id is None
    ok = DepartmentCreate.model_validate(
        {"code": "SALES", "name": "Sales", "branch_id": f"  {_VALID}  "}
    )
    assert ok.branch_id == _VALID.lower()
    nullish = DepartmentCreate.model_validate(
        {"code": "SALES", "name": "Sales", "branch_id": None}
    )
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "branch_001", "a b"):
        with pytest.raises(ValidationError):
            DepartmentCreate.model_validate(
                {"code": "SALES", "name": "Sales", "branch_id": bad}
            )


def test_department_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Department branch" in page
    assert "branch_id: deptBranchId.trim() || null" in page
    assert 'aria-label="Create department"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Department branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /departments" in docs
    assert "Department branch" in docs


@pytest.mark.asyncio
async def test_department_branch_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    suffix = uuid4().hex[:8]
    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": f"B280{suffix[:4]}".upper(), "name": f"Tip280 Branch {suffix}"},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "branch_001"):
        resp = await ac.post(
            "/api/v1/departments",
            headers=headers,
            json={
                "code": f"T{uuid4().hex[:6].upper()}",
                "name": "Tip280 department",
                "branch_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    code = f"T{uuid4().hex[:6].upper()}"
    ok = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": code,
            "name": "Tip280 with branch",
            "branch_id": f"  {str(branch_id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["branch_id"] == str(branch_id).lower()

    missing = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "code": f"T{uuid4().hex[:6].upper()}",
            "name": "Tip280 missing branch",
            "branch_id": str(uuid4()),
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
