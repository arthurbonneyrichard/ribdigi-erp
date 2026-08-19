"""Stage 55 D1 — documentation fidelity for Commercial Licensing & Positioning."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage55_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_55_FIDELITY.md")
    assert (
        "Licensing" in fidelity
        or "Positioning" in fidelity
        or "White-Label" in fidelity
        or "Unit Economics" in fidelity
        or "Competitive" in fidelity
        or "CAC" in fidelity
    )
    for name in (
        "test_white_label_licensing_w1.py",
        "test_unit_economics_positioning_u1.py",
        "test_stage55_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-115" in fidelity or "ADR_115" in fidelity
    assert "H55x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "licensing" in fidelity.lower()
        or "economics" in fidelity.lower()
        or "positioning" in fidelity.lower()
    )

    plan = _read("docs/STAGE_55_PLAN.md")
    assert "STAGE_55_FIDELITY.md" in plan
    for ws in ("W1", "U1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h55 = [ln for ln in plan.splitlines() if "| **H55x** |" in ln][0]
    assert "PENDING" in h55 or "COMPLETE" in h55
    assert "ADR-115" in plan or "ADR_115" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H55x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage55_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_55_FIDELITY.md" in br
    assert "Stage 55 D1" in br or "test_stage55_fidelity_d1.py" in br
    assert (
        "Stage 55 W1" in br
        or "WHITE_LABEL_LICENSING_MVP.md" in br
        or "Stage 55 U1" in br
        or "UNIT_ECONOMICS_POSITIONING_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_55_FIDELITY.md" in fidelity_tail or "Stage 55 D1" in fidelity_tail

    for rel in (
        "docs/WHITE_LABEL_LICENSING_MVP.md",
        "docs/UNIT_ECONOMICS_POSITIONING_MVP.md",
    ):
        assert _read(rel)


def test_stage55_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 55 D1" in api or "STAGE_55_FIDELITY.md" in api
    assert "test_stage55_fidelity_d1.py" in api or "STAGE_55_FIDELITY.md" in api
    assert (
        "WHITE_LABEL_LICENSING_MVP.md" in api
        or "test_white_label_licensing_w1.py" in api
        or "Stage 55 W1" in api
    )
    assert (
        "UNIT_ECONOMICS_POSITIONING_MVP.md" in api
        or "test_unit_economics_positioning_u1.py" in api
        or "Stage 55 U1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 55 D1" in deploy or "STAGE_55_FIDELITY.md" in deploy
    assert (
        "WHITE_LABEL_LICENSING_MVP.md" in deploy
        or "Stage 55 W1" in deploy
        or "UNIT_ECONOMICS_POSITIONING_MVP.md" in deploy
        or "Stage 55 U1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 55 D1" in sec or "STAGE_55_FIDELITY.md" in sec
    assert "test_white_label_licensing_w1.py" in sec or "WHITE_LABEL_LICENSING_MVP.md" in sec
    assert "test_unit_economics_positioning_u1.py" in sec or "UNIT_ECONOMICS_POSITIONING_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_white_label_licensing_w1.py" in launch
    assert "test_unit_economics_positioning_u1.py" in launch
    assert "test_stage55_fidelity_d1.py" in launch
    assert "STAGE_55_FIDELITY.md" in launch
    assert "ADR-115" in launch or "ADR_115" in launch or "STAGE_55_PLAN.md" in launch


def test_stage55_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_55_FIDELITY.md" in pr
    assert "test_stage55_fidelity_d1.py" in pr
    assert "Stage 55 D1" in pr
    assert "Stage 55 W1" in pr
    assert "Stage 55 U1" in pr
    assert (
        "white_label_licensing_live" in pr
        or "cac_ltv_measured_claimed" in pr
        or "competitive_superiority_proven" in pr
        or "franchise_revenue_share_billing_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_55_FIDELITY.md" in roadmap
    assert "Stage 55 D1" in roadmap
    assert "ADR_115_STAGE55_OPEN.md" in roadmap
    assert "STAGE_55_PLAN.md" in roadmap
    assert "test_stage55_fidelity_d1.py" in roadmap
