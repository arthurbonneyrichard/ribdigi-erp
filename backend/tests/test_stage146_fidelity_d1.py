"""Stage 146 D1 — documentation fidelity for inventory AI prediction CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage146_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_146_FIDELITY.md")
    assert (
        "low-stock" in fidelity.lower()
        or "forecast" in fidelity.lower()
        or "dead" in fidelity.lower()
    )
    for name in (
        "test_stage146_low_stock_l1.py",
        "test_stage146_demand_forecast_f1.py",
        "test_stage146_dead_stock_k1.py",
        "test_stage146_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-298" in fidelity or "ADR_298" in fidelity
    assert "H146x" in fidelity
    plan = _read("docs/STAGE_146_PLAN.md")
    assert "STAGE_146_FIDELITY.md" in plan
    for ws in ("L1", "F1", "K1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage146_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_146_FIDELITY.md" in br
    assert "Stage 146 D1" in br or "test_stage146_fidelity_d1.py" in br
    assert "Stage 146 L1" in br or "Stage 146 F1" in br or "Stage 146 K1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_146_FIDELITY.md" in fidelity_tail or "Stage 146 D1" in fidelity_tail


def test_stage146_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 146 D1" in api or "STAGE_146_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 146 D1" in deploy or "STAGE_146_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 146 D1" in sec or "STAGE_146_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage146_low_stock_l1.py" in launch
    assert "test_stage146_demand_forecast_f1.py" in launch
    assert "test_stage146_dead_stock_k1.py" in launch
    assert "test_stage146_fidelity_d1.py" in launch
    assert "STAGE_146_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "low-stock-prediction/export" in manual
        or "Low-Stock" in manual
        or "demand-forecast/export" in manual
        or "Forecast" in manual
        or "dead-stock/export" in manual
        or "Dead-Stock" in manual
    )


def test_stage146_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_146_FIDELITY.md" in pr and "test_stage146_fidelity_d1.py" in pr
    assert "Stage 146 D1" in pr and "Stage 146 L1" in pr and "Stage 146 F1" in pr and "Stage 146 K1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_146_FIDELITY.md" in roadmap and "Stage 146 D1" in roadmap
    assert "ADR_298_STAGE146_OPEN.md" in roadmap and "STAGE_146_PLAN.md" in roadmap
