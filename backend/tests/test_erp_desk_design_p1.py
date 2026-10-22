"""Shared ERP desk language: tokens, page chrome, POS split, sidebar collapse."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_design_tokens_and_page_header():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    header = (ROOT / "frontend/components/PageHeader.tsx").read_text(encoding="utf-8")
    empty = (ROOT / "frontend/components/EmptyState.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    compact = css.replace(" ", "").replace("\n", "")

    assert "--space-4:16px" in css
    assert "--radius-lg:12px" in css
    assert "--control-h:36px" in css
    assert "--shadow:" in css
    assert ".page-head" in css
    assert ".page-empty" in css
    assert 'grid-template-areas:"cartcatalog"' in compact
    assert "nav-compact" in css and "side-edge-chevron" in css
    assert "rotate(180deg)" in css
    assert "list-page-head page-head" in header
    assert "kickerClassName" in header
    assert "children" in header
    assert "role={role}" in empty
    assert "role = 'status'" in empty
    assert "className" in empty
    assert 'aria-label={label}' in shell
    assert "Collapse sidebar" in shell
    assert "Expand sidebar" in shell


def test_desk_pages_use_shared_page_header():
    pages = [
        ROOT / "frontend/app/(dashboard)/ecommerce/page.tsx",
        ROOT / "frontend/app/(dashboard)/reports/page.tsx",
        ROOT / "frontend/app/(dashboard)/jobs/page.tsx",
        ROOT / "frontend/app/(dashboard)/restaurant/page.tsx",
        ROOT / "frontend/app/(dashboard)/gift-cards/page.tsx",
        ROOT / "frontend/app/(dashboard)/notifications/page.tsx",
        ROOT / "frontend/app/(dashboard)/audit/page.tsx",
        ROOT / "frontend/app/(dashboard)/backup/page.tsx",
        ROOT / "frontend/app/(dashboard)/integrations/page.tsx",
        ROOT / "frontend/app/(dashboard)/company/page.tsx",
        ROOT / "frontend/app/(dashboard)/company/billing/page.tsx",
        ROOT / "frontend/app/(dashboard)/hotel/page.tsx",
        ROOT / "frontend/app/(dashboard)/fmcg/page.tsx",
        ROOT / "frontend/app/(dashboard)/prescriptions/page.tsx",
        ROOT / "frontend/app/(dashboard)/hospital/page.tsx",
        ROOT / "frontend/app/(dashboard)/inventory/page.tsx",
        ROOT / "frontend/app/(dashboard)/ai/page.tsx",
        ROOT / "frontend/app/(dashboard)/security/page.tsx",
        ROOT / "frontend/app/(dashboard)/sales/page.tsx",
        ROOT / "frontend/app/(dashboard)/users/page.tsx",
        ROOT / "frontend/app/(dashboard)/purchasing/page.tsx",
        ROOT / "frontend/app/(dashboard)/credit/page.tsx",
        ROOT / "frontend/app/(dashboard)/tax/page.tsx",
        ROOT / "frontend/app/(dashboard)/printers/page.tsx",
        ROOT / "frontend/app/(dashboard)/expenses/page.tsx",
        ROOT / "frontend/app/(dashboard)/customers/page.tsx",
        ROOT / "frontend/app/(dashboard)/accounting/page.tsx",
        ROOT / "frontend/app/(dashboard)/billing/page.tsx",
        ROOT / "frontend/app/(dashboard)/stores/page.tsx",
        ROOT / "frontend/app/(dashboard)/departments/page.tsx",
        ROOT / "frontend/app/(dashboard)/support/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/reports/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/settings/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/billing/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/staff/page.tsx",
        ROOT / "frontend/app/(dashboard)/platform/support/page.tsx",
    ]
    for path in pages:
        text = path.read_text(encoding="utf-8")
        assert "PageHeader" in text, path.name


def test_dashboard_greeting_clock_is_fifty_percent_larger():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    compact = css.replace(" ", "").replace("\n", "")
    assert ".greet-time{--greet-digit-size:3rem}" in compact
    assert ".greet-time{--greet-digit-size:2rem}" not in compact
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert "greet-clock" not in pos
    assert "tpos-clock" not in pos


def test_page_level_empty_states_use_shared_component():
    pages = [
        ROOT / "frontend/app/(dashboard)/ecommerce/page.tsx",
        ROOT / "frontend/app/(dashboard)/customers/page.tsx",
        ROOT / "frontend/app/(dashboard)/credit/page.tsx",
        ROOT / "frontend/app/(dashboard)/reports/page.tsx",
        ROOT / "frontend/app/(dashboard)/inventory/page.tsx",
    ]
    for path in pages:
        text = path.read_text(encoding="utf-8")
        assert "EmptyState" in text, path.name
