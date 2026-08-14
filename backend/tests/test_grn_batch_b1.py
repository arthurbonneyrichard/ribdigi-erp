"""GRN receive with batch / expiry (BR-6.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO GRN Batch",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _sent_po(ac, db_session, *, admin, io, seed, qty: float = 5, vendor: str = "Batch GRN Vendor"):
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": vendor, "kind": "supplier", "email": f"{vendor.replace(' ', '').lower()}@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": qty, "unit_price": 4}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    po_item_id = created.json()["data"]["items"][0]["id"]
    po = await db_session.get(m.PurchaseOrder, po_id)
    po.status = "sent"
    await db_session.commit()
    return po_id, po_item_id


@pytest.mark.asyncio
async def test_grn_batch_required_when_tracks_batches(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-grn-batch-req@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-batch-req@alpha.example.com", tenant_slug="alpha")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = True
    await db_session.commit()

    po_id, po_item_id = await _sent_po(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Batch Req Vendor"
    )

    missing = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 5,
                    "accepted_qty": 5,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert missing.status_code == 400, missing.text
    assert "batch" in missing.text.lower()


@pytest.mark.asyncio
async def test_grn_receive_creates_batch_and_echoes_on_serialize(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-grn-batch-ok@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-batch-ok@alpha.example.com", tenant_slug="alpha")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = True
    stock_before = float(product.stock_qty or 0)
    await db_session.commit()

    po_id, po_item_id = await _sent_po(
        ac, db_session, admin=admin, io=io, seed=seed, qty=4, vendor="Batch OK Vendor"
    )
    mfg = datetime.utcnow() - timedelta(days=10)
    exp = datetime.utcnow() + timedelta(days=120)

    posted = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                    "batch_number": "LOT-GRN-1",
                    "manufacturing_date": mfg.isoformat(),
                    "expiry_date": exp.isoformat(),
                }
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()["data"]
    assert body["items"][0]["batch_number"] == "LOT-GRN-1"
    assert body["items"][0]["expiry_date"]
    assert str(body["items"][0]["expiry_date"])[:10] == exp.date().isoformat()
    assert body["items"][0]["manufacturing_date"]
    assert str(body["items"][0]["manufacturing_date"])[:10] == mfg.date().isoformat()

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_before + 4)

    batches = await ac.get(f"/api/v1/products/{seed['p1'].id}/batches", headers=admin)
    assert batches.status_code == 200
    row = next(b for b in batches.json()["data"] if b["batch_number"] == "LOT-GRN-1")
    assert float(row["quantity"]) >= 4
    assert str(row["expiry_date"])[:10] == exp.date().isoformat()

    got = await ac.get(f"/api/v1/purchasing/grn/{body['id']}", headers=io)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["items"][0]["batch_number"] == "LOT-GRN-1"


@pytest.mark.asyncio
async def test_grn_optional_batch_when_not_tracked(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-grn-batch-opt@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-batch-opt@alpha.example.com", tenant_slug="alpha")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    po_id, po_item_id = await _sent_po(
        ac, db_session, admin=admin, io=io, seed=seed, qty=2, vendor="Batch Opt Vendor"
    )
    posted = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 2,
                    "accepted_qty": 2,
                    "batch_number": "LOT-OPT-1",
                    "expiry_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                }
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["items"][0]["batch_number"] == "LOT-OPT-1"
