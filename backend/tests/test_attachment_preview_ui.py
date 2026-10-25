"""Expense / PI / JE attachment inline preview packaging (BR-9.4)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_attachment_preview_component_and_helpers():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "Content-Disposition" in main
    assert "expose_headers" in main

    helper = (ROOT / "frontend/lib/attachments.ts").read_text(encoding="utf-8")
    assert "fetchAttachment" in helper
    assert "uploadAttachment" in helper
    assert "downloadAttachment" in helper
    assert "triggerBlobDownload" in helper
    assert "apiFetch" in helper
    assert "NEXT_PUBLIC_API_URL" not in helper
    assert "localhost:8000" not in helper
    assert "isImageContentType" in helper
    assert "isPdfContentType" in helper

    comp = (ROOT / "frontend/components/AttachmentPreview.tsx").read_text(encoding="utf-8")
    assert "Attachment preview" in comp or "AttachmentPreview" in comp
    assert "createObjectURL" in comp or "fetchAttachment" in comp
    assert "<iframe" in comp
    assert "<img" in comp


def test_expenses_purchasing_accounting_preview_wired():
    expenses = (ROOT / "frontend/app/(dashboard)/expenses/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in expenses
    assert "Preview" in expenses
    assert "/expenses/${r.id}/attachment" in expenses
    assert "setAttachPreview" in expenses
    assert "uploadAttachment" in expenses
    assert "NEXT_PUBLIC_API_URL" not in expenses
    assert "localhost:8000" not in expenses

    purchasing = (ROOT / "frontend/app/(dashboard)/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in purchasing
    assert "Preview" in purchasing
    assert "uploadAttachment" in purchasing
    assert "NEXT_PUBLIC_API_URL" not in purchasing
    assert "localhost:8000" not in purchasing

    accounting = (ROOT / "frontend/app/(dashboard)/accounting/page.tsx").read_text(encoding="utf-8")
    assert "AttachmentPreview" in accounting
    assert "Preview" in accounting
    assert "uploadAttachment" in accounting
    assert "downloadAttachment" in accounting
    assert "NEXT_PUBLIC_API_URL" not in accounting
    assert "localhost:8000" not in accounting


def test_desk_binary_fetches_use_same_origin_api():
    desks = [
        ROOT / "frontend/app/(dashboard)/inventory/page.tsx",
        ROOT / "frontend/app/(dashboard)/reports/page.tsx",
        ROOT / "frontend/app/(dashboard)/backup/page.tsx",
        ROOT / "frontend/app/(dashboard)/tax/page.tsx",
        ROOT / "frontend/app/(dashboard)/ai/page.tsx",
        ROOT / "frontend/app/(dashboard)/prescriptions/page.tsx",
    ]
    for path in desks:
        text = path.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_API_URL" not in text, path.name
        assert "localhost:8000" not in text, path.name
    inventory = desks[0].read_text(encoding="utf-8")
    assert "downloadAttachment" in inventory
    assert "uploadAttachment" in inventory
    assert "apiFetch" in inventory
    reports = desks[1].read_text(encoding="utf-8")
    assert "downloadAttachment(`/reports/export?" in reports
    backup = desks[2].read_text(encoding="utf-8")
    assert "downloadAttachment(`/backup/${id}/download`" in backup
    tax = desks[3].read_text(encoding="utf-8")
    assert "downloadAttachment(`/reports/export?" in tax
    ai = desks[4].read_text(encoding="utf-8")
    assert "apiFetch('/ai/reports/export'" in ai
    rx = desks[5].read_text(encoding="utf-8")
    assert "uploadAttachment(`/pharmacy/prescriptions/${selected.id}/attachments`" in rx


def test_br_9_4_marked_complete():
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    section = brd.split("#### BR-9.4 Expense Attachments", 1)[1].split("#### BR-9.5", 1)[0]
    assert "[x] Upload receipt images/PDFs" in section
    assert "[x] OCR extraction" in section
    assert "[x] Attachment preview and download" in section
