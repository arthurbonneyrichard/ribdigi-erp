"""Stage 111 I1 — Inventory movement_type Shell leaves (+ warehouse_id URL)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_inventory_movement_type_leaves_i1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    for mt in (
        "stock_in",
        "stock_out",
        "opening_stock",
        "adjustment",
        "transfer_out",
        "transfer_in",
    ):
        assert f"movement_type={mt}" in shell, mt
    assert "Stock In Movements" in shell
    assert "Transfer In Movements" in shell


def test_inventory_movements_warehouse_url_sync_i1():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "syncMovementFiltersUrl" in inv
    assert "warehouse_id" in inv
    assert "Stage 111" in inv
    assert "Movements warehouse filter" in inv or 'aria-label="Movements warehouse filter"' in inv
