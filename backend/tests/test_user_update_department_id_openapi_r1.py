"""UserUpdate.department_id ∈ UuidIdValue OpenAPI honesty (BR-3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UserUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_user_update_department_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = UserUpdate.model_validate({"department_id": f"  {_VALID}  "})
    assert ok.department_id == _VALID.lower()
    omit_ok = UserUpdate.model_validate({"full_name": "Renamed"})
    assert omit_ok.department_id is None
    nullish = UserUpdate.model_validate({"department_id": None})
    assert nullish.department_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "dept_001", "a b"):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"department_id": bad})


def test_user_update_department_id_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Edit user department for" in page
    assert "department_id: trimmed" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User update department_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit user department" in docs
    assert "PATCH /users/{user_id}" in docs


@pytest.mark.asyncio
async def test_user_update_department_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip351-{suffix}@example.com",
            "full_name": "Tip 351 User",
            "password": "SecurePass123!",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    user = data["user"] if isinstance(data, dict) and "user" in data else data
    user_id = user["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "dept_001"):
        resp = await ac.patch(
            f"/api/v1/users/{user_id}",
            headers=admin,
            json={"department_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=admin,
        json={"department_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
