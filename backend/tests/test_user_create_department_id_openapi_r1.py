"""UserCreate.department_id ∈ UuidIdValue OpenAPI honesty (BR-3)."""

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
    "email": "tip300@example.com",
    "full_name": "Tip Three Hundred",
    "password": "SecurePass123!",
}


def test_user_create_department_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = UserCreate.model_validate(_BASE)
    assert omit.department_id is None
    ok = UserCreate.model_validate({**_BASE, "department_id": f"  {_VALID}  "})
    assert ok.department_id == _VALID.lower()
    nullish = UserCreate.model_validate({**_BASE, "department_id": None})
    assert nullish.department_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "dept_001", "a b"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate({**_BASE, "department_id": bad})


def test_user_create_department_id_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User department"' in page
    assert "department_id: form.department_id.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User create department_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "User department" in docs
    assert "POST /users" in docs


@pytest.mark.asyncio
async def test_user_create_department_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for i, bad in enumerate(("", "!!!", "http://evil", "not-a-uuid", "dept_001")):
        resp = await ac.post(
            "/api/v1/users",
            headers=admin,
            json={
                "email": f"tip300-bad-{suffix}-{i}@example.com",
                "full_name": "Tip 300 Bad Department",
                "password": "SecurePass123!",
                "department_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip300-omit-{suffix}@example.com",
            "full_name": "Tip 300 Omit Department",
            "password": "SecurePass123!",
        },
    )
    assert omit.status_code == 200, omit.text
    omit_user = (
        omit.json()["data"]["user"]
        if "user" in omit.json().get("data", {})
        else omit.json()["data"]
    )
    assert omit_user.get("department_id") in (None, "")

    missing = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip300-missing-{suffix}@example.com",
            "full_name": "Tip 300 Missing Department",
            "password": "SecurePass123!",
            "department_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
