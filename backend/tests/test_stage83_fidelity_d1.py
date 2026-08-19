"""Stage 83 D1 — documentation fidelity for Dual-Console Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage83_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_83_FIDELITY.md")
    assert "Chart" in fidelity or "User" in fidelity or "Ops" in fidelity
    for name in (
        "test_store_scoped_charts_s1.py",
        "test_admin_user_ops_u1.py",
        "test_stage83_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-172" in fidelity or "ADR_172" in fidelity
    assert "H83x" in fidelity
    plan = _read("docs/STAGE_83_PLAN.md")
    assert "STAGE_83_FIDELITY.md" in plan
    for ws in ("S1", "U1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h83 = [ln for ln in plan.splitlines() if "| **H83x** |" in ln][0]
    assert "PENDING" in h83 or "COMPLETE" in h83
    assert any(x in plan for x in ("D1 next", "D1 complete", "H83x next", "Closed", "exit met"))


def test_stage83_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_83_FIDELITY.md" in br
    assert "Stage 83 D1" in br or "test_stage83_fidelity_d1.py" in br
    assert "Stage 83 S1" in br or "Stage 83 U1" in br or "store_ids" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_83_FIDELITY.md" in fidelity_tail or "Stage 83 D1" in fidelity_tail


def test_stage83_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 83 D1" in api or "STAGE_83_FIDELITY.md" in api
    assert "test_stage83_fidelity_d1.py" in api or "STAGE_83_FIDELITY.md" in api
    assert "Stage 83 S1" in api or "store_ids" in api or "sales-trend" in api
    assert "Stage 83 U1" in api or "password" in api.lower()
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 83 D1" in deploy or "STAGE_83_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 83 D1" in sec or "STAGE_83_FIDELITY.md" in sec
    assert "test_store_scoped_charts_s1.py" in sec or "store_ids" in sec
    assert "test_admin_user_ops_u1.py" in sec or "Reset password" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_store_scoped_charts_s1.py" in launch
    assert "test_admin_user_ops_u1.py" in launch
    assert "test_stage83_fidelity_d1.py" in launch
    assert "STAGE_83_FIDELITY.md" in launch
    assert "ADR-172" in launch or "ADR_172" in launch or "STAGE_83_PLAN.md" in launch


def test_stage83_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_83_FIDELITY.md" in pr and "test_stage83_fidelity_d1.py" in pr
    assert "Stage 83 D1" in pr and "Stage 83 S1" in pr and "Stage 83 U1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_83_FIDELITY.md" in roadmap and "Stage 83 D1" in roadmap
    assert "ADR_172_STAGE83_OPEN.md" in roadmap and "STAGE_83_PLAN.md" in roadmap
    assert "test_stage83_fidelity_d1.py" in roadmap
