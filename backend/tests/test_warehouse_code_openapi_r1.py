"""WarehouseCreate.code ∈ WarehouseCodeValue OpenAPI (BR-2.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import WarehouseCodeValue, WarehouseCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(WarehouseCodeValue)


def test_warehouse_code_value_schema():
    assert _code.validate_python("  wh-01  ") == "wh-01"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 51):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = WarehouseCreate.model_validate({"name": "Main Stock", "code": "  WH01  "})
    assert ok.code == "WH01"
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate({"name": "Main Stock", "code": "!!!"})
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate({"name": "Main Stock", "code": ""})


def test_warehouse_code_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse code"' in page
    assert "code: whCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse code OpenAPI" in agents
    assert "WarehouseCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WarehouseCodeValue" in docs
    assert "Warehouse code" in docs


@pytest.mark.asyncio
async def test_warehouse_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/warehouses",
            headers=headers,
            json={"name": f"TIP223 WH {suffix}", "code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "name": f"TIP223 WH OK {suffix}",
            "code": f"  w223{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["code"] == f"w223{suffix}".upper()
