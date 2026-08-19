"""CustomRoleCreate / CustomRoleUpdate.label OpenAPI honesty (BR-3.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import CustomRoleCreate, CustomRoleUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_custom_role_label_schema():
    ok = CustomRoleCreate.model_validate(
        {"key": "warehouse_lead", "label": "  Warehouse Lead  ", "base_role": "inventory_officer"}
    )
    assert ok.label == "Warehouse Lead"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            CustomRoleCreate.model_validate(
                {"key": "bad_label_role", "label": bad, "base_role": "cashier"}
            )

    patch_omit = CustomRoleUpdate.model_validate({})
    assert patch_omit.label is None
    patch_ok = CustomRoleUpdate.model_validate({"label": " Renamed Role "})
    assert patch_ok.label == "Renamed Role"
    with pytest.raises(ValidationError):
        CustomRoleUpdate.model_validate({"label": "!!!"})
    with pytest.raises(ValidationError):
        CustomRoleUpdate.model_validate({"label": "  "})


def test_custom_role_label_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Custom role label"' in page
    assert "roleForm.label.trim()" in page
    assert 'aria-label="Create custom role"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Custom role label OpenAPI" in agents
    assert "CustomRoleLabelValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CustomRoleLabelValue" in docs
    assert "Custom role label" in docs


@pytest.mark.asyncio
async def test_custom_role_label_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    key = f"tip138_{suffix}"

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/roles",
            headers=headers,
            json={"key": key, "label": bad, "base_role": "cashier"},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": key,
            "label": f"  Tip138 Role {suffix}  ",
            "base_role": "cashier",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["label"] == f"Tip138 Role {suffix}"

    omit = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=headers,
        json={"is_active": True},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["label"] == f"Tip138 Role {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/roles/{key}",
            headers=headers,
            json={"label": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/roles/{key}",
        headers=headers,
        json={"label": f"  Tip138 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["label"] == f"Tip138 Renamed {suffix}"
