"""StoreCreate.code ∈ StoreCodeValue OpenAPI (BR-13.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StoreCodeValue, StoreCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(StoreCodeValue)


def test_store_code_value_schema():
    assert _code.validate_python("  dt-01  ") == "dt-01"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 51):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = StoreCreate.model_validate({"name": "Downtown", "code": "  DT01  "})
    assert ok.code == "DT01"
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "Downtown", "code": "!!!"})
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "Downtown", "code": ""})


def test_store_code_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Store code"' in page
    assert "code: code.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store code OpenAPI" in agents
    assert "StoreCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StoreCodeValue" in docs
    assert "Store code" in docs


@pytest.mark.asyncio
async def test_store_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"name": f"TIP222 Store {suffix}", "code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": f"TIP222 Store OK {suffix}",
            "code": f"  s222{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["code"] == f"s222{suffix}".upper()
