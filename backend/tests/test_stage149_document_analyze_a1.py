"""Stage 149 A1 — AI document analyze CSV export."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_document_analyze_export_csv(client):
    ac, _seed = client
    headers = await _mgr(ac)
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()
    files = {"file": ("receipt.pdf", pdf_bytes, "application/pdf")}

    exported = await ac.post(
        "/api/v1/ai/documents/analyze/export?document_type=receipt",
        headers=headers,
        files=files,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "document_type" in header and "field_name" in header
    assert "summary" in text
    assert "raw_text_preview" not in text


def test_document_analyze_export_ui_a1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 149" in page
    assert "/ai/documents/analyze/export" in page
    assert "Export analyze CSV" in page
    assert 'id="document"' in page
