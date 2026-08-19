"""BR-7.4 / BR-20.4 configurable document numbering prefix and series."""

from __future__ import annotations

import pytest

from app.document_numbering import format_document_number, normalize_document_numbering
from tests.conftest import auth_headers


def test_format_invoice_series_34535():
    series = normalize_document_numbering(
        {"sales_invoice": {"prefix": "INV", "include_year": False, "pad": 5, "next_number": 34535}}
    )["sales_invoice"]
    assert format_document_number(series, number=34535) == "INV-34535"

    with_year = normalize_document_numbering(
        {"sales_invoice": {"prefix": "INV", "include_year": True, "pad": 4, "next_number": 1}}
    )["sales_invoice"]
    assert format_document_number(with_year, number=1).startswith("INV-")
    assert format_document_number(with_year, number=1).endswith("-0001")


@pytest.mark.asyncio
async def test_configure_and_allocate_sales_invoice_number(client, db_session):
    ac, seed = client
    admin_headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    sales_headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    customer_id = seed["party1"].id
    product_id = seed["p1"].id

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin_headers,
        json={
            "document_numbering": {
                "sales_invoice": {
                    "prefix": "INV",
                    "include_year": False,
                    "pad": 5,
                    "next_number": 34535,
                }
            }
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["document_numbering"]["sales_invoice"]["next_number"] == 34535
    assert data["document_numbering_preview"]["sales_invoice"] == "INV-34535"

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=sales_headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["invoice_number"] == "INV-34535"

    me = await ac.get("/api/v1/tenants/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["data"]["document_numbering"]["sales_invoice"]["next_number"] == 34536
    assert me.json()["data"]["document_numbering_preview"]["sales_invoice"] == "INV-34536"

    second = await ac.post(
        "/api/v1/sales/invoices",
        headers=sales_headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["invoice_number"] == "INV-34536"


@pytest.mark.asyncio
async def test_default_year_padded_invoice_number(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    customer_id = seed["party1"].id
    product_id = seed["p1"].id
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    number = created.json()["data"]["invoice_number"]
    assert number.startswith("INV-")
    assert number.endswith("-0001")
