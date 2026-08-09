"""Purchase order amendment tracking."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _create_sent_po(ac, headers, product_id: str, *, qty: float = 10, price: float = 5):
    supplier = await ac.post("/api/v1/suppliers", headers=headers, json={"name": "Amend Sup"})
    assert supplier.status_code == 200, supplier.text
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "Original",
            "items": [{"product_id": product_id, "quantity": qty, "unit_price": price}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    return sent.json()["data"]


@pytest.mark.asyncio
async def test_draft_patch_without_amendment_history(client):
    ac, seed = client
    headers = await _mgr(ac)
    supplier = await ac.post("/api/v1/suppliers", headers=headers, json={"name": "Draft Sup"})
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 3}],
        },
    )
    po_id = po.json()["data"]["id"]
    line_id = po.json()["data"]["items"][0]["id"]

    patched = await ac.patch(
        f"/api/v1/purchasing/orders/{po_id}",
        headers=headers,
        json={
            "notes": "Updated draft",
            "items": [
                {
                    "id": line_id,
                    "product_id": seed["p1"].id,
                    "quantity": 4,
                    "unit_price": 3,
                }
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["notes"] == "Updated draft"
    assert data["items"][0]["quantity"] == 4
    assert data["revision"] == 1
    assert data["amendment_count"] == 0
    assert data["total_amount"] == 12.0


@pytest.mark.asyncio
async def test_sent_po_amend_bumps_revision_and_history(client):
    ac, seed = client
    headers = await _mgr(ac)
    po = await _create_sent_po(ac, headers, seed["p1"].id, qty=10, price=5)
    po_id = po["id"]
    line_id = po["items"][0]["id"]

    missing_reason = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={"items": [{"id": line_id, "product_id": seed["p1"].id, "quantity": 12, "unit_price": 5}]},
    )
    assert missing_reason.status_code == 422

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={
            "reason": "Supplier confirmed extra units",
            "notes": "Amended notes",
            "items": [
                {
                    "id": line_id,
                    "product_id": seed["p1"].id,
                    "quantity": 12,
                    "unit_price": 5.5,
                }
            ],
        },
    )
    assert amended.status_code == 200, amended.text
    data = amended.json()["data"]
    assert data["revision"] == 2
    assert data["amendment_count"] == 1
    assert data["notes"] == "Amended notes"
    assert data["items"][0]["quantity"] == 12
    assert data["total_amount"] == 66.0

    history = await ac.get(f"/api/v1/purchasing/orders/{po_id}/amendments", headers=headers)
    assert history.status_code == 200, history.text
    rows = history.json()["data"]
    assert len(rows) == 1
    assert rows[0]["revision"] == 2
    assert rows[0]["reason"] == "Supplier confirmed extra units"
    assert rows[0]["changes"]["before"]["header"]["total_amount"] == 50.0
    assert rows[0]["changes"]["after"]["header"]["total_amount"] == 66.0


@pytest.mark.asyncio
async def test_amend_cannot_reduce_below_received(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    po = await _create_sent_po(ac, headers, seed["p1"].id, qty=20, price=2)
    po_id = po["id"]
    line_id = po["items"][0]["id"]

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": line_id,
                    "received_qty": 8,
                    "accepted_qty": 8,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text

    bad = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={
            "reason": "Cut order",
            "items": [
                {
                    "id": line_id,
                    "product_id": seed["p1"].id,
                    "quantity": 5,
                    "unit_price": 2,
                }
            ],
        },
    )
    assert bad.status_code == 400
    assert "received" in bad.json()["detail"].lower()

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={
            "reason": "Reduce outstanding only",
            "items": [
                {
                    "id": line_id,
                    "product_id": seed["p1"].id,
                    "quantity": 8,
                    "unit_price": 2,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "received"
    assert ok.json()["data"]["revision"] == 2
