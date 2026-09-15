"""OpenAPI honesty tips #612–#621: Literal select aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_literal_select_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tax rate type aria OpenAPI",
        "Tax pricing mode aria OpenAPI",
        "Product supply class aria OpenAPI",
        "Warehouse type aria OpenAPI",
        "Cash drawer mode aria OpenAPI",
        "Liquid account kind aria OpenAPI",
        "Cash transfer kind aria OpenAPI",
        "Bank connection provider aria OpenAPI",
        "User record scope aria OpenAPI",
        "POS payment method aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    for label in (
        "Tax rate type",
        "Tax pricing mode",
        "Product supply class",
        "Warehouse type",
        "Cash drawer mode",
        "Liquid account kind",
        "Cash transfer kind",
        "Bank connection provider",
        "User record scope",
        "POS payment method",
    ):
        assert label in docs, label

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate type"' in tax
    assert 'aria-label="Tax pricing mode"' in tax

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Product supply class"' in inventory
    assert 'aria-label="Edit product supply class"' in inventory

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse type"' in stores
    assert 'aria-label="Cash drawer mode"' in stores

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Liquid account kind"' in accounting
    assert 'aria-label="Cash transfer kind"' in accounting
    assert 'aria-label="Bank connection provider"' in accounting

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User record scope"' in users
    assert "Edit user record scope for" in users

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS payment method"' in pos
