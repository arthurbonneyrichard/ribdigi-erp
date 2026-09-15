"""DepartmentCreate.code ∈ DepartmentCodeValue OpenAPI (BR-2.5 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import DepartmentCodeValue, DepartmentCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(DepartmentCodeValue)


def test_department_code_value_schema():
    assert _code.validate_python("  sales  ") == "sales"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = DepartmentCreate.model_validate({"name": "Sales Ops", "code": "  SALES  "})
    assert ok.code == "SALES"
    with pytest.raises(ValidationError):
        DepartmentCreate.model_validate({"name": "Sales Ops", "code": "!!!"})
    with pytest.raises(ValidationError):
        DepartmentCreate.model_validate({"name": "Sales Ops", "code": ""})


def test_department_code_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Department code"' in page
    assert "code: deptCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Department code OpenAPI" in agents
    assert "DepartmentCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "DepartmentCodeValue" in docs
    assert "Department code" in docs


@pytest.mark.asyncio
async def test_department_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/departments",
            headers=headers,
            json={"name": f"TIP225 Dept {suffix}", "code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "name": f"TIP225 Dept OK {suffix}",
            "code": f"  d225{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["code"] == f"d225{suffix}".upper()
