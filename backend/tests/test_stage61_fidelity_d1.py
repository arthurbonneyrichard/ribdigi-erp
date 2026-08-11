"""Stage 61 D1 — documentation fidelity for Commercial Fintech & Supply-Chain."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage61_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_61_FIDELITY.md")
    assert (
        "Fintech" in fidelity
        or "fintech" in fidelity.lower()
        or "lending" in fidelity.lower()
        or "Supply" in fidelity
        or "supply" in fidelity.lower()
    )
    for name in (
        "test_embedded_fintech_f1.py",
        "test_supply_chain_integration_s1.py",
        "test_stage61_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-127" in fidelity or "ADR_127" in fidelity
    assert "H61x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "lending" in fidelity.lower()
        or "supply" in fidelity.lower()
        or "fintech" in fidelity.lower()
    )

    plan = _read("docs/STAGE_61_PLAN.md")
    assert "STAGE_61_FIDELITY.md" in plan
    for ws in ("F1", "S1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h61 = [ln for ln in plan.splitlines() if "| **H61x** |" in ln][0]
    assert "PENDING" in h61 or "COMPLETE" in h61
    assert "ADR-127" in plan or "ADR_127" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H61x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage61_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_61_FIDELITY.md" in br
    assert "Stage 61 D1" in br or "test_stage61_fidelity_d1.py" in br
    assert (
        "Stage 61 F1" in br
        or "EMBEDDED_FINTECH_MVP.md" in br
        or "Stage 61 S1" in br
        or "SUPPLY_CHAIN_INTEGRATION_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_61_FIDELITY.md" in fidelity_tail or "Stage 61 D1" in fidelity_tail

    for rel in (
        "docs/EMBEDDED_FINTECH_MVP.md",
        "docs/SUPPLY_CHAIN_INTEGRATION_MVP.md",
    ):
        assert _read(rel)


def test_stage61_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 61 D1" in api or "STAGE_61_FIDELITY.md" in api
    assert "test_stage61_fidelity_d1.py" in api or "STAGE_61_FIDELITY.md" in api
    assert (
        "EMBEDDED_FINTECH_MVP.md" in api
        or "test_embedded_fintech_f1.py" in api
        or "Stage 61 F1" in api
    )
    assert (
        "SUPPLY_CHAIN_INTEGRATION_MVP.md" in api
        or "test_supply_chain_integration_s1.py" in api
        or "Stage 61 S1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 61 D1" in deploy or "STAGE_61_FIDELITY.md" in deploy
    assert (
        "EMBEDDED_FINTECH_MVP.md" in deploy
        or "Stage 61 F1" in deploy
        or "SUPPLY_CHAIN_INTEGRATION_MVP.md" in deploy
        or "Stage 61 S1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 61 D1" in sec or "STAGE_61_FIDELITY.md" in sec
    assert "test_embedded_fintech_f1.py" in sec or "EMBEDDED_FINTECH_MVP.md" in sec
    assert "test_supply_chain_integration_s1.py" in sec or "SUPPLY_CHAIN_INTEGRATION_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_embedded_fintech_f1.py" in launch
    assert "test_supply_chain_integration_s1.py" in launch
    assert "test_stage61_fidelity_d1.py" in launch
    assert "STAGE_61_FIDELITY.md" in launch
    assert "ADR-127" in launch or "ADR_127" in launch or "STAGE_61_PLAN.md" in launch


def test_stage61_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_61_FIDELITY.md" in pr
    assert "test_stage61_fidelity_d1.py" in pr
    assert "Stage 61 D1" in pr
    assert "Stage 61 F1" in pr
    assert "Stage 61 S1" in pr
    assert (
        "lending_product_live_claimed" in pr
        or "invoice_financing_live_claimed" in pr
        or "supplier_supply_chain_live_claimed" in pr
        or "supplier_portal_live_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_61_FIDELITY.md" in roadmap
    assert "Stage 61 D1" in roadmap
    assert "ADR_127_STAGE61_OPEN.md" in roadmap
    assert "STAGE_61_PLAN.md" in roadmap
    assert "test_stage61_fidelity_d1.py" in roadmap
