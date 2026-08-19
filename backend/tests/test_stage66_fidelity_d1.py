"""Stage 66 D1 — documentation fidelity for MVP Production Launch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage66_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_66_FIDELITY.md")
    assert (
        "Production Launch" in fidelity
        or "production launch" in fidelity.lower()
        or "First Paying Tenant" in fidelity
        or "Go-Live" in fidelity
        or "cutover" in fidelity.lower()
    )
    for name in (
        "test_production_launch_l1.py",
        "test_first_tenant_golive_t1.py",
        "test_stage66_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-138" in fidelity or "ADR_138" in fidelity
    assert "H66x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "cutover" in fidelity.lower()
        or "tenant" in fidelity.lower()
    )

    plan = _read("docs/STAGE_66_PLAN.md")
    assert "STAGE_66_FIDELITY.md" in plan
    for ws in ("L1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h66 = [ln for ln in plan.splitlines() if "| **H66x** |" in ln][0]
    assert "PENDING" in h66 or "COMPLETE" in h66
    assert "ADR-138" in plan or "ADR_138" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H66x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage66_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_66_FIDELITY.md" in br
    assert "Stage 66 D1" in br or "test_stage66_fidelity_d1.py" in br
    assert (
        "Stage 66 L1" in br
        or "PRODUCTION_LAUNCH_MVP.md" in br
        or "Stage 66 T1" in br
        or "FIRST_TENANT_GOLIVE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_66_FIDELITY.md" in fidelity_tail or "Stage 66 D1" in fidelity_tail

    for rel in (
        "docs/PRODUCTION_LAUNCH_MVP.md",
        "docs/FIRST_TENANT_GOLIVE_MVP.md",
    ):
        assert _read(rel)


def test_stage66_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 66 D1" in api or "STAGE_66_FIDELITY.md" in api
    assert "test_stage66_fidelity_d1.py" in api or "STAGE_66_FIDELITY.md" in api
    assert (
        "PRODUCTION_LAUNCH_MVP.md" in api
        or "test_production_launch_l1.py" in api
        or "Stage 66 L1" in api
    )
    assert (
        "FIRST_TENANT_GOLIVE_MVP.md" in api
        or "test_first_tenant_golive_t1.py" in api
        or "Stage 66 T1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 66 D1" in deploy or "STAGE_66_FIDELITY.md" in deploy
    assert (
        "PRODUCTION_LAUNCH_MVP.md" in deploy
        or "Stage 66 L1" in deploy
        or "FIRST_TENANT_GOLIVE_MVP.md" in deploy
        or "Stage 66 T1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 66 D1" in sec or "STAGE_66_FIDELITY.md" in sec
    assert "test_production_launch_l1.py" in sec or "PRODUCTION_LAUNCH_MVP.md" in sec
    assert "test_first_tenant_golive_t1.py" in sec or "FIRST_TENANT_GOLIVE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_production_launch_l1.py" in launch
    assert "test_first_tenant_golive_t1.py" in launch
    assert "test_stage66_fidelity_d1.py" in launch
    assert "STAGE_66_FIDELITY.md" in launch
    assert "ADR-138" in launch or "ADR_138" in launch or "STAGE_66_PLAN.md" in launch


def test_stage66_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_66_FIDELITY.md" in pr
    assert "test_stage66_fidelity_d1.py" in pr
    assert "Stage 66 D1" in pr
    assert "Stage 66 L1" in pr
    assert "Stage 66 T1" in pr
    assert (
        "go_live_claimed" in pr
        or "section_7_signed" in pr
        or "production_cutover_claimed" in pr
        or "first_paying_tenant_claimed" in pr
        or "live_onboarding_success_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_66_FIDELITY.md" in roadmap
    assert "Stage 66 D1" in roadmap
    assert "ADR_138_STAGE66_OPEN.md" in roadmap
    assert "STAGE_66_PLAN.md" in roadmap
    assert "test_stage66_fidelity_d1.py" in roadmap
