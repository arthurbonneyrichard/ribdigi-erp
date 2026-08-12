"""Stage 110 D1 — documentation fidelity for Purchasing Status Leaves, Expense Decision Queue & Admin Audit Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage110_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_110_FIDELITY.md")
    assert "Purchasing" in fidelity or "Expense" in fidelity or "Audit" in fidelity
    for name in (
        "test_stage110_purchasing_status_p1.py",
        "test_stage110_expense_queue_e1.py",
        "test_stage110_admin_audit_a1.py",
        "test_stage110_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-226" in fidelity or "ADR_226" in fidelity
    assert "H110x" in fidelity
    plan = _read("docs/STAGE_110_PLAN.md")
    assert "STAGE_110_FIDELITY.md" in plan
    for ws in ("P1", "E1", "A1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage110_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_110_FIDELITY.md" in br
    assert "Stage 110 D1" in br or "test_stage110_fidelity_d1.py" in br
    assert "Stage 110 P1" in br or "Stage 110 E1" in br or "Stage 110 A1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_110_FIDELITY.md" in fidelity_tail or "Stage 110 D1" in fidelity_tail


def test_stage110_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 110 D1" in api or "STAGE_110_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 110 D1" in deploy or "STAGE_110_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 110 D1" in sec or "STAGE_110_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage110_purchasing_status_p1.py" in launch
    assert "test_stage110_expense_queue_e1.py" in launch
    assert "test_stage110_admin_audit_a1.py" in launch
    assert "test_stage110_fidelity_d1.py" in launch
    assert "STAGE_110_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Draft GRN" in manual
        or "Approved Expenses" in manual
        or "Create Role" in manual
        or "Auth Audit" in manual
        or "Draft Purchases" in manual
    )


def test_stage110_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_110_FIDELITY.md" in pr and "test_stage110_fidelity_d1.py" in pr
    assert "Stage 110 D1" in pr and "Stage 110 P1" in pr and "Stage 110 E1" in pr and "Stage 110 A1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_110_FIDELITY.md" in roadmap and "Stage 110 D1" in roadmap
    assert "ADR_226_STAGE110_OPEN.md" in roadmap and "STAGE_110_PLAN.md" in roadmap
