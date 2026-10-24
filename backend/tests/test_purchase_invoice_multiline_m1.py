"""Manual supplier bills: one header, many product lines (create + post)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _second_product(ac, headers, *, sku: str, name: str, cost: float = 4):
    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": name, "sku": sku, "selling_price": cost + 1, "cost_price": cost},
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def _supplier(ac, headers, name: str, email: str):
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": name, "email": email},
    )
    assert supplier.status_code == 200, supplier.text
    return supplier.json()["data"]


@pytest.mark.asyncio
async def test_manual_bill_two_products_draft_does_not_overwrite_or_post(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await _supplier(ac, headers, "Multi Bill Vendor", "multi-bill@example.com")
    p2 = await _second_product(ac, headers, sku="A-BOLT-ML", name="Alpha Bolt", cost=6)
    p1_before = (await db_session.get(m.Product, seed["p1"].id)).stock_qty
    p2_before = (await db_session.get(m.Product, p2["id"])).stock_qty
    supplier_before = (
        await db_session.get(m.Party, supplier["id"])
    ).balance

    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "discount_amount": 5,
            "currency": "USD",
            "exchange_rate": 1.25,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 10,
                    "discount": 1,
                },
                {
                    "product_id": p2["id"],
                    "quantity": 3,
                    "unit_price": 6,
                    "tax_rate": 5,
                    "discount": 0,
                },
            ],
            "notes": "two product draft",
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["status"] == "draft"
    assert inv["ap_posted"] is False
    assert len(inv["items"]) == 2
    ids = [row["product_id"] for row in inv["items"]]
    assert ids == [seed["p1"].id, p2["id"]]
    # qty×unit 20 + 18 = 38; tax 2 + 0.9 = 2.9; header disc 5; total 35.9
    assert inv["subtotal"] == pytest.approx(38.0)
    assert inv["tax_amount"] == pytest.approx(2.9)
    assert inv["discount_amount"] == pytest.approx(5.0)
    assert inv["total_amount"] == pytest.approx(35.9)
    assert inv["currency"] == "USD"
    assert inv["exchange_rate"] == pytest.approx(1.25)
    assert inv["items"][0]["line_total"] == pytest.approx(21.0)  # 20 + 2 tax - 1 line disc
    assert inv["items"][1]["line_total"] == pytest.approx(18.9)

    await db_session.refresh(await db_session.get(m.Product, seed["p1"].id))
    p1_row = await db_session.get(m.Product, seed["p1"].id)
    p2_row = await db_session.get(m.Product, p2["id"])
    party = await db_session.get(m.Party, supplier["id"])
    assert float(p1_row.stock_qty) == pytest.approx(float(p1_before))
    assert float(p2_row.stock_qty) == pytest.approx(float(p2_before))
    assert float(party.balance or 0) == pytest.approx(float(supplier_before or 0))

    listed = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=headers)
    assert listed.status_code == 200
    assert [row["product_id"] for row in listed.json()["data"]["items"]] == ids


@pytest.mark.asyncio
async def test_manual_bill_post_stocks_every_line_and_ap(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await _supplier(ac, headers, "Posted Multi Vendor", "posted-multi@example.com")
    p2 = await _second_product(ac, headers, sku="A-NUT-ML", name="Alpha Nut", cost=3)
    wh = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Bill Receive WH", "code": "BRWH1"},
    )
    assert wh.status_code == 200, wh.text
    warehouse_id = wh.json()["data"]["id"]

    p1_before = float((await db_session.get(m.Product, seed["p1"].id)).stock_qty)
    p2_before = float((await db_session.get(m.Product, p2["id"])).stock_qty)

    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": warehouse_id,
            "items": [
                {"product_id": seed["p1"].id, "quantity": 4, "unit_price": 8, "tax_rate": 0},
                {"product_id": p2["id"], "quantity": 2, "unit_price": 3, "tax_rate": 0},
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["warehouse_id"] == warehouse_id
    assert inv["status"] == "draft"
    assert inv["ap_posted"] is False

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()["data"]
    assert body["status"] in {"unpaid", "overdue"}
    assert body["ap_posted"] is True
    assert len(body["items"]) == 2

    p1_row = await db_session.get(m.Product, seed["p1"].id)
    p2_row = await db_session.get(m.Product, p2["id"])
    await db_session.refresh(p1_row)
    await db_session.refresh(p2_row)
    assert float(p1_row.stock_qty) == pytest.approx(p1_before + 4)
    assert float(p2_row.stock_qty) == pytest.approx(p2_before + 2)

    party = await db_session.get(m.Party, supplier["id"])
    await db_session.refresh(party)
    assert float(party.balance or 0) == pytest.approx(float(body["total_amount"]))

    for product_id, qty in ((seed["p1"].id, 4), (p2["id"], 2)):
        moves = await ac.get(
            f"/api/v1/inventory/movements?product_id={product_id}",
            headers=headers,
        )
        assert moves.status_code == 200, moves.text
        payload = moves.json()["data"]
        rows = payload.get("movements") if isinstance(payload, dict) else payload
        rows = rows or []
        matched = [
            r
            for r in rows
            if r.get("reference_id") == inv["id"] and r.get("reference_type") == "purchase_invoice"
        ]
        assert matched, (product_id, moves.text)
        assert any(float(r.get("quantity") or 0) == qty for r in matched)
        assert any(r.get("warehouse_id") == warehouse_id for r in matched)

    stmt = await ac.get(
        f"/api/v1/credit/suppliers/{supplier['id']}/statement",
        headers=headers,
    )
    assert stmt.status_code == 200, stmt.text
    assert stmt.json()["data"]["supplier"]["balance"] == pytest.approx(float(body["total_amount"]))


@pytest.mark.asyncio
async def test_manual_bill_rejects_foreign_product_without_partial_header(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await _supplier(ac, headers, "Foreign Line Vendor", "foreign-line@example.com")
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10, "tax_rate": 0},
                {"product_id": seed["p2"].id, "quantity": 1, "unit_price": 10, "tax_rate": 0},
            ],
        },
    )
    assert created.status_code == 404, created.text
    listed = await ac.get("/api/v1/purchasing/invoices", headers=headers)
    assert listed.status_code == 200
    bills = listed.json()["data"]
    if isinstance(bills, dict):
        bills = bills.get("items") or bills.get("data") or []
    assert all(
        (row.get("supplier_id") != supplier["id"])
        or row.get("status") == "cancelled"
        for row in bills
    ) or not any(row.get("supplier_id") == supplier["id"] for row in bills)


@pytest.mark.asyncio
async def test_manual_bill_approve_atomic_when_line_cannot_receive(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await _supplier(ac, headers, "Atomic Bill Vendor", "atomic-bill@example.com")
    p2 = await _second_product(ac, headers, sku="A-BATCH-ML", name="Alpha Batch", cost=2)
    product = await db_session.get(m.Product, p2["id"])
    product.tracks_batches = True
    await db_session.commit()

    p1_before = float((await db_session.get(m.Product, seed["p1"].id)).stock_qty)
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [
                {"product_id": seed["p1"].id, "quantity": 5, "unit_price": 2, "tax_rate": 0},
                {"product_id": p2["id"], "quantity": 1, "unit_price": 2, "tax_rate": 0},
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 400, approved.text
    assert "batch" in approved.text.lower()

    got = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["status"] == "draft"
    assert got.json()["data"]["ap_posted"] is False

    p1_row = await db_session.get(m.Product, seed["p1"].id)
    await db_session.refresh(p1_row)
    assert float(p1_row.stock_qty) == pytest.approx(p1_before)
    party = await db_session.get(m.Party, supplier["id"])
    await db_session.refresh(party)
    assert float(party.balance or 0) == pytest.approx(0)


@pytest.mark.asyncio
async def test_manual_bill_requires_valid_qty_and_at_least_one_line(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    supplier = await _supplier(ac, headers, "Qty Bill Vendor", "qty-bill@example.com")
    empty = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"supplier_id": supplier["id"], "items": []},
    )
    assert empty.status_code in (400, 422), empty.text
    bad_qty = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [
                {"product_id": seed["p1"].id, "quantity": 0, "unit_price": 1},
            ],
        },
    )
    assert bad_qty.status_code == 422, bad_qty.text


def test_create_bill_add_product_appends_line_with_product_id():
    """Create supplier bill: pick product, Add product appends a line; draft sends product_id."""
    page = (ROOT / "frontend/app/(dashboard)/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create supplier bill"' in page
    assert 'title="Create supplier bill"' in page
    assert "function addBillProduct" in page
    assert 'aria-label="Purchase invoice product"' in page
    assert 'aria-label="Add purchase invoice product"' in page
    assert "setBillLines((rows) => [...rows, draft])" in page
    assert "productId" in page
    assert "product_id: line.productId.trim()" in page
    assert "Choose a product first" in page
    # GRN-from-bill path stays a separate modal.
    assert 'aria-label="Draft purchase invoice from GRN"' in page
