"""Statements, credit info, and unbilled PO commitments use base + per-currency lines."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app import fx as fx_mod
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_credit_desk_shows_statement_and_commitment_currency_lines():
    credit = (ROOT / "frontend" / "app" / "(dashboard)" / "credit" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Statement balance by currency"' in credit
    assert 'aria-label="Outstanding by currency"' in credit
    assert 'aria-label="Open purchase orders by currency"' in credit
    assert "commitment_totals_by_currency" in credit
    assert "statement.totals_by_currency" in credit
    assert "creditInfo.totals_by_currency" in credit


@pytest.mark.asyncio
async def test_ghs_and_usd_customer_statement_and_credit_info_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Statement Buyer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    t1 = seed["t1"].id
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=t1,
                invoice_number=f"INV-GHS-{suffix}",
                customer_id=cid,
                status="partial",
                currency="",
                exchange_rate=1,
                total_amount=100,
                paid_amount=40,
            ),
            m.SalesInvoice(
                tenant_id=t1,
                invoice_number=f"INV-USD-{suffix}",
                customer_id=cid,
                status="posted",
                currency="USD",
                exchange_rate=12,
                total_amount=50,
                paid_amount=10,
            ),
        ]
    )
    await db_session.commit()

    stmt = await ac.get(f"/api/v1/credit/customers/{cid}/statement", headers=admin)
    assert stmt.status_code == 200, stmt.text
    body = stmt.json()["data"]
    assert body["base_currency"] == "GHS"
    assert body["outstanding_balance"] == pytest.approx(60 + 40 * 12)
    assert body["outstanding_balance_base"] == pytest.approx(body["outstanding_balance"])
    assert body["outstanding_balance"] != pytest.approx(100.0)
    assert body["totals_by_currency"] == [
        {"currency": "GHS", "total_due": 60.0},
        {"currency": "USD", "total_due": 40.0},
    ]
    usd_line = next(row for row in body["lines"] if row["reference"] == f"INV-USD-{suffix}")
    assert usd_line["balance_due"] == 40.0
    assert usd_line["balance_due_base"] == pytest.approx(480.0)

    info = await ac.get(f"/api/v1/customers/{cid}/credit", headers=admin)
    assert info.status_code == 200, info.text
    credit = info.json()["data"]
    assert credit["open_invoice_total"] == pytest.approx(60 + 40 * 12)
    assert credit["open_invoice_total"] != pytest.approx(100.0)
    assert credit["outstanding_balance"] == pytest.approx(credit["open_invoice_total"])
    assert credit["totals_by_currency"] == body["totals_by_currency"]
    assert credit["base_currency"] == "GHS"


@pytest.mark.asyncio
async def test_ghs_and_usd_supplier_statement_and_credit_info_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Statement Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]
    t1 = seed["t1"].id
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=t1,
                invoice_number=f"PI-GHS-{suffix}",
                supplier_id=sid,
                status="partial",
                currency="",
                exchange_rate=1,
                total_amount=100,
                paid_amount=40,
            ),
            m.PurchaseInvoice(
                tenant_id=t1,
                invoice_number=f"PI-USD-{suffix}",
                supplier_id=sid,
                status="unpaid",
                currency="USD",
                exchange_rate=12,
                total_amount=50,
                paid_amount=10,
            ),
        ]
    )
    await db_session.commit()

    stmt = await ac.get(f"/api/v1/credit/suppliers/{sid}/statement", headers=admin)
    assert stmt.status_code == 200, stmt.text
    body = stmt.json()["data"]
    assert body["base_currency"] == "GHS"
    assert body["outstanding_balance"] == pytest.approx(60 + 40 * 12)
    assert body["outstanding_balance"] != pytest.approx(100.0)
    assert body["totals_by_currency"] == [
        {"currency": "GHS", "total_due": 60.0},
        {"currency": "USD", "total_due": 40.0},
    ]

    info = await ac.get(f"/api/v1/suppliers/{sid}/credit", headers=admin)
    assert info.status_code == 200, info.text
    credit = info.json()["data"]
    assert credit["open_bill_total"] == pytest.approx(60 + 40 * 12)
    assert credit["outstanding_balance"] == pytest.approx(credit["open_bill_total"])
    assert credit["totals_by_currency"] == body["totals_by_currency"]

    schedule = await ac.get(f"/api/v1/suppliers/{sid}/payment-schedule", headers=admin)
    assert schedule.status_code == 200, schedule.text
    sched = schedule.json()["data"]
    assert sched["total_due"] == pytest.approx(60 + 40 * 12)
    assert sched["total_due"] != pytest.approx(100.0)
    assert sched["totals_by_currency"] == body["totals_by_currency"]


@pytest.mark.asyncio
async def test_unbilled_po_commitment_converts_to_base(client, db_session, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Commitment Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]
    usd_number = f"PO-USD-{suffix}"
    db_session.add_all(
        [
            m.PurchaseOrder(
                tenant_id=seed["t1"].id,
                supplier_id=sid,
                po_number=f"PO-GHS-{suffix}",
                status="sent",
                total_amount=60,
                paid_amount=0,
            ),
            m.PurchaseOrder(
                tenant_id=seed["t1"].id,
                supplier_id=sid,
                po_number=usd_number,
                status="sent",
                total_amount=40,
                paid_amount=0,
            ),
        ]
    )
    await db_session.commit()

    real_rate = fx_mod.doc_rate
    real_cur = fx_mod.doc_currency

    def doc_rate(obj):
        if getattr(obj, "po_number", None) == usd_number:
            return 12.0
        return real_rate(obj)

    def doc_currency(obj, fallback="GHS"):
        if getattr(obj, "po_number", None) == usd_number:
            return "USD"
        return real_cur(obj, fallback)

    monkeypatch.setattr("app.fx.doc_rate", doc_rate)
    monkeypatch.setattr("app.fx.doc_currency", doc_currency)

    aging = await ac.get("/api/v1/credit/aging?kind=payable", headers=admin)
    assert aging.status_code == 200, aging.text
    body = aging.json()["data"]
    assert body["commitment_total"] == pytest.approx(60 + 40 * 12)
    assert body["commitment_total"] != pytest.approx(100.0)
    assert body["commitment_totals_by_currency"] == [
        {"currency": "GHS", "total_due": 60.0},
        {"currency": "USD", "total_due": 40.0},
    ]
    party = next(p for p in body["parties"] if p["party_id"] == sid)
    assert party["commitment_total"] == pytest.approx(body["commitment_total"])

    info = await ac.get(f"/api/v1/suppliers/{sid}/credit", headers=admin)
    assert info.status_code == 200, info.text
    credit = info.json()["data"]
    assert credit["commitment_total"] == pytest.approx(60 + 40 * 12)
    assert credit["commitment_totals_by_currency"] == body["commitment_totals_by_currency"]


@pytest.mark.asyncio
async def test_statements_and_credit_info_exclude_other_tenant(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t2"].id,
            invoice_number=f"INV-BETA-{suffix}",
            customer_id=seed["party2"].id,
            status="posted",
            currency="USD",
            exchange_rate=12,
            total_amount=999,
            paid_amount=0,
        )
    )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=seed["t2"].id,
            invoice_number=f"PI-BETA-{suffix}",
            supplier_id=seed["supplier2"].id,
            status="unpaid",
            currency="USD",
            exchange_rate=12,
            total_amount=888,
            paid_amount=0,
        )
    )
    await db_session.commit()

    foreign_cust = await ac.get(
        f"/api/v1/credit/customers/{seed['party2'].id}/statement", headers=admin
    )
    assert foreign_cust.status_code == 404
    foreign_sup = await ac.get(
        f"/api/v1/credit/suppliers/{seed['supplier2'].id}/statement", headers=admin
    )
    assert foreign_sup.status_code == 404
    foreign_info = await ac.get(f"/api/v1/customers/{seed['party2'].id}/credit", headers=admin)
    assert foreign_info.status_code == 404

    own = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Alpha Statement {suffix}"},
    )
    cid = own.json()["data"]["id"]
    stmt = await ac.get(f"/api/v1/credit/customers/{cid}/statement", headers=admin)
    assert stmt.status_code == 200, stmt.text
    refs = [row["reference"] for row in stmt.json()["data"]["lines"]]
    assert f"INV-BETA-{suffix}" not in refs


@pytest.mark.asyncio
async def test_customer_history_purchase_total_uses_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"History Buyer {suffix}"},
    )
    cid = customer.json()["data"]["id"]
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-HIST-GHS-{suffix}",
                customer_id=cid,
                status="posted",
                currency="",
                exchange_rate=1,
                total_amount=60,
                paid_amount=0,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-HIST-USD-{suffix}",
                customer_id=cid,
                status="posted",
                currency="USD",
                exchange_rate=12,
                total_amount=40,
                paid_amount=0,
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                party_id=cid,
                tx_type="pos_sale",
                reference=f"POS-HIST-FX-{suffix}",
                total=10,
                subtotal=10,
                tax=0,
                payload={"exchange_rate": 12},
            ),
        ]
    )
    await db_session.commit()

    hist = await ac.get(f"/api/v1/customers/{cid}/history", headers=admin)
    assert hist.status_code == 200, hist.text
    summary = hist.json()["data"]["summary"]
    assert summary["purchase_total"] == pytest.approx(60 + 40 * 12 + 10 * 12)
    assert summary["purchase_total"] != pytest.approx(110.0)
