"""Stage 47 D1 — documentation fidelity for Commercial Insurance & Audit."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage47_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_47_FIDELITY.md")
    assert (
        "Insurance" in fidelity
        or "Audit" in fidelity
        or "COI" in fidelity
        or "cyber" in fidelity.lower()
    )
    for name in (
        "test_cyber_insurance_i1.py",
        "test_customer_audit_rights_a1.py",
        "test_stage47_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-099" in fidelity or "ADR_099" in fidelity
    assert "H47x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "insurance" in fidelity.lower()
        or "audit" in fidelity.lower()
    )

    plan = _read("docs/STAGE_47_PLAN.md")
    assert "STAGE_47_FIDELITY.md" in plan
    for ws in ("I1", "A1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h47 = [ln for ln in plan.splitlines() if "| **H47x** |" in ln][0]
    assert "PENDING" in h47 or "COMPLETE" in h47
    assert "ADR-099" in plan or "ADR_099" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H47x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage47_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_47_FIDELITY.md" in br
    assert "Stage 47 D1" in br or "test_stage47_fidelity_d1.py" in br
    assert (
        "Stage 47 I1" in br
        or "CYBER_INSURANCE_MVP.md" in br
        or "Stage 47 A1" in br
        or "CUSTOMER_AUDIT_RIGHTS_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_47_FIDELITY.md" in fidelity_tail or "Stage 47 D1" in fidelity_tail

    for rel in (
        "docs/CYBER_INSURANCE_MVP.md",
        "docs/CUSTOMER_AUDIT_RIGHTS_MVP.md",
    ):
        assert _read(rel)


def test_stage47_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 47 D1" in api or "STAGE_47_FIDELITY.md" in api
    assert "test_stage47_fidelity_d1.py" in api or "STAGE_47_FIDELITY.md" in api
    assert (
        "CYBER_INSURANCE_MVP.md" in api
        or "test_cyber_insurance_i1.py" in api
        or "Stage 47 I1" in api
    )
    assert (
        "CUSTOMER_AUDIT_RIGHTS_MVP.md" in api
        or "test_customer_audit_rights_a1.py" in api
        or "Stage 47 A1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 47 D1" in deploy or "STAGE_47_FIDELITY.md" in deploy
    assert (
        "CYBER_INSURANCE_MVP.md" in deploy
        or "Stage 47 I1" in deploy
        or "CUSTOMER_AUDIT_RIGHTS_MVP.md" in deploy
        or "Stage 47 A1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 47 D1" in sec or "STAGE_47_FIDELITY.md" in sec
    assert "test_cyber_insurance_i1.py" in sec or "CYBER_INSURANCE_MVP.md" in sec
    assert "test_customer_audit_rights_a1.py" in sec or "CUSTOMER_AUDIT_RIGHTS_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_cyber_insurance_i1.py" in launch
    assert "test_customer_audit_rights_a1.py" in launch
    assert "test_stage47_fidelity_d1.py" in launch
    assert "STAGE_47_FIDELITY.md" in launch
    assert "ADR-099" in launch or "ADR_099" in launch or "STAGE_47_PLAN.md" in launch


def test_stage47_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_47_FIDELITY.md" in pr
    assert "test_stage47_fidelity_d1.py" in pr
    assert "Stage 47 D1" in pr
    assert "Stage 47 I1" in pr
    assert "Stage 47 A1" in pr
    assert (
        "insurance_certificate_claimed" in pr
        or "customer_audit_rights_live" in pr
        or "coi_issued_claimed" in pr
        or "audit_executed_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_47_FIDELITY.md" in roadmap
    assert "Stage 47 D1" in roadmap
    assert "ADR_099_STAGE47_OPEN.md" in roadmap
    assert "STAGE_47_PLAN.md" in roadmap
    assert "test_stage47_fidelity_d1.py" in roadmap
