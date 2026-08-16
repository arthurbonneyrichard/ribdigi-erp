"""Print/receipt query OpenAPI Literals (BR-20.4 / BR-8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    InvoicePrintFormatValue,
    InvoiceTemplateValue,
    ReceiptChannelValue,
    ReceiptPaperValue,
    ReceiptPrintFormatValue,
)

ROOT = Path(__file__).resolve().parents[2]


def test_print_query_literal_schema():
    inv_fmt = TypeAdapter(InvoicePrintFormatValue)
    assert inv_fmt.validate_python("PDF") == "pdf"
    with pytest.raises(ValidationError):
        inv_fmt.validate_python("")
    with pytest.raises(ValidationError):
        inv_fmt.validate_python("docx")

    tmpl = TypeAdapter(InvoiceTemplateValue)
    assert tmpl.validate_python("Thermal") == "thermal"
    with pytest.raises(ValidationError):
        tmpl.validate_python("letter")

    paper = TypeAdapter(ReceiptPaperValue)
    assert paper.validate_python("58MM") == "58mm"
    with pytest.raises(ValidationError):
        paper.validate_python("112mm")

    rcpt_fmt = TypeAdapter(ReceiptPrintFormatValue)
    assert rcpt_fmt.validate_python("Text") == "text"
    with pytest.raises(ValidationError):
        rcpt_fmt.validate_python("html")

    channel = TypeAdapter(ReceiptChannelValue)
    assert channel.validate_python("SMS") == "sms"
    with pytest.raises(ValidationError):
        channel.validate_python("")
    with pytest.raises(ValidationError):
        channel.validate_python("whatsapp")


def test_print_query_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "/print" in sales or "print?" in sales.lower() or "invoice" in sales.lower()
    assert "58mm" in pos and "80mm" in pos
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Print/receipt query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "receipt/send" in docs
    assert "422" in docs
