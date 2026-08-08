from datetime import datetime, timedelta
from types import SimpleNamespace

from app.schemas import LineItem, SalesInvoiceItemCreate, SalesReturnItemCreate
from app.catalog import serialize_batch, serialize_variant


def test_serialize_variant_and_batch():
    v = SimpleNamespace(
        id="v1",
        product_id="p1",
        name="Large",
        sku="SKU-L",
        barcode=None,
        size="L",
        color=None,
        flavor=None,
        cost_price=1,
        selling_price=2,
        stock_qty=5,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    data = serialize_variant(v)
    assert data["sku"] == "SKU-L"
    assert data["stock_qty"] == 5

    b = SimpleNamespace(
        id="b1",
        product_id="p1",
        variant_id=None,
        warehouse_id=None,
        batch_number="B-1",
        manufacturing_date=None,
        expiry_date=datetime.utcnow() + timedelta(days=10),
        quantity=3,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    assert serialize_batch(b)["batch_number"] == "B-1"
    assert serialize_batch(b)["quantity"] == 3


def test_sale_line_schemas_accept_variant_id():
    line = LineItem(product_id="p1", quantity=2, variant_id="v1")
    assert line.variant_id == "v1"
    inv = SalesInvoiceItemCreate(product_id="p1", quantity=1, variant_id="v1", unit_price=9.5)
    assert inv.variant_id == "v1" and inv.unit_price == 9.5
    ret = SalesReturnItemCreate(product_id="p1", quantity=1, variant_id="v1")
    assert ret.variant_id == "v1"
