"""Purchase order print and paper issue (no supplier email)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.emailer import clear_dev_outbox
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed):
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-po-print@alpha.example.com",
        full_name="IO PO Print",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def test_po_print_ui_and_docs():
    purchasing = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "ariaLabel: 'Print purchase order'" in purchasing
    assert "aria-label={`Print purchase order ${selected.id}`}" in purchasing
    assert "/purchasing/orders/${current.id}/print" in purchasing
    assert "/purchasing/orders/${po.id}/issue" in purchasing
    assert "Email or print a purchase order" in purchasing
    assert "Hand the paper to the supplier" in purchasing
    assert "ariaLabel: 'Email purchase order'" in purchasing
    docs = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "purchasing/orders/{po_id}/print" in docs
    assert "purchasing/orders/{po_id}/issue" in docs
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase order print / paper issue" in agents


@pytest.mark.asyncio
async def test_print_and_issue_without_supplier_email_then_grn(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-print@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    clear_dev_outbox()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Walk-in Paper Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    assert not (supplier.json()["data"].get("email") or "").strip()

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
            "notes": "Hand this paper to the driver",
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_id = po["id"]
    assert po["status"] == "draft"

    missing = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert missing.status_code == 400
    assert "email" in missing.json()["detail"].lower()

    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=io)
    assert printed.status_code == 200, printed.text
    assert "text/html" in printed.headers.get("content-type", "")
    html = printed.text
    assert po["po_number"] in html
    assert "Walk-in Paper Vendor" in html
    assert "Hand this paper to the driver" in html
    assert seed["p1"].name in html or seed["p1"].sku in html
    assert "Order date" in html
    assert "Due " not in html
    still_draft = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io)
    assert still_draft.json()["data"]["status"] == "draft"
    assert not still_draft.json()["data"].get("emailed_to")

    issued = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert issued.status_code == 200, issued.text
    body = issued.json()["data"]
    assert body["status"] == "sent"
    assert not body.get("emailed_to")
    assert not body.get("emailed_at")

    again = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["status"] == "sent"

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": body["items"][0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["status"] == "posted"


@pytest.mark.asyncio
async def test_issue_rejected_after_cancel_and_print_stays_readable(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-print@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Cancelled Paper Vendor"},
    )
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    po_id = created.json()["data"]["id"]
    cancelled = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=io,
        json={"reason": "Supplier walked away"},
    )
    assert cancelled.status_code == 200, cancelled.text
    blocked = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert blocked.status_code == 409
    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=io)
    assert printed.status_code == 200, printed.text
    assert created.json()["data"]["po_number"] in printed.text
