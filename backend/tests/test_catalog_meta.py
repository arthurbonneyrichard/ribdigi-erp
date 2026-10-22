from types import SimpleNamespace

from app import models as m
from app.catalog_meta import (
    DEFAULT_CATEGORIES,
    DEFAULT_UNITS,
    compute_stock_status,
    qty_is_low_stock,
    qty_is_out_of_stock,
    serialize_category,
    serialize_product,
)


def test_qty_zero_is_out_of_stock_not_low():
    assert qty_is_out_of_stock(0) is True
    assert qty_is_out_of_stock(-1) is True
    assert qty_is_low_stock(0, minimum_stock=5, reorder_level=5) is False
    assert qty_is_low_stock(5, minimum_stock=5, reorder_level=2) is True
    assert compute_stock_status(0, 5, 5)["status"] == "out"
    assert compute_stock_status(5, 5, 2)["status"] == "red"
    assert compute_stock_status(20, 5, 2)["status"] == "green"


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


def test_low_stock_floor_uses_max_of_minimum_and_reorder():
    from app.catalog_meta import low_stock_floor, qty_is_low_stock

    assert low_stock_floor(3, 10) == 10
    assert low_stock_floor(12, 10) == 12
    assert qty_is_low_stock(10, minimum_stock=3, reorder_level=10) is True
    assert qty_is_low_stock(11, minimum_stock=3, reorder_level=10) is False
    assert qty_is_low_stock(0, minimum_stock=0, reorder_level=0) is False
    assert qty_is_low_stock(0, minimum_stock=3, reorder_level=10) is False


def test_location_policy_floor_prefers_location_then_product():
    from app.catalog_meta import location_policy_floor, qty_is_low_stock

    assert location_policy_floor(product_reorder_level=10, location_reorder_level=0) == 10
    assert location_policy_floor(product_reorder_level=10, location_reorder_level=4) == 4
    assert location_policy_floor(
        product_minimum_stock=12,
        product_reorder_level=5,
        location_minimum_stock=0,
        location_reorder_level=0,
    ) == 12
    assert location_policy_floor(
        product_minimum_stock=3,
        product_reorder_level=5,
        location_minimum_stock=8,
        location_reorder_level=0,
    ) == 8
    assert qty_is_low_stock(5, minimum_stock=10, reorder_level=10) is True
    assert qty_is_low_stock(0, minimum_stock=10, reorder_level=10) is False
