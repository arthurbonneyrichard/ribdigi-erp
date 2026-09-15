"""BranchCreate.code ∈ BranchCodeValue OpenAPI (BR-2.2 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BranchCodeValue, BranchCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(BranchCodeValue)


def test_branch_code_value_schema():
    assert _code.validate_python("  br-01  ") == "br-01"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = BranchCreate.model_validate({"name": "Accra Branch", "code": "  BR01  "})
    assert ok.code == "BR01"
    with pytest.raises(ValidationError):
        BranchCreate.model_validate({"name": "Accra Branch", "code": "!!!"})
    with pytest.raises(ValidationError):
        BranchCreate.model_validate({"name": "Accra Branch", "code": ""})


def test_branch_code_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Branch code"' in page
    assert "code: brCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Branch code OpenAPI" in agents
    assert "BranchCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BranchCodeValue" in docs
    assert "Branch code" in docs


@pytest.mark.asyncio
async def test_branch_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/branches",
            headers=headers,
            json={"name": f"TIP224 Branch {suffix}", "code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "name": f"TIP224 Branch OK {suffix}",
            "code": f"  b224{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["code"] == f"b224{suffix}".upper()
