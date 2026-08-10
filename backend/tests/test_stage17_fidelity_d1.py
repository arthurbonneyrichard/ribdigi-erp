"""Stage 17 D1 — documentation fidelity for Inventory Catalog & Stock Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage17_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_17_FIDELITY.md")
    assert "BR-5.1" in fidelity and "BR-5.5" in fidelity
    assert "BR-17.1" in fidelity
    assert "test_catalog_fidelity_c1.py" in fidelity
    assert "test_stock_ops_chain_s1.py" in fidelity
    assert "test_stock_count_chain_s2.py" in fidelity
    assert "test_warehouse_transfer_chain_w1.py" in fidelity
    assert "test_low_stock_reorder_l1.py" in fidelity
    assert "test_inventory_audit_a1.py" in fidelity
    assert "test_stage17_fidelity_d1.py" in fidelity
    assert "test_stage17_exit_h17x.py" in fidelity or "H17x" in fidelity
    assert "ADR-040" in fidelity or "exit met" in fidelity.lower()
    assert "INSUFFICIENT_WAREHOUSE_STOCK" in fidelity
    assert "multi-bin" in fidelity.lower() or "FIFO" in fidelity
    assert "ADR-039" in fidelity or "ADR_039" in fidelity

    plan = _read("docs/STAGE_17_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_17_FIDELITY.md" in plan
    for ws in ("C1", "S1", "S2", "W1", "L1", "A1", "D1"):
        assert f"| **{ws}**" in plan
        assert "COMPLETE" in plan
    assert "| **H17x**" in plan and "COMPLETE" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-040" in plan
    assert "STAGE_17_EXIT_CRITERIA.md" in plan
    assert "ADR-040" in plan or "ADR_040" in plan


def test_stage17_br_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 17 C1" in br
    assert "Stage 17 S1" in br
    assert "Stage 17 S2" in br
    assert "Stage 17 W1" in br
    assert "Stage 17 L1" in br
    assert "Stage 17 A1" in br
    assert "Stage 17 D1" in br or "[x] Log every stock change" in br
    assert "[x] **Categories:**" in br
    assert "[x] **Stock In:**" in br
    assert "[x] **Stock Count:**" in br
    assert "[x] **Stock Transfer:**" in br
    assert "[x] View stock levels per warehouse" in br
    assert "[x] Warehouse-specific reorder levels" in br
    assert "[x] Visual indicators on product list" in br
    assert "[x] Generate purchase suggestions" in br
    assert "[x] Log every stock change" in br
    assert "[x] Filter by date range, product, warehouse" in br
    assert "[x] Export to CSV/PDF" in br
    assert "[x] Immutable records" in br
    assert "[x] **Product Changes:**" in br


def test_stage17_api_manual_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 17 C1" in api
    assert "Stage 17 S1" in api
    assert "Stage 17 S2" in api
    assert "Stage 17 W1" in api
    assert "Stage 17 L1" in api
    assert "Stage 17 A1" in api
    assert "Stage 17 D1" in api or "inventory_movements" in api
    assert "/inventory/low-stock/reorder-po" in api
    assert "product_create" in api
    assert "INSUFFICIENT_WAREHOUSE_STOCK" in api
    assert "DELETE /products/{product_id}" not in api.split("### 5.4 Products")[1].split("### 5.5")[0]

    manual = _read("docs/USER_MANUAL.md")
    assert "STAGE_17_FIDELITY.md" in manual
    assert "Stage 17 L1" in manual
    assert "Create draft PO" in manual or "draft purchase order" in manual.lower()
    assert "Generate Purchase Suggestion" not in manual

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 17 A1" in sec
    assert "product_create" in sec
    assert "product_deactivate" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_catalog_fidelity_c1.py" in launch
    assert "test_stock_ops_chain_s1.py" in launch
    assert "test_stock_count_chain_s2.py" in launch
    assert "test_warehouse_transfer_chain_w1.py" in launch
    assert "test_low_stock_reorder_l1.py" in launch
    assert "test_inventory_audit_a1.py" in launch
    assert "test_stage17_fidelity_d1.py" in launch
    assert "STAGE_17_FIDELITY.md" in launch
    assert "test_stage17_exit_h17x.py" in launch


def test_stage17_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_17_FIDELITY.md" in pr
    assert "test_stage17_fidelity_d1.py" in pr
    assert "test_catalog_fidelity_c1.py" in pr
    assert "test_inventory_audit_a1.py" in pr
    assert "test_low_stock_reorder_l1.py" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_17_FIDELITY.md" in roadmap
    assert "Stage 17 D1" in roadmap
    assert "ADR_039_STAGE17_OPEN.md" in roadmap
    assert "STAGE_17_PLAN.md" in roadmap
    assert "STAGE_17_EXIT_CRITERIA.md" in roadmap
    assert "ADR_040_STAGE17_FREEZE.md" in roadmap
