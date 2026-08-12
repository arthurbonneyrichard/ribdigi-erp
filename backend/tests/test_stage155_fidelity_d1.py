"""Stage 155 D1 — documentation fidelity for store inventory / sales / warehouse-stock CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage155_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_155_FIDELITY.md")
    assert (
        "inventory" in fidelity.lower()
        or "sales" in fidelity.lower()
        or "warehouse" in fidelity.lower()
    )
    for name in (
        "test_stage155_store_inventory_i1.py",
        "test_stage155_store_sales_s1.py",
        "test_stage155_warehouse_stock_w1.py",
        "test_stage155_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-316" in fidelity or "ADR_316" in fidelity
    assert "H155x" in fidelity
    plan = _read("docs/STAGE_155_PLAN.md")
    assert "STAGE_155_FIDELITY.md" in plan
    for ws in ("I1", "S1", "W1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage155_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_155_FIDELITY.md" in br
    assert "Stage 155 D1" in br or "test_stage155_fidelity_d1.py" in br
    assert "Stage 155 I1" in br or "Stage 155 S1" in br or "Stage 155 W1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_155_FIDELITY.md" in fidelity_tail or "Stage 155 D1" in fidelity_tail


def test_stage155_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 155 D1" in api or "STAGE_155_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 155 D1" in deploy or "STAGE_155_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 155 D1" in sec or "STAGE_155_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage155_store_inventory_i1.py" in launch
    assert "test_stage155_store_sales_s1.py" in launch
    assert "test_stage155_warehouse_stock_w1.py" in launch
    assert "test_stage155_fidelity_d1.py" in launch
    assert "STAGE_155_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "inventory/export" in manual
        or "Store Inventory" in manual
        or "sales/export" in manual
        or "Store Sales" in manual
        or "warehouse-stock/export" in manual
        or "Warehouse-Stock" in manual
    )


def test_stage155_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_155_FIDELITY.md" in pr and "test_stage155_fidelity_d1.py" in pr
    assert "Stage 155 D1" in pr and "Stage 155 I1" in pr and "Stage 155 S1" in pr and "Stage 155 W1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_155_FIDELITY.md" in roadmap and "Stage 155 D1" in roadmap
    assert "ADR_316_STAGE155_OPEN.md" in roadmap and "STAGE_155_PLAN.md" in roadmap
