from app.notifications import DEFAULT_PREFERENCES, merge_preferences, VALID_CATEGORIES


def test_default_preferences_cover_core_types():
    assert "low_stock" in DEFAULT_PREFERENCES
    assert "payment_due" in DEFAULT_PREFERENCES
    assert "new_order" in DEFAULT_PREFERENCES
    assert DEFAULT_PREFERENCES["low_stock"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["new_order"]["dashboard"] is True


def test_merge_preferences_overrides_channels():
    merged = merge_preferences({"low_stock": {"email": True, "dashboard": False}})
    assert merged["low_stock"]["email"] is True
    assert merged["low_stock"]["dashboard"] is False
    assert merged["system"]["dashboard"] is True
    assert merged["new_order"]["dashboard"] is True


def test_valid_categories():
    assert "shift_variance" in VALID_CATEGORIES
    assert "expense_approval" in VALID_CATEGORIES
    assert "new_order" in VALID_CATEGORIES
    assert "purchase_received" in VALID_CATEGORIES
