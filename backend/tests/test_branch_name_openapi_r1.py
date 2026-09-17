"""BranchCreate / BranchUpdate.name OpenAPI honesty (BR-2.3 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BranchCreate, BranchUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_branch_name_schema():
    ok = BranchCreate.model_validate({"name": "  East Wing  ", "code": "EW01"})
    assert ok.name == "East Wing"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BranchCreate.model_validate({"name": bad, "code": "X1"})

    patch_omit = BranchUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = BranchUpdate.model_validate({"name": " Renamed Branch "})
    assert patch_ok.name == "Renamed Branch"
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        BranchUpdate.model_validate({"name": "  "})


def test_branch_name_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Branch name" in stores
    assert "Edit branch name" in stores
    assert "brName.trim()" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Branch name OpenAPI" in agents
    assert "BranchNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BranchNameValue" in docs
    assert "Branch name" in docs
    assert "Edit branch name" in docs


@pytest.mark.asyncio
async def test_branch_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    br_code = f"B128{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/branches",
            headers=headers,
            json={"name": bad, "code": br_code},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"name": f"  Tip128 Branch {suffix}  ", "code": br_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip128 Branch {suffix}"
    branch_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip128 Branch {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
