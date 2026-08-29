"""DepartmentCreate / DepartmentUpdate.name OpenAPI honesty (BR-2.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import DepartmentCreate, DepartmentUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_department_name_schema():
    ok = DepartmentCreate.model_validate({"name": "  Sales Ops  ", "code": "SALES"})
    assert ok.name == "Sales Ops"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            DepartmentCreate.model_validate({"name": bad, "code": "X1"})

    patch_omit = DepartmentUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = DepartmentUpdate.model_validate({"name": " Renamed Dept "})
    assert patch_ok.name == "Renamed Dept"
    with pytest.raises(ValidationError):
        DepartmentUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        DepartmentUpdate.model_validate({"name": "  "})


def test_department_name_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Department name" in stores
    assert "Edit department name" in stores
    assert "deptName.trim()" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Department name OpenAPI" in agents
    assert "DepartmentNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "DepartmentNameValue" in docs
    assert "Department name" in docs
    assert "Edit department name" in docs


@pytest.mark.asyncio
async def test_department_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    dept_code = f"D132{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/departments",
            headers=headers,
            json={"name": bad, "code": dept_code},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"name": f"  Tip132 Department {suffix}  ", "code": dept_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip132 Department {suffix}"
    department_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/departments/{department_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/departments/{department_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip132 Department {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/departments/{department_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
