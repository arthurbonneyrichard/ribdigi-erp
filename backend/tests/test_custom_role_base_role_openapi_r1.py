"""CustomRoleCreate.base_role OpenAPI Literal (BR-3.x)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import CustomRoleCreate

ROOT = Path(__file__).resolve().parents[2]


def test_custom_role_base_role_literal_schema():
    ok = CustomRoleCreate.model_validate(
        {"key": "warehouse_lead", "label": "Warehouse Lead", "base_role": "inventory_officer"}
    )
    assert ok.base_role == "inventory_officer"

    coerced = CustomRoleCreate.model_validate(
        {"key": "lead", "label": "Lead", "base_role": "  Cashier "}
    )
    assert coerced.base_role == "cashier"

    omitted = CustomRoleCreate.model_validate(
        {"key": "custom_a", "label": "A", "permissions": {"inventory": ["read"]}}
    )
    assert omitted.base_role is None

    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "base_role": ""}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "base_role": "   "}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "base_role": "super_admin"}
        )
    with pytest.raises(ValidationError):
        CustomRoleCreate.model_validate(
            {"key": "x", "label": "X", "base_role": "garbage_xyz"}
        )


def test_custom_role_base_role_ui_and_docs():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "base_role" in users
    assert "Clone from" in users
    assert "super_admin" in users
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "base_role" in api
    assert "super_admin" in api
    assert "422" in api
