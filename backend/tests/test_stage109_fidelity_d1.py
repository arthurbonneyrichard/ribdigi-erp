"""Stage 109 D1 — documentation fidelity for Report Filters, Document Status Leaves & Platform Status Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage109_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_109_FIDELITY.md")
    assert "Report" in fidelity or "Sales" in fidelity or "Platform" in fidelity
    for name in (
        "test_stage109_report_filters_r1.py",
        "test_stage109_sales_status_s1.py",
        "test_stage109_ops_status_o1.py",
        "test_stage109_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-224" in fidelity or "ADR_224" in fidelity
    assert "H109x" in fidelity
    plan = _read("docs/STAGE_109_PLAN.md")
    assert "STAGE_109_FIDELITY.md" in plan
    for ws in ("R1", "S1", "O1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage109_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_109_FIDELITY.md" in br
    assert "Stage 109 D1" in br or "test_stage109_fidelity_d1.py" in br
    assert "Stage 109 R1" in br or "Stage 109 S1" in br or "Stage 109 O1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_109_FIDELITY.md" in fidelity_tail or "Stage 109 D1" in fidelity_tail


def test_stage109_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 109 D1" in api or "STAGE_109_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 109 D1" in deploy or "STAGE_109_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 109 D1" in sec or "STAGE_109_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage109_report_filters_r1.py" in launch
    assert "test_stage109_sales_status_s1.py" in launch
    assert "test_stage109_ops_status_o1.py" in launch
    assert "test_stage109_fidelity_d1.py" in launch
    assert "STAGE_109_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Draft Quotations" in manual
        or "Confirmed Orders" in manual
        or "Active Tenants" in manual
        or "Bank Reconciliation" in manual
        or "Report from date" in manual
        or "report filters" in manual.lower()
    )


def test_stage109_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_109_FIDELITY.md" in pr and "test_stage109_fidelity_d1.py" in pr
    assert "Stage 109 D1" in pr and "Stage 109 R1" in pr and "Stage 109 S1" in pr and "Stage 109 O1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_109_FIDELITY.md" in roadmap and "Stage 109 D1" in roadmap
    assert "ADR_224_STAGE109_OPEN.md" in roadmap and "STAGE_109_PLAN.md" in roadmap
