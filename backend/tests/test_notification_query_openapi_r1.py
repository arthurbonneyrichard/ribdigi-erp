"""GET /notifications status + category Query OpenAPI Literals (BR-4.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.notifications import VALID_CATEGORIES
from app.schemas import NotificationCategoryValue, NotificationStatusValue

ROOT = Path(__file__).resolve().parents[2]


def test_notification_category_literal_covers_valid():
    lit = NotificationCategoryValue.__args__[0]
    assert set(lit.__args__) == set(VALID_CATEGORIES)


def test_notification_query_literal_schema():
    status = TypeAdapter(NotificationStatusValue)
    assert status.validate_python("Unread") == "unread"
    with pytest.raises(ValidationError):
        status.validate_python("")
    with pytest.raises(ValidationError):
        status.validate_python("archived")

    cat = TypeAdapter(NotificationCategoryValue)
    assert cat.validate_python("  Low_Stock ") == "low_stock"
    assert cat.validate_python("quotation_expiry") == "quotation_expiry"
    with pytest.raises(ValidationError):
        cat.validate_python("")
    with pytest.raises(ValidationError):
        cat.validate_python("not_a_category")


def test_notification_query_ui_and_docs():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "CATEGORY_CHIPS" in page
    assert "quotation_expiry" in page
    assert "recurring_expense_due" in page
    assert "transfer" in page
    assert "setStatus('unread')" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Notification list query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "VALID_CATEGORIES" in docs or "category" in docs
