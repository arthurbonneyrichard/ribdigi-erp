"""OpenAPI honesty tips #622–#632: party/receipt/platform select aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_party_receipt_platform_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "POS receipt paper aria OpenAPI",
        "Balance sheet compare aria OpenAPI",
        "Report schedule weekday aria OpenAPI",
        "Customer profile type aria OpenAPI",
        "Customer status aria OpenAPI",
        "Supplier profile type aria OpenAPI",
        "Supplier status aria OpenAPI",
        "Purchase return reason aria OpenAPI",
        "Subscription package aria OpenAPI",
        "Subscription term unit aria OpenAPI",
        "Platform grant role aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    for label in (
        "POS receipt paper",
        "Balance sheet compare",
        "Report schedule weekday",
        "Customer profile type",
        "Customer status",
        "Supplier profile type",
        "Supplier status",
        "Purchase return reason",
        "Subscription package",
        "Subscription term unit",
        "Platform grant role",
    ):
        assert label in docs, label

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS receipt paper"' in pos

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Balance sheet compare"' in reports
    assert 'aria-label="Report schedule weekday"' in reports

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer profile type"' in sales
    assert 'aria-label="Customer status"' in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Supplier profile type"' in purchasing
    assert 'aria-label="Supplier status"' in purchasing
    assert 'aria-label="Purchase return reason"' in purchasing

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Subscription package"' in platform
    assert 'aria-label="Subscription term unit"' in platform

    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Platform grant role"' in staff
