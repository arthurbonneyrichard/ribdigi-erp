"""Purchase request lifecycle: draft → pending → approved → converted PO."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _mgr_headers(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _ensure_supplier(ac, headers) -> str:
    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PR Supplier"},
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]


@pytest.mark.asyncio
async def test_purchase_request_approve_convert_flow(client):
    ac, seed = client
    mgr = await _mgr_headers(ac)
    super_h = await _super_headers(ac, seed)

    supplier_id = await _ensure_supplier(ac, mgr)
    product_id = seed["p1"].id

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=mgr,
        json={
            "supplier_id": supplier_id,
            "department": "Store Ops",
            "items": [{"product_id": product_id, "quantity": 12, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    pr = created.json()["data"]
    assert pr["status"] == "draft"
    assert pr["department"] == "Store Ops"
    assert len(pr["items"]) == 1

    submitted = await ac.post(
        f"/api/v1/purchasing/requests/{pr['id']}/submit",
        headers=mgr,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    # Creator cannot approve own request
    self_approve = await ac.post(
        f"/api/v1/purchasing/requests/{pr['id']}/approve",
        headers=mgr,
    )
    assert self_approve.status_code == 403

    approved = await ac.post(
        f"/api/v1/purchasing/requests/{pr['id']}/approve",
        headers=super_h,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["approved_by"]

    converted = await ac.post(
        f"/api/v1/purchasing/requests/{pr['id']}/convert",
        headers=mgr,
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()["data"]
    assert body["request"]["status"] == "converted"
    assert body["purchase_order"]["status"] == "draft"
    assert body["purchase_order"]["purchase_request_id"] == pr["id"]
    assert body["purchase_order"]["items"][0]["quantity"] == 12
    assert body["request"]["purchase_order_id"] == body["purchase_order"]["id"]


@pytest.mark.asyncio
async def test_purchase_request_reject_and_isolation(client):
    ac, seed = client
    mgr = await _mgr_headers(ac)
    super_h = await _super_headers(ac, seed)

    supplier_id = await _ensure_supplier(ac, mgr)
    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=mgr,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 3}],
        },
    )
    pr_id = created.json()["data"]["id"]
    await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=mgr)

    rejected = await ac.post(
        f"/api/v1/purchasing/requests/{pr_id}/reject",
        headers=super_h,
        json={"reason": "Budget hold"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["rejection_reason"] == "Budget hold"

    bad = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=mgr)
    assert bad.status_code == 409

    foreign = await ac.get(
        f"/api/v1/purchasing/requests/{pr_id}",
        headers=await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta"),
    )
    assert foreign.status_code in {403, 404}
