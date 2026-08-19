"""Stage 130 D1 — documentation fidelity for Cheques, POS Sessions & Stock Counts Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage130_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_130_FIDELITY.md")
    assert "cheque" in fidelity.lower() or "pos" in fidelity.lower() or "stock" in fidelity.lower()
    for name in (
        "test_stage130_cheques_export_c1.py",
        "test_stage130_pos_sessions_p1.py",
        "test_stage130_stock_counts_s1.py",
        "test_stage130_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-266" in fidelity or "ADR_266" in fidelity
    assert "H130x" in fidelity
    plan = _read("docs/STAGE_130_PLAN.md")
    assert "STAGE_130_FIDELITY.md" in plan
    for ws in ("C1", "P1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage130_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_130_FIDELITY.md" in br
    assert "Stage 130 D1" in br or "test_stage130_fidelity_d1.py" in br
    assert "Stage 130 C1" in br or "Stage 130 P1" in br or "Stage 130 S1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_130_FIDELITY.md" in fidelity_tail or "Stage 130 D1" in fidelity_tail


def test_stage130_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 130 D1" in api or "STAGE_130_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 130 D1" in deploy or "STAGE_130_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 130 D1" in sec or "STAGE_130_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage130_cheques_export_c1.py" in launch
    assert "test_stage130_pos_sessions_p1.py" in launch
    assert "test_stage130_stock_counts_s1.py" in launch
    assert "test_stage130_fidelity_d1.py" in launch
    assert "STAGE_130_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Cheques CSV" in manual
        or "cheques/export" in manual
        or "POS Session" in manual
        or "pos/sessions/export" in manual
        or "Stock Count" in manual
        or "stock-counts/export" in manual
    )


def test_stage130_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_130_FIDELITY.md" in pr and "test_stage130_fidelity_d1.py" in pr
    assert "Stage 130 D1" in pr and "Stage 130 C1" in pr and "Stage 130 P1" in pr and "Stage 130 S1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_130_FIDELITY.md" in roadmap and "Stage 130 D1" in roadmap
    assert "ADR_266_STAGE130_OPEN.md" in roadmap and "STAGE_130_PLAN.md" in roadmap
