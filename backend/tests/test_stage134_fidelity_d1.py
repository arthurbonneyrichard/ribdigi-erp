"""Stage 134 D1 — documentation fidelity for Purchase Request/Order/GRN Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage134_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_134_FIDELITY.md")
    assert (
        "request" in fidelity.lower()
        or "order" in fidelity.lower()
        or "grn" in fidelity.lower()
    )
    for name in (
        "test_stage134_requests_export_r1.py",
        "test_stage134_orders_export_o1.py",
        "test_stage134_grn_export_g1.py",
        "test_stage134_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-274" in fidelity or "ADR_274" in fidelity
    assert "H134x" in fidelity
    plan = _read("docs/STAGE_134_PLAN.md")
    assert "STAGE_134_FIDELITY.md" in plan
    for ws in ("R1", "O1", "G1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage134_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_134_FIDELITY.md" in br
    assert "Stage 134 D1" in br or "test_stage134_fidelity_d1.py" in br
    assert "Stage 134 R1" in br or "Stage 134 O1" in br or "Stage 134 G1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_134_FIDELITY.md" in fidelity_tail or "Stage 134 D1" in fidelity_tail


def test_stage134_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 134 D1" in api or "STAGE_134_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 134 D1" in deploy or "STAGE_134_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 134 D1" in sec or "STAGE_134_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage134_requests_export_r1.py" in launch
    assert "test_stage134_orders_export_o1.py" in launch
    assert "test_stage134_grn_export_g1.py" in launch
    assert "test_stage134_fidelity_d1.py" in launch
    assert "STAGE_134_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Purchase Request" in manual
        or "requests/export" in manual
        or "Purchase Order" in manual
        or "purchasing/orders/export" in manual
        or "GRN" in manual
        or "grn/export" in manual
    )


def test_stage134_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_134_FIDELITY.md" in pr and "test_stage134_fidelity_d1.py" in pr
    assert "Stage 134 D1" in pr and "Stage 134 R1" in pr and "Stage 134 O1" in pr and "Stage 134 G1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_134_FIDELITY.md" in roadmap and "Stage 134 D1" in roadmap
    assert "ADR_274_STAGE134_OPEN.md" in roadmap and "STAGE_134_PLAN.md" in roadmap
