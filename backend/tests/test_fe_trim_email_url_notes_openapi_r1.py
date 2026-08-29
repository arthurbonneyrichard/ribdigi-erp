"""OpenAPI honesty tips #586–#589: FE trim email/URL/notes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_fe_trim_email_url_notes_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Bank feed URL FE trim OpenAPI",
        "Customer email FE trim OpenAPI",
        "Login / reset email FE trim OpenAPI",
        "AI prediction line notes FE trim OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "connFeedUrl.trim() || null" in docs
    assert "Customer email" in docs
    assert "customerEmail.trim() || null" in docs
    assert "Login email" in docs
    assert "Password reset email" in docs
    assert "email.trim()" in docs
    assert "String(x.notes || '').trim() || null" in docs

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "connFeedUrl.trim() || null" in accounting
    assert 'aria-label="Bank feed URL"' in accounting

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "email: customerEmail.trim() || null" in sales
    assert 'aria-label="Customer email"' in sales

    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Login email"' in login
    assert "email: email.trim()" in login
    assert login.count("email.trim()") >= 2  # login + resend

    forgot = (ROOT / "frontend/app/forgot-password/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Password reset email"' in forgot
    assert "email: email.trim()" in forgot

    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "notes: String(x.notes || '').trim() || null" in ai
    assert "predictionNotes.trim() || null" in ai
