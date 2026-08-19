"""Stage 19 A1: API standards fidelity (BR-18.6)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_success_envelope_json_and_v1_prefix(client):
    ac, _seed = client
    res = await ac.get("/api/v1/health")
    assert res.status_code == 200
    assert "application/json" in res.headers.get("content-type", "")
    body = res.json()
    assert body["success"] is True
    assert "data" in body
    assert "message" in body
    assert res.request.url.path.startswith("/api/v1/")


@pytest.mark.asyncio
async def test_rest_methods_and_json_round_trip(client):
    ac, seed = client
    headers = await _mgr(ac)

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["success"] is True
    assert isinstance(listed.json()["data"], list)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "S19 A1 Product",
            "sku": "S19-A1-SKU",
            "cost_price": 1,
            "selling_price": 2,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["success"] is True
    product_id = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"selling_price": 3},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["data"]["selling_price"]) == 3

    got = await ac.get(f"/api/v1/products/{product_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["sku"] == "S19-A1-SKU"


@pytest.mark.asyncio
async def test_http_exception_detail_shape(client):
    ac, seed = client
    headers = await _mgr(ac)

    missing = await ac.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
    detail = missing.json().get("detail")
    assert detail is not None
    assert isinstance(detail, (str, dict))

    unauth = await ac.get("/api/v1/products")
    assert unauth.status_code == 401
    assert "detail" in unauth.json()


@pytest.mark.asyncio
async def test_list_limit_param_on_audit_logs(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    # Generate a few audit rows via login already in admin auth
    limited = await ac.get("/api/v1/audit-logs?limit=2", headers=admin)
    assert limited.status_code == 200, limited.text
    body = limited.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) <= 2


def test_openapi_available_when_not_production():
    client = TestClient(app)
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    spec = openapi.json()
    assert "openapi" in spec
    assert "paths" in spec
    assert any(p.startswith("/api/v1/") for p in spec["paths"])
    docs = client.get("/docs")
    assert docs.status_code == 200


@pytest.mark.asyncio
async def test_webhook_surface_still_present(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    listed = await ac.get("/api/v1/webhooks", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["success"] is True
    assert isinstance(listed.json()["data"], list)


def test_br_18_6_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    section = br.split("#### BR-18.6 API Standards")[1].split("#### BR-19.1")[0].split("### 4.19")[0]
    assert "[x] RESTful design with standard HTTP methods" in section
    assert "[x] JSON request/response format" in section
    assert "[x] Standard error response structure" in section
    assert "[x] Pagination for list endpoints" in section
    assert "[x] Versioning (/api/v1/)" in section
    assert "[x] OpenAPI/Swagger documentation auto-generated" in section
    assert "[x] Webhook support for event subscriptions" in section
    assert "Stage 19 A1" in section

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    a1_line = [ln for ln in plan.splitlines() if "| **A1**" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_api_standards_a1.py" in plan
