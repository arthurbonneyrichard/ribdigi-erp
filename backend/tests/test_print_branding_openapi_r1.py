"""PrintBrandingUpdate header/footer OpenAPI honesty (BR-20.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.print_branding import (
    DEFAULT_INVOICE_TEMPLATE,
    DEFAULT_RECEIPT_PAPER,
    print_branding_settings,
)
from app.schemas import PrintBrandingUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_print_branding_literal_schema():
    bare = PrintBrandingUpdate.model_validate({})
    assert bare.default_invoice_template is None
    assert bare.default_receipt_paper is None
    assert bare.header_text is None
    assert bare.footer_text is None

    ok = PrintBrandingUpdate.model_validate(
        {
            "default_invoice_template": "THERMAL",
            "default_receipt_paper": "58MM",
            "header_text": "  Fresh daily  ",
            "footer_text": "  Pay within 14 days  ",
        }
    )
    assert ok.default_invoice_template == "thermal"
    assert ok.default_receipt_paper == "58mm"
    assert ok.header_text == "Fresh daily"
    assert ok.footer_text == "Pay within 14 days"

    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_invoice_template": ""})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_invoice_template": "letter"})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_receipt_paper": ""})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_receipt_paper": "112mm"})

    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PrintBrandingUpdate.model_validate({"header_text": bad})
        with pytest.raises(ValidationError):
            PrintBrandingUpdate.model_validate({"footer_text": bad})


def test_print_branding_read_path_coerces_garbage():
    class _T:
        print_branding = {
            "default_invoice_template": "bogus",
            "default_receipt_paper": "wide",
        }
        logo_url = None

    cfg = print_branding_settings(_T())
    assert cfg["default_invoice_template"] == DEFAULT_INVOICE_TEMPLATE
    assert cfg["default_receipt_paper"] == DEFAULT_RECEIPT_PAPER


def test_print_branding_ui_and_docs():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "invTemplate" in company and "receiptPaper" in company
    assert 'aria-label="Print branding header text"' in company
    assert 'aria-label="Print branding footer text"' in company
    assert 'aria-label="Save print branding"' in company
    assert "printHeader.trim() || null" in company
    assert 'value="a4"' in company and 'value="thermal"' in company
    assert 'value="80mm"' in company and 'value="58mm"' in company
    assert "/settings/print" in company
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PrintHeaderTextValue" in agents and "PrintFooterTextValue" in agents
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/settings/print" in api
    assert "PrintHeaderTextValue" in api
    assert 'Literal["a4","thermal"]' in api
    assert 'Literal["58mm","80mm"]' in api
    assert "422" in api


@pytest.mark.asyncio
async def test_print_branding_header_footer_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for field, bad in (
        ("header_text", "   "),
        ("header_text", "!!!"),
        ("header_text", "http://evil"),
        ("footer_text", "   "),
        ("footer_text", "!!!"),
        ("footer_text", "http://evil"),
    ):
        resp = await ac.patch(
            "/api/v1/settings/print",
            headers=headers,
            json={field: bad},
        )
        assert resp.status_code == 422, (field, bad, resp.text)

    ok = await ac.patch(
        "/api/v1/settings/print",
        headers=headers,
        json={
            "header_text": "Tip210 Fresh daily — API hello-world",
            "footer_text": "Tip210 Thank you — API hello-world",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["header_text"] == "Tip210 Fresh daily — API hello-world"
    assert body["footer_text"] == "Tip210 Thank you — API hello-world"

    cleared = await ac.patch(
        "/api/v1/settings/print",
        headers=headers,
        json={"header_text": None, "footer_text": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["header_text"] == ""
    assert cleared.json()["data"]["footer_text"] == ""
