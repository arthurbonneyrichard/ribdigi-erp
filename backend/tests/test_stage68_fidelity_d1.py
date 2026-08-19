"""Stage 68 D1 — documentation fidelity for Platform ↔ Tenant Console."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage68_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_68_FIDELITY.md")
    assert (
        "RIBDIGI HOUSE" in fidelity
        or "Ribdigi House" in fidelity
        or "TENANT COMPANY" in fidelity
        or "Tenant Company" in fidelity
    )
    for name in (
        "test_ribdigi_house_console_h1.py",
        "test_tenant_company_console_t1.py",
        "test_stage68_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-142" in fidelity or "ADR_142" in fidelity
    assert "H68x" in fidelity
    assert "ADR-002" in fidelity or "billing" in fidelity.lower()

    plan = _read("docs/STAGE_68_PLAN.md")
    assert "STAGE_68_FIDELITY.md" in plan
    for ws in ("H1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h68 = [ln for ln in plan.splitlines() if "| **H68x** |" in ln][0]
    assert "PENDING" in h68 or "COMPLETE" in h68
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H68x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage68_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_68_FIDELITY.md" in br
    assert "Stage 68 D1" in br or "test_stage68_fidelity_d1.py" in br
    assert (
        "Stage 68 H1" in br
        or "RIBDIGI_HOUSE_CONSOLE_MVP.md" in br
        or "Stage 68 T1" in br
        or "TENANT_COMPANY_CONSOLE_MVP.md" in br
    )
    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_68_FIDELITY.md" in fidelity_tail or "Stage 68 D1" in fidelity_tail
    for rel in ("docs/RIBDIGI_HOUSE_CONSOLE_MVP.md", "docs/TENANT_COMPANY_CONSOLE_MVP.md"):
        assert _read(rel)


def test_stage68_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 68 D1" in api or "STAGE_68_FIDELITY.md" in api
    assert "test_stage68_fidelity_d1.py" in api or "STAGE_68_FIDELITY.md" in api
    assert "Stage 68 H1" in api or "RIBDIGI_HOUSE_CONSOLE_MVP.md" in api
    assert "Stage 68 T1" in api or "TENANT_COMPANY_CONSOLE_MVP.md" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 68 D1" in deploy or "STAGE_68_FIDELITY.md" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 68 D1" in sec or "STAGE_68_FIDELITY.md" in sec
    assert "test_ribdigi_house_console_h1.py" in sec or "RIBDIGI_HOUSE_CONSOLE_MVP.md" in sec
    assert "test_tenant_company_console_t1.py" in sec or "TENANT_COMPANY_CONSOLE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ribdigi_house_console_h1.py" in launch
    assert "test_tenant_company_console_t1.py" in launch
    assert "test_stage68_fidelity_d1.py" in launch
    assert "STAGE_68_FIDELITY.md" in launch
    assert "ADR-142" in launch or "ADR_142" in launch or "STAGE_68_PLAN.md" in launch


def test_stage68_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_68_FIDELITY.md" in pr
    assert "test_stage68_fidelity_d1.py" in pr
    assert "Stage 68 D1" in pr
    assert "Stage 68 H1" in pr
    assert "Stage 68 T1" in pr
    assert (
        "billing_complete_claimed" in pr
        or "tenant_modules_reclaimed_complete" in pr
        or "subscriptions_live_claimed" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_68_FIDELITY.md" in roadmap
    assert "Stage 68 D1" in roadmap
    assert "ADR_142_STAGE68_OPEN.md" in roadmap
    assert "STAGE_68_PLAN.md" in roadmap
    assert "test_stage68_fidelity_d1.py" in roadmap
