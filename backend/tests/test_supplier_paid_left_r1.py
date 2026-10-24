"""Supplier table totals: total paid and amount left (agree with AP aging)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app.credit import supplier_paid_and_left
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_purchasing_tables_show_paid_left_and_received_date():
    page = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert '<th className="col-num">Total paid</th>' in page
    assert "aria-label={`Total paid to ${s.name}`}" in page
    assert "aria-label={`Amount left for ${s.name}`}" in page
    assert '<th className="col-date">Date received</th>' in page
    assert "formatDate(g.received_at || g.created_at, formatPrefs)" in page
    assert page.count('<th className="col-num">Amount paid</th>') >= 3
    assert page.count('<th className="col-num">Amount left</th>') >= 4
    # Supplier details panel and per-currency lines.
    assert "aria-label={`Supplier total paid ${managed?.name || ''}`.trim()}" in page
    assert "aria-label={`Supplier amount left ${managed?.name || ''}`.trim()}" in page
    assert 'className="purchase-ui-money-lines"' in page
    # Phone: the four money tables stack into one card per row.
    assert page.count("purchase-ui-stack") >= 4
    css = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "purchase-ui.css"
    ).read_text(encoding="utf-8")
    phone = css.split("@media (max-width: 720px) {")[1]
    assert ".table.purchase-ui-stack thead" in phone
    assert "td[data-label]::before" in phone
    assert "overflow-wrap: anywhere;" in phone


@pytest.mark.asyncio
async def test_supplier_list_total_paid_and_amount_left_after_partial_payment(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Paid Left Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 5, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    issued = await ac.post(f"/api/v1/purchasing/orders/{po['id']}/issue", headers=admin)
    assert issued.status_code == 200, issued.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=admin,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {"po_item_id": po["items"][0]["id"], "received_qty": 5, "accepted_qty": 5}
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_body = grn.json()["data"]
    assert grn_body["received_at"]
    assert grn_body["received_at"] == grn_body["created_at"]
    listed_grns = await ac.get("/api/v1/purchasing/grn", headers=admin)
    assert listed_grns.status_code == 200, listed_grns.text
    row = next(g for g in listed_grns.json()["data"] if g["id"] == grn_body["id"])
    assert row["received_at"]

    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_body["id"]},
    )
    assert bill.status_code == 200, bill.text
    inv = bill.json()["data"]
    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve", headers=admin, json={}
    )
    assert approved.status_code == 200, approved.text
    total = float(approved.json()["data"]["total_amount"])
    assert total == pytest.approx(50.0)

    pay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "purchase_invoice_id": inv["id"],
            "amount": 20,
            "payment_method": "bank_transfer",
        },
    )
    assert pay.status_code == 200, pay.text

    detail = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=admin)
    body = detail.json()["data"]
    assert body["paid_amount"] == pytest.approx(20.0)
    assert body["balance_due"] == pytest.approx(30.0)

    listed = await ac.get("/api/v1/suppliers", headers=admin)
    assert listed.status_code == 200, listed.text
    sup = next(s for s in listed.json()["data"] if s["id"] == supplier_id)
    assert sup["total_paid"] == pytest.approx(20.0)
    assert sup["amount_left"] == pytest.approx(30.0)
    assert isinstance(sup["total_paid"], (int, float))

    assert sup["base_currency"] == "GHS"
    assert sup["totals_by_currency"] == [
        {"currency": "GHS", "total_paid": 20.0, "amount_left": 30.0}
    ]

    detail_sup = await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=admin)
    assert detail_sup.status_code == 200, detail_sup.text
    one = detail_sup.json()["data"]
    for key in ("total_paid", "amount_left", "base_currency", "totals_by_currency"):
        assert one[key] == sup[key]

    aging = await ac.get("/api/v1/credit/aging?kind=payable", headers=admin)
    assert aging.status_code == 200, aging.text
    party = next(p for p in aging.json()["data"]["parties"] if p["party_id"] == supplier_id)
    assert party["total_due"] == pytest.approx(sup["amount_left"])
    assert party["total_due_base"] == pytest.approx(sup["amount_left"])

    # Cross-tenant: a beta row pointing at the alpha supplier id must not leak in.
    db_session.add(
        m.SupplierPayment(
            tenant_id=seed["t2"].id,
            payment_number=f"SP-B-{suffix}",
            supplier_id=supplier_id,
            amount=999,
        )
    )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=seed["t2"].id,
            invoice_number=f"PI-B-{suffix}",
            supplier_id=seed["supplier2"].id,
            status="unpaid",
            total_amount=77,
            paid_amount=0,
        )
    )
    await db_session.commit()
    again = await ac.get("/api/v1/suppliers", headers=admin)
    rows = again.json()["data"]
    assert seed["supplier2"].id not in {s["id"] for s in rows}
    sup = next(s for s in rows if s["id"] == supplier_id)
    assert sup["total_paid"] == pytest.approx(20.0)
    assert sup["amount_left"] == pytest.approx(30.0)

    detail_again = await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=admin)
    assert detail_again.json()["data"]["total_paid"] == pytest.approx(20.0)
    assert detail_again.json()["data"]["amount_left"] == pytest.approx(30.0)
    other = await ac.get(f"/api/v1/suppliers/{seed['supplier2'].id}", headers=admin)
    assert other.status_code == 404

    beta = await supplier_paid_and_left(db_session, seed["t2"].id)
    assert beta[seed["supplier2"].id]["amount_left"] == pytest.approx(77.0)
    assert beta[supplier_id]["total_paid"] == pytest.approx(999.0)
    alpha = await supplier_paid_and_left(db_session, seed["t1"].id)
    assert seed["supplier2"].id not in alpha


@pytest.mark.asyncio
async def test_ghs_and_usd_bills_stay_separate_not_summed(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers", headers=admin, json={"name": f"Two Currency Vendor {suffix}"}
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]
    t1 = seed["t1"].id
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=t1, invoice_number=f"PI-GHS-{suffix}", supplier_id=sid,
                status="partial", currency="", exchange_rate=1, total_amount=100, paid_amount=40,
            ),
            m.PurchaseInvoice(
                tenant_id=t1, invoice_number=f"PI-USD-{suffix}", supplier_id=sid,
                status="partial", currency="USD", exchange_rate=12, total_amount=50, paid_amount=10,
            ),
            m.SupplierPayment(
                tenant_id=t1, payment_number=f"SP-GHS-{suffix}", supplier_id=sid,
                amount=40, currency="GHS", exchange_rate=1,
            ),
            m.SupplierPayment(
                tenant_id=t1, payment_number=f"SP-USD-{suffix}", supplier_id=sid,
                amount=10, currency="USD", exchange_rate=12,
            ),
        ]
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/suppliers", headers=admin)
    assert listed.status_code == 200, listed.text
    sup = next(s for s in listed.json()["data"] if s["id"] == sid)
    assert sup["totals_by_currency"] == [
        {"currency": "GHS", "total_paid": 40.0, "amount_left": 60.0},
        {"currency": "USD", "total_paid": 10.0, "amount_left": 40.0},
    ]
    # Scalars are base currency at each document's stored rate, never a mixed sum.
    assert sup["base_currency"] == "GHS"
    assert sup["total_paid"] == pytest.approx(40 + 10 * 12)
    assert sup["amount_left"] == pytest.approx(60 + 40 * 12)
    assert sup["total_paid"] != pytest.approx(50.0)
    assert sup["amount_left"] != pytest.approx(100.0)

    detail = await ac.get(f"/api/v1/suppliers/{sid}", headers=admin)
    assert detail.json()["data"]["totals_by_currency"] == sup["totals_by_currency"]
    assert detail.json()["data"]["amount_left"] == pytest.approx(sup["amount_left"])

    aging = await ac.get("/api/v1/credit/aging?kind=payable", headers=admin)
    party = next(p for p in aging.json()["data"]["parties"] if p["party_id"] == sid)
    assert party["totals_by_currency"] == [
        {"currency": "GHS", "total_due": 60.0},
        {"currency": "USD", "total_due": 40.0},
    ]
    assert party["total_due_base"] == pytest.approx(sup["amount_left"])


@pytest.mark.asyncio
async def test_bounced_cheque_payment_is_not_counted_as_paid(client, db_session):
    ac, seed = client
    suffix = uuid4().hex[:8]
    supplier = m.Party(tenant_id=seed["t1"].id, name=f"Cheque Vendor {suffix}", kind="supplier")
    db_session.add(supplier)
    await db_session.flush()
    good = m.SupplierPayment(
        tenant_id=seed["t1"].id, payment_number=f"SP-G-{suffix}", supplier_id=supplier.id, amount=15
    )
    bounced = m.SupplierPayment(
        tenant_id=seed["t1"].id, payment_number=f"SP-X-{suffix}", supplier_id=supplier.id, amount=40
    )
    db_session.add_all([good, bounced])
    await db_session.flush()
    db_session.add(
        m.Cheque(
            tenant_id=seed["t1"].id,
            direction="issued",
            status="bounced",
            cheque_number=f"CHQ-{suffix}",
            amount=40,
            party_id=supplier.id,
            supplier_payment_id=bounced.id,
        )
    )
    await db_session.commit()
    out = await supplier_paid_and_left(db_session, seed["t1"].id)
    assert out[supplier.id]["total_paid"] == pytest.approx(15.0)
    assert out[supplier.id]["amount_left"] == pytest.approx(0.0)
