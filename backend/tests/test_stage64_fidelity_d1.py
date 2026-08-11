"""Stage 64 D1 — documentation fidelity for Commercial Analytics & Franchise."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage64_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_64_FIDELITY.md")
    assert (
        "BI" in fidelity
        or "analytics" in fidelity.lower()
        or "Franchise" in fidelity
        or "franchise" in fidelity.lower()
        or "chain" in fidelity.lower()
    )
    for name in (
        "test_advanced_bi_b1.py",
        "test_franchise_chain_f1.py",
        "test_stage64_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-133" in fidelity or "ADR_133" in fidelity
    assert "H64x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "bi" in fidelity.lower()
        or "franchise" in fidelity.lower()
        or "analytics" in fidelity.lower()
    )

    plan = _read("docs/STAGE_64_PLAN.md")
    assert "STAGE_64_FIDELITY.md" in plan
    for ws in ("B1", "F1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h64 = [ln for ln in plan.splitlines() if "| **H64x** |" in ln][0]
    assert "PENDING" in h64 or "COMPLETE" in h64
    assert "ADR-133" in plan or "ADR_133" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H64x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage64_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_64_FIDELITY.md" in br
    assert "Stage 64 D1" in br or "test_stage64_fidelity_d1.py" in br
    assert (
        "Stage 64 B1" in br
        or "ADVANCED_BI_MVP.md" in br
        or "Stage 64 F1" in br
        or "FRANCHISE_CHAIN_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_64_FIDELITY.md" in fidelity_tail or "Stage 64 D1" in fidelity_tail

    for rel in (
        "docs/ADVANCED_BI_MVP.md",
        "docs/FRANCHISE_CHAIN_MVP.md",
    ):
        assert _read(rel)


def test_stage64_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 64 D1" in api or "STAGE_64_FIDELITY.md" in api
    assert "test_stage64_fidelity_d1.py" in api or "STAGE_64_FIDELITY.md" in api
    assert (
        "ADVANCED_BI_MVP.md" in api
        or "test_advanced_bi_b1.py" in api
        or "Stage 64 B1" in api
    )
    assert (
        "FRANCHISE_CHAIN_MVP.md" in api
        or "test_franchise_chain_f1.py" in api
        or "Stage 64 F1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 64 D1" in deploy or "STAGE_64_FIDELITY.md" in deploy
    assert (
        "ADVANCED_BI_MVP.md" in deploy
        or "Stage 64 B1" in deploy
        or "FRANCHISE_CHAIN_MVP.md" in deploy
        or "Stage 64 F1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 64 D1" in sec or "STAGE_64_FIDELITY.md" in sec
    assert "test_advanced_bi_b1.py" in sec or "ADVANCED_BI_MVP.md" in sec
    assert "test_franchise_chain_f1.py" in sec or "FRANCHISE_CHAIN_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_advanced_bi_b1.py" in launch
    assert "test_franchise_chain_f1.py" in launch
    assert "test_stage64_fidelity_d1.py" in launch
    assert "STAGE_64_FIDELITY.md" in launch
    assert "ADR-133" in launch or "ADR_133" in launch or "STAGE_64_PLAN.md" in launch


def test_stage64_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_64_FIDELITY.md" in pr
    assert "test_stage64_fidelity_d1.py" in pr
    assert "Stage 64 D1" in pr
    assert "Stage 64 B1" in pr
    assert "Stage 64 F1" in pr
    assert (
        "advanced_bi_live_claimed" in pr
        or "custom_analytics_live_claimed" in pr
        or "franchise_chain_live_claimed" in pr
        or "chain_enterprise_deals_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_64_FIDELITY.md" in roadmap
    assert "Stage 64 D1" in roadmap
    assert "ADR_133_STAGE64_OPEN.md" in roadmap
    assert "STAGE_64_PLAN.md" in roadmap
    assert "test_stage64_fidelity_d1.py" in roadmap
