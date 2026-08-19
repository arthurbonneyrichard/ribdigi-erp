"""Stage 86 D1 — documentation fidelity for House Provision & Platform Access Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage86_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_86_FIDELITY.md")
    assert "Provision" in fidelity or "Platform Access" in fidelity
    for name in (
        "test_platform_tenant_provision_p1.py",
        "test_platform_email_reset_e1.py",
        "test_platform_audit_activity_a1.py",
        "test_stage86_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-178" in fidelity or "ADR_178" in fidelity
    assert "H86x" in fidelity
    plan = _read("docs/STAGE_86_PLAN.md")
    assert "STAGE_86_FIDELITY.md" in plan
    for ws in ("P1", "E1", "A1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h86 = [ln for ln in plan.splitlines() if "| **H86x** |" in ln][0]
    assert "PENDING" in h86 or "COMPLETE" in h86
    assert any(x in plan for x in ("D1 next", "D1 complete", "H86x next", "Closed", "exit met"))


def test_stage86_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_86_FIDELITY.md" in br
    assert "Stage 86 D1" in br or "test_stage86_fidelity_d1.py" in br
    assert "Stage 86 P1" in br or "Stage 86 E1" in br or "Stage 86 A1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_86_FIDELITY.md" in fidelity_tail or "Stage 86 D1" in fidelity_tail


def test_stage86_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 86 D1" in api or "STAGE_86_FIDELITY.md" in api
    assert "test_stage86_fidelity_d1.py" in api or "STAGE_86_FIDELITY.md" in api
    assert "Stage 86 P1" in api or "platform/tenants" in api
    assert "Stage 86 E1" in api or "password-reset-email" in api
    assert "Stage 86 A1" in api or "platform/activity" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 86 D1" in deploy or "STAGE_86_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 86 D1" in sec or "STAGE_86_FIDELITY.md" in sec
    assert "test_platform_tenant_provision_p1.py" in sec or "platform.tenant.create" in sec
    assert "test_platform_email_reset_e1.py" in sec or "password-reset-email" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_tenant_provision_p1.py" in launch
    assert "test_platform_email_reset_e1.py" in launch
    assert "test_platform_audit_activity_a1.py" in launch
    assert "test_stage86_fidelity_d1.py" in launch
    assert "STAGE_86_FIDELITY.md" in launch
    assert "ADR-178" in launch or "ADR_178" in launch or "STAGE_86_PLAN.md" in launch


def test_stage86_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_86_FIDELITY.md" in pr and "test_stage86_fidelity_d1.py" in pr
    assert "Stage 86 D1" in pr and "Stage 86 P1" in pr and "Stage 86 E1" in pr and "Stage 86 A1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_86_FIDELITY.md" in roadmap and "Stage 86 D1" in roadmap
    assert "ADR_178_STAGE86_OPEN.md" in roadmap and "STAGE_86_PLAN.md" in roadmap
    assert "test_stage86_fidelity_d1.py" in roadmap
