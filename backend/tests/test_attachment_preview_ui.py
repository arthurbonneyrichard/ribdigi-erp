"""Expense / PI / JE attachment inline preview packaging (BR-9.4)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_attachment_preview_component_and_helpers():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "Content-Disposition" in main
    assert "expose_headers" in main

    helper = (ROOT / "frontend/lib/attachments.ts").read_text(encoding="utf-8")
    assert "fetchAttachment" in helper
    assert "isImageContentType" in helper
    assert "isPdfContentType" in helper

    comp = (ROOT / "frontend/components/AttachmentPreview.tsx").read_text(encoding="utf-8")
    assert "Attachment preview" in comp or "AttachmentPreview" in comp
    assert "createObjectURL" in comp or "fetchAttachment" in comp
    assert "<iframe" in comp
    assert "<img" in comp


def test_expenses_purchasing_accounting_preview_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in expenses
    assert "Preview" in expenses
    assert "/expenses/${r.id}/attachment" in expenses
    assert "setAttachPreview" in expenses

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in purchasing
    assert "Preview" in purchasing

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in accounting
    assert "Preview" in accounting


def test_br_9_4_marked_complete():
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    section = brd.split("#### BR-9.4 Expense Attachments", 1)[1].split("#### BR-9.5", 1)[0]
    assert "[x] Upload receipt images/PDFs" in section
    assert "[x] OCR extraction" in section
    assert "[x] Attachment preview and download" in section
