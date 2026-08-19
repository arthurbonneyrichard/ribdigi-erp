"""Stage 90 D1 — documentation fidelity for House Operator Visibility & Delivery Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage90_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_90_FIDELITY.md")
    assert "Visibility" in fidelity or "Delivery" in fidelity
    for name in (
        "test_platform_email_delivery_visibility_e1.py",
        "test_house_operator_surfaces_o1.py",
        "test_platform_roster_findability_q1.py",
        "test_stage90_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-186" in fidelity or "ADR_186" in fidelity
    assert "H90x" in fidelity
    plan = _read("docs/STAGE_90_PLAN.md")
    assert "STAGE_90_FIDELITY.md" in plan
    for ws in ("E1", "O1", "Q1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h90 = [ln for ln in plan.splitlines() if "| **H90x** |" in ln][0]
    assert "PENDING" in h90 or "COMPLETE" in h90
    assert any(x in plan for x in ("D1 next", "D1 complete", "H90x next", "Closed", "exit met"))


def test_stage90_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_90_FIDELITY.md" in br
    assert "Stage 90 D1" in br or "test_stage90_fidelity_d1.py" in br
    assert "Stage 90 E1" in br or "Stage 90 O1" in br or "Stage 90 Q1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_90_FIDELITY.md" in fidelity_tail or "Stage 90 D1" in fidelity_tail


def test_stage90_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 90 D1" in api or "STAGE_90_FIDELITY.md" in api
    assert "test_stage90_fidelity_d1.py" in api or "STAGE_90_FIDELITY.md" in api
    assert "Stage 90 E1" in api or "platform.email.delivery" in api or "delivery_only" in api
    assert "Stage 90 O1" in api or "operator_contacts" in api
    assert "Stage 90 Q1" in api or "admin email" in api or "findability" in api.lower()
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 90 D1" in deploy or "STAGE_90_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 90 D1" in sec or "STAGE_90_FIDELITY.md" in sec
    assert "test_platform_email_delivery_visibility_e1.py" in sec or "platform.email.delivery" in sec
    assert "test_house_operator_surfaces_o1.py" in sec or "rate_limit" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_email_delivery_visibility_e1.py" in launch
    assert "test_house_operator_surfaces_o1.py" in launch
    assert "test_platform_roster_findability_q1.py" in launch
    assert "test_stage90_fidelity_d1.py" in launch
    assert "STAGE_90_FIDELITY.md" in launch
    assert "ADR-186" in launch or "ADR_186" in launch or "STAGE_90_PLAN.md" in launch


def test_stage90_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_90_FIDELITY.md" in pr and "test_stage90_fidelity_d1.py" in pr
    assert "Stage 90 D1" in pr and "Stage 90 E1" in pr and "Stage 90 O1" in pr and "Stage 90 Q1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_90_FIDELITY.md" in roadmap and "Stage 90 D1" in roadmap
    assert "ADR_186_STAGE90_OPEN.md" in roadmap and "STAGE_90_PLAN.md" in roadmap
    assert "test_stage90_fidelity_d1.py" in roadmap
