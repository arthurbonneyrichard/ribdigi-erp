"""BR-6.6 purchase return debit note numbering and print."""

from __future__ import annotations

import pytest

from app.document_numbering import format_document_number, normalize_document_numbering
from app.purchasing import render_debit_note_text
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


def test_render_debit_note_text_includes_refs():
    text = render_debit_note_text(
        {
            "debit_note_number": "DN-2026-0001",
            "return_number": "PR-2026-0001",
            "status": "posted",
            "reason": "damaged",
            "subtotal": 20,
            "tax_amount": 0,
            "total_amount": 20,
            "posted_at": "2026-08-09T12:00:00",
            "items": [{"product_id": "p1", "quantity": 2, "unit_price": 10, "line_total": 20}],
        },
        supplier_name="Acme Supply",
        company_name="Alpha Co",
        po_number="PO-9",
        grn_number="GRN-3",
    )
    assert "DEBIT NOTE DN-2026-0001" in text
    assert "PO: PO-9" in text and "GRN: GRN-3" in text
    assert "Total credit: 20.00" in text


def test_debit_note_numbering_defaults():
    cfg = normalize_document_numbering(None)
    assert "purchase_debit_note" in cfg and "purchase_return" in cfg
    assert format_document_number(cfg["purchase_debit_note"], number=1).startswith("DN-")


@pytest.mark.asyncio
async def test_purchase_return_debit_note_allocate_and_print(client):
    ac, seed = client
    headers = await _mgr(ac)
    admin = await _admin(ac)
    product_id = str(seed["p1"].id)

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={
            "document_numbering": {
                "purchase_return": {
                    "prefix": "PR",
                    "include_year": False,
                    "pad": 4,
                    "next_number": 41,
                },
                "purchase_debit_note": {
                    "prefix": "DN",
                    "include_year": False,
                    "pad": 4,
                    "next_number": 7,
                },
            }
        },
    )
    assert patched.status_code == 200, patched.text

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Debit Note Sup"},
    )
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 5, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_number = po.json()["data"]["po_number"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 5,
                    "accepted_qty": 5,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]
    grn_number = grn.json()["data"]["grn_number"]
    grn_item_id = grn.json()["data"]["items"][0]["id"]

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={
            "goods_receipt_id": grn_id,
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 2}],
        },
    )
    assert created.status_code == 200, created.text
    ret = created.json()["data"]
    assert ret["return_number"] == "PR-0041"
    assert ret["debit_note_number"] is None
    return_id = ret["id"]

    draft_print = await ac.get(f"/api/v1/purchasing/returns/{return_id}/print", headers=headers)
    assert draft_print.status_code == 409

    posted = await ac.post(f"/api/v1/purchasing/returns/{return_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    data = posted.json()["data"]
    assert data["status"] == "posted"
    assert data["debit_note_number"] == "DN-0007"

    printed = await ac.get(f"/api/v1/purchasing/returns/{return_id}/print", headers=headers)
    assert printed.status_code == 200, printed.text
    body = printed.json()["data"]
    assert body["po_number"] == po_number
    assert body["grn_number"] == grn_number
    text = body["text"]
    assert "DEBIT NOTE DN-0007" in text
    assert "PR-0041" in text
    assert "Debit Note Sup" in text
    assert "Alpha Co" in text
    assert po_number in text and grn_number in text


@pytest.mark.asyncio
async def test_foreign_purchase_return_print_404(client):
    ac, _seed = client
    headers = await _mgr(ac)
    r = await ac.get(
        "/api/v1/purchasing/returns/00000000-0000-4000-8000-000000000099/print",
        headers=headers,
    )
    assert r.status_code == 404
