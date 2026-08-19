"""Stage 136 S1 — supplier payment register list + CSV."""

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
async def test_supplier_payments_list_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Stage136 Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    db_session.add_all(
        [
            m.SupplierPayment(
                tenant_id=seed["t1"].id,
                payment_number="SPAY-136-BANK",
                supplier_id=supplier.id,
                amount=100,
                payment_method="bank_transfer",
            ),
            m.SupplierPayment(
                tenant_id=seed["t1"].id,
                payment_number="SPAY-136-CHQ",
                supplier_id=supplier.id,
                amount=40,
                payment_method="cheque",
            ),
        ]
    )
    await db_session.commit()

    listed = await ac.get(
        "/api/v1/credit/supplier-payments?payment_method=bank_transfer", headers=headers
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r.get("payment_number") == "SPAY-136-BANK" for r in rows)
    assert all(r.get("payment_method") == "bank_transfer" for r in rows)
    assert not any(r.get("payment_number") == "SPAY-136-CHQ" for r in rows)

    exported = await ac.get(
        "/api/v1/credit/supplier-payments/export?payment_method=cheque", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "payment_number" in header and "supplier_id" in header
    assert "SPAY-136-CHQ" in exported.text
    assert "SPAY-136-BANK" not in exported.text


def test_supplier_payments_ui_s1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 136" in page
    assert "/credit/supplier-payments/export" in page
    assert "Supplier payments CSV" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Supplier Payments" in shell
    assert "kind=payable#payments" in shell
