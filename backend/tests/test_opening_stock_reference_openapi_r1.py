"""OpeningStockCreate.reference OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import OpeningStockCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_opening_stock_reference_schema():
    omit = OpeningStockCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}]}
    )
    assert omit.reference is None
    ok = OpeningStockCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}], "reference": "  FY2026-OS  "}
    )
    assert ok.reference == "FY2026-OS"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            OpeningStockCreate.model_validate(
                {"lines": [{"product_id": "p1", "quantity": 1}], "reference": bad}
            )


def test_opening_stock_reference_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening stock reference"' in page
    assert "openingReference.trim() || null" in page
    assert 'aria-label="Post opening stock"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening stock reference OpenAPI" in agents
    assert "OpeningStockReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "OpeningStockReferenceValue" in docs
    assert "Opening stock reference" in docs


@pytest.mark.asyncio
async def test_opening_stock_reference_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    products = await ac.get("/api/v1/products", headers=admin)
    assert products.status_code == 200, products.text
    rows = products.json().get("data") or []
    assert rows, "seed products required"
    product_id = rows[0]["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=admin,
            json={
                "reference": bad,
                "post_journal": False,
                "lines": [{"product_id": product_id, "quantity": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "post_journal": False,
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert omit.status_code == 200, omit.text
    auto_ref = omit.json()["data"].get("reference") or ""
    assert auto_ref.startswith("OS-"), auto_ref

    ok = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "reference": f"  TIP152-{suffix}  ",
            "post_journal": False,
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reference"] == f"TIP152-{suffix}"
