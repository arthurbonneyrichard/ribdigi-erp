"""Stage 34 D1 — documentation fidelity for Commercial Customer Assurance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage34_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_34_FIDELITY.md")
    assert (
        "Assurance" in fidelity
        or "Questionnaire" in fidelity
        or "Customer" in fidelity
    )
    assert "test_assurance_evidence_a1.py" in fidelity
    assert "test_compliance_questionnaire_c1.py" in fidelity
    assert "test_stage34_fidelity_d1.py" in fidelity
    assert "ADR-073" in fidelity or "ADR_073" in fidelity
    assert "H34x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "attestation" in fidelity.lower()
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "SOC" in fidelity
    )

    plan = _read("docs/STAGE_34_PLAN.md")
    assert "STAGE_34_FIDELITY.md" in plan
    for ws in ("A1", "C1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    for ws in ("S1", "B1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "DEFERRED" in line or "COMPLETE" in line, ws
    h34 = [ln for ln in plan.splitlines() if "| **H34x** |" in ln][0]
    assert "PENDING" in h34 or "COMPLETE" in h34
    assert "ADR-073" in plan or "ADR_073" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H34x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage34_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_34_FIDELITY.md" in br
    assert "Stage 34 D1" in br or "test_stage34_fidelity_d1.py" in br
    assert (
        "Stage 34 A1" in br
        or "ASSURANCE_EVIDENCE_MVP.md" in br
        or "Stage 34 C1" in br
        or "COMPLIANCE_QUESTIONNAIRE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_34_FIDELITY.md" in fidelity_tail or "Stage 34 D1" in fidelity_tail

    assert _read("docs/ASSURANCE_EVIDENCE_MVP.md")
    assert _read("docs/COMPLIANCE_QUESTIONNAIRE_MVP.md")


def test_stage34_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 34 D1" in api or "STAGE_34_FIDELITY.md" in api
    assert "test_stage34_fidelity_d1.py" in api or "STAGE_34_FIDELITY.md" in api
    assert (
        "ASSURANCE_EVIDENCE_MVP.md" in api
        or "test_assurance_evidence_a1.py" in api
        or "Stage 34 A1" in api
    )
    assert (
        "COMPLIANCE_QUESTIONNAIRE_MVP.md" in api
        or "test_compliance_questionnaire_c1.py" in api
        or "Stage 34 C1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 34 D1" in deploy or "STAGE_34_FIDELITY.md" in deploy
    assert (
        "ASSURANCE_EVIDENCE_MVP.md" in deploy
        or "Stage 34 A1" in deploy
        or "COMPLIANCE_QUESTIONNAIRE_MVP.md" in deploy
        or "Stage 34 C1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 34 D1" in sec or "STAGE_34_FIDELITY.md" in sec
    assert "test_assurance_evidence_a1.py" in sec or "ASSURANCE_EVIDENCE_MVP.md" in sec
    assert "test_compliance_questionnaire_c1.py" in sec or "COMPLIANCE_QUESTIONNAIRE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_assurance_evidence_a1.py" in launch
    assert "test_compliance_questionnaire_c1.py" in launch
    assert "test_stage34_fidelity_d1.py" in launch
    assert "STAGE_34_FIDELITY.md" in launch
    assert "ADR-073" in launch or "ADR_073" in launch or "STAGE_34_PLAN.md" in launch


def test_stage34_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_34_FIDELITY.md" in pr
    assert "test_stage34_fidelity_d1.py" in pr
    assert "Stage 34 D1" in pr
    assert "Stage 34 A1" in pr
    assert "Stage 34 C1" in pr
    assert (
        "go_live_claimed" in pr
        or "§7" in pr
        or "attestation" in pr.lower()
        or "Remaining" in pr
        or "packaging" in pr.lower()
        or "soc2_complete_claimed" in pr
        or "customer_assurance_claimed" in pr
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_34_FIDELITY.md" in roadmap
    assert "Stage 34 D1" in roadmap
    assert "ADR_073_STAGE34_OPEN.md" in roadmap
    assert "STAGE_34_PLAN.md" in roadmap
    assert "test_stage34_fidelity_d1.py" in roadmap
