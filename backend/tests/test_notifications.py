from app.notifications import (
    DEFAULT_PREFERENCES,
    VALID_CATEGORIES,
    category_group,
    merge_preferences,
)


def test_default_preferences_cover_core_types():
    assert "low_stock" in DEFAULT_PREFERENCES
    assert "new_order" in DEFAULT_PREFERENCES
    assert "payment_due" in DEFAULT_PREFERENCES
    assert "quotation_expiry" in DEFAULT_PREFERENCES
    assert "recurring_expense" in DEFAULT_PREFERENCES
    assert DEFAULT_PREFERENCES["low_stock"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["new_order"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["quotation_expiry"]["email"] is True
    assert DEFAULT_PREFERENCES["recurring_expense"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["expense_approval"]["email"] is True
    assert DEFAULT_PREFERENCES["expense_approval"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["expense_decision"]["email"] is True
    assert DEFAULT_PREFERENCES["expense_decision"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["ai_insight"]["email"] is True
    assert DEFAULT_PREFERENCES["ai_insight"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["security"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["security"]["email"] is True


def test_merge_preferences_overrides_channels():
    merged = merge_preferences({"low_stock": {"email": True, "dashboard": False}})
    assert merged["low_stock"]["email"] is True
    assert merged["low_stock"]["dashboard"] is False
    assert merged["system"]["dashboard"] is True


def test_valid_categories():
    assert "shift_variance" in VALID_CATEGORIES
    assert "new_order" in VALID_CATEGORIES
    assert "expense_approval" in VALID_CATEGORIES
    assert "expense_decision" in VALID_CATEGORIES
    assert "quotation_expiry" in VALID_CATEGORIES
    assert "recurring_expense" in VALID_CATEGORIES
    assert "ai_insight" in VALID_CATEGORIES


def test_category_group_mapping():
    assert category_group("low_stock") == "stock"
    assert category_group("new_order") == "orders"
    assert category_group("payment_due") == "payments"
    assert category_group("unknown_thing") == "system"
