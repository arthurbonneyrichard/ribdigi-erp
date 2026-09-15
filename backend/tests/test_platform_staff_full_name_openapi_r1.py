"""PlatformStaffCreate / PlatformStaffUpdate.full_name OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PlatformStaffCreate, PlatformStaffUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_staff_full_name_schema():
    ok = PlatformStaffCreate.model_validate(
        {
            "email": "ok@example.com",
            "full_name": "  Ada Lovelace  ",
            "password": "SecurePass123!",
        }
    )
    assert ok.full_name == "Ada Lovelace"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PlatformStaffCreate.model_validate(
                {
                    "email": "bad@example.com",
                    "full_name": bad,
                    "password": "SecurePass123!",
                }
            )

    patch_omit = PlatformStaffUpdate.model_validate({})
    assert patch_omit.full_name is None
    patch_ok = PlatformStaffUpdate.model_validate({"full_name": " Renamed Staff "})
    assert patch_ok.full_name == "Renamed Staff"
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"full_name": "!!!"})
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"full_name": "  "})


def test_platform_staff_full_name_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Platform staff full name"' in staff
    assert "form.full_name.trim()" in staff
    assert 'aria-label="Create platform staff"' in staff
    assert "!form.full_name.trim()" in staff
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform staff full name OpenAPI" in agents
    assert "PlatformStaffFullNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PlatformStaffFullNameValue" in docs
    assert "Platform staff full name" in docs


@pytest.mark.asyncio
async def test_platform_staff_full_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/platform/staff",
            headers=admin,
            json={
                "email": f"bad-name-{suffix}-{abs(hash(bad)) % 10000}@example.com",
                "full_name": bad,
                "password": "SecurePass123!",
                "role": "platform_support",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"tip145-{suffix}@example.com",
            "full_name": f"  Tip145 Staff {suffix}  ",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["full_name"] == f"Tip145 Staff {suffix}"
    uid = ok.json()["data"]["id"]

    keep = await ac.patch(
        f"/api/v1/platform/staff/{uid}",
        headers=admin,
        json={"is_active": True},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["full_name"] == f"Tip145 Staff {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/platform/staff/{uid}",
            headers=admin,
            json={"full_name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/platform/staff/{uid}",
        headers=admin,
        json={"full_name": f"  Tip145 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["full_name"] == f"Tip145 Renamed {suffix}"
