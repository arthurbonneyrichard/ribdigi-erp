"""Hash-chained audit coverage for purchasing/sales/accounting writes."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import audit as audit_svc
from app import models as m
from app import purchasing as purchasing_svc
from app import sales as sales_svc
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_invoice_post_and_journal_are_hash_chained(client, db_session):
    ac, seed = client
    invoice = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        customer_id=seed["party1"].id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
    )
    invoice = await sales_svc.post_sales_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        invoice_id=invoice.id,
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    listed = await ac.get("/api/v1/audit-logs", headers=headers, params={"action": "invoice_posted"})
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert rows
    assert rows[0]["integrity_hash"]
    assert rows[0]["module"] == "sales"
    assert rows[0]["entity_id"] == invoice.id

    journals = await ac.get(
        "/api/v1/audit-logs", headers=headers, params={"action": "journal_posted"}
    )
    assert journals.status_code == 200
    jrows = journals.json()["data"]
    assert jrows
    assert jrows[0]["integrity_hash"]
    assert jrows[0]["module"] == "accounting"

    verify = await ac.get("/api/v1/audit-logs/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_purchase_invoice_approve_audited_with_hash(client, db_session):
    ac, seed = client
    supplier = m.Party(
        tenant_id=seed["t1"].id,
        name="Audit Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.flush()
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
    )
    inv = await purchasing_svc.approve_purchase_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        invoice_id=inv.id,
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    listed = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "purchase_invoice_approved"},
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert rows
    assert rows[0]["integrity_hash"]
    assert rows[0]["module"] == "purchasing"
    assert rows[0]["entity_id"] == inv.id

    chain = await audit_svc.verify_chain(db_session, seed["t1"].id)
    assert chain["valid"] is True


@pytest.mark.asyncio
async def test_po_create_audited_with_hash(client, db_session):
    ac, seed = client
    supplier = m.Party(
        tenant_id=seed["t1"].id,
        name="PO Audit Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.flush()
    po = await purchasing_svc.create_purchase_order(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 3}],
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "po_created",
                m.AuditLog.entity_id == po.id,
            )
        )
    ).scalar_one()
    assert row.integrity_hash
    assert row.module == "purchasing"
