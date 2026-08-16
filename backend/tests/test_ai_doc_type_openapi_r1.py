"""POST /ai/documents/analyze document_type Form OpenAPI Literal (BR-21.8)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from pypdf import PdfWriter

from app.ai_documents import VALID_DOC_TYPES
from app.schemas import AiDocumentTypeValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_ai_document_type_literal_covers_valid():
    lit = AiDocumentTypeValue.__args__[0]
    assert set(lit.__args__) == set(VALID_DOC_TYPES)


def test_ai_document_type_literal_schema():
    adapter = TypeAdapter(AiDocumentTypeValue)
    assert adapter.validate_python("auto") == "auto"
    assert adapter.validate_python("  Invoice ") == "invoice"
    assert adapter.validate_python("Purchase_Order") == "purchase_order"
    assert adapter.validate_python("RECEIPT") == "receipt"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("contract")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_ai_document_type_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'value="auto"' in page
    assert 'value="receipt"' in page
    assert 'value="invoice"' in page
    assert 'value="purchase_order"' in page
    assert "Document type" in page
    assert "documentType" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI document_type OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "document_type" in docs
    assert "422" in docs
    assert "Document type" in docs


@pytest.mark.asyncio
async def test_documents_analyze_document_type_blank_and_invalid_422(client):
    ac, _seed = client
    headers = await _mgr(ac)
    headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    files = {"file": ("invoice.pdf", _blank_pdf(), "application/pdf")}

    blank = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files=files,
        data={"document_type": ""},
    )
    assert blank.status_code == 422, blank.text

    whitespace = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files={"file": ("invoice.pdf", _blank_pdf(), "application/pdf")},
        data={"document_type": "   "},
    )
    assert whitespace.status_code == 422, whitespace.text

    bad = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files={"file": ("invoice.pdf", _blank_pdf(), "application/pdf")},
        data={"document_type": "contract"},
    )
    assert bad.status_code == 422, bad.text


@pytest.mark.asyncio
async def test_documents_analyze_document_type_coerce_ok(client, monkeypatch):
    from app import expense_ocr as ocr_svc

    ac, _seed = client
    monkeypatch.setattr(
        ocr_svc,
        "extract_text",
        lambda media: ("Tax Invoice INV-1\nTotal: GHS 10.00", "pdf"),
    )
    headers = await _mgr(ac)
    headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    r = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files={"file": ("invoice.pdf", _blank_pdf(), "application/pdf")},
        data={"document_type": "  Invoice "},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["document_type_requested"] == "invoice"
