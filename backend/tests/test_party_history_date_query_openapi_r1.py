"""Customer/supplier history from_date/to_date Query OpenAPI honesty (BR-7.1 / BR-6.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_party_history():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    assert adapter.validate_python("2026-08-17T12:00:00") == "2026-08-17T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01", "2026-02-30"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_party_history_date_ui_and_docs():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit history from date"' in credit
    assert 'aria-label="Credit history to date"' in credit
    assert "histFromDate" in credit
    assert "/customers/" in credit and "/history" in credit
    assert "/suppliers/" in credit and "/history" in credit
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer/supplier history date Query OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "/customers/{customer_id}/history" in docs
    assert "/suppliers/{supplier_id}/history" in docs


@pytest.mark.asyncio
async def test_party_history_date_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    cust = await ac.get("/api/v1/customers", headers=headers)
    assert cust.status_code == 200, cust.text
    customers = cust.json()["data"]
    assert customers, "expected seeded customers"
    customer_id = customers[0]["id"]

    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "History Date Query Supplier", "kind": "supplier"},
    )
    assert created.status_code in (200, 201), created.text
    supplier_id = created.json()["data"]["id"]

    paths = (
        f"/api/v1/customers/{customer_id}/history",
        f"/api/v1/suppliers/{supplier_id}/history",
    )

    for path in paths:
        blank = await ac.get(f"{path}?from_date=", headers=headers)
        assert blank.status_code == 422, (path, blank.text)

        bad = await ac.get(f"{path}?from_date=not-a-date", headers=headers)
        assert bad.status_code == 422, (path, bad.text)

        slash = await ac.get(f"{path}?to_date=01/02/2024", headers=headers)
        assert slash.status_code == 422, (path, slash.text)

        ok = await ac.get(
            f"{path}?from_date=2020-01-01&to_date=2099-12-31",
            headers=headers,
        )
        assert ok.status_code == 200, (path, ok.text)
        body = ok.json()["data"]
        assert isinstance(body, dict)
        assert "summary" in body or "purchases" in body

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, (path, omit.text)
