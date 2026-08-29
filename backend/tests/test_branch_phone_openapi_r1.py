"""BranchCreate / BranchUpdate.phone OpenAPI honesty (Multi-Store Branch phone)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BranchCreate, BranchUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_branch_phone_schema():
    create_omit = BranchCreate.model_validate({"code": "ACC", "name": "Accra"})
    assert create_omit.phone is None
    create_ok = BranchCreate.model_validate(
        {"code": "KUM", "name": "Kumasi", "phone": " +233241111111 "}
    )
    assert create_ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            BranchCreate.model_validate({"code": "X", "name": "X", "phone": bad})

    patch_omit = BranchUpdate.model_validate({})
    assert patch_omit.phone is None
    patch_ok = BranchUpdate.model_validate({"phone": "+233200000001"})
    assert patch_ok.phone == "+233200000001"
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"phone": ""})
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"phone": "not-a-phone"})


def test_branch_phone_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Branch phone"' in page
    assert "brPhone.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Branch phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Branch phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_branch_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={"code": "BLN", "name": "Blank Phone", "phone": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={"code": "BAD", "name": "Bad Phone", "phone": "not-a-phone"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={
            "code": "OKP",
            "name": "Ok Phone Branch",
            "phone": "+233241111111",
        },
    )
    assert ok.status_code == 200, ok.text
    branch = ok.json()["data"]
    assert branch["phone"] == "+233241111111"
    branch_id = branch["id"]

    patch_bad = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"phone": "123"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"phone": "+233200000099"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["phone"] == "+233200000099"

    omit = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"name": "Ok Phone Branch"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["phone"] == "+233200000099"
