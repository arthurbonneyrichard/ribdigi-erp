"""Stage 36 D1 — documentation fidelity for Commercial Assurance Completion."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage36_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_36_FIDELITY.md")
    assert (
        "Assurance Completion" in fidelity
        or "Support SLA" in fidelity
        or "Billing-deferred" in fidelity
        or "Billing-Deferred" in fidelity
    )
    for name in (
        "test_support_sla_boundary_s1.py",
        "test_billing_deferred_honesty_b1.py",
        "test_stage36_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-077" in fidelity or "ADR_077" in fidelity
    assert "H36x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "SLA" in fidelity
        or "billing" in fidelity.lower()
    )

    plan = _read("docs/STAGE_36_PLAN.md")
    assert "STAGE_36_FIDELITY.md" in plan
    for ws in ("S1", "B1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h36 = [ln for ln in plan.splitlines() if "| **H36x** |" in ln][0]
    assert "PENDING" in h36 or "COMPLETE" in h36
    assert "ADR-077" in plan or "ADR_077" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H36x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage36_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_36_FIDELITY.md" in br
    assert "Stage 36 D1" in br or "test_stage36_fidelity_d1.py" in br
    assert (
        "Stage 36 S1" in br
        or "SUPPORT_SLA_BOUNDARY_MVP.md" in br
        or "Stage 36 B1" in br
        or "BILLING_DEFERRED_HONESTY_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_36_FIDELITY.md" in fidelity_tail or "Stage 36 D1" in fidelity_tail

    for rel in (
        "docs/SUPPORT_SLA_BOUNDARY_MVP.md",
        "docs/BILLING_DEFERRED_HONESTY_MVP.md",
    ):
        assert _read(rel)


def test_stage36_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 36 D1" in api or "STAGE_36_FIDELITY.md" in api
    assert "test_stage36_fidelity_d1.py" in api or "STAGE_36_FIDELITY.md" in api
    assert (
        "SUPPORT_SLA_BOUNDARY_MVP.md" in api
        or "test_support_sla_boundary_s1.py" in api
        or "Stage 36 S1" in api
    )
    assert (
        "BILLING_DEFERRED_HONESTY_MVP.md" in api
        or "test_billing_deferred_honesty_b1.py" in api
        or "Stage 36 B1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 36 D1" in deploy or "STAGE_36_FIDELITY.md" in deploy
    assert (
        "SUPPORT_SLA_BOUNDARY_MVP.md" in deploy
        or "Stage 36 S1" in deploy
        or "BILLING_DEFERRED_HONESTY_MVP.md" in deploy
        or "Stage 36 B1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 36 D1" in sec or "STAGE_36_FIDELITY.md" in sec
    assert "test_support_sla_boundary_s1.py" in sec or "SUPPORT_SLA_BOUNDARY_MVP.md" in sec
    assert "test_billing_deferred_honesty_b1.py" in sec or "BILLING_DEFERRED_HONESTY_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_support_sla_boundary_s1.py" in launch
    assert "test_billing_deferred_honesty_b1.py" in launch
    assert "test_stage36_fidelity_d1.py" in launch
    assert "STAGE_36_FIDELITY.md" in launch
    assert "ADR-077" in launch or "ADR_077" in launch or "STAGE_36_PLAN.md" in launch


def test_stage36_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_36_FIDELITY.md" in pr
    assert "test_stage36_fidelity_d1.py" in pr
    assert "Stage 36 D1" in pr
    assert "Stage 36 S1" in pr
    assert "Stage 36 B1" in pr
    assert (
        "support_sla_claimed" in pr
        or "billing_complete_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_36_FIDELITY.md" in roadmap
    assert "Stage 36 D1" in roadmap
    assert "ADR_077_STAGE36_OPEN.md" in roadmap
    assert "STAGE_36_PLAN.md" in roadmap
    assert "test_stage36_fidelity_d1.py" in roadmap
