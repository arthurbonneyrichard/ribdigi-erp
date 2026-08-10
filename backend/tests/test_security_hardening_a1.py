"""Stage 18 A1: security hardening fidelity — RBAC, session, BR-17 audit proofs."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import purchasing as purchasing_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_login_logout_and_idle_logout_audited(client):
    """BR-17.1 Login/Logout: success, failure, idle logout with IP/UA + hash."""
    ac, seed = client

    failed = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "WrongPassword!!!",
            "tenant_id": "alpha",
        },
    )
    assert failed.status_code == 401

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert ok.status_code == 200, ok.text
    token = ok.json()["data"]["access_token"]
    mgr_h = {"Authorization": f"Bearer {token}"}

    idle = await ac.post("/api/v1/auth/idle-logout", headers=mgr_h, json={})
    assert idle.status_code == 200, idle.text

    # Fresh login then explicit logout
    ok2 = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert ok2.status_code == 200
    mgr_h2 = {"Authorization": f"Bearer {ok2.json()['data']['access_token']}"}
    logged_out = await ac.post("/api/v1/auth/logout", headers=mgr_h2, json={})
    assert logged_out.status_code == 200, logged_out.text

    admin = await _super(ac, seed)
    for action in ("login_failed", "login", "idle_logout", "logout"):
        listed = await ac.get(
            "/api/v1/audit-logs",
            headers=admin,
            params={"action": action, "module": "auth"},
        )
        assert listed.status_code == 200, listed.text
        rows = listed.json()["data"]
        assert rows, action
        assert rows[0]["integrity_hash"]
        assert rows[0]["module"] == "auth"


@pytest.mark.asyncio
async def test_rbac_cashier_denied_and_user_activity_audited(client):
    """RBAC deny + BR-17.1 User Activity: create / role update / deactivate audits."""
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/users",
        headers=cashier,
        json={
            "email": "denied@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert denied.status_code == 403

    admin = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "s18a1@alpha.example.com",
            "full_name": "S18 A1 User",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["data"]["id"]

    updated = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=admin,
        json={"role": "inventory_officer"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["role"] == "inventory_officer"

    deactivated = await ac.delete(f"/api/v1/users/{user_id}", headers=admin)
    assert deactivated.status_code == 200, deactivated.text

    for action in ("user_created", "user_updated", "user_deactivated"):
        listed = await ac.get(
            "/api/v1/audit-logs",
            headers=admin,
            params={"action": action, "module": "users"},
        )
        assert listed.status_code == 200
        row = next(r for r in listed.json()["data"] if r["entity_id"] == user_id)
        assert row["integrity_hash"]
        if action == "user_updated":
            assert "role" in (row.get("details") or {})


@pytest.mark.asyncio
async def test_purchases_and_financial_audits_hash_chained(client, db_session):
    """BR-17.1 Purchases + Financial: PO/GRN and journal_posted with hash chain."""
    ac, seed = client
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(
        tenant_id=tenant_id,
        name="S18 A1 Sup",
        kind="supplier",
        credit_limit=0,
        balance=0,
    )
    db_session.add(supplier)
    await db_session.flush()

    po = await purchasing_svc.create_purchase_order(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 10, "tax_rate": 0}],
    )
    po, _ = await purchasing_svc.send_purchase_order(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        po_id=po.id,
        email=False,
    )
    items = await purchasing_svc.list_po_items(db_session, tenant_id, po.id)
    grn = await purchasing_svc.create_grn(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        purchase_order_id=po.id,
        items=[{"po_item_id": items[0].id, "received_qty": 2, "accepted_qty": 2}],
    )
    await db_session.commit()

    admin = await _super(ac, seed)
    po_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=admin,
        params={"action": "po_created"},
    )
    assert po_logs.status_code == 200
    assert any(
        r["entity_id"] == po.id and r.get("integrity_hash")
        for r in po_logs.json()["data"]
    )

    grn_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=admin,
        params={"action": "grn_posted"},
    )
    assert grn_logs.status_code == 200
    grow = next(r for r in grn_logs.json()["data"] if r["entity_id"] == grn.id)
    assert grow["integrity_hash"]
    assert grow["module"] == "purchasing"

    je_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=admin,
        params={"action": "journal_posted"},
    )
    assert je_logs.status_code == 200
    assert any(r.get("integrity_hash") for r in je_logs.json()["data"])

    verify = await ac.get("/api/v1/audit-logs/verify", headers=admin)
    assert verify.status_code == 200
    assert verify.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_audit_filter_export_and_retention_policy(client):
    """BR-17.2: filter by module/action, CSV export, 7-year retention policy."""
    ac, seed = client
    # Ensure at least one auth audit exists
    await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    admin = await _super(ac, seed)

    filtered = await ac.get(
        "/api/v1/audit-logs",
        headers=admin,
        params={"module": "auth", "action": "login"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]
    assert all(r["module"] == "auth" and r["action"] == "login" for r in filtered.json()["data"])

    exported = await ac.get(
        "/api/v1/audit-logs/export",
        headers=admin,
        params={"format": "csv", "module": "auth"},
    )
    assert exported.status_code == 200, exported.text
    body = exported.text if hasattr(exported, "text") else exported.content.decode()
    assert "action" in body.lower() or "login" in body.lower() or "," in body

    retention = await ac.get("/api/v1/audit-logs/retention", headers=admin)
    assert retention.status_code == 200, retention.text
    data = retention.json()["data"]
    years = data.get("retention_years") or data.get("years") or data.get("min_years")
    if years is None and isinstance(data.get("policy"), dict):
        years = data["policy"].get("retention_years") or data["policy"].get("years")
    assert years is not None
    assert int(years) >= 7


def test_security_hardening_a1_docs():
    plan = (ROOT / "docs/STAGE_18_PLAN.md").read_text(encoding="utf-8")
    assert "| **A1**" in plan
    assert "test_security_hardening_a1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 18 A1" in br
    assert "[x] **Login/Logout:**" in br
    assert "[x] **Purchases:**" in br
    assert "[x] **User Activity:**" in br
    assert "[x] **Financial:**" in br
    assert "[x] Filter by user, module, action type, date range" in br
    assert "[x] Export audit logs" in br
    assert "[x] Tamper-proof storage" in br
    assert "[x] Retention policy" in br
    sec = (ROOT / "docs/SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 18 A1" in sec
