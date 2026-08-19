"""Stage 80 D1 — documentation fidelity for Dual-Console Dashboard."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage80_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_80_FIDELITY.md")
    assert "Platform" in fidelity and "Dashboard" in fidelity
    for name in (
        "test_platform_dashboard_charts_p1.py",
        "test_tenant_role_dashboard_t1.py",
        "test_stage80_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-166" in fidelity or "ADR_166" in fidelity
    assert "H80x" in fidelity
    plan = _read("docs/STAGE_80_PLAN.md")
    assert "STAGE_80_FIDELITY.md" in plan
    for ws in ("P1", "T1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h80 = [ln for ln in plan.splitlines() if "| **H80x** |" in ln][0]
    assert "PENDING" in h80 or "COMPLETE" in h80
    assert any(x in plan for x in ("D1 next", "D1 complete", "H80x next", "Closed", "exit met"))


def test_stage80_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_80_FIDELITY.md" in br
    assert "Stage 80 D1" in br or "test_stage80_fidelity_d1.py" in br
    assert (
        "Stage 80 P1" in br
        or "platform/dashboard" in br
        or "Stage 80 T1" in br
        or "dashboard_views" in br
    )
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_80_FIDELITY.md" in fidelity_tail or "Stage 80 D1" in fidelity_tail


def test_stage80_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 80 D1" in api or "STAGE_80_FIDELITY.md" in api
    assert "test_stage80_fidelity_d1.py" in api or "STAGE_80_FIDELITY.md" in api
    assert "Stage 80 P1" in api or "platform/dashboard" in api
    assert "Stage 80 T1" in api or "dashboard_views" in api or "role-scoped" in api.lower()
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 80 D1" in deploy or "STAGE_80_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 80 D1" in sec or "STAGE_80_FIDELITY.md" in sec
    assert "test_platform_dashboard_charts_p1.py" in sec or "platform/dashboard" in sec
    assert "test_tenant_role_dashboard_t1.py" in sec or "role-scoped" in sec.lower()
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_platform_dashboard_charts_p1.py" in launch
    assert "test_tenant_role_dashboard_t1.py" in launch
    assert "test_stage80_fidelity_d1.py" in launch
    assert "STAGE_80_FIDELITY.md" in launch
    assert "ADR-166" in launch or "ADR_166" in launch or "STAGE_80_PLAN.md" in launch


def test_stage80_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_80_FIDELITY.md" in pr and "test_stage80_fidelity_d1.py" in pr
    assert "Stage 80 D1" in pr and "Stage 80 P1" in pr and "Stage 80 T1" in pr
    assert (
        "mrr_fabricated_claimed" in pr
        or "billing_complete_claimed" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
        or "deferred" in pr.lower()
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_80_FIDELITY.md" in roadmap and "Stage 80 D1" in roadmap
    assert "ADR_166_STAGE80_OPEN.md" in roadmap and "STAGE_80_PLAN.md" in roadmap
    assert "test_stage80_fidelity_d1.py" in roadmap
