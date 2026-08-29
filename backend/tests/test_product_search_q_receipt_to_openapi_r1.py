"""OpenAPI honesty tips #493–#494: product search Query `q` + receipt override `to`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductSearchQueryValue, ReceiptOverrideToValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_q = TypeAdapter(ProductSearchQueryValue)
_to = TypeAdapter(ReceiptOverrideToValue)


def test_product_search_q_and_receipt_to_schema():
    assert _q.validate_python("") == ""
    assert _q.validate_python("  flour  ") == "flour"
    assert _q.validate_python("SKU-1") == "SKU-1"
    for bad in ("!!!", "@@@", "http://evil", "://x"):
        with pytest.raises(ValidationError):
            _q.validate_python(bad)
    with pytest.raises(ValidationError):
        _q.validate_python("x" * 121)

    assert "@" in _to.validate_python("  override@example.com  ")
    assert _to.validate_python("+15551234567").startswith("+")
    for bad in ("", "!!!", "not-an-email", "123", "http://evil"):
        with pytest.raises(ValidationError):
            _to.validate_python(bad)


def test_product_search_q_receipt_to_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Product lookup search Query OpenAPI",
        "POS product search Query OpenAPI",
        "POS receipt send Query `to` OpenAPI",
    ):
        assert title in agents, title
    assert "ProductSearchQueryValue" in agents
    assert "ReceiptOverrideToValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProductSearchQueryValue" in docs
    assert "ReceiptOverrideToValue" in docs
    assert "/inventory/products/lookup" in docs
    assert "Integrator lookup" in docs

    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product lookup search"' in inv
    assert "params.set('q', q)" in inv

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Barcode scan or product search"' in pos
    assert 'aria-label="POS receipt override to"' in pos
    assert "receiptTo.trim()" in pos


@pytest.mark.asyncio
async def test_product_search_q_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for path in ("/api/v1/inventory/products/lookup", "/api/v1/pos/products/search"):
        for bad in ("!!!", "@@@", "http://evil"):
            resp = await ac.get(f"{path}?q={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)
        empty = await ac.get(f"{path}?q=", headers=headers)
        assert empty.status_code == 200, (path, empty.text)
        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, (path, omit.text)
        ok = await ac.get(f"{path}?q=flour", headers=headers)
        assert ok.status_code == 200, (path, ok.text)


@pytest.mark.asyncio
async def test_receipt_override_to_value_wired_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "ReceiptOverrideToValue" in api
    assert "ProductSearchQueryValue" in api
    assert api.count("q: Annotated[ProductSearchQueryValue, Query()]") >= 2
