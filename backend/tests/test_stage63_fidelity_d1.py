"""Stage 63 D1 — documentation fidelity for Commercial Capital & Scale."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage63_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_63_FIDELITY.md")
    assert (
        "IPO" in fidelity
        or "funding" in fidelity.lower()
        or "scale" in fidelity.lower()
        or "50" in fidelity
        or "Series B" in fidelity
    )
    for name in (
        "test_ipo_readiness_p1.py",
        "test_global_scale_g1.py",
        "test_stage63_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-131" in fidelity or "ADR_131" in fidelity
    assert "H63x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "ipo" in fidelity.lower()
        or "scale" in fidelity.lower()
        or "funding" in fidelity.lower()
    )

    plan = _read("docs/STAGE_63_PLAN.md")
    assert "STAGE_63_FIDELITY.md" in plan
    for ws in ("P1", "G1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h63 = [ln for ln in plan.splitlines() if "| **H63x** |" in ln][0]
    assert "PENDING" in h63 or "COMPLETE" in h63
    assert "ADR-131" in plan or "ADR_131" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H63x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage63_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_63_FIDELITY.md" in br
    assert "Stage 63 D1" in br or "test_stage63_fidelity_d1.py" in br
    assert (
        "Stage 63 P1" in br
        or "IPO_READINESS_MVP.md" in br
        or "Stage 63 G1" in br
        or "GLOBAL_SCALE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_63_FIDELITY.md" in fidelity_tail or "Stage 63 D1" in fidelity_tail

    for rel in (
        "docs/IPO_READINESS_MVP.md",
        "docs/GLOBAL_SCALE_MVP.md",
    ):
        assert _read(rel)


def test_stage63_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 63 D1" in api or "STAGE_63_FIDELITY.md" in api
    assert "test_stage63_fidelity_d1.py" in api or "STAGE_63_FIDELITY.md" in api
    assert (
        "IPO_READINESS_MVP.md" in api
        or "test_ipo_readiness_p1.py" in api
        or "Stage 63 P1" in api
    )
    assert (
        "GLOBAL_SCALE_MVP.md" in api
        or "test_global_scale_g1.py" in api
        or "Stage 63 G1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 63 D1" in deploy or "STAGE_63_FIDELITY.md" in deploy
    assert (
        "IPO_READINESS_MVP.md" in deploy
        or "Stage 63 P1" in deploy
        or "GLOBAL_SCALE_MVP.md" in deploy
        or "Stage 63 G1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 63 D1" in sec or "STAGE_63_FIDELITY.md" in sec
    assert "test_ipo_readiness_p1.py" in sec or "IPO_READINESS_MVP.md" in sec
    assert "test_global_scale_g1.py" in sec or "GLOBAL_SCALE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ipo_readiness_p1.py" in launch
    assert "test_global_scale_g1.py" in launch
    assert "test_stage63_fidelity_d1.py" in launch
    assert "STAGE_63_FIDELITY.md" in launch
    assert "ADR-131" in launch or "ADR_131" in launch or "STAGE_63_PLAN.md" in launch


def test_stage63_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_63_FIDELITY.md" in pr
    assert "test_stage63_fidelity_d1.py" in pr
    assert "Stage 63 D1" in pr
    assert "Stage 63 P1" in pr
    assert "Stage 63 G1" in pr
    assert (
        "ipo_readiness_live_claimed" in pr
        or "series_b_c_funding_claimed" in pr
        or "global_scale_50k_customers_claimed" in pr
        or "twenty_plus_countries_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_63_FIDELITY.md" in roadmap
    assert "Stage 63 D1" in roadmap
    assert "ADR_131_STAGE63_OPEN.md" in roadmap
    assert "STAGE_63_PLAN.md" in roadmap
    assert "test_stage63_fidelity_d1.py" in roadmap
