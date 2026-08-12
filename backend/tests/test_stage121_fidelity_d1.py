"""Stage 121 D1 — documentation fidelity for Inactive Stores, Warehouses & Location Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage121_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_121_FIDELITY.md")
    assert "Inactive" in fidelity or "store" in fidelity.lower() or "Warehouse" in fidelity
    for name in (
        "test_stage121_inactive_stores_s1.py",
        "test_stage121_inactive_warehouses_w1.py",
        "test_stage121_location_export_x1.py",
        "test_stage121_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-248" in fidelity or "ADR_248" in fidelity
    assert "H121x" in fidelity
    plan = _read("docs/STAGE_121_PLAN.md")
    assert "STAGE_121_FIDELITY.md" in plan
    for ws in ("S1", "W1", "X1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage121_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_121_FIDELITY.md" in br
    assert "Stage 121 D1" in br or "test_stage121_fidelity_d1.py" in br
    assert "Stage 121 S1" in br or "Stage 121 W1" in br or "Stage 121 X1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_121_FIDELITY.md" in fidelity_tail or "Stage 121 D1" in fidelity_tail


def test_stage121_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 121 D1" in api or "STAGE_121_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 121 D1" in deploy or "STAGE_121_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 121 D1" in sec or "STAGE_121_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage121_inactive_stores_s1.py" in launch
    assert "test_stage121_inactive_warehouses_w1.py" in launch
    assert "test_stage121_location_export_x1.py" in launch
    assert "test_stage121_fidelity_d1.py" in launch
    assert "STAGE_121_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Inactive Stores" in manual
        or "Inactive Warehouses" in manual
        or "Export stores CSV" in manual
        or "stores/export" in manual
    )


def test_stage121_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_121_FIDELITY.md" in pr and "test_stage121_fidelity_d1.py" in pr
    assert "Stage 121 D1" in pr and "Stage 121 S1" in pr and "Stage 121 W1" in pr and "Stage 121 X1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_121_FIDELITY.md" in roadmap and "Stage 121 D1" in roadmap
    assert "ADR_248_STAGE121_OPEN.md" in roadmap and "STAGE_121_PLAN.md" in roadmap
