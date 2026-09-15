"""PlatformGrantAccess.user_id ∈ UuidIdValue OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PlatformGrantAccess, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_platform_grant_user_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PlatformGrantAccess.model_validate(
        {"user_id": f"  {_VALID}  ", "role": "platform_support"}
    )
    assert ok.user_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "u1", "user_001"):
        with pytest.raises(ValidationError):
            PlatformGrantAccess.model_validate({"user_id": bad})
    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"role": "platform_support"})


def test_platform_grant_user_id_ui_and_docs():
    page = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Grant dashboard"' in page
    assert "user_id: String(row.id).trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform grant user_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/platform/staff/grant" in docs
    assert "Grant dashboard" in docs


@pytest.mark.asyncio
async def test_platform_grant_user_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "u1"):
        resp = await ac.post(
            "/api/v1/platform/staff/grant",
            headers=headers,
            json={"user_id": bad, "role": "platform_support"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/platform/staff/grant",
        headers=headers,
        json={"user_id": f"  {str(uuid4()).upper()}  ", "role": "platform_support"},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
