"""Stage 33 D1 — documentation fidelity for Commercial MVP Continuity."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage33_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_33_FIDELITY.md")
    assert (
        "Continuity" in fidelity
        or "Residual" in fidelity
        or "Compliance" in fidelity
        or "Onboarding" in fidelity
        or "Knowledge" in fidelity
    )
    assert "test_residual_risk_k1.py" in fidelity
    assert "test_compliance_readiness_c1.py" in fidelity
    assert "test_first_tenant_onboarding_f1.py" in fidelity
    assert "test_knowledge_transfer_t1.py" in fidelity
    assert "test_stage33_fidelity_d1.py" in fidelity
    assert "ADR-071" in fidelity or "ADR_071" in fidelity
    assert "H33x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "attestation" in fidelity.lower()
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "SOC" in fidelity
    )

    plan = _read("docs/STAGE_33_PLAN.md")
    assert "STAGE_33_FIDELITY.md" in plan
    for ws in ("K1", "C1", "F1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h33 = [ln for ln in plan.splitlines() if "| **H33x** |" in ln][0]
    assert "PENDING" in h33 or "COMPLETE" in h33
    assert "ADR-071" in plan or "ADR_071" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H33x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage33_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_33_FIDELITY.md" in br
    assert "Stage 33 D1" in br or "test_stage33_fidelity_d1.py" in br
    assert (
        "Stage 33 K1" in br
        or "RESIDUAL_RISK_MVP.md" in br
        or "Stage 33 C1" in br
        or "COMPLIANCE_READINESS_MVP.md" in br
        or "Stage 33 F1" in br
        or "FIRST_TENANT_ONBOARDING_MVP.md" in br
        or "Stage 33 T1" in br
        or "KNOWLEDGE_TRANSFER_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_33_FIDELITY.md" in fidelity_tail or "Stage 33 D1" in fidelity_tail

    assert _read("docs/RESIDUAL_RISK_MVP.md")
    assert _read("docs/COMPLIANCE_READINESS_MVP.md")
    assert _read("docs/FIRST_TENANT_ONBOARDING_MVP.md")
    assert _read("docs/KNOWLEDGE_TRANSFER_MVP.md")


def test_stage33_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 33 D1" in api or "STAGE_33_FIDELITY.md" in api
    assert "test_stage33_fidelity_d1.py" in api or "STAGE_33_FIDELITY.md" in api
    assert (
        "RESIDUAL_RISK_MVP.md" in api
        or "test_residual_risk_k1.py" in api
        or "Stage 33 K1" in api
    )
    assert (
        "COMPLIANCE_READINESS_MVP.md" in api
        or "test_compliance_readiness_c1.py" in api
        or "Stage 33 C1" in api
    )
    assert (
        "FIRST_TENANT_ONBOARDING_MVP.md" in api
        or "test_first_tenant_onboarding_f1.py" in api
        or "Stage 33 F1" in api
    )
    assert (
        "KNOWLEDGE_TRANSFER_MVP.md" in api
        or "test_knowledge_transfer_t1.py" in api
        or "Stage 33 T1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 33 D1" in deploy or "STAGE_33_FIDELITY.md" in deploy
    assert (
        "RESIDUAL_RISK_MVP.md" in deploy
        or "Stage 33 K1" in deploy
        or "COMPLIANCE_READINESS_MVP.md" in deploy
        or "FIRST_TENANT_ONBOARDING_MVP.md" in deploy
        or "KNOWLEDGE_TRANSFER_MVP.md" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 33 D1" in sec or "STAGE_33_FIDELITY.md" in sec
    assert "test_residual_risk_k1.py" in sec or "RESIDUAL_RISK_MVP.md" in sec
    assert "test_compliance_readiness_c1.py" in sec or "COMPLIANCE_READINESS_MVP.md" in sec
    assert "test_first_tenant_onboarding_f1.py" in sec or "FIRST_TENANT_ONBOARDING_MVP.md" in sec
    assert "test_knowledge_transfer_t1.py" in sec or "KNOWLEDGE_TRANSFER_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_residual_risk_k1.py" in launch
    assert "test_compliance_readiness_c1.py" in launch
    assert "test_first_tenant_onboarding_f1.py" in launch
    assert "test_knowledge_transfer_t1.py" in launch
    assert "test_stage33_fidelity_d1.py" in launch
    assert "STAGE_33_FIDELITY.md" in launch
    assert "ADR-071" in launch or "ADR_071" in launch or "STAGE_33_PLAN.md" in launch


def test_stage33_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_33_FIDELITY.md" in pr
    assert "test_stage33_fidelity_d1.py" in pr
    assert "Stage 33 D1" in pr
    assert "Stage 33 K1" in pr
    assert "Stage 33 C1" in pr
    assert "Stage 33 F1" in pr
    assert "Stage 33 T1" in pr
    assert (
        "go_live_claimed" in pr
        or "§7" in pr
        or "attestation" in pr.lower()
        or "Remaining" in pr
        or "packaging" in pr.lower()
        or "soc2_complete_claimed" in pr
        or "live_training_claimed" in pr
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_33_FIDELITY.md" in roadmap
    assert "Stage 33 D1" in roadmap
    assert "ADR_071_STAGE33_OPEN.md" in roadmap
    assert "STAGE_33_PLAN.md" in roadmap
    assert "test_stage33_fidelity_d1.py" in roadmap
