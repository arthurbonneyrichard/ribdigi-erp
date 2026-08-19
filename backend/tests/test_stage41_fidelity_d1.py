"""Stage 41 D1 — documentation fidelity for Commercial Accessibility & Change Governance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage41_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_41_FIDELITY.md")
    assert (
        "Accessibility" in fidelity
        or "Change" in fidelity
        or "Governance" in fidelity
        or "WCAG" in fidelity
        or "maintenance" in fidelity.lower()
    )
    for name in (
        "test_accessibility_statement_a1.py",
        "test_change_governance_c1.py",
        "test_stage41_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-087" in fidelity or "ADR_087" in fidelity
    assert "H41x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "WCAG" in fidelity
        or "change" in fidelity.lower()
    )

    plan = _read("docs/STAGE_41_PLAN.md")
    assert "STAGE_41_FIDELITY.md" in plan
    for ws in ("A1", "C1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h41 = [ln for ln in plan.splitlines() if "| **H41x** |" in ln][0]
    assert "PENDING" in h41 or "COMPLETE" in h41
    assert "ADR-087" in plan or "ADR_087" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H41x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage41_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_41_FIDELITY.md" in br
    assert "Stage 41 D1" in br or "test_stage41_fidelity_d1.py" in br
    assert (
        "Stage 41 A1" in br
        or "ACCESSIBILITY_STATEMENT_MVP.md" in br
        or "Stage 41 C1" in br
        or "CHANGE_GOVERNANCE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_41_FIDELITY.md" in fidelity_tail or "Stage 41 D1" in fidelity_tail

    for rel in (
        "docs/ACCESSIBILITY_STATEMENT_MVP.md",
        "docs/CHANGE_GOVERNANCE_MVP.md",
    ):
        assert _read(rel)


def test_stage41_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 41 D1" in api or "STAGE_41_FIDELITY.md" in api
    assert "test_stage41_fidelity_d1.py" in api or "STAGE_41_FIDELITY.md" in api
    assert (
        "ACCESSIBILITY_STATEMENT_MVP.md" in api
        or "test_accessibility_statement_a1.py" in api
        or "Stage 41 A1" in api
    )
    assert (
        "CHANGE_GOVERNANCE_MVP.md" in api
        or "test_change_governance_c1.py" in api
        or "Stage 41 C1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 41 D1" in deploy or "STAGE_41_FIDELITY.md" in deploy
    assert (
        "ACCESSIBILITY_STATEMENT_MVP.md" in deploy
        or "Stage 41 A1" in deploy
        or "CHANGE_GOVERNANCE_MVP.md" in deploy
        or "Stage 41 C1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 41 D1" in sec or "STAGE_41_FIDELITY.md" in sec
    assert "test_accessibility_statement_a1.py" in sec or "ACCESSIBILITY_STATEMENT_MVP.md" in sec
    assert "test_change_governance_c1.py" in sec or "CHANGE_GOVERNANCE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_accessibility_statement_a1.py" in launch
    assert "test_change_governance_c1.py" in launch
    assert "test_stage41_fidelity_d1.py" in launch
    assert "STAGE_41_FIDELITY.md" in launch
    assert "ADR-087" in launch or "ADR_087" in launch or "STAGE_41_PLAN.md" in launch


def test_stage41_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_41_FIDELITY.md" in pr
    assert "test_stage41_fidelity_d1.py" in pr
    assert "Stage 41 D1" in pr
    assert "Stage 41 A1" in pr
    assert "Stage 41 C1" in pr
    assert (
        "wcag_aa_claimed" in pr
        or "accessibility_audit_claimed" in pr
        or "change_calendar_live" in pr
        or "maintenance_portal_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_41_FIDELITY.md" in roadmap
    assert "Stage 41 D1" in roadmap
    assert "ADR_087_STAGE41_OPEN.md" in roadmap
    assert "STAGE_41_PLAN.md" in roadmap
    assert "test_stage41_fidelity_d1.py" in roadmap
