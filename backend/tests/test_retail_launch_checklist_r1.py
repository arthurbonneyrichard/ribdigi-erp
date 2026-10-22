"""In-repo rows from the 22 Oct 2026 retail launch checklist."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest
from app import models as m
from app.dashboard import build_dashboard
from app.stores import warehouse_for_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_second_warehouse_for_a_store_is_blocked(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Launch Till", "code": "LCH-TILL"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    second = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Till WH 2", "code": "LCH-WH-2", "store_id": store_id},
    )
    assert second.status_code == 400, second.text
    assert "already has a warehouse" in second.text


@pytest.mark.asyncio
async def test_warehouse_for_store_picks_one_when_two_exist(db_session, seeded):
    store = m.Store(tenant_id=seeded["t1"].id, name="Dup WH Store", code="DUP-WH")
    db_session.add(store)
    await db_session.flush()
    db_session.add_all(
        [
            m.Warehouse(
                tenant_id=seeded["t1"].id,
                store_id=store.id,
                name="Dup A",
                code="DUP-A",
            ),
            m.Warehouse(
                tenant_id=seeded["t1"].id,
                store_id=store.id,
                name="Dup B",
                code="DUP-B",
            ),
        ]
    )
    await db_session.flush()
    chosen = await warehouse_for_store(db_session, seeded["t1"].id, store.id)
    assert chosen.code == "DUP-A"


@pytest.mark.asyncio
async def test_dashboard_store_scope_includes_company_wide_expenses(db_session, seeded):
    store = m.Store(tenant_id=seeded["t1"].id, name="Dash Store", code="DASH-EXP")
    db_session.add(store)
    await db_session.flush()
    before = await build_dashboard(db_session, seeded["t1"].id, store_id=store.id)
    db_session.add(
        m.Expense(
            tenant_id=seeded["t1"].id,
            category="Rent",
            description="HQ rent",
            amount=140,
            expense_date=datetime.utcnow(),
            payment_method="bank_transfer",
            store_id=None,
            status="approved",
        )
    )
    await db_session.commit()
    dash = await build_dashboard(db_session, seeded["t1"].id, store_id=store.id)
    assert dash["total_expenses"] == round(float(before["total_expenses"]) + 140, 2)


@pytest.mark.asyncio
async def test_shop_can_close_an_open_support_ticket(client, monkeypatch):
    from app.emailer import EmailResult

    async def fake_send(**kwargs):
        return EmailResult(sent=True, mode="console", recipients=[kwargs.get("to", "")])

    monkeypatch.setattr("app.emailer.send_email", fake_send)
    ac, _seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/support/tickets",
        headers=cashier,
        json={
            "subject": "That fixed it",
            "description": "Printing is working again after the last reply.",
            "category": "printing_barcode_receipt",
        },
    )
    assert created.status_code == 200, created.text
    ticket_id = created.json()["data"]["ticket"]["id"]
    closed = await ac.post(f"/api/v1/support/tickets/{ticket_id}/close", headers=cashier)
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["ticket"]["status"] == "closed"


def test_launch_ui_source_fixes():
    globals_css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".main .plat-hero h1{color:var(--sand)}" in globals_css
    assert ".shell > .main{padding-left:52px}" in globals_css
    sales = (ROOT / "frontend/app/(dashboard)/sales/sales-ui.css").read_text(encoding="utf-8")
    base = sales.split("@media")[0]
    assert "display: flex" in base
    assert ".sales-ui-path" in base
    credit = (ROOT / "frontend/app/(dashboard)/credit/page.tsx").read_text(encoding="utf-8")
    assert "function selectKind" in credit
    assert "setPartyId('')" in credit
    inventory = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    assert "if (pharmacyOps)" in inventory
    assert "apiOptional('/pharmacy/batch-holds'" in inventory
    support = (ROOT / "frontend/app/(dashboard)/support/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Close ticket"' in support
    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert "LoginLegalLinks" in login
    terms = (ROOT / "frontend/app/legal/terms/page.tsx").read_text(encoding="utf-8")
    privacy = (ROOT / "frontend/app/legal/privacy/page.tsx").read_text(encoding="utf-8")
    assert "Terms of Service" in terms
    assert "Privacy Policy" in privacy
    journal = (ROOT / "frontend/lib/posOfflineJournal.ts").read_text(encoding="utf-8")
    assert "return null;" in journal
    assert "8765" in journal
    ai = (ROOT / "frontend/app/(dashboard)/ai/page.tsx").read_text(encoding="utf-8")
    assert "{chatAvailable ? (" in ai
    assert 'aria-label="Ask AI chat"' in ai
