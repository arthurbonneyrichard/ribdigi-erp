"""Stage 72 D1 — documentation fidelity for Commercial Packaging Closeout."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage72_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_72_FIDELITY.md")
    assert "Residual" in fidelity or "Archive" in fidelity or "Packaging" in fidelity
    for name in (
        "test_commercial_residual_r1.py",
        "test_commercial_packaging_archive_p1.py",
        "test_stage72_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-150" in fidelity or "ADR_150" in fidelity
    assert "H72x" in fidelity

    plan = _read("docs/STAGE_72_PLAN.md")
    assert "STAGE_72_FIDELITY.md" in plan
    for ws in ("R1", "P1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h72 = [ln for ln in plan.splitlines() if "| **H72x** |" in ln][0]
    assert "PENDING" in h72 or "COMPLETE" in h72
    assert any(x in plan for x in ("D1 next", "D1 complete", "H72x next", "Closed", "exit met"))


def test_stage72_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_72_FIDELITY.md" in br
    assert "Stage 72 D1" in br or "test_stage72_fidelity_d1.py" in br
    assert (
        "Stage 72 R1" in br
        or "COMMERCIAL_RESIDUAL_MVP.md" in br
        or "Stage 72 P1" in br
        or "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in br
    )
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_72_FIDELITY.md" in fidelity_tail or "Stage 72 D1" in fidelity_tail
    for rel in ("docs/COMMERCIAL_RESIDUAL_MVP.md", "docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md"):
        assert _read(rel)


def test_stage72_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 72 D1" in api or "STAGE_72_FIDELITY.md" in api
    assert "test_stage72_fidelity_d1.py" in api or "STAGE_72_FIDELITY.md" in api
    assert "Stage 72 R1" in api or "COMMERCIAL_RESIDUAL_MVP.md" in api
    assert "Stage 72 P1" in api or "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 72 D1" in deploy or "STAGE_72_FIDELITY.md" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 72 D1" in sec or "STAGE_72_FIDELITY.md" in sec
    assert "test_commercial_residual_r1.py" in sec or "COMMERCIAL_RESIDUAL_MVP.md" in sec
    assert "test_commercial_packaging_archive_p1.py" in sec or "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_residual_r1.py" in launch
    assert "test_commercial_packaging_archive_p1.py" in launch
    assert "test_stage72_fidelity_d1.py" in launch
    assert "STAGE_72_FIDELITY.md" in launch
    assert "ADR-150" in launch or "ADR_150" in launch or "STAGE_72_PLAN.md" in launch


def test_stage72_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_72_FIDELITY.md" in pr
    assert "test_stage72_fidelity_d1.py" in pr
    assert "Stage 72 D1" in pr
    assert "Stage 72 R1" in pr
    assert "Stage 72 P1" in pr
    assert (
        "residual_closed_claimed" in pr
        or "packaging_archive_live_claimed" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_72_FIDELITY.md" in roadmap
    assert "Stage 72 D1" in roadmap
    assert "ADR_150_STAGE72_OPEN.md" in roadmap
    assert "STAGE_72_PLAN.md" in roadmap
    assert "test_stage72_fidelity_d1.py" in roadmap
