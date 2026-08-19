"""Stage 102 A1 — AI section + Activity surface discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_ai_and_invoices_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/ai#chat" in shell
    assert "/ai#forecast" in shell
    assert "/ai#dead-stock" in shell
    assert "/ai#insights" in shell
    assert "/ai#security" in shell
    assert "/sales?tab=invoices" in shell
    assert "Sales Invoices" in shell


def test_ai_section_anchors_and_audit_dates_a1():
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    for anchor in (
        "chat",
        "forecast",
        "dead-stock",
        "insights",
        "security",
        "document",
        "customer",
        "low-stock",
    ):
        assert f'id="{anchor}"' in ai, anchor
    assert "scrollIntoView" in ai

    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "from_date" in audit
    assert "to_date" in audit
    assert "fromDate" in audit or "from_date" in audit
    assert "syncUrl" in audit
