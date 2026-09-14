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
    from uuid import uuid4

    pid, vid = str(uuid4()), str(uuid4())
    line = LineItem(product_id=pid, quantity=2, variant_id=vid)
    assert line.variant_id == vid
    inv = SalesInvoiceItemCreate(product_id=pid, quantity=1, variant_id=vid, unit_price=9.5)
    assert inv.variant_id == vid and inv.unit_price == 9.5
    ret = SalesReturnItemCreate(
        product_id=pid, quantity=1, variant_id=vid, condition="sellable"
    )
    assert ret.variant_id == vid
    assert ret.condition == "sellable"
