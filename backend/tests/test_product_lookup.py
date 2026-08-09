import pytest

from app import barcodes as barcode_svc
from app import models as m
from app.product_lookup import pick_exact_scan_match
from tests.conftest import auth_headers


def test_pick_exact_scan_match_prefers_barcode():
    rows = [
        {"id": "1", "sku": "A", "barcode": "111"},
        {"id": "2", "sku": "B", "barcode": "222"},
    ]
    assert pick_exact_scan_match(rows, "222")["id"] == "2"
    assert pick_exact_scan_match(rows, "missing") is None
    assert pick_exact_scan_match([{"id": "only", "sku": "X", "barcode": None}], "anything")["id"] == "only"


@pytest.mark.asyncio
async def test_inventory_products_lookup_by_barcode(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    code = barcode_svc.generate_ean13(body12="200987654321")
    product = await db_session.get(m.Product, seed["p1"].id)
    product.barcode = code
    await db_session.commit()

    found = await ac.get(
        f"/api/v1/inventory/products/lookup?q={code}&barcode={code}",
        headers=headers,
    )
    assert found.status_code == 200, found.text
    ids = {row["product_id"] for row in found.json()["data"]}
    assert seed["p1"].id in ids

    # Inventory manager without relying on POS module
    pos = await ac.get(f"/api/v1/pos/products/search?q={code}", headers=headers)
    # manager may or may not have POS — lookup must work regardless
    assert found.status_code == 200
    assert pos.status_code in (200, 403)
