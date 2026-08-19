"""Stage 30 D1 — documentation fidelity for Go-Live Support."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage30_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_30_FIDELITY.md")
    assert "Go-Live" in fidelity or "Evidence" in fidelity or "Attestation" in fidelity
    assert "test_evidence_ledger_l1.py" in fidelity
    assert "test_incident_pack_i1.py" in fidelity
    assert "test_support_runbook_s1.py" in fidelity
    assert "test_attestation_pack_a1.py" in fidelity
    assert "test_stage30_fidelity_d1.py" in fidelity
    assert "ADR-065" in fidelity or "ADR_065" in fidelity
    assert "H30x" in fidelity
    assert (
        "attestation" in fidelity.lower()
        or "§7" in fidelity
        or "PagerDuty" in fidelity
        or "execution" in fidelity.lower()
        or "Remaining" in fidelity
    )
    assert "ADMIN_MANUAL" in fidelity or "admin" in fidelity.lower()

    plan = _read("docs/STAGE_30_PLAN.md")
    assert "STAGE_30_FIDELITY.md" in plan
    for ws in ("L1", "I1", "S1", "A1", "D1", "H30x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-066" in plan or "ADR_066" in plan
    assert "Closed" in plan or "exit met" in plan.lower()
    assert "ADR-066" in fidelity or "ADR_066" in fidelity or "exit met" in fidelity.lower()


def test_stage30_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_30_FIDELITY.md" in br
    assert "Stage 30 D1" in br or "test_stage30_fidelity_d1.py" in br
    assert (
        "Stage 30 L1" in br
        or "EVIDENCE_LEDGER_MVP.md" in br
        or "Stage 30 A1" in br
        or "ATTESTATION_PACK_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_30_FIDELITY.md" in fidelity_tail or "Stage 30 D1" in fidelity_tail

    assert _read("docs/EVIDENCE_LEDGER_MVP.md")
    assert _read("docs/INCIDENT_PACK_MVP.md")
    assert _read("docs/SUPPORT_RUNBOOK_MVP.md")
    assert _read("docs/ATTESTATION_PACK_MVP.md")


def test_stage30_api_deploy_security_launch_admin():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 30 D1" in api or "STAGE_30_FIDELITY.md" in api
    assert "test_stage30_fidelity_d1.py" in api or "STAGE_30_FIDELITY.md" in api
    assert (
        "EVIDENCE_LEDGER_MVP.md" in api
        or "test_evidence_ledger_l1.py" in api
        or "Stage 30 L1" in api
    )
    assert (
        "INCIDENT_PACK_MVP.md" in api
        or "test_incident_pack_i1.py" in api
        or "Stage 30 I1" in api
    )
    assert (
        "SUPPORT_RUNBOOK_MVP.md" in api
        or "test_support_runbook_s1.py" in api
        or "Stage 30 S1" in api
    )
    assert (
        "ATTESTATION_PACK_MVP.md" in api
        or "test_attestation_pack_a1.py" in api
        or "Stage 30 A1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 30 D1" in deploy or "STAGE_30_FIDELITY.md" in deploy
    assert (
        "EVIDENCE_LEDGER_MVP.md" in deploy
        or "Stage 30 L1" in deploy
        or "ATTESTATION_PACK_MVP.md" in deploy
        or "INCIDENT_PACK_MVP.md" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 30 D1" in sec or "STAGE_30_FIDELITY.md" in sec
    assert "test_evidence_ledger_l1.py" in sec or "EVIDENCE_LEDGER_MVP.md" in sec
    assert "test_incident_pack_i1.py" in sec or "INCIDENT_PACK_MVP.md" in sec
    assert "test_support_runbook_s1.py" in sec or "SUPPORT_RUNBOOK_MVP.md" in sec
    assert "test_attestation_pack_a1.py" in sec or "ATTESTATION_PACK_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_evidence_ledger_l1.py" in launch
    assert "test_incident_pack_i1.py" in launch
    assert "test_support_runbook_s1.py" in launch
    assert "test_attestation_pack_a1.py" in launch
    assert "test_stage30_fidelity_d1.py" in launch
    assert "STAGE_30_FIDELITY.md" in launch
    assert "STAGE_30_EXIT_CRITERIA.md" in launch or "ADR-066" in launch

    admin = _read("docs/ADMIN_MANUAL.md")
    assert "Stage 30 S1" in admin or "SUPPORT_RUNBOOK_MVP.md" in admin
    support = _read("docs/SUPPORT_RUNBOOK_MVP.md")
    assert "Stage 30 S1" in support
    assert "ADMIN_MANUAL" in support or "admin" in support.lower()


def test_stage30_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_30_FIDELITY.md" in pr
    assert "test_stage30_fidelity_d1.py" in pr
    assert "Stage 30 D1" in pr
    assert "Stage 30 L1" in pr
    assert "Stage 30 I1" in pr
    assert "Stage 30 S1" in pr
    assert "Stage 30 A1" in pr
    assert "STAGE_30_EXIT_CRITERIA.md" in pr or "ADR-066" in pr or "ADR_066" in pr
    assert (
        "attestation" in pr.lower()
        or "§7" in pr
        or "PagerDuty" in pr
        or "execution" in pr.lower()
        or "Remaining" in pr
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_30_FIDELITY.md" in roadmap
    assert "Stage 30 D1" in roadmap
    assert "ADR_065_STAGE30_OPEN.md" in roadmap
    assert "STAGE_30_PLAN.md" in roadmap
    assert "test_stage30_fidelity_d1.py" in roadmap
    assert "STAGE_30_EXIT_CRITERIA.md" in roadmap
    assert "ADR_066_STAGE30_FREEZE.md" in roadmap
