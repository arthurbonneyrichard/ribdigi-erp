"""Party profile_type / status OpenAPI Literals (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PartyCreate, PartyUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_party_profile_type_status_literal_schema():
    ok = PartyCreate.model_validate({"name": "A", "profile_type": "walk_in", "status": "inactive"})
    assert ok.profile_type == "walk_in"
    assert ok.status == "inactive"
    defaulted = PartyCreate.model_validate({"name": "B"})
    assert defaulted.profile_type == "registered"
    assert defaulted.status == "active"

    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "x", "profile_type": ""})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "x", "profile_type": "bogus"})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "x", "status": ""})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "x", "status": "archived"})

    bare = PartyUpdate.model_validate({})
    assert bare.profile_type is None and bare.status is None
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"profile_type": ""})
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"status": "gone"})


def test_party_profile_type_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "customerProfileType" in sales
    assert 'value="walk_in"' in sales
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "supplierProfileType" in purchasing
    assert 'value="manufacturer"' in purchasing
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "profile_type" in api
    assert "Literal" in api
    assert "422" in api
