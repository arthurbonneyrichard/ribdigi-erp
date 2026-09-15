"""UserCreate.branch_id ∈ UuidIdValue OpenAPI honesty (BR-3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UserCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_BASE = {
    "email": "tip299@example.com",
    "full_name": "Tip Two Nine Nine",
    "password": "SecurePass123!",
}


def test_user_create_branch_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = UserCreate.model_validate(_BASE)
    assert omit.branch_id is None
    ok = UserCreate.model_validate({**_BASE, "branch_id": f"  {_VALID}  "})
    assert ok.branch_id == _VALID.lower()
    nullish = UserCreate.model_validate({**_BASE, "branch_id": None})
    assert nullish.branch_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "br_001", "a b"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate({**_BASE, "branch_id": bad})


def test_user_create_branch_id_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User branch"' in page
    assert "branch_id: form.branch_id.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User create branch_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "User branch" in docs
    assert "POST /users" in docs


@pytest.mark.asyncio
async def test_user_create_branch_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for i, bad in enumerate(("", "!!!", "http://evil", "not-a-uuid", "br_001")):
        resp = await ac.post(
            "/api/v1/users",
            headers=admin,
            json={
                "email": f"tip299-bad-{suffix}-{i}@example.com",
                "full_name": "Tip 299 Bad Branch",
                "password": "SecurePass123!",
                "branch_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip299-omit-{suffix}@example.com",
            "full_name": "Tip 299 Omit Branch",
            "password": "SecurePass123!",
        },
    )
    assert omit.status_code == 200, omit.text
    omit_user = (
        omit.json()["data"]["user"]
        if "user" in omit.json().get("data", {})
        else omit.json()["data"]
    )
    assert omit_user.get("branch_id") in (None, "")

    missing = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip299-missing-{suffix}@example.com",
            "full_name": "Tip 299 Missing Branch",
            "password": "SecurePass123!",
            "branch_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
