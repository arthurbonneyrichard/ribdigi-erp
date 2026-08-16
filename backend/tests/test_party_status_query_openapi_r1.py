"""GET /customers|/suppliers status Query OpenAPI Literal (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api import _PARTY_STATUSES
from app.schemas import PartyStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_status_literal_covers_valid():
    lit = PartyStatusValue.__args__[0]
    assert set(lit.__args__) == set(_PARTY_STATUSES)


def test_party_status_literal_schema():
    adapter = TypeAdapter(PartyStatusValue)
    assert adapter.validate_python("active") == "active"
    assert adapter.validate_python("  Inactive ") == "inactive"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("archived")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_party_status_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer status filter"' in sales
    assert 'value="active"' in sales and 'value="inactive"' in sales
    assert 'aria-label="Supplier status filter"' in purchasing
    assert 'value="active"' in purchasing and 'value="inactive"' in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party list status Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "?status=active|inactive" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_party_list_status_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/customers", "/api/v1/suppliers"):
        blank = await ac.get(f"{path}?status=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?status=archived", headers=headers)
        assert bad.status_code == 422, bad.text

        ok = await ac.get(f"{path}?status=Active", headers=headers)
        assert ok.status_code == 200, ok.text
        assert isinstance(ok.json()["data"], list)

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, omit.text
