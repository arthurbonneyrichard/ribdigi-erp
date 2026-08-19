"""Stage 138 D1 — documentation fidelity for approval/settings CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage138_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_138_FIDELITY.md")
    assert (
        "early-pay" in fidelity.lower()
        or "early pay" in fidelity.lower()
        or "expense" in fidelity.lower()
        or "purchasing" in fidelity.lower()
    )
    for name in (
        "test_stage138_early_pay_settings_c1.py",
        "test_stage138_expense_settings_e1.py",
        "test_stage138_purchasing_settings_p1.py",
        "test_stage138_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-282" in fidelity or "ADR_282" in fidelity
    assert "H138x" in fidelity
    plan = _read("docs/STAGE_138_PLAN.md")
    assert "STAGE_138_FIDELITY.md" in plan
    for ws in ("C1", "E1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage138_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_138_FIDELITY.md" in br
    assert "Stage 138 D1" in br or "test_stage138_fidelity_d1.py" in br
    assert "Stage 138 C1" in br or "Stage 138 E1" in br or "Stage 138 P1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_138_FIDELITY.md" in fidelity_tail or "Stage 138 D1" in fidelity_tail


def test_stage138_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 138 D1" in api or "STAGE_138_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 138 D1" in deploy or "STAGE_138_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 138 D1" in sec or "STAGE_138_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage138_early_pay_settings_c1.py" in launch
    assert "test_stage138_expense_settings_e1.py" in launch
    assert "test_stage138_purchasing_settings_p1.py" in launch
    assert "test_stage138_fidelity_d1.py" in launch
    assert "STAGE_138_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "settings/export" in manual
        or "Early-pay" in manual
        or "Early pay" in manual
        or "approval settings" in manual.lower()
        or "Approval settings" in manual
    )


def test_stage138_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_138_FIDELITY.md" in pr and "test_stage138_fidelity_d1.py" in pr
    assert "Stage 138 D1" in pr and "Stage 138 C1" in pr and "Stage 138 E1" in pr and "Stage 138 P1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_138_FIDELITY.md" in roadmap and "Stage 138 D1" in roadmap
    assert "ADR_282_STAGE138_OPEN.md" in roadmap and "STAGE_138_PLAN.md" in roadmap
