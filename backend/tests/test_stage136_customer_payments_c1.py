"""Stage 136 C1 — customer payment register list + CSV."""

from __future__ import annotations

from pathlib import Path

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


@pytest.mark.asyncio
async def test_customer_payments_list_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    customer = m.Party(
        tenant_id=seed["t1"].id, name="Stage136 Customer", kind="customer", credit_limit=0
    )
    db_session.add(customer)
    await db_session.flush()

    db_session.add_all(
        [
            m.CustomerPayment(
                tenant_id=seed["t1"].id,
                payment_number="CPAY-136-CASH",
                customer_id=customer.id,
                amount=50,
                payment_method="cash",
            ),
            m.CustomerPayment(
                tenant_id=seed["t1"].id,
                payment_number="CPAY-136-CARD",
                customer_id=customer.id,
                amount=75,
                payment_method="card",
            ),
        ]
    )
    await db_session.commit()

    listed = await ac.get(
        "/api/v1/credit/customer-payments?payment_method=cash", headers=headers
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r.get("payment_number") == "CPAY-136-CASH" for r in rows)
    assert all(r.get("payment_method") == "cash" for r in rows)
    assert not any(r.get("payment_number") == "CPAY-136-CARD" for r in rows)

    exported = await ac.get(
        "/api/v1/credit/customer-payments/export?payment_method=card", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "payment_number" in header and "payment_method" in header
    assert "CPAY-136-CARD" in exported.text
    assert "CPAY-136-CASH" not in exported.text


def test_customer_payments_ui_c1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 136" in page
    assert "/credit/customer-payments/export" in page
    assert "Customer payments CSV" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Customer Payments" in shell
    assert "kind=receivable#payments" in shell
