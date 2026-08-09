from app.notifications import DEFAULT_PREFERENCES, merge_preferences, VALID_CATEGORIES


def test_default_preferences_cover_core_types():
    assert "low_stock" in DEFAULT_PREFERENCES
    assert "payment_due" in DEFAULT_PREFERENCES
    assert "quotation_expiry" in DEFAULT_PREFERENCES
    assert "recurring_expense" in DEFAULT_PREFERENCES
    assert DEFAULT_PREFERENCES["low_stock"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["quotation_expiry"]["email"] is True
    assert DEFAULT_PREFERENCES["recurring_expense"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["expense_approval"]["email"] is True
    assert DEFAULT_PREFERENCES["expense_approval"]["dashboard"] is True


def test_merge_preferences_overrides_channels():
    merged = merge_preferences({"low_stock": {"email": True, "dashboard": False}})
    assert merged["low_stock"]["email"] is True
    assert merged["low_stock"]["dashboard"] is False
    assert merged["system"]["dashboard"] is True


def test_valid_categories():
    assert "shift_variance" in VALID_CATEGORIES
    assert "expense_approval" in VALID_CATEGORIES
    assert "quotation_expiry" in VALID_CATEGORIES
    assert "recurring_expense" in VALID_CATEGORIES
