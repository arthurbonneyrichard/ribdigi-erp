"""catalog unit code ∈ UnitCodeValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UnitCodeValue, UnitOfMeasureCreate, UnitOfMeasureUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(UnitCodeValue)


def test_unit_code_value_schema():
    assert _code.validate_python("  box12  ") == "box12"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 21):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = UnitOfMeasureCreate.model_validate({"code": "  BOX  ", "name": "Box"})
    assert ok.code == "BOX"
    with pytest.raises(ValidationError):
        UnitOfMeasureCreate.model_validate({"code": "!!!", "name": "Box"})
    with pytest.raises(ValidationError):
        UnitOfMeasureCreate.model_validate({"code": "", "name": "Box"})

    patch_ok = UnitOfMeasureUpdate.model_validate({"code": " CS "})
    assert patch_ok.code == "CS"
    with pytest.raises(ValidationError):
        UnitOfMeasureUpdate.model_validate({"code": "http://x"})


def test_unit_code_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Unit code"' in page
    assert "code: unitCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Unit code OpenAPI" in agents
    assert "UnitCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UnitCodeValue" in docs
    assert "Unit code" in docs


@pytest.mark.asyncio
async def test_unit_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/catalog/units",
            headers=headers,
            json={"code": bad, "name": f"TIP221 Unit {suffix}"},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": f"  u221{suffix}  ",
            "name": f"TIP221 Unit OK {suffix}",
        },
    )
    assert hello.status_code == 200, hello.text
    # service uppercases stored code
    assert hello.json()["data"]["code"] == f"u221{suffix}".upper()
    unit_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/catalog/units/{unit_id}",
        headers=headers,
        json={"code": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text
