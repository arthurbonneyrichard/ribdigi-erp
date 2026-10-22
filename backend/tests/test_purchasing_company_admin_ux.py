"""Purchasing persist, isolation, numbering lock, and Company Admin UI strings."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_purchasing_nav_distinguishes_receive_goods_and_supplier_bills():
    shell = (ROOT / "frontend" / "components" / "Shell.tsx").read_text(encoding="utf-8")
    page = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "['Supplier Bills', '/purchasing?tab=invoices'" in shell
    assert "['Receive Goods', '/purchasing?tab=grn'" in shell
    assert "['History', '/purchasing?tab=history'" in shell
    assert "/reports?tab=purchases" not in shell
    assert "['Purchases', '/purchasing?tab=invoices'" not in shell
    assert "Purchase Goods" not in shell
    assert "1 Suppliers" in page
    assert "2 Orders" in page
    assert "3 Receive goods" in page
    assert "4 Supplier bills" in page
    assert "5 Returns" in page
    assert "['grn', 'Receive Goods']" in page
    assert "['invoices', 'Supplier Bills']" in page
    assert "['history', 'History']" in page
    assert "Purchase history" in page
    assert "BR-6.3" not in page
    assert "BR-6.5" not in page


@pytest.mark.asyncio
async def test_po_grn_bill_persist_isolation_and_locked_numbers(client, db_session, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    admin = await _super(ac, seed)
    year = datetime.utcnow().year

    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email="admin@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await db_session.commit()
    beta = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")

    hack = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": "00000000-0000-0000-0000-000000000001",
            "po_number": "CLIENT-1",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert hack.status_code == 422, hack.text

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "UX Persist Supplier", "email": "ux-persist@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    prefix_lock = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={"purchase_order_numbering": {"prefix": "HACK", "next_number": 1}},
    )
    assert prefix_lock.status_code == 200, prefix_lock.text
    assert prefix_lock.json()["data"]["purchase_order_numbering"]["prefix"] == "PO"

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["po_number"].startswith(f"PO-{year}-")
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]

    foreign = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=beta)
    assert foreign.status_code == 404

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text

    grn_body = {
        "purchase_order_id": po_id,
        "items": [
            {
                "po_item_id": po_item_id,
                "received_qty": 2,
                "accepted_qty": 2,
            }
        ],
    }
    grn = await ac.post("/api/v1/purchasing/grn", headers=admin, json=grn_body)
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["grn_number"].startswith(f"GRN-{year}-")
    grn_id = grn.json()["data"]["id"]

    retry = await ac.post("/api/v1/purchasing/grn", headers=admin, json=grn_body)
    assert retry.status_code == 409, retry.text

    foreign_grn = await ac.get(f"/api/v1/purchasing/grn/{grn_id}", headers=beta)
    assert foreign_grn.status_code == 404

    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id, "supplier_invoice_number": "VEN-88"},
    )
    assert bill.status_code == 200, bill.text
    assert bill.json()["data"]["invoice_number"].startswith(f"PINV-{year}-")
    listed = await ac.get("/api/v1/purchasing/invoices", headers=admin)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["data"]}
    assert bill.json()["data"]["id"] in ids
