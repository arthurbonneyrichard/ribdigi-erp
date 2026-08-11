"""Stage 87 D1 — documentation fidelity for House Integrity & Console Boundary Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage87_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_87_FIDELITY.md")
    assert "Integrity" in fidelity or "Console Boundary" in fidelity
    for name in (
        "test_platform_audit_integrity_x1.py",
        "test_house_ops_surface_y1.py",
        "test_console_boundary_z1.py",
        "test_stage87_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-180" in fidelity or "ADR_180" in fidelity
    assert "H87x" in fidelity
    plan = _read("docs/STAGE_87_PLAN.md")
    assert "STAGE_87_FIDELITY.md" in plan
    for ws in ("X1", "Y1", "Z1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h87 = [ln for ln in plan.splitlines() if "| **H87x** |" in ln][0]
    assert "PENDING" in h87 or "COMPLETE" in h87
    assert any(x in plan for x in ("D1 next", "D1 complete", "H87x next", "Closed", "exit met"))


def test_stage87_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_87_FIDELITY.md" in br
    assert "Stage 87 D1" in br or "test_stage87_fidelity_d1.py" in br
    assert "Stage 87 X1" in br or "Stage 87 Y1" in br or "Stage 87 Z1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_87_FIDELITY.md" in fidelity_tail or "Stage 87 D1" in fidelity_tail


def test_stage87_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 87 D1" in api or "STAGE_87_FIDELITY.md" in api
    assert "test_stage87_fidelity_d1.py" in api or "STAGE_87_FIDELITY.md" in api
    assert "Stage 87 X1" in api or "platform/audit/export" in api
    assert "Stage 87 Y1" in api or "platform_notes" in api or "tenants" in api
    assert "Stage 87 Z1" in api or "ribdigi_principal" in api or "middleware" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 87 D1" in deploy or "STAGE_87_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 87 D1" in sec or "STAGE_87_FIDELITY.md" in sec
    assert "test_platform_audit_integrity_x1.py" in sec or "audit/export" in sec
    assert "test_console_boundary_z1.py" in sec or "ribdigi_principal" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_audit_integrity_x1.py" in launch
    assert "test_house_ops_surface_y1.py" in launch
    assert "test_console_boundary_z1.py" in launch
    assert "test_stage87_fidelity_d1.py" in launch
    assert "STAGE_87_FIDELITY.md" in launch
    assert "ADR-180" in launch or "ADR_180" in launch or "STAGE_87_PLAN.md" in launch


def test_stage87_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_87_FIDELITY.md" in pr and "test_stage87_fidelity_d1.py" in pr
    assert "Stage 87 D1" in pr and "Stage 87 X1" in pr and "Stage 87 Y1" in pr and "Stage 87 Z1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_87_FIDELITY.md" in roadmap and "Stage 87 D1" in roadmap
    assert "ADR_180_STAGE87_OPEN.md" in roadmap and "STAGE_87_PLAN.md" in roadmap
    assert "test_stage87_fidelity_d1.py" in roadmap
