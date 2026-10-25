"""AR aging total_due uses stored-rate base; per-currency lines stay separate."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_credit_desk_shows_receivable_currency_lines():
    credit = (ROOT / "frontend" / "app" / "(dashboard)" / "credit" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "payableCurrencyLines" in credit
    assert "lines.length > 1" in credit
    assert "kind === 'payable' && lines.length > 1" not in credit
    assert 'aria-label="Customer balance by currency"' in credit
    assert "balance_due_base" in credit
    assert "overdue_total" in credit


@pytest.mark.asyncio
async def test_ghs_and_usd_receivables_stay_separate_not_summed(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Two Currency Buyer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    t1 = seed["t1"].id
    past = datetime.utcnow() - timedelta(days=10)
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
                status="overdue",
                currency="USD",
                exchange_rate=12,
                total_amount=50,
                paid_amount=10,
                due_date=past,
            ),
        ]
    )
    await db_session.commit()

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=admin)
    assert aging.status_code == 200, aging.text
    body = aging.json()["data"]
    party = next(p for p in body["parties"] if p["party_id"] == cid)
    assert party["totals_by_currency"] == [
        {"currency": "GHS", "total_due": 60.0},
        {"currency": "USD", "total_due": 40.0},
    ]
    assert party["total_due"] == pytest.approx(60 + 40 * 12)
    assert party["total_due_base"] == pytest.approx(party["total_due"])
    assert party["total_due"] != pytest.approx(100.0)
    assert body["base_currency"] == "GHS"
    assert body["total_due"] == body["total_due_base"]
    assert body["total_due"] == pytest.approx(party["total_due"])
    assert any(row["currency"] == "USD" and row["total_due"] == 40.0 for row in body["totals_by_currency"])
    assert body["overdue_total"] == pytest.approx(40 * 12)
    assert body["not_yet_due_total"] == pytest.approx(60.0)

    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200, dash.text
    assert dash.json()["data"]["ar_total_due"] == pytest.approx(body["total_due"])


@pytest.mark.asyncio
async def test_ar_aging_does_not_include_other_tenant(client, db_session):
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
    await db_session.commit()

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=admin)
    assert aging.status_code == 200, aging.text
    body = aging.json()["data"]
    party_ids = {p["party_id"] for p in body["parties"]}
    assert seed["party2"].id not in party_ids
    docs = [d["document_number"] for d in body["documents"]]
    assert f"INV-BETA-{suffix}" not in docs
