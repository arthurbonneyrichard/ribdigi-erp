"""OpenAPI honesty tips #639–#644: API Standards docs follow-through."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app import api as api_mod
from app.inventory import lookup_products
from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_ISO = TypeAdapter(IsoDateQueryValue)


def test_api_standards_honesty_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Request Content-Type honesty OpenAPI",
        "Response media-type honesty OpenAPI",
        "Date input honesty OpenAPI",
        "HTTP Methods honesty OpenAPI",
        "Product lookup list shape honesty OpenAPI",
        "Error code catalog honesty OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]

    assert "multipart/form-data" in standards
    assert "All requests and responses use **JSON**" not in standards
    assert "Content-Type header must be: `application/json`" not in standards

    assert "YYYY-MM-DD" in standards
    assert "YYYY-MM-DDTHH:MM:SSZ`)" not in standards or "Not limited" in standards
    assert "IsoDateQueryValue" in standards

    assert "Non-JSON responses" in standards
    assert "Prometheus" in standards or "/metrics" in standards

    assert "Full update" not in standards
    assert "exchange-rates" in standards
    assert "warehouse-stock/reorder" in standards
    assert "reorder-policy" in standards
    assert "primarily `PATCH`" in standards or "primarily PATCH" in standards

    assert "inventory/products/lookup" in standards
    assert "items" in standards and "count" in standards
    assert "next_cursor" not in standards
    assert "{ items, pagination }" in standards or "pagination }" in standards

    errors = docs.split("### Common Error Codes")[1].split("## Appendix A")[0]
    assert "AUTHENTICATION_FAILED" not in errors
    assert "TOKEN_EXPIRED" not in errors
    assert "DUPLICATE_ENTRY" not in errors
    assert "RESOURCE_NOT_FOUND" not in errors
    assert "INSUFFICIENT_PERMISSIONS" not in errors
    assert "metrics" in errors.lower() or "operator-side" in errors.lower()
    assert "CREDIT_LIMIT_EXCEEDED" in errors
    assert "INSUFFICIENT_STOCK" in errors
    assert "RATE_LIMIT_EXCEEDED" in errors
    assert "EMAIL_NOT_VERIFIED" in errors

    lookup_doc = docs.split("**Integrator lookup")[1].split("### 5.5")[0]
    assert '"items"' in lookup_doc or "`items`" in lookup_doc
    assert "bare product array" in lookup_doc or "not a bare" in lookup_doc


def test_iso_date_query_accepts_date_and_datetime():
    assert _ISO.validate_python("2026-08-07") == "2026-08-07"
    assert _ISO.validate_python("2026-08-07T13:51:00Z") == "2026-08-07T13:51:00Z"
    with pytest.raises(ValidationError):
        _ISO.validate_python("01/02/2024")
    with pytest.raises(ValidationError):
        _ISO.validate_python("not-a-date")
    with pytest.raises(ValidationError):
        _ISO.validate_python("")


def test_put_routes_are_only_three_upserts():
    src = Path(api_mod.__file__).read_text(encoding="utf-8")
    puts = [
        line.strip()
        for line in src.splitlines()
        if line.strip().startswith("@api.put(")
    ]
    assert len(puts) == 3, puts
    joined = "\n".join(puts)
    assert "/credit/exchange-rates/{currency_code}" in joined
    assert "/inventory/warehouse-stock/reorder" in joined
    assert "/stores/{store_id}/reorder-policy" in joined


def test_product_lookup_returns_items_wrapper_shape():
    src = inspect.getsource(lookup_products)
    assert '"items"' in src
    assert '"count"' in src
    assert '"q"' in src
    assert "next_cursor" not in src
    assert "pagination" not in src


@pytest.mark.asyncio
async def test_product_lookup_live_shape(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )
    resp = await ac.get(
        "/api/v1/inventory/products/lookup",
        params={"q": "x", "limit": 5},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    data = body["data"]
    assert set(data.keys()) >= {"q", "barcode", "count", "items"}
    assert isinstance(data["items"], list)
    assert "pagination" not in data
    assert "next_cursor" not in data
