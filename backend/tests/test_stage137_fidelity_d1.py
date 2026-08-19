"""Stage 137 D1 — documentation fidelity for inventory ops CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage137_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_137_FIDELITY.md")
    assert (
        "movement" in fidelity.lower()
        or "low-stock" in fidelity.lower()
        or "expir" in fidelity.lower()
    )
    for name in (
        "test_stage137_movements_export_m1.py",
        "test_stage137_low_stock_l1.py",
        "test_stage137_expiring_batches_e1.py",
        "test_stage137_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-280" in fidelity or "ADR_280" in fidelity
    assert "H137x" in fidelity
    plan = _read("docs/STAGE_137_PLAN.md")
    assert "STAGE_137_FIDELITY.md" in plan
    for ws in ("M1", "L1", "E1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage137_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_137_FIDELITY.md" in br
    assert "Stage 137 D1" in br or "test_stage137_fidelity_d1.py" in br
    assert "Stage 137 M1" in br or "Stage 137 L1" in br or "Stage 137 E1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_137_FIDELITY.md" in fidelity_tail or "Stage 137 D1" in fidelity_tail


def test_stage137_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 137 D1" in api or "STAGE_137_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 137 D1" in deploy or "STAGE_137_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 137 D1" in sec or "STAGE_137_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage137_movements_export_m1.py" in launch
    assert "test_stage137_low_stock_l1.py" in launch
    assert "test_stage137_expiring_batches_e1.py" in launch
    assert "test_stage137_fidelity_d1.py" in launch
    assert "STAGE_137_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "movements/export" in manual
        or "Stock Movements" in manual
        or "low-stock/export" in manual
        or "Low-stock" in manual
        or "expiring/export" in manual
        or "Expiring" in manual
    )


def test_stage137_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_137_FIDELITY.md" in pr and "test_stage137_fidelity_d1.py" in pr
    assert "Stage 137 D1" in pr and "Stage 137 M1" in pr and "Stage 137 L1" in pr and "Stage 137 E1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_137_FIDELITY.md" in roadmap and "Stage 137 D1" in roadmap
    assert "ADR_280_STAGE137_OPEN.md" in roadmap and "STAGE_137_PLAN.md" in roadmap
