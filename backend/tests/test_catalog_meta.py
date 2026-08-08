from app.catalog_meta import (
    DEFAULT_CATEGORIES,
    DEFAULT_UNITS,
    serialize_category,
    serialize_product,
)
from app import models as m
from types import SimpleNamespace


def test_default_units_and_categories_seed_lists():
    assert ("PCS", "Pieces") in DEFAULT_UNITS
    assert any(c[0] == "GEN" for c in DEFAULT_CATEGORIES)


def test_serialize_category_and_product():
    cat = SimpleNamespace(
        id="c1",
        parent_id=None,
        code="GEN",
        name="General",
        is_active=True,
        created_at=None,
    )
    assert serialize_category(cat)["code"] == "GEN"

    product = m.Product(
        name="Widget",
        sku="W1",
        category="General",
        category_id="c1",
        brand_id=None,
        unit_id=None,
        image_url="t1/product_images/x.png",
        cost_price=1,
        selling_price=2,
        stock_qty=3,
        reorder_level=0,
        tax_exempt=False,
        tracks_batches=False,
        is_active=True,
    )
    data = serialize_product(product)
    assert data["has_image"] is True
    assert data["category_id"] == "c1"
    assert data["sku"] == "W1"
