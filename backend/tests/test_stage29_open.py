"""Stage 29 open — plan + ADR-063 exist; Stage 28 freeze remains."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage29_plan_and_open_adr():
    plan = (ROOT / "docs" / "STAGE_29_PLAN.md").read_text(encoding="utf-8")
    assert "Hardening" in plan or "Cutover" in plan or "Pen-Test" in plan or "pen-test" in plan.lower()
    assert "ADR-063" in plan or "ADR_063" in plan
    for ws in ("V1", "B2", "T1", "X1", "D1", "H29x"):
        assert f"| **{ws}** |" in plan, ws
    assert (
        "PENDING" in plan
        or "V1 next" in plan
        or "V1 complete" in plan
        or "B2 next" in plan
        or "B2 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "X1 next" in plan
        or "X1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H29x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )
    assert "Pen-Test" in plan or "ZAP" in plan or "pen-test" in plan.lower() or "OWASP" in plan
    assert "PgBouncer" in plan
    assert "TLS" in plan or "cert-manager" in plan.lower() or "Cert-manager" in plan
    assert "Cutover" in plan or "cutover" in plan.lower() or "LAUNCH" in plan
    assert "paid billing" in plan.lower() or "ADR-002" in plan
    assert "ci.yml" in plan.lower() or "Stage 18 C1" in plan
    assert "Stage 28" in plan or "R1" in plan  # must not reopen Stage 28 packs as new Complete intent

    adr = (ROOT / "docs" / "ADR_063_STAGE29_OPEN.md").read_text(encoding="utf-8")
    assert "Stage 29" in adr
    assert "STAGE_29_PLAN.md" in adr
    assert "V1" in adr and "H29x" in adr
    assert "ADR-062" in adr or "ADR_062" in adr
    assert "Hardening" in adr or "Cutover" in adr or "Pen-Test" in adr
    assert "PgBouncer" in adr or "TLS" in adr or "Cutover" in adr


def test_stage28_freeze_amended_for_stage29():
    freeze = (ROOT / "docs" / "ADR_062_STAGE28_FREEZE.md").read_text(encoding="utf-8")
    assert "Amendment" in freeze
    assert "ADR-063" in freeze or "ADR_063" in freeze
    assert "STAGE_29_PLAN.md" in freeze
    assert "frozen" in freeze.lower()


def test_stage29_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_29_PLAN.md" in launch
    assert "ADR-063" in launch or "ADR_063" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_063_STAGE29_OPEN.md" in roadmap
    assert "STAGE_29_PLAN.md" in roadmap
    assert "Stage 29 open" in roadmap
