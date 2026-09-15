"""User / custom-role key shape OpenAPI honesty (BR-3.1 / BR-3.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import CustomRoleCreate, UserCreate, UserUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_role_key_schema():
    created = UserCreate.model_validate(
        {
            "email": "a@example.com",
            "full_name": "A",
            "password": "SecurePass123!",
            "role": " Cashier ",
        }
    )
    assert created.role == "cashier"

    omitted = UserCreate.model_validate(
        {
            "email": "b@example.com",
            "full_name": "B",
            "password": "SecurePass123!",
        }
    )
    assert omitted.role == "cashier"

    for bad in ("", " ", "A", "Cashier!", "1cashier", "super admin"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate(
                {
                    "email": "c@example.com",
                    "full_name": "C",
                    "password": "SecurePass123!",
                    "role": bad,
                }
            )

    bare = UserUpdate.model_validate({})
    assert bare.role is None
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"role": ""})
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"role": "!!"})

    key_ok = CustomRoleCreate.model_validate(
        {"key": " Floor_Lead ", "label": "Floor", "base_role": "cashier"}
    )
    assert key_ok.key == "floor_lead"
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "", "label": "X", "base_role": "cashier"}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "Bad Key!", "label": "X", "base_role": "cashier"}
        )


def test_role_key_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User role"' in page
    assert "Change role for ${r.email}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Role key shape OpenAPI" in agents
    assert "RoleKeyValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "RoleKeyValue" in docs
    assert "Users **User role** select" in docs


@pytest.mark.asyncio
async def test_user_role_blank_malformed_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    base = {
        "email": f"rolekey-{uuid4().hex[:8]}@example.com",
        "full_name": "Role Key",
        "password": "SecurePass123!",
    }

    blank = await ac.post("/api/v1/users", headers=headers, json={**base, "role": ""})
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={**base, "role": "Cashier!"},
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={**base, "role": "Sales_Officer"},
    )
    assert ok.status_code == 200, ok.text
    user = ok.json()["data"]["user"]
    assert user["role"] == "sales_officer"

    patch_blank = await ac.patch(
        f"/api/v1/users/{user['id']}",
        headers=headers,
        json={"role": ""},
    )
    assert patch_blank.status_code == 422, patch_blank.text

    # Soft-deactivate so leftover users don't clutter other tests.
    deactivate = await ac.patch(
        f"/api/v1/users/{user['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivate.status_code == 200, deactivate.text


@pytest.mark.asyncio
async def test_custom_role_key_blank_malformed_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={"key": "", "label": "X", "base_role": "cashier"},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={"key": "Bad Key!", "label": "X", "base_role": "cashier"},
    )
    assert bad.status_code == 422, bad.text
