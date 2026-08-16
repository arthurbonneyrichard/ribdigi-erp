"""User / custom-role record_scope OpenAPI Literal (BR-3.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.rbac import RECORD_SCOPES, normalize_record_scope
from app.schemas import (
    CustomRoleCreate,
    CustomRoleUpdate,
    UserCreate,
    UserUpdate,
)

ROOT = Path(__file__).resolve().parents[2]


def test_record_scope_literal_schema():
    ok = UserCreate.model_validate(
        {
            "email": "a@example.com",
            "full_name": "A",
            "password": "SecurePass123!",
            "record_scope": "BRANCH",
        }
    )
    assert ok.record_scope == "branch"
    omitted = UserCreate.model_validate(
        {
            "email": "b@example.com",
            "full_name": "B",
            "password": "SecurePass123!",
        }
    )
    assert omitted.record_scope is None

    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "c@example.com",
                "full_name": "C",
                "password": "SecurePass123!",
                "record_scope": "",
            }
        )
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "d@example.com",
                "full_name": "D",
                "password": "SecurePass123!",
                "record_scope": "   ",
            }
        )
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "e@example.com",
                "full_name": "E",
                "password": "SecurePass123!",
                "record_scope": "tenant",
            }
        )

    bare = UserUpdate.model_validate({})
    assert bare.record_scope is None
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"record_scope": ""})
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"record_scope": "everyone"})

    role = CustomRoleCreate.model_validate({"key": "ops", "label": "Ops", "record_scope": "Own"})
    assert role.record_scope == "own"
    with pytest.raises(ValidationError):
        CustomRoleUpdate.model_validate({"record_scope": ""})


def test_normalize_record_scope_defense():
    for item in sorted(RECORD_SCOPES):
        assert normalize_record_scope(item) == item
    assert normalize_record_scope(None) == "all"
    assert normalize_record_scope(None, default="own") == "own"
    with pytest.raises(ValueError):
        normalize_record_scope("tenant")


def test_record_scope_ui_and_docs():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "RECORD_SCOPES" in users
    assert "record_scope" in users
    assert "own" in users and "department" in users and "branch" in users and "all" in users
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["own","department","branch","all"]' in api
    assert "422" in api
