"""CustomRoleCreate/Update.permissions OpenAPI honesty (BR-3.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import CustomRoleCreate, CustomRoleUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_custom_role_permissions_schema_forbid():
    ok = CustomRoleCreate.model_validate(
        {
            "key": "warehouse_lead",
            "label": "Warehouse Lead",
            "permissions": {"Inventory": ["READ", "write"]},
        }
    )
    assert ok.permissions == {"inventory": ["read", "write"]}

    clone = CustomRoleCreate.model_validate(
        {"key": "clone_a", "label": "Clone A", "base_role": "inventory_officer"}
    )
    assert clone.permissions is None

    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"inventory": ["read"]}, "extra": 1}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {}}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"spaceship": ["read"]}}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"inventory": ["launch"]}}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"inventory": []}}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"*": ["*"]}}
        )
    # platform modules are not assignable on custom roles
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "permissions": {"platform": ["read"]}}
        )

    patch_ok = CustomRoleUpdate.model_validate({"permissions": {"sales": ["read"]}})
    assert patch_ok.permissions == {"sales": ["read"]}
    with pytest.raises(ValidationError):
        CustomRoleUpdate.model_validate({"permissions": {"inventory": ["nope"]}})
    with pytest.raises(ValidationError):
        CustomRoleUpdate.model_validate({"is_active": True, "unknown": True})


def test_custom_role_permissions_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Custom role key"' in page
    assert 'aria-label="Custom role label"' in page
    assert 'aria-label="Clone from system role"' in page
    assert 'aria-label="Create custom role"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Custom role permissions OpenAPI" in agents
    assert "ASSIGNABLE_MODULES" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ApiKeyPermissionAction" in docs
    assert "extra=forbid" in docs
    assert "POST /roles" in docs


@pytest.mark.asyncio
async def test_custom_role_permissions_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    bad_module = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "bad_mod_role",
            "label": "Bad Mod",
            "permissions": {"spaceship": ["read"]},
        },
    )
    assert bad_module.status_code == 422, bad_module.text

    bad_action = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "bad_act_role",
            "label": "Bad Act",
            "permissions": {"inventory": ["launch"]},
        },
    )
    assert bad_action.status_code == 422, bad_action.text

    wildcard = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "star_role",
            "label": "Star",
            "permissions": {"*": ["*"]},
        },
    )
    assert wildcard.status_code == 422, wildcard.text

    # Happy path: explicit permissions (hello-world)
    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "key": "openapi_perm_hw",
            "label": "OpenAPI Perm HW",
            "permissions": {"inventory": ["read", "write"], "dashboard": ["read"]},
            "record_scope": "own",
        },
    )
    assert created.status_code in {200, 201}, created.text
    body = created.json()["data"]
    assert body.get("role") == "openapi_perm_hw"
    assert "inventory" in (body.get("permissions") or {})

    # PATCH bad permissions → 422; soft activate still OK
    patched_bad = await ac.patch(
        "/api/v1/roles/openapi_perm_hw",
        headers=headers,
        json={"permissions": {"inventory": ["teleport"]}},
    )
    assert patched_bad.status_code == 422, patched_bad.text

    patched_ok = await ac.patch(
        "/api/v1/roles/openapi_perm_hw",
        headers=headers,
        json={"is_active": True},
    )
    assert patched_ok.status_code == 200, patched_ok.text
