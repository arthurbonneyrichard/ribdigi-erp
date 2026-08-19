"""Stage 160 D1 — documentation fidelity for profit-loss / cash-flow / balance-sheet path CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage160_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_160_FIDELITY.md")
    assert (
        "profit-loss" in fidelity.lower()
        or "cash-flow" in fidelity.lower()
        or "balance-sheet" in fidelity.lower()
    )
    for name in (
        "test_stage160_profit_loss_p1.py",
        "test_stage160_cash_flow_c1.py",
        "test_stage160_balance_sheet_s1.py",
        "test_stage160_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-326" in fidelity or "ADR_326" in fidelity
    assert "H160x" in fidelity
    plan = _read("docs/STAGE_160_PLAN.md")
    assert "STAGE_160_FIDELITY.md" in plan
    for ws in ("P1", "C1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage160_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_160_FIDELITY.md" in br
    assert "Stage 160 D1" in br or "test_stage160_fidelity_d1.py" in br
    assert "Stage 160 P1" in br or "Stage 160 C1" in br or "Stage 160 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_160_FIDELITY.md" in fidelity_tail or "Stage 160 D1" in fidelity_tail


def test_stage160_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 160 D1" in api or "STAGE_160_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 160 D1" in deploy or "STAGE_160_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 160 D1" in sec or "STAGE_160_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage160_profit_loss_p1.py" in launch
    assert "test_stage160_cash_flow_c1.py" in launch
    assert "test_stage160_balance_sheet_s1.py" in launch
    assert "test_stage160_fidelity_d1.py" in launch
    assert "STAGE_160_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "profit-loss/export" in manual
        or "Profit-Loss" in manual
        or "cash-flow/export" in manual
        or "Cash-Flow" in manual
        or "balance-sheet/export" in manual
        or "Balance-Sheet" in manual
    )


def test_stage160_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_160_FIDELITY.md" in pr and "test_stage160_fidelity_d1.py" in pr
    assert "Stage 160 D1" in pr and "Stage 160 P1" in pr and "Stage 160 C1" in pr and "Stage 160 S1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_160_FIDELITY.md" in roadmap and "Stage 160 D1" in roadmap
    assert "ADR_326_STAGE160_OPEN.md" in roadmap and "STAGE_160_PLAN.md" in roadmap
