"""Stage 24 N1 — shared document numbering series fidelity.

Proves tenant `document_numbering` covers all DOC_KEYS (preview + configure)
and live allocation for quotation / sales order / invoice / sales return /
credit note / PO / GRN with configured prefixes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi import HTTPException

from app.document_numbering import DOC_KEYS, DEFAULTS, merge_document_numbering
from app.inventory import apply_stock_change
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

YEAR = __import__("datetime").datetime.utcnow().year

SERIES_PATCH = {
    "sales_invoice": {"prefix": "N1INV", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_invoice": {"prefix": "N1PINV", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_order": {"prefix": "N1PO", "include_year": True, "pad": 4, "next_number": 1},
    "goods_receipt": {"prefix": "N1GRN", "include_year": True, "pad": 4, "next_number": 1},
    "sales_quotation": {"prefix": "N1QT", "include_year": True, "pad": 4, "next_number": 1},
    "sales_order": {"prefix": "N1SO", "include_year": True, "pad": 4, "next_number": 1},
    "sales_return": {"prefix": "N1SR", "include_year": True, "pad": 4, "next_number": 1},
    "sales_credit_note": {"prefix": "N1CN", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_return": {"prefix": "N1PR", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_debit_note": {"prefix": "N1DN", "include_year": True, "pad": 4, "next_number": 1},
}


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def _expect(prefix: str, n: int = 1) -> str:
    return f"{prefix}-{YEAR}-{str(n).zfill(4)}"


@pytest.mark.asyncio
async def test_configure_and_preview_all_doc_keys(client):
    ac, _seed = client
    headers = await _admin(ac)

    assert set(DOC_KEYS) == set(DEFAULTS)
    assert set(SERIES_PATCH) == set(DOC_KEYS)

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"document_numbering": SERIES_PATCH},
    )
    assert profile.status_code == 200, profile.text
    data = profile.json()["data"]
    numbering = data["document_numbering"]
    preview = data["document_numbering_preview"]

    for key in DOC_KEYS:
        assert key in numbering, key
        assert key in preview, key
        assert numbering[key]["prefix"] == SERIES_PATCH[key]["prefix"]
        assert preview[key].startswith(SERIES_PATCH[key]["prefix"] + "-")

    with pytest.raises(HTTPException) as exc:
        merge_document_numbering({}, {"unknown_doc": {"prefix": "X"}})
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_live_allocate_quote_order_invoice_return_po_grn(client, db_session):
    ac, seed = client
    admin = await _admin(ac)
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product_id = seed["p1"].id

    cfg = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"document_numbering": SERIES_PATCH},
    )
    assert cfg.status_code == 200, cfg.text

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=40,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "N1 Numbering Customer",
            "party_type": "registered",
            "credit_limit": 5000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 2, "unit_price": 10}],
        },
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["data"]["quotation_number"] == _expect("N1QT", 1)

    order_conv = await ac.post(
        f"/api/v1/sales/quotations/{quote.json()['data']['id']}/convert-order",
        headers=headers,
    )
    assert order_conv.status_code == 200, order_conv.text
    order = order_conv.json()["data"]
    assert order["order_number"] == _expect("N1SO", 1)

    confirmed = await ac.post(
        f"/api/v1/sales/orders/{order['id']}/confirm", headers=headers
    )
    assert confirmed.status_code == 200, confirmed.text

    inv_conv = await ac.post(
        f"/api/v1/sales/orders/{order['id']}/convert-invoice", headers=headers
    )
    assert inv_conv.status_code == 200, inv_conv.text
    invoice = inv_conv.json()["data"]
    assert invoice["invoice_number"] == _expect("N1INV", 1)

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice['id']}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice["id"],
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    assert ret.json()["data"]["return_number"] == _expect("N1SR", 1)

    posted_ret = await ac.post(
        f"/api/v1/sales/returns/{ret.json()['data']['id']}/post", headers=headers
    )
    assert posted_ret.status_code == 200, posted_ret.text
    assert posted_ret.json()["data"]["credit_note_number"] == _expect("N1CN", 1)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "N1 Numbering Supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3,
                    "unit_price": 4,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_body = po.json()["data"]
    assert po_body["po_number"] == _expect("N1PO", 1)

    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po_body['id']}/send", headers=headers
    )
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_body["id"],
            "items": [
                {
                    "po_item_id": po_body["items"][0]["id"],
                    "received_qty": 3,
                    "accepted_qty": 3,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["grn_number"] == _expect("N1GRN", 1)


def test_n1_plan_and_docs_cite_stage24():
    plan = (ROOT / "docs" / "STAGE_24_PLAN.md").read_text(encoding="utf-8")
    n1_line = [ln for ln in plan.splitlines() if "| **N1** |" in ln][0]
    assert "COMPLETE" in n1_line
    assert "test_document_numbering_n1.py" in plan
    assert (
        "N1 complete" in plan
        or "G1 next" in plan
        or "N1–G1 complete" in plan
        or "O1 next" in plan
        or "N1–G1–O1–D1 complete" in plan
        or "H24x next" in plan
    )

    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s204 = br.split("#### BR-20.4 Numbering & Templates")[1].split("### 4.21")[0]
    assert "Stage 24 N1" in s204
    assert "sales_order" in s204
    assert "sales_credit_note" in s204 or "credit note" in s204.lower()
    assert "test_document_numbering_n1.py" in s204

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_document_numbering_n1.py" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Stage 24 N1" in roadmap
    assert "test_document_numbering_n1.py" in roadmap
