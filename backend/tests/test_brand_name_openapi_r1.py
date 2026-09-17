"""BrandCreate / BrandUpdate.name OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BrandCreate, BrandUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_brand_name_schema():
    ok = BrandCreate.model_validate({"name": "  Acme Brand  ", "code": "ACME"})
    assert ok.name == "Acme Brand"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BrandCreate.model_validate({"name": bad, "code": "X1"})

    patch_omit = BrandUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = BrandUpdate.model_validate({"name": " Renamed Brand "})
    assert patch_ok.name == "Renamed Brand"
    with pytest.raises(ValidationError):
        BrandUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        BrandUpdate.model_validate({"name": "  "})


def test_brand_name_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Brand name"' in inv
    assert "brandName.trim()" in inv
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Brand name OpenAPI" in agents
    assert "BrandNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BrandNameValue" in docs
    assert "Brand name" in docs


@pytest.mark.asyncio
async def test_brand_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    brand_code = f"BR129{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/catalog/brands",
            headers=headers,
            json={"name": bad, "code": brand_code},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"name": f"  Tip129 Brand {suffix}  ", "code": brand_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip129 Brand {suffix}"
    brand_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip129 Brand {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
