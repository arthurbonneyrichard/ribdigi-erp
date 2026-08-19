"""Stage 111 D1 — documentation fidelity for Inventory Movement Types, Posted Sales Returns & Cheque Hash Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage111_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_111_FIDELITY.md")
    assert "Inventory" in fidelity or "Sales Returns" in fidelity or "Cheque" in fidelity
    for name in (
        "test_stage111_inventory_movement_types_i1.py",
        "test_stage111_posted_sales_returns_s1.py",
        "test_stage111_cheque_hash_c1.py",
        "test_stage111_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-228" in fidelity or "ADR_228" in fidelity
    assert "H111x" in fidelity
    plan = _read("docs/STAGE_111_PLAN.md")
    assert "STAGE_111_FIDELITY.md" in plan
    for ws in ("I1", "S1", "C1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage111_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_111_FIDELITY.md" in br
    assert "Stage 111 D1" in br or "test_stage111_fidelity_d1.py" in br
    assert "Stage 111 I1" in br or "Stage 111 S1" in br or "Stage 111 C1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_111_FIDELITY.md" in fidelity_tail or "Stage 111 D1" in fidelity_tail


def test_stage111_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 111 D1" in api or "STAGE_111_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 111 D1" in deploy or "STAGE_111_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 111 D1" in sec or "STAGE_111_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage111_inventory_movement_types_i1.py" in launch
    assert "test_stage111_posted_sales_returns_s1.py" in launch
    assert "test_stage111_cheque_hash_c1.py" in launch
    assert "test_stage111_fidelity_d1.py" in launch
    assert "STAGE_111_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Stock In Movements" in manual
        or "Posted Sales Returns" in manual
        or "Deposited Cheques" in manual
        or "Cleared Cheques" in manual
    )


def test_stage111_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_111_FIDELITY.md" in pr and "test_stage111_fidelity_d1.py" in pr
    assert "Stage 111 D1" in pr and "Stage 111 I1" in pr and "Stage 111 S1" in pr and "Stage 111 C1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_111_FIDELITY.md" in roadmap and "Stage 111 D1" in roadmap
    assert "ADR_228_STAGE111_OPEN.md" in roadmap and "STAGE_111_PLAN.md" in roadmap
