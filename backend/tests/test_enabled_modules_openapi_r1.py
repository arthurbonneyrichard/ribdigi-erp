"""enabled_modules OpenAPI Literal (packageable modules)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.packages import PACKAGEABLE_MODULES
from app.schemas import TenantModulesUpdate, TenantSubscriptionAssign

ROOT = Path(__file__).resolve().parents[2]


def test_enabled_modules_literal_schema():
    ok = TenantModulesUpdate.model_validate(
        {"enabled_modules": ["POS", " inventory ", "sales"]}
    )
    assert ok.enabled_modules == ["pos", "inventory", "sales"]

    omitted = TenantModulesUpdate.model_validate({"reset_to_package": True})
    assert omitted.enabled_modules is None

    with pytest.raises(ValidationError):
        TenantModulesUpdate.model_validate({"enabled_modules": ["pos", ""]})
    with pytest.raises(ValidationError):
        TenantModulesUpdate.model_validate({"enabled_modules": ["garbage_xyz"]})
    with pytest.raises(ValidationError):
        TenantModulesUpdate.model_validate({"enabled_modules": ["platform"]})

    assign = TenantSubscriptionAssign.model_validate(
        {
            "package_code": "professional",
            "term_value": 1,
            "enabled_modules": ["dashboard", "stores"],
        }
    )
    assert assign.enabled_modules == ["dashboard", "stores"]
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {
                "package_code": "professional",
                "term_value": 1,
                "enabled_modules": ["not_a_module"],
            }
        )

    # Keep schema catalog aligned with packages.py
    from typing import get_args

    from app.schemas import PackageableModuleValue

    # Annotated -> unwrap
    args = get_args(PackageableModuleValue)
    lit = args[0] if args else None
    assert set(get_args(lit)) == set(PACKAGEABLE_MODULES)


def test_enabled_modules_ui_and_docs():
    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert "enabled_modules" in platform
    assert "packageable" in platform
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PACKAGEABLE_MODULES" in api
    assert "422" in api
