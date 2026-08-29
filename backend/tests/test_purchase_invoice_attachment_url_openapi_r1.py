"""PurchaseInvoiceCreate.attachment_url ∈ WebhookUrlValue OpenAPI (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseInvoiceCreate, WebhookUrlValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_url = TypeAdapter(WebhookUrlValue)


def test_purchase_invoice_attachment_url_value_schema():
    assert _url.validate_python("  https://files.example.com/inv.pdf  ") == (
        "https://files.example.com/inv.pdf"
    )
    assert _url.validate_python("http://localhost:9000/a.pdf") == "http://localhost:9000/a.pdf"
    for bad in ("", " ", "ftp://evil", "not-a-url", "www.x", "http://remote.example/x", "!!!"):
        with pytest.raises(ValidationError):
            _url.validate_python(bad)

    ok = PurchaseInvoiceCreate.model_validate(
        {"attachment_url": "  https://cdn.example.com/po.pdf  ", "items": []}
    )
    assert ok.attachment_url == "https://cdn.example.com/po.pdf"
    omit = PurchaseInvoiceCreate.model_validate({"items": []})
    assert omit.attachment_url is None
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate({"attachment_url": ""})
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate({"attachment_url": "ftp://evil"})
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate({"attachment_url": "not-a-url"})


def test_purchase_invoice_attachment_url_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert page.count('aria-label="Purchase invoice attachment URL"') >= 2
    assert "invAttachmentUrl.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice attachment URL OpenAPI" in agents
    assert "PurchaseInvoiceCreate.attachment_url" in agents
    assert "WebhookUrlValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "attachment_url" in docs
    assert "WebhookUrlValue" in docs
    assert "Purchase invoice attachment URL" in docs


@pytest.mark.asyncio
async def test_purchase_invoice_attachment_url_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP240 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip240-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    product_id = seed["p1"].id
    item = {
        "product_id": product_id,
        "quantity": 1,
        "unit_price": 12.5,
        "tax_rate": 0,
    }

    for bad in ("", "ftp://evil", "not-a-url", "http://remote.example/x"):
        r = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "attachment_url": bad,
                "items": [item],
            },
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "attachment_url": f"  https://files.example.com/tip240-{suffix}.pdf  ",
            "items": [item],
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["attachment_url"] == f"https://files.example.com/tip240-{suffix}.pdf"
    assert data["has_attachment"] is True

    omit = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [item],
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["attachment_url"] is None
