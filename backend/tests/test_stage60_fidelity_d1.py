"""Stage 60 D1 — documentation fidelity for Commercial Manufacturing & Tax."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage60_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_60_FIDELITY.md")
    assert (
        "Manufacturing" in fidelity
        or "MRP" in fidelity
        or "Tax" in fidelity
        or "GST" in fidelity
        or "VAT" in fidelity
    )
    for name in (
        "test_advanced_manufacturing_m1.py",
        "test_multi_country_tax_t1.py",
        "test_stage60_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-125" in fidelity or "ADR_125" in fidelity
    assert "H60x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "mrp" in fidelity.lower()
        or "tax" in fidelity.lower()
        or "manufactur" in fidelity.lower()
    )

    plan = _read("docs/STAGE_60_PLAN.md")
    assert "STAGE_60_FIDELITY.md" in plan
    for ws in ("M1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h60 = [ln for ln in plan.splitlines() if "| **H60x** |" in ln][0]
    assert "PENDING" in h60 or "COMPLETE" in h60
    assert "ADR-125" in plan or "ADR_125" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H60x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage60_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_60_FIDELITY.md" in br
    assert "Stage 60 D1" in br or "test_stage60_fidelity_d1.py" in br
    assert (
        "Stage 60 M1" in br
        or "ADVANCED_MANUFACTURING_MVP.md" in br
        or "Stage 60 T1" in br
        or "MULTI_COUNTRY_TAX_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_60_FIDELITY.md" in fidelity_tail or "Stage 60 D1" in fidelity_tail

    for rel in (
        "docs/ADVANCED_MANUFACTURING_MVP.md",
        "docs/MULTI_COUNTRY_TAX_MVP.md",
    ):
        assert _read(rel)


def test_stage60_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 60 D1" in api or "STAGE_60_FIDELITY.md" in api
    assert "test_stage60_fidelity_d1.py" in api or "STAGE_60_FIDELITY.md" in api
    assert (
        "ADVANCED_MANUFACTURING_MVP.md" in api
        or "test_advanced_manufacturing_m1.py" in api
        or "Stage 60 M1" in api
    )
    assert (
        "MULTI_COUNTRY_TAX_MVP.md" in api
        or "test_multi_country_tax_t1.py" in api
        or "Stage 60 T1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 60 D1" in deploy or "STAGE_60_FIDELITY.md" in deploy
    assert (
        "ADVANCED_MANUFACTURING_MVP.md" in deploy
        or "Stage 60 M1" in deploy
        or "MULTI_COUNTRY_TAX_MVP.md" in deploy
        or "Stage 60 T1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 60 D1" in sec or "STAGE_60_FIDELITY.md" in sec
    assert "test_advanced_manufacturing_m1.py" in sec or "ADVANCED_MANUFACTURING_MVP.md" in sec
    assert "test_multi_country_tax_t1.py" in sec or "MULTI_COUNTRY_TAX_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_advanced_manufacturing_m1.py" in launch
    assert "test_multi_country_tax_t1.py" in launch
    assert "test_stage60_fidelity_d1.py" in launch
    assert "STAGE_60_FIDELITY.md" in launch
    assert "ADR-125" in launch or "ADR_125" in launch or "STAGE_60_PLAN.md" in launch


def test_stage60_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_60_FIDELITY.md" in pr
    assert "test_stage60_fidelity_d1.py" in pr
    assert "Stage 60 D1" in pr
    assert "Stage 60 M1" in pr
    assert "Stage 60 T1" in pr
    assert (
        "mrp_module_live_claimed" in pr
        or "production_scheduling_live_claimed" in pr
        or "multi_country_tax_engine_claimed" in pr
        or "tax_efile_portal_live_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_60_FIDELITY.md" in roadmap
    assert "Stage 60 D1" in roadmap
    assert "ADR_125_STAGE60_OPEN.md" in roadmap
    assert "STAGE_60_PLAN.md" in roadmap
    assert "test_stage60_fidelity_d1.py" in roadmap
