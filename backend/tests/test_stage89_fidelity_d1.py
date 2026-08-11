"""Stage 89 D1 — documentation fidelity for House Customer Assist & Roster Intelligence Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage89_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_89_FIDELITY.md")
    assert "Assist" in fidelity or "Roster Intelligence" in fidelity
    for name in (
        "test_platform_tenant_admin_assist_a1.py",
        "test_platform_roster_intel_f1.py",
        "test_platform_catalog_billing_c1.py",
        "test_stage89_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-184" in fidelity or "ADR_184" in fidelity
    assert "H89x" in fidelity
    plan = _read("docs/STAGE_89_PLAN.md")
    assert "STAGE_89_FIDELITY.md" in plan
    for ws in ("A1", "F1", "C1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h89 = [ln for ln in plan.splitlines() if "| **H89x** |" in ln][0]
    assert "PENDING" in h89 or "COMPLETE" in h89
    assert any(x in plan for x in ("D1 next", "D1 complete", "H89x next", "Closed", "exit met"))


def test_stage89_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_89_FIDELITY.md" in br
    assert "Stage 89 D1" in br or "test_stage89_fidelity_d1.py" in br
    assert "Stage 89 A1" in br or "Stage 89 F1" in br or "Stage 89 C1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_89_FIDELITY.md" in fidelity_tail or "Stage 89 D1" in fidelity_tail


def test_stage89_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 89 D1" in api or "STAGE_89_FIDELITY.md" in api
    assert "test_stage89_fidelity_d1.py" in api or "STAGE_89_FIDELITY.md" in api
    assert "Stage 89 A1" in api or "admin/password-reset-email" in api
    assert "Stage 89 F1" in api or "plan_code" in api or "at_risk_count" in api
    assert "Stage 89 C1" in api or "catalog" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 89 D1" in deploy or "STAGE_89_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 89 D1" in sec or "STAGE_89_FIDELITY.md" in sec
    assert "test_platform_tenant_admin_assist_a1.py" in sec or "admin/password-reset" in sec
    assert "test_platform_roster_intel_f1.py" in sec or "at_risk" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_tenant_admin_assist_a1.py" in launch
    assert "test_platform_roster_intel_f1.py" in launch
    assert "test_platform_catalog_billing_c1.py" in launch
    assert "test_stage89_fidelity_d1.py" in launch
    assert "STAGE_89_FIDELITY.md" in launch
    assert "ADR-184" in launch or "ADR_184" in launch or "STAGE_89_PLAN.md" in launch


def test_stage89_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_89_FIDELITY.md" in pr and "test_stage89_fidelity_d1.py" in pr
    assert "Stage 89 D1" in pr and "Stage 89 A1" in pr and "Stage 89 F1" in pr and "Stage 89 C1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_89_FIDELITY.md" in roadmap and "Stage 89 D1" in roadmap
    assert "ADR_184_STAGE89_OPEN.md" in roadmap and "STAGE_89_PLAN.md" in roadmap
    assert "test_stage89_fidelity_d1.py" in roadmap
