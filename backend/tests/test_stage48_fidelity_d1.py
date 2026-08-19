"""Stage 48 D1 — documentation fidelity for Commercial Services."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage48_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_48_FIDELITY.md")
    assert (
        "Services" in fidelity
        or "SOW" in fidelity
        or "Training" in fidelity
        or "Professional" in fidelity
    )
    for name in (
        "test_professional_services_sow_p1.py",
        "test_customer_training_cert_t1.py",
        "test_stage48_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-101" in fidelity or "ADR_101" in fidelity
    assert "H48x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "SOW" in fidelity
        or "training" in fidelity.lower()
    )

    plan = _read("docs/STAGE_48_PLAN.md")
    assert "STAGE_48_FIDELITY.md" in plan
    for ws in ("P1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h48 = [ln for ln in plan.splitlines() if "| **H48x** |" in ln][0]
    assert "PENDING" in h48 or "COMPLETE" in h48
    assert "ADR-101" in plan or "ADR_101" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H48x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage48_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_48_FIDELITY.md" in br
    assert "Stage 48 D1" in br or "test_stage48_fidelity_d1.py" in br
    assert (
        "Stage 48 P1" in br
        or "PROFESSIONAL_SERVICES_SOW_MVP.md" in br
        or "Stage 48 T1" in br
        or "CUSTOMER_TRAINING_CERT_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_48_FIDELITY.md" in fidelity_tail or "Stage 48 D1" in fidelity_tail

    for rel in (
        "docs/PROFESSIONAL_SERVICES_SOW_MVP.md",
        "docs/CUSTOMER_TRAINING_CERT_MVP.md",
    ):
        assert _read(rel)


def test_stage48_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 48 D1" in api or "STAGE_48_FIDELITY.md" in api
    assert "test_stage48_fidelity_d1.py" in api or "STAGE_48_FIDELITY.md" in api
    assert (
        "PROFESSIONAL_SERVICES_SOW_MVP.md" in api
        or "test_professional_services_sow_p1.py" in api
        or "Stage 48 P1" in api
    )
    assert (
        "CUSTOMER_TRAINING_CERT_MVP.md" in api
        or "test_customer_training_cert_t1.py" in api
        or "Stage 48 T1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 48 D1" in deploy or "STAGE_48_FIDELITY.md" in deploy
    assert (
        "PROFESSIONAL_SERVICES_SOW_MVP.md" in deploy
        or "Stage 48 P1" in deploy
        or "CUSTOMER_TRAINING_CERT_MVP.md" in deploy
        or "Stage 48 T1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 48 D1" in sec or "STAGE_48_FIDELITY.md" in sec
    assert "test_professional_services_sow_p1.py" in sec or "PROFESSIONAL_SERVICES_SOW_MVP.md" in sec
    assert "test_customer_training_cert_t1.py" in sec or "CUSTOMER_TRAINING_CERT_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_professional_services_sow_p1.py" in launch
    assert "test_customer_training_cert_t1.py" in launch
    assert "test_stage48_fidelity_d1.py" in launch
    assert "STAGE_48_FIDELITY.md" in launch
    assert "ADR-101" in launch or "ADR_101" in launch or "STAGE_48_PLAN.md" in launch


def test_stage48_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_48_FIDELITY.md" in pr
    assert "test_stage48_fidelity_d1.py" in pr
    assert "Stage 48 D1" in pr
    assert "Stage 48 P1" in pr
    assert "Stage 48 T1" in pr
    assert (
        "signed_sow_claimed" in pr
        or "live_training_claimed" in pr
        or "professional_services_live" in pr
        or "training_complete_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_48_FIDELITY.md" in roadmap
    assert "Stage 48 D1" in roadmap
    assert "ADR_101_STAGE48_OPEN.md" in roadmap
    assert "STAGE_48_PLAN.md" in roadmap
    assert "test_stage48_fidelity_d1.py" in roadmap
