"""Stage 100 D1 — documentation fidelity for Reports & Ledger Discovery Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage100_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_100_FIDELITY.md")
    assert "Reports" in fidelity and ("Ledger" in fidelity or "GL" in fidelity)
    for name in (
        "test_stage100_reports_statements_r1.py",
        "test_stage100_gl_leaves_g1.py",
        "test_stage100_tenant_admin_u1.py",
        "test_stage100_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-206" in fidelity or "ADR_206" in fidelity
    assert "H100x" in fidelity
    plan = _read("docs/STAGE_100_PLAN.md")
    assert "STAGE_100_FIDELITY.md" in plan
    for ws in ("R1", "G1", "U1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage100_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_100_FIDELITY.md" in br
    assert "Stage 100 D1" in br or "test_stage100_fidelity_d1.py" in br
    assert "Stage 100 R1" in br or "Stage 100 G1" in br or "Stage 100 U1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_100_FIDELITY.md" in fidelity_tail or "Stage 100 D1" in fidelity_tail


def test_stage100_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 100 D1" in api or "STAGE_100_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 100 D1" in deploy or "STAGE_100_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 100 D1" in sec or "STAGE_100_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage100_reports_statements_r1.py" in launch
    assert "test_stage100_gl_leaves_g1.py" in launch
    assert "test_stage100_tenant_admin_u1.py" in launch
    assert "test_stage100_fidelity_d1.py" in launch
    assert "STAGE_100_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Profit & Loss" in manual
        or "Chart of Accounts" in manual
        or "Trial Balance" in manual
        or "Users" in manual
    )


def test_stage100_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_100_FIDELITY.md" in pr and "test_stage100_fidelity_d1.py" in pr
    assert "Stage 100 D1" in pr and "Stage 100 R1" in pr and "Stage 100 G1" in pr and "Stage 100 U1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_100_FIDELITY.md" in roadmap and "Stage 100 D1" in roadmap
    assert "ADR_206_STAGE100_OPEN.md" in roadmap and "STAGE_100_PLAN.md" in roadmap
