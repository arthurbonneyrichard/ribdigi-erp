"""Stage 157 D1 — documentation fidelity for predictions / sales-trend / top-products CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage157_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_157_FIDELITY.md")
    assert (
        "prediction" in fidelity.lower()
        or "sales-trend" in fidelity.lower()
        or "top-product" in fidelity.lower()
    )
    for name in (
        "test_stage157_inventory_predictions_p1.py",
        "test_stage157_sales_trend_s1.py",
        "test_stage157_top_products_t1.py",
        "test_stage157_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-320" in fidelity or "ADR_320" in fidelity
    assert "H157x" in fidelity
    plan = _read("docs/STAGE_157_PLAN.md")
    assert "STAGE_157_FIDELITY.md" in plan
    for ws in ("P1", "S1", "T1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage157_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_157_FIDELITY.md" in br
    assert "Stage 157 D1" in br or "test_stage157_fidelity_d1.py" in br
    assert "Stage 157 P1" in br or "Stage 157 S1" in br or "Stage 157 T1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_157_FIDELITY.md" in fidelity_tail or "Stage 157 D1" in fidelity_tail


def test_stage157_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 157 D1" in api or "STAGE_157_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 157 D1" in deploy or "STAGE_157_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 157 D1" in sec or "STAGE_157_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage157_inventory_predictions_p1.py" in launch
    assert "test_stage157_sales_trend_s1.py" in launch
    assert "test_stage157_top_products_t1.py" in launch
    assert "test_stage157_fidelity_d1.py" in launch
    assert "STAGE_157_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "predictions/export" in manual
        or "Inventory Predictions" in manual
        or "sales-trend/export" in manual
        or "Sales-Trend" in manual
        or "top-products/export" in manual
        or "Top-Products" in manual
    )


def test_stage157_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_157_FIDELITY.md" in pr and "test_stage157_fidelity_d1.py" in pr
    assert "Stage 157 D1" in pr and "Stage 157 P1" in pr and "Stage 157 S1" in pr and "Stage 157 T1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_157_FIDELITY.md" in roadmap and "Stage 157 D1" in roadmap
    assert "ADR_320_STAGE157_OPEN.md" in roadmap and "STAGE_157_PLAN.md" in roadmap
