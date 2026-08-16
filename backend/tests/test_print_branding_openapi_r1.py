"""Print branding template/paper OpenAPI Literals (BR-20.4)."""

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

ROOT = Path(__file__).resolve().parents[2]


def test_print_branding_literal_schema():
    bare = PrintBrandingUpdate.model_validate({})
    assert bare.default_invoice_template is None
    assert bare.default_receipt_paper is None

    ok = PrintBrandingUpdate.model_validate(
        {
            "default_invoice_template": "THERMAL",
            "default_receipt_paper": "58MM",
        }
    )
    assert ok.default_invoice_template == "thermal"
    assert ok.default_receipt_paper == "58mm"

    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_invoice_template": ""})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_invoice_template": "letter"})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_receipt_paper": ""})
    with pytest.raises(ValidationError):
        PrintBrandingUpdate.model_validate({"default_receipt_paper": "112mm"})


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
    assert 'value="a4"' in company and 'value="thermal"' in company
    assert 'value="80mm"' in company and 'value="58mm"' in company
    assert "/settings/print" in company
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/settings/print" in api
    assert 'Literal["a4","thermal"]' in api
    assert 'Literal["58mm","80mm"]' in api
    assert "422" in api
