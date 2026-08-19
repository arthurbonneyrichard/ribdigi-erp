"""Stage 133 D1 — documentation fidelity for Sales Quotation/Order/Return Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage133_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_133_FIDELITY.md")
    assert (
        "quotation" in fidelity.lower()
        or "order" in fidelity.lower()
        or "return" in fidelity.lower()
    )
    for name in (
        "test_stage133_quotations_export_q1.py",
        "test_stage133_orders_export_o1.py",
        "test_stage133_returns_export_r1.py",
        "test_stage133_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-272" in fidelity or "ADR_272" in fidelity
    assert "H133x" in fidelity
    plan = _read("docs/STAGE_133_PLAN.md")
    assert "STAGE_133_FIDELITY.md" in plan
    for ws in ("Q1", "O1", "R1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage133_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_133_FIDELITY.md" in br
    assert "Stage 133 D1" in br or "test_stage133_fidelity_d1.py" in br
    assert "Stage 133 Q1" in br or "Stage 133 O1" in br or "Stage 133 R1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_133_FIDELITY.md" in fidelity_tail or "Stage 133 D1" in fidelity_tail


def test_stage133_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 133 D1" in api or "STAGE_133_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 133 D1" in deploy or "STAGE_133_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 133 D1" in sec or "STAGE_133_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage133_quotations_export_q1.py" in launch
    assert "test_stage133_orders_export_o1.py" in launch
    assert "test_stage133_returns_export_r1.py" in launch
    assert "test_stage133_fidelity_d1.py" in launch
    assert "STAGE_133_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Quotation" in manual
        or "quotations/export" in manual
        or "Sales Order" in manual
        or "orders/export" in manual
        or "Sales Return" in manual
        or "returns/export" in manual
    )


def test_stage133_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_133_FIDELITY.md" in pr and "test_stage133_fidelity_d1.py" in pr
    assert "Stage 133 D1" in pr and "Stage 133 Q1" in pr and "Stage 133 O1" in pr and "Stage 133 R1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_133_FIDELITY.md" in roadmap and "Stage 133 D1" in roadmap
    assert "ADR_272_STAGE133_OPEN.md" in roadmap and "STAGE_133_PLAN.md" in roadmap
