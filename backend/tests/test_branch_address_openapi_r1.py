"""BranchCreate / BranchUpdate.address OpenAPI honesty (Multi-Store Branch address)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BranchCreate, BranchUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_branch_address_schema():
    create_omit = BranchCreate.model_validate({"code": "ACC", "name": "Accra"})
    assert create_omit.address is None
    create_ok = BranchCreate.model_validate(
        {"code": "KUM", "name": "Kumasi", "address": "  12 Branch Rd  "}
    )
    assert create_ok.address == "12 Branch Rd"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            BranchCreate.model_validate({"code": "X", "name": "X", "address": bad})

    patch_omit = BranchUpdate.model_validate({})
    assert patch_omit.address is None
    patch_ok = BranchUpdate.model_validate({"address": "99 Ring Road"})
    assert patch_ok.address == "99 Ring Road"
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"address": ""})
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"address": "!!!"})


def test_branch_address_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Branch address"' in page
    assert "AddressValue" in page or "Omit blank address" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Branch address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Branch address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_branch_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={"code": "BLA", "name": "Blank Address", "address": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={"code": "BAD", "name": "Bad Address", "address": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/branches",
        headers=admin,
        json={
            "code": "OKA",
            "name": "Ok Address Branch",
            "address": "12 Branch Street, Accra",
        },
    )
    assert ok.status_code == 200, ok.text
    branch = ok.json()["data"]
    assert branch["address"] == "12 Branch Street, Accra"
    branch_id = branch["id"]

    patch_bad = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"address": "http://addr.example"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"address": "99 Ring Road, Accra"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["address"] == "99 Ring Road, Accra"

    omit = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=admin,
        json={"name": "Ok Address Branch"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["address"] == "99 Ring Road, Accra"
