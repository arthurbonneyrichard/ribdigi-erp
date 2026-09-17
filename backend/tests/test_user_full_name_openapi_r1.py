"""UserCreate / UserUpdate.full_name OpenAPI honesty (BR-3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import UserCreate, UserUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_user_full_name_schema():
    ok = UserCreate.model_validate(
        {
            "email": "ok@example.com",
            "full_name": "  Ada Lovelace  ",
            "password": "SecurePass123!",
        }
    )
    assert ok.full_name == "Ada Lovelace"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate(
                {
                    "email": "bad@example.com",
                    "full_name": bad,
                    "password": "SecurePass123!",
                }
            )

    patch_omit = UserUpdate.model_validate({})
    assert patch_omit.full_name is None
    patch_ok = UserUpdate.model_validate({"full_name": " Renamed User "})
    assert patch_ok.full_name == "Renamed User"
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"full_name": "!!!"})
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"full_name": "  "})


def test_user_full_name_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User full name"' in page
    assert "form.full_name.trim()" in page
    assert 'aria-label="Create user"' in page
    assert "!form.full_name.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User full name OpenAPI" in agents
    assert "UserFullNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UserFullNameValue" in docs
    assert "User full name" in docs


@pytest.mark.asyncio
async def test_user_full_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/users",
            headers=admin,
            json={
                "email": f"bad-name-{suffix}-{abs(hash(bad)) % 10000}@alpha.example.com",
                "full_name": bad,
                "password": "SecurePass123!",
                "role": "cashier",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip146-{suffix}@alpha.example.com",
            "full_name": f"  Tip146 User {suffix}  ",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert ok.status_code == 200, ok.text
    user = ok.json()["data"].get("user") or ok.json()["data"]
    assert user["full_name"] == f"Tip146 User {suffix}"
    uid = user["id"]

    keep = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=admin,
        json={"is_active": True},
    )
    assert keep.status_code == 200, keep.text
    keep_user = keep.json()["data"].get("user") or keep.json()["data"]
    assert keep_user["full_name"] == f"Tip146 User {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/users/{uid}",
            headers=admin,
            json={"full_name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=admin,
        json={"full_name": f"  Tip146 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    renamed_user = renamed.json()["data"].get("user") or renamed.json()["data"]
    assert renamed_user["full_name"] == f"Tip146 Renamed {suffix}"
