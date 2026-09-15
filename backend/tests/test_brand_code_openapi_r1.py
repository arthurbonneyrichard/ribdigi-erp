"""catalog brand code ∈ BrandCodeValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BrandCodeValue, BrandCreate, BrandUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(BrandCodeValue)


def test_brand_code_value_schema():
    assert _code.validate_python("  acme-01  ") == "acme-01"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = BrandCreate.model_validate({"code": "  ACME  ", "name": "Acme Co"})
    assert ok.code == "ACME"
    with pytest.raises(ValidationError):
        BrandCreate.model_validate({"code": "!!!", "name": "Acme Co"})
    with pytest.raises(ValidationError):
        BrandCreate.model_validate({"code": "", "name": "Acme Co"})

    patch_ok = BrandUpdate.model_validate({"code": " BETA "})
    assert patch_ok.code == "BETA"
    with pytest.raises(ValidationError):
        BrandUpdate.model_validate({"code": "http://x"})


def test_brand_code_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Brand code"' in page
    assert "code: brandCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Brand code OpenAPI" in agents
    assert "BrandCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BrandCodeValue" in docs
    assert "Brand code" in docs


@pytest.mark.asyncio
async def test_brand_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/catalog/brands",
            headers=headers,
            json={"code": bad, "name": f"TIP220 Brand {suffix}"},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={
            "code": f"  tip220{suffix}  ",
            "name": f"TIP220 Brand OK {suffix}",
        },
    )
    assert hello.status_code == 200, hello.text
    # service uppercases stored code
    assert hello.json()["data"]["code"] == f"tip220{suffix}".upper()
    brand_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=headers,
        json={"code": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text
