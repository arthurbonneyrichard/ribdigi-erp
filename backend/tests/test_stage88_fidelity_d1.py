"""Stage 88 D1 — documentation fidelity for House Lifecycle & Staff Security Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage88_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_88_FIDELITY.md")
    assert "Lifecycle" in fidelity or "Staff Security" in fidelity
    for name in (
        "test_platform_tenant_lifecycle_l1.py",
        "test_platform_tenant_roster_r1.py",
        "test_platform_staff_security_s1.py",
        "test_stage88_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-182" in fidelity or "ADR_182" in fidelity
    assert "H88x" in fidelity
    plan = _read("docs/STAGE_88_PLAN.md")
    assert "STAGE_88_FIDELITY.md" in plan
    for ws in ("L1", "R1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h88 = [ln for ln in plan.splitlines() if "| **H88x** |" in ln][0]
    assert "PENDING" in h88 or "COMPLETE" in h88
    assert any(x in plan for x in ("D1 next", "D1 complete", "H88x next", "Closed", "exit met"))


def test_stage88_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_88_FIDELITY.md" in br
    assert "Stage 88 D1" in br or "test_stage88_fidelity_d1.py" in br
    assert "Stage 88 L1" in br or "Stage 88 R1" in br or "Stage 88 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_88_FIDELITY.md" in fidelity_tail or "Stage 88 D1" in fidelity_tail


def test_stage88_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 88 D1" in api or "STAGE_88_FIDELITY.md" in api
    assert "test_stage88_fidelity_d1.py" in api or "STAGE_88_FIDELITY.md" in api
    assert "Stage 88 L1" in api or "lifecycle" in api
    assert "Stage 88 R1" in api or "tenants/export" in api or "at-risk" in api
    assert "Stage 88 S1" in api or "users/sessions" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 88 D1" in deploy or "STAGE_88_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 88 D1" in sec or "STAGE_88_FIDELITY.md" in sec
    assert "test_platform_tenant_lifecycle_l1.py" in sec or "lifecycle" in sec
    assert "test_platform_staff_security_s1.py" in sec or "users/sessions" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_tenant_lifecycle_l1.py" in launch
    assert "test_platform_tenant_roster_r1.py" in launch
    assert "test_platform_staff_security_s1.py" in launch
    assert "test_stage88_fidelity_d1.py" in launch
    assert "STAGE_88_FIDELITY.md" in launch
    assert "ADR-182" in launch or "ADR_182" in launch or "STAGE_88_PLAN.md" in launch


def test_stage88_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_88_FIDELITY.md" in pr and "test_stage88_fidelity_d1.py" in pr
    assert "Stage 88 D1" in pr and "Stage 88 L1" in pr and "Stage 88 R1" in pr and "Stage 88 S1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_88_FIDELITY.md" in roadmap and "Stage 88 D1" in roadmap
    assert "ADR_182_STAGE88_OPEN.md" in roadmap and "STAGE_88_PLAN.md" in roadmap
    assert "test_stage88_fidelity_d1.py" in roadmap
