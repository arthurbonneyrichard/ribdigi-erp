"""Stage 53 D1 — documentation fidelity for Commercial API & Lifecycle."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage53_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_53_FIDELITY.md")
    assert (
        "API" in fidelity
        or "Integration" in fidelity
        or "Cancellation" in fidelity
        or "Churn" in fidelity
        or "Lifecycle" in fidelity
        or "Refund" in fidelity
    )
    for name in (
        "test_api_integration_commercial_a1.py",
        "test_cancellation_churn_c1.py",
        "test_stage53_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-111" in fidelity or "ADR_111" in fidelity
    assert "H53x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "api" in fidelity.lower()
        or "cancellation" in fidelity.lower()
        or "churn" in fidelity.lower()
    )

    plan = _read("docs/STAGE_53_PLAN.md")
    assert "STAGE_53_FIDELITY.md" in plan
    for ws in ("A1", "C1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h53 = [ln for ln in plan.splitlines() if "| **H53x** |" in ln][0]
    assert "PENDING" in h53 or "COMPLETE" in h53
    assert "ADR-111" in plan or "ADR_111" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H53x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage53_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_53_FIDELITY.md" in br
    assert "Stage 53 D1" in br or "test_stage53_fidelity_d1.py" in br
    assert (
        "Stage 53 A1" in br
        or "API_INTEGRATION_COMMERCIAL_MVP.md" in br
        or "Stage 53 C1" in br
        or "CANCELLATION_CHURN_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_53_FIDELITY.md" in fidelity_tail or "Stage 53 D1" in fidelity_tail

    for rel in (
        "docs/API_INTEGRATION_COMMERCIAL_MVP.md",
        "docs/CANCELLATION_CHURN_MVP.md",
    ):
        assert _read(rel)


def test_stage53_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 53 D1" in api or "STAGE_53_FIDELITY.md" in api
    assert "test_stage53_fidelity_d1.py" in api or "STAGE_53_FIDELITY.md" in api
    assert (
        "API_INTEGRATION_COMMERCIAL_MVP.md" in api
        or "test_api_integration_commercial_a1.py" in api
        or "Stage 53 A1" in api
    )
    assert (
        "CANCELLATION_CHURN_MVP.md" in api
        or "test_cancellation_churn_c1.py" in api
        or "Stage 53 C1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 53 D1" in deploy or "STAGE_53_FIDELITY.md" in deploy
    assert (
        "API_INTEGRATION_COMMERCIAL_MVP.md" in deploy
        or "Stage 53 A1" in deploy
        or "CANCELLATION_CHURN_MVP.md" in deploy
        or "Stage 53 C1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 53 D1" in sec or "STAGE_53_FIDELITY.md" in sec
    assert "test_api_integration_commercial_a1.py" in sec or "API_INTEGRATION_COMMERCIAL_MVP.md" in sec
    assert "test_cancellation_churn_c1.py" in sec or "CANCELLATION_CHURN_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_api_integration_commercial_a1.py" in launch
    assert "test_cancellation_churn_c1.py" in launch
    assert "test_stage53_fidelity_d1.py" in launch
    assert "STAGE_53_FIDELITY.md" in launch
    assert "ADR-111" in launch or "ADR_111" in launch or "STAGE_53_PLAN.md" in launch


def test_stage53_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_53_FIDELITY.md" in pr
    assert "test_stage53_fidelity_d1.py" in pr
    assert "Stage 53 D1" in pr
    assert "Stage 53 A1" in pr
    assert "Stage 53 C1" in pr
    assert (
        "api_rate_limit_upgrade_billing_live" in pr
        or "cancellation_portal_live" in pr
        or "refund_processing_claimed" in pr
        or "connector_fee_billing_claimed" in pr
        or "churn_measurement_live" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_53_FIDELITY.md" in roadmap
    assert "Stage 53 D1" in roadmap
    assert "ADR_111_STAGE53_OPEN.md" in roadmap
    assert "STAGE_53_PLAN.md" in roadmap
    assert "test_stage53_fidelity_d1.py" in roadmap
