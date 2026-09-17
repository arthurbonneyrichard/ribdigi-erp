"""BrandCreate / BrandUpdate.description OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BrandCreate, BrandUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_brand_description_schema():
    omit = BrandCreate.model_validate({"code": "B1", "name": "Acme"})
    assert omit.description is None
    nullish = BrandCreate.model_validate(
        {"code": "B1", "name": "Acme", "description": None}
    )
    assert nullish.description is None
    ok = BrandCreate.model_validate(
        {"code": "B1", "name": "Acme", "description": "  Heritage line  "}
    )
    assert ok.description == "Heritage line"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BrandCreate.model_validate(
                {"code": "B1", "name": "Acme", "description": bad}
            )

    patch_omit = BrandUpdate.model_validate({})
    assert patch_omit.description is None
    patch_ok = BrandUpdate.model_validate({"description": " Renamed blurb "})
    assert patch_ok.description == "Renamed blurb"
    with pytest.raises(ValidationError):
        BrandUpdate.model_validate({"description": "!!!"})
    with pytest.raises(ValidationError):
        BrandUpdate.model_validate({"description": "  "})


def test_brand_description_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Brand description"' in page
    assert "brandDescription.trim() || null" in page
    assert 'aria-label="Add brand"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Brand description OpenAPI" in agents
    assert "BrandDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BrandDescriptionValue" in docs
    assert "Brand description" in docs


@pytest.mark.asyncio
async def test_brand_description_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/catalog/brands",
            headers=admin,
            json={
                "code": f"T156{suffix[:4]}",
                "name": f"Tip156 Bad {suffix}",
                "description": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/catalog/brands",
        headers=admin,
        json={"code": f"O156{suffix[:4]}", "name": f"Tip156 Omit {suffix}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("description") in (None, "")

    ok = await ac.post(
        "/api/v1/catalog/brands",
        headers=admin,
        json={
            "code": f"K156{suffix[:4]}",
            "name": f"Tip156 Ok {suffix}",
            "description": f"  Tip156 narrative {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    bid = ok.json()["data"]["id"]
    assert ok.json()["data"]["description"] == f"Tip156 narrative {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/catalog/brands/{bid}",
            headers=admin,
            json={"description": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/catalog/brands/{bid}",
        headers=admin,
        json={"description": f"  Tip156 renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["description"] == f"Tip156 renamed {suffix}"
