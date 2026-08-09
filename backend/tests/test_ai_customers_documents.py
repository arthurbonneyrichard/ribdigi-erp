"""Phase 4 / BR-21.8 + BR-21.9 document and customer assistants."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import ai_customers as ai_customers_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_customer_churn_best_and_assist(db_session, seeded):
    tenant_id = seeded["t1"].id
    now = datetime.utcnow()
    # Recent heavy buyer
    for i in range(4):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-CUST-{i}",
            customer_id=seeded["party1"].id,
            status="posted",
            subtotal=200,
            total_amount=200,
            paid_amount=200,
            created_at=now - timedelta(days=i * 3),
            posted_at=now - timedelta(days=i * 3),
        )
        db_session.add(inv)
    # Stale second customer
    stale = m.Party(
        tenant_id=tenant_id,
        name="Alpha Quiet Co",
        kind="customer",
        status="active",
        credit_limit=50,
        balance=0,
    )
    db_session.add(stale)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-CUST-STALE",
            customer_id=stale.id,
            status="posted",
            subtotal=10,
            total_amount=10,
            paid_amount=10,
            created_at=now - timedelta(days=120),
            posted_at=now - timedelta(days=120),
        )
    )
    await db_session.commit()

    intel = await ai_customers_svc.customer_intelligence(db_session, tenant_id)
    assert intel["customer_count"] >= 2
    assert intel["best_customers"][0]["customer_id"] == seeded["party1"].id
    assert any(c["customer_id"] == stale.id for c in intel["churn_risks"])
    assert intel["promotion_suggestions"]

    assist = await ai_customers_svc.assist_customer(
        db_session,
        tenant_id,
        customer_id=seeded["party1"].id,
        query="What is my current outstanding balance?",
    )
    assert "outstanding balance" in assist["answer"].lower()
    assert assist["customer"]["customer_id"] == seeded["party1"].id


@pytest.mark.asyncio
async def test_customer_assist_api_tenant_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            invoice_number="INV-CA-1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=80,
            total_amount=80,
            created_at=now,
            posted_at=now,
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/ai/customers/insights", headers=headers)
    assert r.status_code == 200, r.text
    names = {c["name"] for c in r.json()["data"]["best_customers"]}
    assert "Beta" not in " ".join(names)

    assist = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "Who are my best customers?"},
    )
    assert assist.status_code == 200, assist.text
    assert "Alpha" in assist.json()["data"]["answer"] or assist.json()["data"]["best_customers"]


@pytest.mark.asyncio
async def test_document_analyze_receipt_text_pdf(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    from io import BytesIO
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    db_session.add(
        m.Party(
            tenant_id=seed["t1"].id,
            name="Alpha Supplier",
            kind="supplier",
            status="active",
        )
    )
    await db_session.commit()

    files = {"file": ("receipt.pdf", pdf_bytes, "application/pdf")}
    r = await ac.post(
        "/api/v1/ai/documents/analyze?document_type=receipt",
        headers=headers,
        files=files,
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert "extracted_fields" in body
    assert "matches" in body
    assert "discrepancies" in body
    assert body["document_type"] == "receipt"
    assert isinstance(body["discrepancies"], list)
