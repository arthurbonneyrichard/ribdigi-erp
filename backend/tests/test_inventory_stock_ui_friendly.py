"""Inventory stock tabs: no BR- codes; compact list + drawer pattern."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend/app/(dashboard)/inventory/page.tsx"


def _section(text: str, tab: str, nxt: str | None) -> str:
    start = text.find(f"{{tab === '{tab}' &&")
    if nxt:
        end = text.find(f"{{tab === '{nxt}' &&")
    else:
        end = len(text)
    assert start >= 0 and end > start, (tab, nxt, start, end)
    return text[start:end]


def test_stock_tabs_ui_matches_categories_pattern():
    page = PAGE.read_text(encoding="utf-8")
    batches = _section(page, "batches", "opening")
    opening = _section(page, "opening", "expiry")
    expiry = _section(page, "expiry", "counts")
    counts = _section(page, "counts", "movements")
    movements = _section(page, "movements", "adjust")
    adjust = _section(page, "adjust", "stockout")
    stockout = _section(page, "stockout", "whstock")
    whstock = _section(page, "whstock", "transfers")
    transfers = _section(page, "transfers", None)

    for chunk in (
        batches,
        opening,
        expiry,
        counts,
        movements,
        adjust,
        stockout,
        whstock,
        transfers,
    ):
        assert "BR-" not in chunk
        assert "cat-panel" in chunk
        assert "UuidIdValue" not in chunk

    assert "<h2" in batches and "Batches" in batches
    assert "Receive batch" in batches
    assert "FormModal" in batches
    assert "No batches yet" in batches

    assert "Opening stock" in opening
    assert "assigned when you save" in opening
    assert "Opening stock reference" in opening
    assert "Post opening stock" in opening

    assert "Expiry" in expiry
    assert "Set expiry" in expiry
    assert "No batches expiring" in expiry
    assert "Save expiry lot" in page
    assert "recordExpiryLot" in page

    assert "Stock count" in counts
    assert "Start count" in counts
    assert "inv-drawer" in counts

    assert "Stock history" in movements
    assert "No stock history yet" in movements

    assert "Adjust stock" in adjust
    assert "Confirm adjustment" in adjust
    assert "Select reason" in adjust
    assert "Manage stock" in adjust

    assert "Stock out" in stockout
    assert "Issue stock" in stockout

    assert "Manage stock" in whstock
    assert "Low stock" in whstock
    assert "Receive stock" in whstock
    assert "Adjust stock" in whstock

    assert "Stock transfer" in transfers
    assert "Add Transfer" in transfers
    assert "assigned when you save" in transfers
    assert 'aria-label="Opening stock reference"' in page
