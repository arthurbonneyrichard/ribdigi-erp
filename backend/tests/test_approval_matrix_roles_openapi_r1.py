"""Approval matrix roles[] OpenAPI honesty (expense + PR; BR-9.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import TypeAdapter, ValidationError

from app.rbac import VALID_ROLES
from app.schemas import (
    ApprovalLevelUpdate,
    PurchaseApprovalLevelUpdate,
    PurchaseApprovalSettingsUpdate,
    SystemRoleValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _literal_values(annotated) -> set[str]:
    cur: object = annotated
    for _ in range(6):
        origin = get_origin(cur)
        args = get_args(cur)
        if origin is Literal:
            return set(args)
        if not args:
            break
        cur = args[0]
    raise AssertionError(f"Could not unwrap Literal from {annotated!r}")


def test_system_role_literal_matches_valid_roles():
    adapter = TypeAdapter(SystemRoleValue)
    lit = _literal_values(SystemRoleValue)
    assert lit == set(VALID_ROLES)
    for role in VALID_ROLES:
        assert adapter.validate_python(role) == role
        assert adapter.validate_python(f"  {role.upper()} ") == role

    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("not_a_role")
    with pytest.raises(ValidationError):
        adapter.validate_python("custom_warehouse_lead")


def test_approval_level_roles_schema():
    ok = ApprovalLevelUpdate.model_validate(
        {"min_amount": 100, "roles": ["Store_Manager", "company_admin"]}
    )
    assert ok.roles == ["store_manager", "company_admin"]

    with pytest.raises(ValidationError):
        ApprovalLevelUpdate.model_validate(
            {"min_amount": 100, "roles": ["store_manager"], "extra": 1}
        )
    with pytest.raises(ValidationError):
        ApprovalLevelUpdate.model_validate({"min_amount": 100, "roles": []})
    with pytest.raises(ValidationError):
        ApprovalLevelUpdate.model_validate({"min_amount": 100, "roles": ["ghost_role"]})
    with pytest.raises(ValidationError):
        ApprovalLevelUpdate.model_validate({"min_amount": 100, "roles": [""]})

    pr = PurchaseApprovalLevelUpdate.model_validate(
        {"roles": ["COMPANY_ADMIN"], "label": "Admin"}
    )
    assert pr.roles == ["company_admin"]
    with pytest.raises(ValidationError):
        PurchaseApprovalSettingsUpdate.model_validate(
            {"levels": [{"roles": ["nope"]}], "extra": True}
        )


def test_approval_matrix_roles_ui_and_docs():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "SYSTEM_ROLES" in expenses
    assert 'aria-label="Save expense approval matrix"' in expenses
    assert "expense-approval-system-roles" in expenses
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "SYSTEM_ROLES" in purchasing
    assert 'aria-label="Save PR approval matrix"' in purchasing
    assert "pr-approval-system-roles" in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Approval matrix roles OpenAPI" in agents
    assert "SystemRoleValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SystemRoleValue" in docs
    assert "PATCH /expenses/settings" in docs
    assert "purchasing/requests/settings" in docs


@pytest.mark.asyncio
async def test_expense_approval_matrix_roles_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    bad = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {
                    "min_amount": 50,
                    "roles": ["not_a_role"],
                    "label": "Bad",
                }
            ]
        },
    )
    assert bad.status_code == 422, bad.text

    blank = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={"levels": [{"min_amount": 50, "roles": [""], "label": "Blank"}]},
    )
    assert blank.status_code == 422, blank.text

    ok = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {
                    "min_amount": 75,
                    "roles": ["store_manager"],
                    "label": "OpenAPI L1",
                },
                {
                    "min_amount": 500,
                    "roles": ["Company_Admin", "super_admin"],
                    "label": "OpenAPI L2",
                },
            ]
        },
    )
    assert ok.status_code == 200, ok.text
    levels = (ok.json()["data"] or {}).get("levels") or []
    assert len(levels) >= 2
    assert levels[0]["roles"] == ["store_manager"]
    assert "company_admin" in levels[1]["roles"]

    pr_bad = await ac.patch(
        "/api/v1/purchasing/requests/settings",
        headers=headers,
        json={"levels": [{"roles": ["ghost"], "label": "X"}]},
    )
    assert pr_bad.status_code == 422, pr_bad.text

    pr_ok = await ac.patch(
        "/api/v1/purchasing/requests/settings",
        headers=headers,
        json={
            "levels": [
                {"roles": ["store_manager"], "label": "SM"},
                {"roles": ["company_admin"], "label": "CA"},
            ]
        },
    )
    assert pr_ok.status_code == 200, pr_ok.text
