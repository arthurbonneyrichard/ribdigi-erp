"""Stage 54 D1 — documentation fidelity for Commercial Go-To-Market."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage54_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_54_FIDELITY.md")
    assert (
        "Marketing" in fidelity
        or "Sales" in fidelity
        or "Go-To-Market" in fidelity
        or "GTM" in fidelity
        or "testimonial" in fidelity.lower()
    )
    for name in (
        "test_digital_marketing_m1.py",
        "test_direct_sales_s1.py",
        "test_stage54_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-113" in fidelity or "ADR_113" in fidelity
    assert "H54x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "marketing" in fidelity.lower()
        or "sales" in fidelity.lower()
    )

    plan = _read("docs/STAGE_54_PLAN.md")
    assert "STAGE_54_FIDELITY.md" in plan
    for ws in ("M1", "S1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h54 = [ln for ln in plan.splitlines() if "| **H54x** |" in ln][0]
    assert "PENDING" in h54 or "COMPLETE" in h54
    assert "ADR-113" in plan or "ADR_113" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H54x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage54_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_54_FIDELITY.md" in br
    assert "Stage 54 D1" in br or "test_stage54_fidelity_d1.py" in br
    assert (
        "Stage 54 M1" in br
        or "DIGITAL_MARKETING_MVP.md" in br
        or "Stage 54 S1" in br
        or "DIRECT_SALES_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_54_FIDELITY.md" in fidelity_tail or "Stage 54 D1" in fidelity_tail

    for rel in (
        "docs/DIGITAL_MARKETING_MVP.md",
        "docs/DIRECT_SALES_MVP.md",
    ):
        assert _read(rel)


def test_stage54_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 54 D1" in api or "STAGE_54_FIDELITY.md" in api
    assert "test_stage54_fidelity_d1.py" in api or "STAGE_54_FIDELITY.md" in api
    assert (
        "DIGITAL_MARKETING_MVP.md" in api
        or "test_digital_marketing_m1.py" in api
        or "Stage 54 M1" in api
    )
    assert (
        "DIRECT_SALES_MVP.md" in api
        or "test_direct_sales_s1.py" in api
        or "Stage 54 S1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 54 D1" in deploy or "STAGE_54_FIDELITY.md" in deploy
    assert (
        "DIGITAL_MARKETING_MVP.md" in deploy
        or "Stage 54 M1" in deploy
        or "DIRECT_SALES_MVP.md" in deploy
        or "Stage 54 S1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 54 D1" in sec or "STAGE_54_FIDELITY.md" in sec
    assert "test_digital_marketing_m1.py" in sec or "DIGITAL_MARKETING_MVP.md" in sec
    assert "test_direct_sales_s1.py" in sec or "DIRECT_SALES_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_digital_marketing_m1.py" in launch
    assert "test_direct_sales_s1.py" in launch
    assert "test_stage54_fidelity_d1.py" in launch
    assert "STAGE_54_FIDELITY.md" in launch
    assert "ADR-113" in launch or "ADR_113" in launch or "STAGE_54_PLAN.md" in launch


def test_stage54_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_54_FIDELITY.md" in pr
    assert "test_stage54_fidelity_d1.py" in pr
    assert "Stage 54 D1" in pr
    assert "Stage 54 M1" in pr
    assert "Stage 54 S1" in pr
    assert (
        "digital_marketing_campaigns_live" in pr
        or "inside_sales_team_live" in pr
        or "case_studies_published_claimed" in pr
        or "enterprise_pipeline_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_54_FIDELITY.md" in roadmap
    assert "Stage 54 D1" in roadmap
    assert "ADR_113_STAGE54_OPEN.md" in roadmap
    assert "STAGE_54_PLAN.md" in roadmap
    assert "test_stage54_fidelity_d1.py" in roadmap
