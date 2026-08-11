"""Stage 56 D1 — documentation fidelity for Commercial Onboarding & Expansion."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage56_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_56_FIDELITY.md")
    assert (
        "Onboarding" in fidelity
        or "Expansion" in fidelity
        or "Implementation" in fidelity
        or "Geographic" in fidelity
        or "migration" in fidelity.lower()
    )
    for name in (
        "test_implementation_onboarding_o1.py",
        "test_geographic_expansion_g1.py",
        "test_stage56_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-117" in fidelity or "ADR_117" in fidelity
    assert "H56x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "onboarding" in fidelity.lower()
        or "expansion" in fidelity.lower()
        or "geographic" in fidelity.lower()
    )

    plan = _read("docs/STAGE_56_PLAN.md")
    assert "STAGE_56_FIDELITY.md" in plan
    for ws in ("O1", "G1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h56 = [ln for ln in plan.splitlines() if "| **H56x** |" in ln][0]
    assert "PENDING" in h56 or "COMPLETE" in h56
    assert "ADR-117" in plan or "ADR_117" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H56x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage56_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_56_FIDELITY.md" in br
    assert "Stage 56 D1" in br or "test_stage56_fidelity_d1.py" in br
    assert (
        "Stage 56 O1" in br
        or "IMPLEMENTATION_ONBOARDING_MVP.md" in br
        or "Stage 56 G1" in br
        or "GEOGRAPHIC_EXPANSION_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_56_FIDELITY.md" in fidelity_tail or "Stage 56 D1" in fidelity_tail

    for rel in (
        "docs/IMPLEMENTATION_ONBOARDING_MVP.md",
        "docs/GEOGRAPHIC_EXPANSION_MVP.md",
    ):
        assert _read(rel)


def test_stage56_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 56 D1" in api or "STAGE_56_FIDELITY.md" in api
    assert "test_stage56_fidelity_d1.py" in api or "STAGE_56_FIDELITY.md" in api
    assert (
        "IMPLEMENTATION_ONBOARDING_MVP.md" in api
        or "test_implementation_onboarding_o1.py" in api
        or "Stage 56 O1" in api
    )
    assert (
        "GEOGRAPHIC_EXPANSION_MVP.md" in api
        or "test_geographic_expansion_g1.py" in api
        or "Stage 56 G1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 56 D1" in deploy or "STAGE_56_FIDELITY.md" in deploy
    assert (
        "IMPLEMENTATION_ONBOARDING_MVP.md" in deploy
        or "Stage 56 O1" in deploy
        or "GEOGRAPHIC_EXPANSION_MVP.md" in deploy
        or "Stage 56 G1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 56 D1" in sec or "STAGE_56_FIDELITY.md" in sec
    assert "test_implementation_onboarding_o1.py" in sec or "IMPLEMENTATION_ONBOARDING_MVP.md" in sec
    assert "test_geographic_expansion_g1.py" in sec or "GEOGRAPHIC_EXPANSION_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_implementation_onboarding_o1.py" in launch
    assert "test_geographic_expansion_g1.py" in launch
    assert "test_stage56_fidelity_d1.py" in launch
    assert "STAGE_56_FIDELITY.md" in launch
    assert "ADR-117" in launch or "ADR_117" in launch or "STAGE_56_PLAN.md" in launch


def test_stage56_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_56_FIDELITY.md" in pr
    assert "test_stage56_fidelity_d1.py" in pr
    assert "Stage 56 D1" in pr
    assert "Stage 56 O1" in pr
    assert "Stage 56 G1" in pr
    assert (
        "data_migration_fee_billing_live" in pr
        or "multi_market_expansion_claimed" in pr
        or "international_localization_claimed" in pr
        or "onsite_training_delivery_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_56_FIDELITY.md" in roadmap
    assert "Stage 56 D1" in roadmap
    assert "ADR_117_STAGE56_OPEN.md" in roadmap
    assert "STAGE_56_PLAN.md" in roadmap
    assert "test_stage56_fidelity_d1.py" in roadmap
