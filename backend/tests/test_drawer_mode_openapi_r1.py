"""Store cash drawer_mode OpenAPI Literal (BR-8.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import StoreDrawerSettingsUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_drawer_mode_literal_schema():
    ok = StoreDrawerSettingsUpdate.model_validate({"drawer_mode": "mock"})
    assert ok.drawer_mode == "mock"
    # omit field → None (no change on PATCH)
    bare = StoreDrawerSettingsUpdate.model_validate({})
    assert bare.drawer_mode is None
    with pytest.raises(ValidationError):
        StoreDrawerSettingsUpdate.model_validate({"drawer_mode": ""})
    with pytest.raises(ValidationError):
        StoreDrawerSettingsUpdate.model_validate({"drawer_mode": "   "})
    with pytest.raises(ValidationError):
        StoreDrawerSettingsUpdate.model_validate({"drawer_mode": "usb"})


def test_drawer_mode_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "drawerMode" in stores
    assert 'value="browser_bridge"' in stores
    assert 'value="mock"' in stores
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "drawer_mode" in api
    assert "Literal" in api or "omit/blank/invalid → **422**" in api or "blank/invalid → **422**" in api
