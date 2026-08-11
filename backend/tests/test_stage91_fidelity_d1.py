"""Stage 91 D1 — documentation fidelity for House Operator Investigation & Evidence Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage91_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_91_FIDELITY.md")
    assert "Investigation" in fidelity or "Evidence" in fidelity
    for name in (
        "test_platform_audit_investigation_i1.py",
        "test_platform_nav_delivery_n1.py",
        "test_house_posture_evidence_p1.py",
        "test_stage91_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-188" in fidelity or "ADR_188" in fidelity
    assert "H91x" in fidelity
    plan = _read("docs/STAGE_91_PLAN.md")
    assert "STAGE_91_FIDELITY.md" in plan
    for ws in ("I1", "N1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h91 = [ln for ln in plan.splitlines() if "| **H91x** |" in ln][0]
    assert "PENDING" in h91 or "COMPLETE" in h91
    assert any(x in plan for x in ("D1 next", "D1 complete", "H91x next", "Closed", "exit met"))


def test_stage91_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_91_FIDELITY.md" in br
    assert "Stage 91 D1" in br or "test_stage91_fidelity_d1.py" in br
    assert "Stage 91 I1" in br or "Stage 91 N1" in br or "Stage 91 P1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_91_FIDELITY.md" in fidelity_tail or "Stage 91 D1" in fidelity_tail


def test_stage91_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 91 D1" in api or "STAGE_91_FIDELITY.md" in api
    assert "test_stage91_fidelity_d1.py" in api or "STAGE_91_FIDELITY.md" in api
    assert "Stage 91 I1" in api or "from_date" in api or "default_recent_days" in api
    assert "Stage 91 N1" in api or "last_house_email_delivery" in api
    assert "Stage 91 P1" in api or "/platform/evidence" in api or "active_session_count" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 91 D1" in deploy or "STAGE_91_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 91 D1" in sec or "STAGE_91_FIDELITY.md" in sec
    assert "test_platform_audit_investigation_i1.py" in sec or "from_date" in sec
    assert "test_house_posture_evidence_p1.py" in sec or "/platform/evidence" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_audit_investigation_i1.py" in launch
    assert "test_platform_nav_delivery_n1.py" in launch
    assert "test_house_posture_evidence_p1.py" in launch
    assert "test_stage91_fidelity_d1.py" in launch
    assert "STAGE_91_FIDELITY.md" in launch
    assert "ADR-188" in launch or "ADR_188" in launch or "STAGE_91_PLAN.md" in launch


def test_stage91_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_91_FIDELITY.md" in pr and "test_stage91_fidelity_d1.py" in pr
    assert "Stage 91 D1" in pr and "Stage 91 I1" in pr and "Stage 91 N1" in pr and "Stage 91 P1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_91_FIDELITY.md" in roadmap and "Stage 91 D1" in roadmap
    assert "ADR_188_STAGE91_OPEN.md" in roadmap and "STAGE_91_PLAN.md" in roadmap
    assert "test_stage91_fidelity_d1.py" in roadmap
