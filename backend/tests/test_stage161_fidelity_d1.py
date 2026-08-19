"""Stage 161 D1 — documentation fidelity for reports P&L / TB / tax path CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage161_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_161_FIDELITY.md")
    assert (
        "profit-loss" in fidelity.lower()
        or "trial-balance" in fidelity.lower()
        or "tax" in fidelity.lower()
    )
    for name in (
        "test_stage161_profit_loss_l1.py",
        "test_stage161_trial_balance_b1.py",
        "test_stage161_tax_x1.py",
        "test_stage161_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-328" in fidelity or "ADR_328" in fidelity
    assert "H161x" in fidelity
    plan = _read("docs/STAGE_161_PLAN.md")
    assert "STAGE_161_FIDELITY.md" in plan
    for ws in ("L1", "B1", "X1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage161_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_161_FIDELITY.md" in br
    assert "Stage 161 D1" in br or "test_stage161_fidelity_d1.py" in br
    assert "Stage 161 L1" in br or "Stage 161 B1" in br or "Stage 161 X1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_161_FIDELITY.md" in fidelity_tail or "Stage 161 D1" in fidelity_tail


def test_stage161_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 161 D1" in api or "STAGE_161_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 161 D1" in deploy or "STAGE_161_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 161 D1" in sec or "STAGE_161_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage161_profit_loss_l1.py" in launch
    assert "test_stage161_trial_balance_b1.py" in launch
    assert "test_stage161_tax_x1.py" in launch
    assert "test_stage161_fidelity_d1.py" in launch
    assert "STAGE_161_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "profit-loss/export" in manual
        or "Profit-Loss" in manual
        or "trial-balance/export" in manual
        or "Trial-Balance" in manual
        or "tax/export" in manual
        or "Tax Path" in manual
    )


def test_stage161_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_161_FIDELITY.md" in pr and "test_stage161_fidelity_d1.py" in pr
    assert "Stage 161 D1" in pr and "Stage 161 L1" in pr and "Stage 161 B1" in pr and "Stage 161 X1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_161_FIDELITY.md" in roadmap and "Stage 161 D1" in roadmap
    assert "ADR_328_STAGE161_OPEN.md" in roadmap and "STAGE_161_PLAN.md" in roadmap
